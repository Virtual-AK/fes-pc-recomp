"""Speed test switch: PS2_NODRAW=1 makes the GS accept every shape but draw none of them, so the time per frame (PS2_TIME) shows what the
game code, the vector units and the sound need without any drawing. Comparing it with a normal run shows how much of a frame the drawing costs.
The picture stays empty; use it only for timing.
Usage (in the ps2-web-recomp folder): python3 ps2run_nodraw_patch.py [runtime/src/gs/gs.cpp]
Safe to run twice. Rebuild afterwards: ninja -C build/native-p3fes ps2run
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gs.cpp'
s = open(p).read()
if 'PS2_NODRAW' in s:
    print("already patched"); raise SystemExit
OLD = 'void kick(bool draw) {\n    State &s = g_state;\n'
if s.count(OLD) != 1:
    print("PATCH NOT APPLIED: kick()"); raise SystemExit(1)
s = s.replace(OLD, OLD + '    static const bool nodraw = std::getenv("PS2_NODRAW") != nullptr;\n    if (nodraw) draw = false;\n', 1)
open(p, 'w').write(s)
print("patched (PS2_NODRAW)")
