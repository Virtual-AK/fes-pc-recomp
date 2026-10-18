"""Opt-in test for the Tartarus minimap tile alignment: on a 1:1 textured triangle whose texture coordinate runs backwards
(flipped / rotated tiles) the coordinate is moved one texel, so flipped and unflipped tiles line up. Patches
runtime/src/gs/raster.cpp (the CPU route). Switch: PS2_TRI_FLIPFIX=1 turns it on; without it nothing changes.
Use together with PS2_TRI_CENTER=1 (apply ps2run_tricenter_patch.py first):
  PS2_TRI_CENTER=1 PS2_TRI_FLIPFIX=1 PS2_GS=cpu ps2run ... --load-state X.state --frames N --frames-dir c
Usage (in the ps2-web-recomp folder): python3 ps2run_flipfix_patch.py [runtime/src/gs/raster.cpp]
Safe to run twice. Rebuild afterwards: ninja -C build/native-p3fes
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/raster.cpp'
s = open(p).read()
if 'PS2_TRI_FLIPFIX' in s:
    print("already patched"); raise SystemExit
ANCHOR = "    const float inv = 1.0f / area;\n"
BLOCK = '    static const bool flipfix = std::getenv("PS2_TRI_FLIPFIX") != nullptr;\n    if (flipfix && s.tme) {\n        // flip_fix: a 1:1 textured axis whose coordinate decreases is shifted one texel\n        float tu[3], tv[3];\n        const Attr *ap[3] = {&a0, &a1, &a2};\n        for (int i = 0; i < 3; ++i) {\n            if (s.fst) { tu[i] = ap[i]->s / 16.0f; tv[i] = ap[i]->t / 16.0f; }\n            else {\n                const float q = ap[i]->q != 0.0f ? ap[i]->q : 1.0f;\n                tu[i] = ap[i]->s / q * static_cast<float>(1 << s.tw);\n                tv[i] = ap[i]->t / q * static_cast<float>(1 << s.th);\n            }\n        }\n        const auto grad = [&](const float *f, float &gx, float &gy) {\n            gx = ((f[1] - f[0]) * (y2 - y0) - (f[2] - f[0]) * (y1 - y0)) * inv;\n            gy = ((f[2] - f[0]) * (x1 - x0) - (f[1] - f[0]) * (x2 - x0)) * inv;\n        };\n        float ux, uy, vx, vy;\n        grad(tu, ux, uy);\n        grad(tv, vx, vy);\n        const auto flipped = [](float gx, float gy) {\n            const float g = std::fabs(gx) >= std::fabs(gy) ? gx : gy;\n            return std::fabs(std::fabs(g) - 1.0f) < 0.05f && g < 0.0f;\n        };\n        const bool fu = flipped(ux, uy), fv = flipped(vx, vy);\n        Attr *wp[3] = {&a0, &a1, &a2};\n        for (int i = 0; i < 3; ++i) {\n            if (s.fst) {\n                if (fu) wp[i]->s -= 16.0f;\n                if (fv) wp[i]->t -= 16.0f;\n            } else {\n                const float q = wp[i]->q != 0.0f ? wp[i]->q : 1.0f;\n                if (fu) wp[i]->s -= q / static_cast<float>(1 << s.tw);\n                if (fv) wp[i]->t -= q / static_cast<float>(1 << s.th);\n            }\n        }\n    }\n'
if s.count(ANCHOR) != 1:
    print("PATCH NOT APPLIED: raster.cpp does not look like the expected source"); raise SystemExit(1)
s = s.replace(ANCHOR, ANCHOR + BLOCK, 1)
open(p, 'w').write(s)
print("patched (PS2_TRI_FLIPFIX=1 shifts backwards 1:1 texture axes by one texel)")
