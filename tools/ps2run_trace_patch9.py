"""Ninth trace step (run after ps2run_trace_patch6.py): PS2_DUMP_TEXDRAW=frame,folder writes every 4-bit and 8-bit paletted texture
as it looks at the moment of its FIRST DRAW in that frame (frame only, not the following ones) as dd_<tbp>_<psm>_<w>x<h>.ppm in the
folder, using the palette the drawing really uses, and prints a line per texture: "[dtex] f.. tbp cbp csa psm size nonzero=N of M
indices, colours=K". Run with PS2_GS=cpu so the picture memory can be read. The pictures are game pictures: keep them local;
the printed lines are numbers only.
Usage (in the ps2-web-recomp folder): python3 ps2run_trace_patch9.py [runtime/src/gs/gs.cpp]
Safe to run twice. Rebuild afterwards: ninja -C build/native-p3fes ps2run
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gs.cpp'
s = open(p).read()
if 'PS2_DUMP_TEXDRAW' in s:
    print("already patched"); raise SystemExit
if 'void trace_prim(const State &s, int needed) {' not in s:
    print("PATCH NOT APPLIED: run ps2run_trace_patch6.py first"); raise SystemExit(1)
OLD = 'void trace_prim(const State &s, int needed) {\n'
CALL_OLD = '        trace_prim(s, needed);\n'
if s.count(OLD) != 1 or s.count(CALL_OLD) != 1:
    print("PATCH NOT APPLIED: kick()"); raise SystemExit(1)
HELP = r'''void dump_tex_draw(const State &s) {
    static const char *spec = std::getenv("PS2_DUMP_TEXDRAW");
    if (!spec) return;
    static const unsigned long long fr = std::strtoull(spec, nullptr, 10);
    static const char *dir = std::strchr(spec, ',') ? std::strchr(spec, ',') + 1 : ".";
    if (static_cast<unsigned long long>(ps2::frame_count()) != fr) return;
    if (!((s.prim >> 4) & 1u)) return;
    const Context &c = s.ctx[(s.prim >> 9) & 1u];
    const std::uint64_t t = c.tex0;
    const unsigned tbp = t & 0x3FFF, tbw = (t >> 14) & 0x3F, psm = (t >> 20) & 0x3F, w = 1u << ((t >> 26) & 15), h = 1u << ((t >> 30) & 15);
    const unsigned cbp = (t >> 37) & 0x3FFF, csa = (t >> 56) & 31;
    if (psm != 0x13 && psm != 0x14) return;
    char path[512];
    std::snprintf(path, sizeof path, "%s/dd_%04X_%02X_%ux%u.ppm", dir, tbp, psm, w, h);
    if (std::FILE *chk = std::fopen(path, "rb")) { std::fclose(chk); return; }
    std::FILE *f = std::fopen(path, "wb");
    if (!f) return;
    std::fprintf(f, "P6\n%u %u\n255\n", w, h);
    unsigned long nonzero = 0;
    bool seen[256] = {};
    std::uint32_t colours = 0;
    for (unsigned y = 0; y < h; ++y)
        for (unsigned x = 0; x < w; ++x) {
            const unsigned idx = read_pixel(psm, tbp, tbw, x, y) & 255u;
            if (idx) ++nonzero;
            if (!seen[idx]) { seen[idx] = true; ++colours; }
            const std::uint32_t pc = s.clut[(idx + (psm == 0x14 ? csa * 16u : 0u)) & 511u];
            std::fputc(pc & 255, f); std::fputc((pc >> 8) & 255, f); std::fputc((pc >> 16) & 255, f);
        }
    std::fclose(f);
    std::fprintf(stderr, "[dtex] f%llu tbp=%04X cbp=%04X csa=%u psm=%02X size=%ux%u nonzero=%lu of %lu indices, colours=%u pal0=%08X pal1=%08X pal2=%08X pal3=%08X\n",
                 static_cast<unsigned long long>(ps2::frame_count()), tbp, cbp, csa, psm, w, h, nonzero, static_cast<unsigned long>(w) * h, colours,
                 s.clut[(psm == 0x14 ? csa * 16u : 0u) & 511u], s.clut[((psm == 0x14 ? csa * 16u : 0u) + 1) & 511u],
                 s.clut[((psm == 0x14 ? csa * 16u : 0u) + 2) & 511u], s.clut[((psm == 0x14 ? csa * 16u : 0u) + 3) & 511u]);
}

'''
s = s.replace(OLD, HELP + OLD, 1)
s = s.replace(CALL_OLD, CALL_OLD + '        dump_tex_draw(s);\n', 1)
open(p, 'w').write(s)
print("patched (PS2_DUMP_TEXDRAW)")
