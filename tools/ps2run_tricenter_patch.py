"""Opt-in test for the Tartarus minimap (dashed tile outlines): texture coordinates and colours of triangles are read at the
CENTRE of each pixel instead of its corner, like the real graphics chip. Patches runtime/src/gs/raster.cpp (the CPU route).
Switch: PS2_TRI_CENTER=1 turns it on; without it nothing changes. Used to compare a frame both ways:
  PS2_GS=cpu ps2run ... --load-state X.state --frames N --frames-dir a            (old)
  PS2_TRI_CENTER=1 PS2_GS=cpu ps2run ... --load-state X.state --frames N --frames-dir b   (new)
Usage (in the ps2-web-recomp folder): python3 ps2run_tricenter_patch.py [runtime/src/gs/raster.cpp]
Safe to run twice. Rebuild afterwards: ninja -C build/native-p3fes
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/raster.cpp'
s = open(p).read()
if 'PS2_TRI_CENTER' in s:
    print("already patched"); raise SystemExit
A_OLD = """    const float inv = 1.0f / area;
    const float sg = area > 0.0f ? 1.0f : -1.0f;
    const auto edge_in ="""
A_NEW = """    const float inv = 1.0f / area;
    const float sg = area > 0.0f ? 1.0f : -1.0f;
    static const bool centre = std::getenv("PS2_TRI_CENTER") != nullptr;
    const auto edge_in ="""
B_OLD = """            const float w0 = e0 * inv;
            const float w1 = e1 * inv;
            const float w2 = 1.0f - w0 - w1;
            plot(s, x, y, lerp3(a0, a1, a2, w0, w1, w2));"""
B_NEW = """            float w0 = e0 * inv;
            float w1 = e1 * inv;
            if (centre) {
                const float cx = px + 0.5f, cy = py + 0.5f;
                w0 = ((x1 - cx) * (y2 - cy) - (x2 - cx) * (y1 - cy)) * inv;
                w1 = ((x2 - cx) * (y0 - cy) - (x0 - cx) * (y2 - cy)) * inv;
            }
            const float w2 = 1.0f - w0 - w1;
            plot(s, x, y, lerp3(a0, a1, a2, w0, w1, w2));"""
I_OLD = "#include <cstring>\n"
I_NEW = "#include <cstdlib>\n#include <cstring>\n"
for o in [A_OLD, B_OLD, I_OLD]:
    if s.count(o) != 1:
        print("PATCH NOT APPLIED: raster.cpp does not look like the expected source"); raise SystemExit(1)
s = s.replace(A_OLD, A_NEW, 1).replace(B_OLD, B_NEW, 1).replace(I_OLD, I_NEW, 1)
open(p, 'w').write(s)
print("patched (PS2_TRI_CENTER=1 reads triangle textures at pixel centres)")
