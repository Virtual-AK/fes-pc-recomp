"""Fix for the thin diagonal lines inside text and across glyphs (Load Data list, transitions, text boxes): in the graphics-card
route (browser build and PC window) a textured quad is drawn as two triangles. At 2x or 3x resolution the sample points of the
pixel grid fall exactly on the shared diagonal, and float rounding made both triangles reject the point, leaving a hairline gap.
After this patch a sample whose edge value is within 0.00001 of zero counts as exactly on the edge, so the top-left rule decides
it: exactly one of the two triangles draws the pixel. Patches runtime/src/gs/gpu/gs.wgsl (edge_in).
Usage (in the ps2-web-recomp folder): python3 ps2gpu_edgetie_patch.py [runtime/src/gs/gpu/gs.wgsl]
Safe to run twice. Rebuild both builds afterwards.
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gpu/gs.wgsl'
s = open(p).read()
if 'edge_tie' in s:
    print("already patched"); raise SystemExit
OLD = "fn edge_in(w: f32, inclusive: u32) -> bool {\n    return w > 0.0 || (w == 0.0 && inclusive != 0u);\n}\n"
NEW = """fn edge_in(w: f32, inclusive: u32) -> bool {
    // edge_tie: a sample within rounding noise of the edge counts as on it, so the top-left rule picks one triangle
    let tie = 0.00001;
    return w > tie || (abs(w) <= tie && inclusive != 0u);
}
"""
if s.count(OLD) != 1:
    print("PATCH NOT APPLIED: edge_in() not found (or changed)"); raise SystemExit(1)
open(p, 'w').write(s.replace(OLD, NEW, 1))
print("patched (edge ties are decided by the top-left rule)")
