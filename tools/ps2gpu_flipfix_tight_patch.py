"""Fix for the leftover lines and the shifted bottom-right corner of text boxes: the "flipped tile" step (ps2gpu_flipfix_patch.py, made for
the Tartarus map) moved any texture axis that runs backwards and is within 5% of 1:1 by one texel. The text box strips are 253 pixels
wide for 252 texels (and 22 pixels high for 21), so they were caught too: the left strip got a shifted row (a pale line) and the mirrored
right strip got a shifted column (the corner no longer matched the left one). Map tiles are exactly 1:1, so the step now only applies
within 0.2% of 1:1. Patches runtime/src/gs/gpu/gs.wgsl.
Usage (in the ps2-web-recomp folder): python3 ps2gpu_flipfix_tight_patch.py [runtime/src/gs/gpu/gs.wgsl]
Safe to run twice. Needs ps2gpu_flipfix_patch.py applied first. Rebuild both builds afterwards.
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gpu/gs.wgsl'
s = open(p).read()
A = 'if (gu < 0.0 && abs(abs(gu) - 1.0) < 0.05) {'
B = 'if (gv < 0.0 && abs(abs(gv) - 1.0) < 0.05) {'
if A.replace('0.05', '0.002') in s and B.replace('0.05', '0.002') in s:
    print("already patched"); raise SystemExit
if s.count(A) != 1 or s.count(B) != 1:
    print("PATCH NOT APPLIED: the flip_fix step was not found (apply ps2gpu_flipfix_patch.py first)"); raise SystemExit(1)
s = s.replace(A, A.replace('0.05', '0.002')).replace(B, B.replace('0.05', '0.002'))
open(p, 'w').write(s)
print("patched (flipped-tile shift only for exactly 1:1 tiles)")
