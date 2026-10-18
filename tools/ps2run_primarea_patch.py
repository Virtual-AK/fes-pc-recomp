"""Trace filter: PS2_TRACE_PRIMAREA=N makes PS2_TRACE_PRIM print only shapes whose bounding box covers at least N pixels (for example 20000),
so a long frame range stays small enough to save from the browser. Numbers only.
Usage (in the ps2-web-recomp folder): python3 ps2run_primarea_patch.py [runtime/src/gs/gs.cpp]
Needs ps2run_trace_patch6.py applied first. Safe to run twice. Rebuild afterwards (native: ninja -C build/native-p3fes ps2run; web: scripts/build_web.sh p3fes)
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gs.cpp'
s = open(p).read()
if 'PS2_TRACE_PRIMAREA' in s:
    print("already patched"); raise SystemExit
OLD = '    if (f < from || f >= to) return;\n    const std::uint64_t pr = s.prim;\n'
if s.count(OLD) != 1:
    print("PATCH NOT APPLIED: trace_prim() range check (apply ps2run_trace_patch6.py first)"); raise SystemExit(1)
NEW = '''    if (f < from || f >= to) return;
    static const char *area_spec = std::getenv("PS2_TRACE_PRIMAREA");
    if (area_spec) {
        static const unsigned long long min_area = std::strtoull(area_spec, nullptr, 10);
        unsigned x0 = ~0u, x1 = 0, y0 = ~0u, y1 = 0;
        for (int i = 0; i < needed; ++i) {
            const unsigned qx = static_cast<unsigned>(s.queue[i].x), qy = static_cast<unsigned>(s.queue[i].y);
            if (qx < x0) x0 = qx;
            if (qx > x1) x1 = qx;
            if (qy < y0) y0 = qy;
            if (qy > y1) y1 = qy;
        }
        if (((x1 - x0) / 16ull) * ((y1 - y0) / 16ull) < min_area) return;
    }
    const std::uint64_t pr = s.prim;
'''
s = s.replace(OLD, NEW, 1)
open(p, 'w').write(s)
print("patched (PS2_TRACE_PRIMAREA)")
