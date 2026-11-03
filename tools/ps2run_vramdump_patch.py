"""Graphics memory dump for the PC window of PS2 Web Recomp (a diagnostic; changes nothing on screen).

With PS2_DUMP_VRAMFLAG=<flag file>,<output file> set, the window looks every so often for the flag file. When it appears, the window saves the
whole graphics memory once to the output file (4 MB; the first 4 bytes are the resolution multiplier, then the memory as 32-bit words) and writes a
"[vramdump]" line to the log. Delete the flag file and create it again to take another one. Use it to look at the exact textures and palettes the game
has in memory while something odd is on screen.

  PS2_DUMP_VRAMFLAG=C:\\p3fes\\vram.on,C:\\p3fes\\vram.bin      (in ~/.p3fes-window-env; create the flag in WSL with: touch /mnt/c/p3fes/vram.on)

Run in the ps2-web-recomp folder:  python3 ps2run_vramdump_patch.py [folder]
(patches runtime/src/gs/gs.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
TAG = 'ps2run_vramdump_patch.py'
REL = 'runtime/src/gs/gs.cpp'

CODE = r'''// ---- graphics memory dump (%TAG%) ----
void dump_vram_flag() {
#ifdef PS2_GPU
    static const char *spec = std::getenv("PS2_DUMP_VRAMFLAG");
    if (!spec || !gpu_on()) return;
    static std::string flag, out;
    static bool init = false, done = false;
    static unsigned n = 0;
    if (!init) {
        init = true;
        const char *comma = std::strchr(spec, ',');
        flag = comma ? std::string(spec, comma) : std::string(spec);
        out = comma ? std::string(comma + 1) : std::string("vram.bin");
        std::fprintf(stderr, "[vramdump] watching %s, will write %s\n", flag.c_str(), out.c_str());
    }
    if ((++n & 1023u) != 0) return;
    std::FILE *f = std::fopen(flag.c_str(), "rb");
    const bool on = f != nullptr;
    if (f) std::fclose(f);
    if (!on) {
        done = false;
        return;
    }
    if (done) return;
    done = true;
    std::vector<std::uint32_t> vram, clut;
    std::uint32_t scale = 1;
    gpu::read_state(vram, scale, clut);
    std::FILE *o = std::fopen(out.c_str(), "wb");
    if (!o) {
        std::fprintf(stderr, "[vramdump] cannot write %s\n", out.c_str());
        return;
    }
    std::fwrite(&scale, 4, 1, o);
    std::fwrite(vram.data(), 4, vram.size(), o);
    std::fclose(o);
    std::fprintf(stderr, "[vramdump] wrote %zu words (resolution x%u) to %s\n", vram.size(), scale, out.c_str());
#endif
}
// ---- end graphics memory dump ----

'''.replace('%TAG%', TAG)

EDITS = [
    ('void kick(bool draw) {\n', CODE + 'void kick(bool draw) {\n'),
    ('        dump_tex_draw(s);\n        Context &uc', '        dump_tex_draw(s);\n        dump_vram_flag();  // ' + TAG + '\n        Context &uc'),
]
try:
    raw = open(root + '/' + REL, newline='').read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + REL)
    raise SystemExit(1)
t = raw.replace('\r\n', '\n')
if TAG in t:
    print("already patched")
    raise SystemExit
for old, _ in EDITS:
    if t.count(old) != 1:
        print("PATCH NOT APPLIED: " + REL + " does not look like the expected source")
        raise SystemExit(1)
for old, new in EDITS:
    t = t.replace(old, new)
open(root + '/' + REL, 'w', newline='').write(t.replace('\n', '\r\n') if '\r\n' in raw else t)
print("patched (%d edits)" % len(EDITS))
