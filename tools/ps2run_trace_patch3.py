"""Third trace step (run after ps2run_trace_patch.py): PS2_DUMP_TEX=frame,folder writes every distinct
texture the game sets during that frame as a grey picture of its palette indices (tex_<tbp>_<psm>_<w>x<h>.pgm)
into the folder. Run with PS2_GS=cpu so the picture memory is readable. These are game pictures: keep local.
Usage: python3 ps2run_trace_patch3.py [runtime/src/gs/gs.cpp]
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gs.cpp'
s = open(p).read()
if 'PS2_DUMP_TEX' in s:
    print("already patched"); raise SystemExit
def sub(old, new):
    global s
    if s.count(old) != 1:
        print("PATCH NOT APPLIED: text not found:", old.strip()[:60]); raise SystemExit(1)
    s = s.replace(old, new)
sub('        if (trace_tex()) print_tex0("TEX0", static_cast<unsigned>(reg - 6), value);\n',
'''        if (trace_tex()) print_tex0("TEX0", static_cast<unsigned>(reg - 6), value);
        dump_tex(value);
''')
sub('void load_clut(std::uint64_t tex0) {\n    const std::uint32_t cld',
'''void dump_tex(std::uint64_t t) {
    static const char *spec = std::getenv("PS2_DUMP_TEX");
    if (!spec) return;
    static const unsigned long long fr = std::strtoull(spec, nullptr, 10);
    static const char *dir = std::strchr(spec, ',') ? std::strchr(spec, ',') + 1 : ".";
    if (static_cast<unsigned long long>(ps2::frame_count()) != fr) return;
    const unsigned tbp = t & 0x3FFF, tbw = (t >> 14) & 0x3F, psm = (t >> 20) & 0x3F, w = 1u << ((t >> 26) & 15), h = 1u << ((t >> 30) & 15);
    if (psm != 0x13 && psm != 0x14) return;
    char path[512];
    std::snprintf(path, sizeof path, "%s/tex_%04X_%02X_%ux%u.pgm", dir, tbp, psm, w, h);
    if (std::FILE *chk = std::fopen(path, "rb")) { std::fclose(chk); return; }
    std::FILE *f = std::fopen(path, "wb");
    if (!f) return;
    std::fprintf(f, "P5\\n%u %u\\n255\\n", w, h);
    for (unsigned y = 0; y < h; ++y)
        for (unsigned x = 0; x < w; ++x) {
            const unsigned v = read_pixel(psm, tbp, tbw, x, y);
            std::fputc(psm == 0x14 ? static_cast<int>(v * 17) : static_cast<int>(v & 255), f);
        }
    std::fclose(f);
}

void load_clut(std::uint64_t tex0) {
    const std::uint32_t cld''')
open(p, 'w').write(s)
print("patched")
