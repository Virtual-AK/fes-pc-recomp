"""Trace aid: PS2_DUMP_VU1=FROM_FRAME,XGKICK_ADDRESS_HEX saves the VU1 program and its memory for ONE packet, so the program can be read offline.
At the first XGKICK at that address in or after that frame it writes, into the current folder: vu1_code.bin (micro memory, 16 KB),
vu1_pre.bin (data memory when the program started), vu1_post.bin (data memory at the kick), vu1_regs_pre.bin (registers at program start,
raw struct) and vu1_info.txt (frame, program start address, kick address). Example for the broken cut-in portraits:
  PS2_DUMP_VU1=25077,2D2
These files are game data: keep them on your PC, send them to me in chat only, never to GitHub.
Usage (in the ps2-web-recomp folder): python3 ps2run_vudump_patch.py [runtime/src/vu_micro.cpp]
Safe to run twice. Rebuild afterwards (native: ninja -C build/native-p3fes ps2run)
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/vu_micro.cpp'
s = open(p).read()
if 'PS2_DUMP_VU1' in s:
    print("already patched"); raise SystemExit
A = 'void trace_xgk(Unit &u, const std::uint8_t *buffer, std::uint32_t count, std::uint32_t address) {\n'
B = 'void run(int n, std::uint32_t address) {\n'
C = '    trace_xgk(u, buffer, count, address);\n'
if s.count(A) != 1 or s.count(B) != 1 or s.count(C) != 1:
    print("PATCH NOT APPLIED: vu_micro.cpp does not look like the expected source"); raise SystemExit(1)
HELP = '''std::uint8_t g_dump_pre[16384];
Vu0Regs g_dump_regs;
std::uint32_t g_dump_entry = 0;
bool g_dump_done = false;

void dump_enter(std::uint32_t address) {
    static const bool on = std::getenv("PS2_DUMP_VU1") != nullptr;
    if (!on || g_dump_done) return;
    std::memcpy(g_dump_pre, g_vu1_mem, sizeof g_dump_pre);
    g_dump_regs = g_vu1;
    g_dump_entry = address;
}

void dump_kick(const Unit &u, std::uint32_t address) {
    static const char *spec = std::getenv("PS2_DUMP_VU1");
    if (!spec || g_dump_done || u.code != g_vu1_code) return;
    const unsigned long long from = std::strtoull(spec, nullptr, 10);
    const char *c = std::strchr(spec, ',');
    if (!c) return;
    const std::uint32_t want = static_cast<std::uint32_t>(std::strtoul(c + 1, nullptr, 16));
    const unsigned long long f = static_cast<unsigned long long>(ps2::frame_count());
    if (f < from || address != want) return;
    g_dump_done = true;
    const auto put = [](const char *name, const void *data, std::size_t n) {
        std::FILE *fp = std::fopen(name, "wb");
        if (!fp) return;
        std::fwrite(data, 1, n, fp);
        std::fclose(fp);
    };
    put("vu1_code.bin", g_vu1_code, 16384);
    put("vu1_pre.bin", g_dump_pre, 16384);
    put("vu1_post.bin", u.data, 16384);
    put("vu1_regs_pre.bin", &g_dump_regs, sizeof g_dump_regs);
    if (std::FILE *fp = std::fopen("vu1_info.txt", "w")) {
        std::fprintf(fp, "frame=%llu program_start=%X kick=%X\\n", f, g_dump_entry, address);
        std::fclose(fp);
    }
    std::fprintf(stderr, "[vudump] f%llu program_start=%X kick=%X: wrote vu1_code.bin vu1_pre.bin vu1_post.bin vu1_regs_pre.bin vu1_info.txt\\n", f, g_dump_entry, address);
}

'''
s = s.replace(A, HELP + A, 1)
s = s.replace(B, B + '    if (n == 1) dump_enter(address);\n', 1)
s = s.replace(C, '    dump_kick(u, address);\n' + C, 1)
open(p, 'w').write(s)
print("patched (PS2_DUMP_VU1)")
