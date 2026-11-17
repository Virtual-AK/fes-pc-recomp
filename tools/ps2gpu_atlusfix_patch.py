"""Fix for the stray dark lines that hang below the A and the U of the ATLUS boot logo: the logo picture the game ships with has two leftover
strokes in it (one pixel column of dark blue under the A, two under the U). They are in the picture itself, so no upscaling or filtering
setting removes them. This patch reads those few pixels as the black next to them, only for the logo picture (a 1024 wide 4-bit texture at
graphics block 0x2F60) and nothing else. Patches runtime/src/gs/gpu/gs.wgsl (fetch). Works in the PC window and the browser.
Usage (in the ps2-web-recomp folder): python3 ps2gpu_atlusfix_patch.py [runtime/src/gs/gpu/gs.wgsl]
Safe to run twice. Rebuild both builds afterwards.
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gpu/gs.wgsl'
s = open(p).read()
if 'atlus_fix' in s:
    print("already patched"); raise SystemExit
OLD = """fn fetch(s: Setup, xi: i32, yi: i32, k: u32) -> u32 {
    let x = texel_x(s, xi);
    let y = texel_y(s, yi);
"""
NEW = """fn fetch(s: Setup, xi: i32, yi: i32, k: u32) -> u32 {
    var x = texel_x(s, xi);
    let y = texel_y(s, yi);
    // atlus_fix: two leftover strokes in the ATLUS logo picture (under the A and under the U) read as the black beside them
    if (s.tbp == 0x2F60u && s.tw == 10u && s.tpsm == 0x14u) {
        if (x == 233u && y >= 232u && y <= 239u) {
            x = 232u;
        }
        if ((x == 378u || x == 379u) && y >= 256u && y <= 263u) {
            x = 377u;
        }
    }
"""
if s.count(OLD) != 1:
    print("PATCH NOT APPLIED: fetch() was not found (or changed)"); raise SystemExit(1)
open(p, 'w').write(s.replace(OLD, NEW, 1))
print("patched (the two leftover strokes in the ATLUS logo are hidden)")
