"""Sixth trace step: PS2_TRACE_PRIM=from,to prints one line for every shape (point, line, triangle, sprite) that the GS is asked to draw
in frames from..to: "[prim] f<frame> type=.. iip=.. tme=.. fge=.. abe=.. fst=.. ctx=.. tbp=.. psm=.. tw=.. th=.. tcc=.. tfx=.. alpha=.. test=..
clamp=.. frame=.. zbuf=.. ofx=.. ofy=.. pmc=.. pm=.. cc=.. pabe=.. fba=.. scis=..", followed by a line per corner with the raw position (12.4 fixed point, before subtracting ofx and ofy),
z, colour, ST, Q and UV. Numbers only, no game content.
Usage (in the ps2-web-recomp folder): python3 ps2run_trace_patch6.py [runtime/src/gs/gs.cpp]
Safe to run twice; an older patched tree is upgraded in place (adds ofx, ofy and the global drawing switches). Rebuild afterwards: ninja -C build/native-p3fes ps2run
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gs.cpp'
s = open(p).read()

FRESH = 'PS2_TRACE_PRIM' not in s
OLD = 'void kick(bool draw) {\n    State &s = g_state;\n'
if FRESH and s.count(OLD) != 1:
    print("PATCH NOT APPLIED: kick()"); raise SystemExit(1)
HELP = r'''void trace_prim(const State &s, int needed) {
    static const char *spec = std::getenv("PS2_TRACE_PRIM");
    if (!spec) return;
    static const unsigned long long from = std::strtoull(spec, nullptr, 10);
    static const unsigned long long to = std::strchr(spec, ',') ? std::strtoull(std::strchr(spec, ',') + 1, nullptr, 10) : from + 1;
    const unsigned long long f = static_cast<unsigned long long>(ps2::frame_count());
    if (f < from || f >= to) return;
    const std::uint64_t pr = s.prim;
    const unsigned ctx = static_cast<unsigned>(pr >> 9) & 1u;
    const Context &c = s.ctx[ctx];
    std::fprintf(stderr, "[prim] f%llu type=%u iip=%u tme=%u fge=%u abe=%u fst=%u ctx=%u tbp=%llX psm=%llX tw=%llu th=%llu tcc=%llu tfx=%llu alpha=%llX test=%llX clamp=%llX frame=%llX zbuf=%llX ofx=%u ofy=%u\n",
                 f, static_cast<unsigned>(pr & 7u), static_cast<unsigned>(pr >> 3) & 1u, static_cast<unsigned>(pr >> 4) & 1u, static_cast<unsigned>(pr >> 5) & 1u,
                 static_cast<unsigned>(pr >> 6) & 1u, static_cast<unsigned>(pr >> 8) & 1u, ctx,
                 static_cast<unsigned long long>(c.tex0 & 0x3FFF), static_cast<unsigned long long>((c.tex0 >> 20) & 0x3F),
                 static_cast<unsigned long long>((c.tex0 >> 26) & 15), static_cast<unsigned long long>((c.tex0 >> 30) & 15),
                 static_cast<unsigned long long>((c.tex0 >> 34) & 1), static_cast<unsigned long long>((c.tex0 >> 35) & 3),
                 static_cast<unsigned long long>(c.alpha), static_cast<unsigned long long>(c.test), static_cast<unsigned long long>(c.clamp),
                 static_cast<unsigned long long>(c.frame), static_cast<unsigned long long>(c.zbuf),
                 static_cast<unsigned>(c.xyoffset & 0xFFFFu), static_cast<unsigned>((c.xyoffset >> 32) & 0xFFFFu));
    for (int i = 0; i < needed; ++i) {
        const Vertex &v = s.queue[i];
        std::fprintf(stderr, "[prim]   v%d x=%u y=%u z=%u rgba=%02X%02X%02X%02X s=%g t=%g q=%g u=%u v=%u\n", i, static_cast<unsigned>(v.x), static_cast<unsigned>(v.y),
                     static_cast<unsigned>(v.z), v.r, v.g, v.b, v.a, static_cast<double>(v.s), static_cast<double>(v.t), static_cast<double>(v.q),
                     static_cast<unsigned>(v.u), static_cast<unsigned>(v.v));
    }
}

'''
if FRESH: s = s.replace(OLD, HELP + OLD, 1)
OLD2 = '    if (draw) {\n        if (cpu_raster()) raster::draw(s, s.queue, needed);\n'
if FRESH and s.count(OLD2) != 1:
    print("PATCH NOT APPLIED: draw call"); raise SystemExit(1)
if FRESH: s = s.replace(OLD2, '    if (draw) {\n        trace_prim(s, needed);\n        if (cpu_raster()) raster::draw(s, s.queue, needed);\n', 1)

msgs = []
if 'ofx=%u' not in s:
    A = r'frame=%llX zbuf=%llX\n",'
    B = 'static_cast<unsigned long long>(c.frame), static_cast<unsigned long long>(c.zbuf));\n'
    if s.count(A) != 1 or s.count(B) != 1:
        print("PATCH NOT APPLIED: cannot upgrade"); raise SystemExit(1)
    s = s.replace(A, r'frame=%llX zbuf=%llX ofx=%u ofy=%u\n",', 1)
    s = s.replace(B, 'static_cast<unsigned long long>(c.frame), static_cast<unsigned long long>(c.zbuf),\n'
                     '                 static_cast<unsigned>(c.xyoffset & 0xFFFFu), static_cast<unsigned>((c.xyoffset >> 32) & 0xFFFFu));\n', 1)
    msgs.append("offset added")
if 'pabe=%llX' not in s:
    A = r'ofx=%u ofy=%u\n",'
    B = 'static_cast<unsigned>((c.xyoffset >> 32) & 0xFFFFu));\n'
    if s.count(A) != 1 or s.count(B) != 1:
        print("PATCH NOT APPLIED: cannot upgrade"); raise SystemExit(1)
    s = s.replace(A, r'ofx=%u ofy=%u pmc=%llX pm=%llX cc=%llX pabe=%llX fba=%llX scis=%llX\n",', 1)
    s = s.replace(B, 'static_cast<unsigned>((c.xyoffset >> 32) & 0xFFFFu),\n'
                     '                 static_cast<unsigned long long>(s.prmodecont), static_cast<unsigned long long>(s.prmode), static_cast<unsigned long long>(s.colclamp),\n'
                     '                 static_cast<unsigned long long>(s.pabe), static_cast<unsigned long long>(c.fba), static_cast<unsigned long long>(c.scissor));\n', 1)
    msgs.append("prmodecont, colclamp, pabe, fba, scissor added")
if not msgs:
    print("already patched"); raise SystemExit
open(p, 'w').write(s)
print("patched (PS2_TRACE_PRIM: " + ", ".join(msgs) + ")")
