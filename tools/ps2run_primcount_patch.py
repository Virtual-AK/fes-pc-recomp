"""Trace aid: PS2_TRACE_PRIMCOUNT=1 prints one short line per frame, "[primcount] f<frame> n=<all shapes> main=<shapes drawn to the screen buffer>",
so the frame that holds a heavy scene (for example a cut-in with about 14,000 shapes) can be found without a huge PS2_TRACE_PRIM log. Numbers only.
Usage (in the ps2-web-recomp folder): python3 ps2run_primcount_patch.py [runtime/src/gs/gs.cpp]
Needs ps2run_trace_patch6.py applied first. Safe to run twice. Rebuild afterwards (native: ninja -C build/native-p3fes ps2run; web: scripts/build_web.sh p3fes)
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gs.cpp'
s = open(p).read()
if 'PS2_TRACE_PRIMCOUNT' in s:
    print("already patched"); raise SystemExit
OLD = 'void trace_prim(const State &s, int needed) {\n'
if s.count(OLD) != 1:
    print("PATCH NOT APPLIED: trace_prim() (apply ps2run_trace_patch6.py first)"); raise SystemExit(1)
NEW = OLD + '''    static const bool primcount = std::getenv("PS2_TRACE_PRIMCOUNT") != nullptr;
    if (primcount) {
        static unsigned long long last_f = ~0ull, n_all = 0, n_main = 0;
        const unsigned long long cf = static_cast<unsigned long long>(ps2::frame_count());
        if (cf != last_f) {
            if (last_f != ~0ull) std::fprintf(stderr, "[primcount] f%llu n=%llu main=%llu\\n", last_f, n_all, n_main);
            last_f = cf; n_all = 0; n_main = 0;
        }
        ++n_all;
        if ((s.ctx[(s.prim >> 9) & 1u].frame & 0x1FFull) == 0) ++n_main;
    }
'''
s = s.replace(OLD, NEW, 1)
open(p, 'w').write(s)
print("patched (PS2_TRACE_PRIMCOUNT)")
