"""Fourth trace step (run after patch3): PS2_DUMP_TEX also writes each texture in real colour
(tc_<tbp>_<psm>_<w>x<h>.ppm) using the palette at its CBP. Run with PS2_GS=cpu. Game pictures: keep local.
Usage: python3 ps2run_trace_patch4.py [runtime/src/gs/gs.cpp]
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gs.cpp'
s = open(p).read()
if 'dump_tex_color' in s:
    print("already patched"); raise SystemExit
def sub(old, new):
    global s
    if s.count(old) != 1:
        print("PATCH NOT APPLIED: text not found:", old.strip()[:60]); raise SystemExit(1)
    s = s.replace(old, new)
sub('        dump_tex(value);\n', '        dump_tex(value);\n        dump_tex_color(value);\n')
sub('void load_clut(std::uint64_t tex0) {\n    const std::uint32_t cld',
'''void dump_tex_color(std::uint64_t t) {
    static const char *spec = std::getenv("PS2_DUMP_TEX");
    if (!spec) return;
    static const unsigned long long fr = std::strtoull(spec, nullptr, 10);
    static const char *dir = std::strchr(spec, ',') ? std::strchr(spec, ',') + 1 : ".";
    const unsigned long long now = static_cast<unsigned long long>(ps2::frame_count());
    if (now < fr || now > fr + 3) return;
    const unsigned tbp = t & 0x3FFF, tbw = (t >> 14) & 0x3F, psm = (t >> 20) & 0x3F, w = 1u << ((t >> 26) & 15), h = 1u << ((t >> 30) & 15);
    const unsigned cbp = (t >> 37) & 0x3FFF, csa = (t >> 56) & 31;
    if (psm != 0x13 && psm != 0x14) return;
    char path[512];
    std::snprintf(path, sizeof path, "%s/tc_%04X_%02X_%ux%u.ppm", dir, tbp, psm, w, h);
    if (std::FILE *chk = std::fopen(path, "rb")) { std::fclose(chk); return; }
    std::uint32_t pal[256];
    const unsigned n = psm == 0x13 ? 256 : 16;
    for (unsigned i = 0; i < n; ++i) {
        unsigned x, y;
        if (psm == 0x13) { const unsigned j = (i & ~0x18u) | ((i & 0x08u) << 1) | ((i & 0x10u) >> 1); x = j & 15u; y = j >> 4; }
        else { x = i & 7u; y = i >> 3; }
        pal[i] = read_pixel(0, cbp, 1, x, y);
        (void)csa;
    }
    std::FILE *f = std::fopen(path, "wb");
    if (!f) return;
    std::fprintf(f, "P6\\n%u %u\\n255\\n", w, h);
    for (unsigned y = 0; y < h; ++y)
        for (unsigned x = 0; x < w; ++x) {
            const std::uint32_t c = pal[read_pixel(psm, tbp, tbw, x, y) & 255u];
            std::fputc(c & 255, f); std::fputc((c >> 8) & 255, f); std::fputc((c >> 16) & 255, f);
        }
    std::fclose(f);
}

void load_clut(std::uint64_t tex0) {
    const std::uint32_t cld''')
open(p, 'w').write(s)
print("patched")
