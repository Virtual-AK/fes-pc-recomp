"""Eighth trace step (run after ps2run_trace_patch7.py): PS2_TRACE_VUMEM=from,to,ADDR,QWORDS,RUN dumps the VU1 data memory
(the vertex data a program is about to work on) at the start of one run of the VU1 program that starts at byte address ADDR (hex),
in frames from..to. RUN counts that program's runs in the process, starting at 0. QWORDS is how many 16-byte entries to print from
TOP. Each line: entry number, the four words in hex, then the same four as floating point. Numbers only (a few vertex values),
no pictures, no code. Example: PS2_TRACE_VUMEM=25079,25080,36F0,40,0
Usage (in the ps2-web-recomp folder): python3 ps2run_trace_patch8.py [runtime/src/vif.cpp]
Safe to run twice. Rebuild afterwards: ninja -C build/native-p3fes ps2run
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/vif.cpp'
s = open(p).read()
if 'PS2_TRACE_VUMEM' in s:
    print("already patched"); raise SystemExit
if 'PS2_TRACE_VIF' not in s:
    print("PATCH NOT APPLIED: run ps2run_trace_patch7.py first"); raise SystemExit(1)
A = '    vu::run(unit, address);\n'
if s.count(A) != 1:
    print("PATCH NOT APPLIED: run_vu"); raise SystemExit(1)
T = r'''    if (unit == 1 && !shadow(unit)) {
        static const char *dm = std::getenv("PS2_TRACE_VUMEM");
        if (dm) {
            char *e1 = nullptr, *e2 = nullptr, *e3 = nullptr, *e4 = nullptr;
            const unsigned long long from = std::strtoull(dm, &e1, 10);
            const unsigned long long to = (e1 && *e1 == ',') ? std::strtoull(e1 + 1, &e2, 10) : from + 1;
            const unsigned long want = (e2 && *e2 == ',') ? std::strtoul(e2 + 1, &e3, 16) : 0;
            const unsigned long count = (e3 && *e3 == ',') ? std::strtoul(e3 + 1, &e4, 10) : 40;
            const unsigned long which = (e4 && *e4 == ',') ? std::strtoul(e4 + 1, nullptr, 10) : 0;
            const unsigned long long f = static_cast<unsigned long long>(ps2::frame_count());
            static unsigned long runs = 0;
            if (f >= from && f < to && address == want) {
                if (runs++ == which) {
                    const std::uint8_t *mem = vu_data(1);
                    std::fprintf(stderr, "[vumem] f%llu run addr=%04X top=%u itop=%u\n", f, address, u.top, u.itop);
                    for (unsigned long i = 0; i < count && (u.top + i) < 1024; ++i) {
                        std::uint32_t w[4];
                        float fl[4];
                        std::memcpy(w, mem + (u.top + i) * 16, 16);
                        std::memcpy(fl, w, 16);
                        std::fprintf(stderr, "[vumem] %3lu  %08X %08X %08X %08X   %g %g %g %g\n", i, w[0], w[1], w[2], w[3],
                                     static_cast<double>(fl[0]), static_cast<double>(fl[1]), static_cast<double>(fl[2]), static_cast<double>(fl[3]));
                    }
                }
            }
        }
    }
'''
s = s.replace(A, T + A, 1)
open(p, 'w').write(s)
print("patched (PS2_TRACE_VUMEM)")
