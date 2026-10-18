"""Fix for the misaligned tiles on the Tartarus minimap: in the graphics-card route (browser build and PC window), on a 1:1
textured triangle whose texture coordinate runs backwards (flipped / rotated tiles) the coordinate is moved one texel, so
flipped and unflipped tiles line up. Patches runtime/src/gs/gpu/gs.wgsl. Apply ps2gpu_tricenter_patch.py first.
Usage (in the ps2-web-recomp folder): python3 ps2gpu_flipfix_patch.py [runtime/src/gs/gpu/gs.wgsl]
Safe to run twice. Rebuild both builds afterwards.
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gpu/gs.wgsl'
s = open(p).read()
if 'flip_fix' in s:
    print("already patched"); raise SystemExit
OLD = "            let t = vertex_tex(p, 0u) * a0 + vertex_tex(p, 1u) * a1 + vertex_tex(p, 2u) * a2;\n"
NEW = """            var t = vertex_tex(p, 0u) * a0 + vertex_tex(p, 1u) * a1 + vertex_tex(p, 2u) * a2;
            // flip_fix: a 1:1 textured axis whose coordinate runs backwards is moved one texel
            if (has(s, F_TME)) {
                var tu = array<f32, 3>(0.0, 0.0, 0.0);
                var tv = array<f32, 3>(0.0, 0.0, 0.0);
                for (var i = 0u; i < 3u; i = i + 1u) {
                    let vt = vertex_tex(p, i);
                    if (has(s, F_FST)) {
                        tu[i] = vt.x / 16.0;
                        tv[i] = vt.y / 16.0;
                    } else {
                        var q = vt.z;
                        if (q == 0.0) {
                            q = 1.0;
                        }
                        tu[i] = vt.x / q * f32(1u << s.tw);
                        tv[i] = vt.y / q * f32(1u << s.th);
                    }
                }
                let ux = ((tu[1] - tu[0]) * (y2 - y0) - (tu[2] - tu[0]) * (y1 - y0)) * inv;
                let uy = ((tu[2] - tu[0]) * (x1 - x0) - (tu[1] - tu[0]) * (x2 - x0)) * inv;
                let vx = ((tv[1] - tv[0]) * (y2 - y0) - (tv[2] - tv[0]) * (y1 - y0)) * inv;
                let vy = ((tv[2] - tv[0]) * (x1 - x0) - (tv[1] - tv[0]) * (x2 - x0)) * inv;
                var gu = uy;
                if (abs(ux) >= abs(uy)) {
                    gu = ux;
                }
                var gv = vy;
                if (abs(vx) >= abs(vy)) {
                    gv = vx;
                }
                if (gu < 0.0 && abs(abs(gu) - 1.0) < 0.05) {
                    if (has(s, F_FST)) {
                        t.x = t.x - 16.0;
                    } else {
                        t.x = t.x - t.z / f32(1u << s.tw);
                    }
                }
                if (gv < 0.0 && abs(abs(gv) - 1.0) < 0.05) {
                    if (has(s, F_FST)) {
                        t.y = t.y - 16.0;
                    } else {
                        t.y = t.y - t.z / f32(1u << s.th);
                    }
                }
            }
"""
if s.count(OLD) != 1:
    print("PATCH NOT APPLIED: gs.wgsl does not look like the expected source (apply ps2gpu_tricenter_patch.py first)"); raise SystemExit(1)
open(p, 'w').write(s.replace(OLD, NEW, 1))
print("patched (flipped minimap tiles are moved one texel)")
