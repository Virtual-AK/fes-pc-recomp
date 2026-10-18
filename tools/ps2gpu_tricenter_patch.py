"""Fix for the dashed tile outlines on the Tartarus minimap (and a likely cause of other soft or shifted picture edges): in the
graphics-card drawing route (browser build and PC window) the colours and texture coordinates of triangles are now read at the
CENTRE of each pixel, like the real graphics chip, instead of its corner. A flipped tile (the minimap turns with the camera) used
to pick the neighbouring texel on the flipped axis, so the tile's outline texel showed as dashes.
Patches runtime/src/gs/gpu/gs.wgsl. The depth value is still read the old way (unchanged).
Tested first with the CPU route (ps2run_tricenter_patch.py, PS2_TRI_CENTER=1): the outlines turned solid.
Usage (in the ps2-web-recomp folder): python3 ps2gpu_tricenter_patch.py [runtime/src/gs/gpu/gs.wgsl]
Safe to run twice. Rebuild both: ninja -C build/native-p3fes   and   scripts/build_web.sh p3fes
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gpu/gs.wgsl'
s = open(p).read()
if 'tri_centre' in s:
    print("already patched"); raise SystemExit
OLD = """            let w2 = 1.0 - w0 - w1;
            let c = vertex_attr(p, 0u) * w0 + vertex_attr(p, 1u) * w1 + vertex_attr(p, 2u) * w2;
            let t = vertex_tex(p, 0u) * w0 + vertex_tex(p, 1u) * w1 + vertex_tex(p, 2u) * w2;
"""
NEW = """            let w2 = 1.0 - w0 - w1;
            // tri_centre: colours and texture coordinates are read at the centre of the pixel (sample)
            let cxc = px + 0.5 / f32(SCALE);
            let cyc = py + 0.5 / f32(SCALE);
            let a0 = ((x1 - cxc) * (y2 - cyc) - (x2 - cxc) * (y1 - cyc)) * inv;
            let a1 = ((x2 - cxc) * (y0 - cyc) - (x0 - cxc) * (y2 - cyc)) * inv;
            let a2 = 1.0 - a0 - a1;
            let c = vertex_attr(p, 0u) * a0 + vertex_attr(p, 1u) * a1 + vertex_attr(p, 2u) * a2;
            let t = vertex_tex(p, 0u) * a0 + vertex_tex(p, 1u) * a1 + vertex_tex(p, 2u) * a2;
"""
if s.count(OLD) != 1:
    print("PATCH NOT APPLIED: gs.wgsl does not look like the expected source"); raise SystemExit(1)
open(p, 'w').write(s.replace(OLD, NEW, 1))
print("patched (triangle colours and textures read at pixel centres)")
