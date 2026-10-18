"""Tenth trace step (run after ps2run_trace_patch6.py): PS2_SKIP_PRIM=frame,mode,value leaves out ONE class of shapes in that single
frame (the shapes are still counted but not drawn), so a frame picture shows which class is responsible for a visual fault.
mode and value: ctx,0 or ctx,1 (drawing setup 0 or 1); tme,0 or tme,1 (untextured or textured); abe,0 or abe,1 (without or with
blending); type,N (0 point, 1 line, 2 line strip, 3 triangle, 4 triangle strip, 5 triangle fan, 6 sprite); tbp,HEX (texture base).
Example: PS2_SKIP_PRIM=25079,tme,0 . The frame picture to look at is the one numbered one higher (frame_25080.ppm).
Usage (in the ps2-web-recomp folder): python3 ps2run_trace_patch10.py [runtime/src/gs/gs.cpp]
Safe to run twice. Rebuild afterwards: ninja -C build/native-p3fes ps2run
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gs.cpp'
s = open(p).read()
if 'PS2_SKIP_PRIM' in s:
    print("already patched"); raise SystemExit
if 'void trace_prim(const State &s, int needed) {' not in s:
    print("PATCH NOT APPLIED: run ps2run_trace_patch6.py first"); raise SystemExit(1)
OLD = 'void trace_prim(const State &s, int needed) {\n'
CALL_OLD = '    if (s.count < needed) return;\n    if (draw) {\n'
if s.count(OLD) != 1 or s.count(CALL_OLD) != 1:
    print("PATCH NOT APPLIED: kick()"); raise SystemExit(1)
HELP = r'''bool skip_prim(const State &s) {
    static const char *spec = std::getenv("PS2_SKIP_PRIM");
    if (!spec) return false;
    static const unsigned long long fr = std::strtoull(spec, nullptr, 10);
    static const char *c1 = std::strchr(spec, ',');
    static const char *c2 = c1 ? std::strchr(c1 + 1, ',') : nullptr;
    if (!c2) return false;
    if (static_cast<unsigned long long>(ps2::frame_count()) != fr) return false;
    const std::string mode(c1 + 1, c2);
    const unsigned long long pr = s.prim;
    const unsigned ctx = static_cast<unsigned>(pr >> 9) & 1u;
    if (mode == "ctx") return ctx == std::strtoul(c2 + 1, nullptr, 10);
    if (mode == "tme") return ((pr >> 4) & 1u) == std::strtoul(c2 + 1, nullptr, 10);
    if (mode == "abe") return ((pr >> 6) & 1u) == std::strtoul(c2 + 1, nullptr, 10);
    if (mode == "type") return (pr & 7u) == std::strtoul(c2 + 1, nullptr, 10);
    if (mode == "tbp") return (s.ctx[ctx].tex0 & 0x3FFF) == std::strtoul(c2 + 1, nullptr, 16);
    return false;
}

'''
s = s.replace(OLD, HELP + OLD, 1)
s = s.replace(CALL_OLD, '    if (s.count < needed) return;\n    if (draw && skip_prim(s)) draw = false;\n    if (draw) {\n', 1)
if '#include <string>' not in s:
    s = '#include <string>\n' + s
open(p, 'w').write(s)
print("patched (PS2_SKIP_PRIM)")
