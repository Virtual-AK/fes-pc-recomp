"""Colour rounding fix for the PC window of PS2 Web Recomp (fixes the dither-like speckle on the Priestess boss and anything else drawn with an alpha test).

The window works out a pixel's colour and transparency from the triangle's corners with floating point maths. For a flat value such as a transparency of
127 the result can come out as 126.99999, which was cut down to 126, so the alpha test ("at least 127") failed for a scatter of pixels. The console keeps flat
values exact. The fix adds a tiny amount (0.002) before the cut, which has no visible effect on anything else.

Run in the ps2-web-recomp folder:  python3 ps2run_colfix_patch.py [folder]
(patches runtime/src/gs/gpu/gs.wgsl; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
TAG = 'ps2run_colfix_patch.py'
REL = 'runtime/src/gs/gpu/gs.wgsl'
OLD = '    var r = i32(at.r);\n    var g = i32(at.g);\n    var b = i32(at.b);\n    var a = i32(at.a);\n'
NEW = ('    var r = i32(at.r + 0.002);   // ' + TAG + ': flat colours stay exact\n'
       '    var g = i32(at.g + 0.002);\n    var b = i32(at.b + 0.002);\n    var a = i32(at.a + 0.002);\n')
try:
    raw = open(root + '/' + REL, newline='').read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + REL)
    raise SystemExit(1)
t = raw.replace('\r\n', '\n')
if TAG in t:
    print("already patched")
    raise SystemExit
if t.count(OLD) != 1:
    print("PATCH NOT APPLIED: " + REL + " does not look like the expected source")
    raise SystemExit(1)
t = t.replace(OLD, NEW)
open(root + '/' + REL, 'w', newline='').write(t.replace('\n', '\r\n') if '\r\n' in raw else t)
print("patched")
