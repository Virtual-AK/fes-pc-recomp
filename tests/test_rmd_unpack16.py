#!/usr/bin/env python3
"""Test the 16-bit animation value decode against values read from a real character (N00001A)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
import p3fes_rmd as r

ok = True
def check(raw, want, tol=1e-4):
    global ok
    got = r.unpack16(raw)
    if abs(got - want) > tol:
        ok = False
        print('FAIL %04x: got %.5f, want %.5f' % (raw, got, want))

# anchors: 1.0, 0.75, 0.5 and their negatives; values derived from the real rest pose table
for raw, want in ((0x7800, 1.0), (0x7400, 0.75), (0x7000, 0.5), (0xF800, -1.0), (0xF400, -0.75), (0x0000, 0.0),
                  (0xF54C, -0.83103), (0xD432, -0.04764), (0x585F, 0.0654), (0x6F9D, 0.48786), (0x56FE, 0.05856)):
    check(raw, want, 2e-4)
# the block gives x = offset + scale * v; bone 6 of N00001A has x 43.9246 at raw 0x7800
x = 1.99759 + 41.927 * r.unpack16(0x7800)
if abs(x - 43.9246) > 1e-3:
    ok = False; print('FAIL block offset/scale: %.4f' % x)
print('unpack16 test:', 'OK' if ok else 'FAILED')
sys.exit(0 if ok else 1)
