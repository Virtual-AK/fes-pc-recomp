"""Second trace step (run after ps2run_trace_patch.py): with PS2_TRACE_TEX set, every [trx] line is
preceded by a [up] line giving how many bytes the PREVIOUS upload actually received and how many of
them were not zero. Numbers only. Usage: python3 ps2run_trace_patch2.py [runtime/src/gs/gs.cpp]
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gs.cpp'
s = open(p).read()
if 'g_up_bytes' in s:
    print("already patched"); raise SystemExit
def sub(old, new):
    global s
    if s.count(old) != 1:
        print("PATCH NOT APPLIED: text not found:", old.strip()[:60]); raise SystemExit(1)
    s = s.replace(old, new)
sub('void feed_image(const std::uint8_t *data, std::size_t bytes) {\n',
'''unsigned long long g_up_bytes = 0, g_up_nz = 0;

void feed_image(const std::uint8_t *data, std::size_t bytes) {
    if ((g_state.trxdir & 3u) == 0) {
        g_up_bytes += bytes;
        for (std::size_t i = 0; i < bytes; ++i) g_up_nz += data[i] != 0;
    }
''')
sub('        if (trace_tex())\n            std::fprintf(stderr, "[trx] f',
'''        if (trace_tex()) {
            std::fprintf(stderr, "[up] bytes=%llu nonzero=%llu\\n", g_up_bytes, g_up_nz);
        }
        g_up_bytes = g_up_nz = 0;
        if (trace_tex())
            std::fprintf(stderr, "[trx] f''')
open(p, 'w').write(s)
print("patched")
