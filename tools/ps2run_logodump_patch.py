"""ATLUS logo dump for the PC window of PS2 Web Recomp (a diagnostic; it changes nothing on screen).

With PS2_DUMP_LOGO=<prefix> set (in ~/.p3fes-window-env), the window saves the graphics memory and the palette memory by itself a moment after each show of a
1024 x 512 4-bit picture ( the ATLUS logo and the Sofdec / ADX screen at boot, the ATLUS logo again after
Back to Title in the System Menu): <prefix>-ep1.bin and .clut, <prefix>-ep2..., up to six. Each .bin is the same as the one PS2_DUMP_VRAMFLAG writes (a 4 byte
resolution multiplier, then the memory as 32-bit words); each .clut is the palette memory (32-bit words). The log gets "[logodump]" lines with the picture's settings.

  PS2_DUMP_LOGO=C:\\p3fes\\logo      (in ~/.p3fes-window-env)

Run in the ps2-web-recomp folder:  python3 ps2run_logodump_patch.py [folder]
(patches runtime/src/gs/gpu/gpu.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
TAG = 'ps2run_logodump_patch.py'
GPU = 'runtime/src/gs/gpu/gpu.cpp'

ANCHOR = '    SetupCache &cache = g_setup_cache;\n'
CODE = r'''    {  // %TAG%
        static const char *dl_out = std::getenv("PS2_DUMP_LOGO");
        static std::uint64_t dl_count = 0, dl_last = 0;
        static int dl_episode = 0, dl_hits = 0;
        ++dl_count;
        if (dl_out) {
            const std::uint64_t t = c.tex0;
            if (((t >> 26) & 15u) == 10u && ((t >> 30) & 15u) == 9u && ((t >> 20) & 63u) == 0x14u) {
                if (dl_episode == 0 || dl_count - dl_last > 3000) {
                    ++dl_episode;
                    dl_hits = 0;
                }
                dl_last = dl_count;
                if (++dl_hits == 40 && dl_episode <= 6) {
                    std::vector<std::uint32_t> vram, clut;
                    std::uint32_t scale = 1;
                    read_state(vram, scale, clut);
                    const std::string base = std::string(dl_out) + "-ep" + std::to_string(dl_episode);
                    std::FILE *o = std::fopen((base + ".bin").c_str(), "wb");
                    if (o) {
                        std::fwrite(&scale, 4, 1, o);
                        std::fwrite(vram.data(), 4, vram.size(), o);
                        std::fclose(o);
                    }
                    o = std::fopen((base + ".clut").c_str(), "wb");
                    if (o) {
                        std::fwrite(clut.data(), 4, clut.size(), o);
                        std::fclose(o);
                    }
                    std::fprintf(stderr, "[logodump] episode %d tex0=%llx tbp=%x tbw=%u cbp=%x (resolution x%u, %zu palette words)\n", dl_episode,
                                 static_cast<unsigned long long>(t), static_cast<unsigned>(t & 0x3FFFu), static_cast<unsigned>((t >> 14) & 63u),
                                 static_cast<unsigned>((t >> 37) & 0x3FFFu), scale, clut.size());
                }
            }
        }
    }
'''.replace('%TAG%', TAG)

try:
    with open(root + '/' + GPU, newline='') as f:
        raw = f.read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + GPU)
    raise SystemExit(1)
crlf = '\r\n' in raw
t = raw.replace('\r\n', '\n')
if TAG in t:
    print("already patched")
    raise SystemExit
if t.count(ANCHOR) != 1:
    print("PATCH NOT APPLIED: " + GPU + " does not look like the expected source")
    raise SystemExit(1)
t = t.replace(ANCHOR, CODE + ANCHOR)
with open(root + '/' + GPU, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched")
