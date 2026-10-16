#!/usr/bin/env python3
"""`p3fes_field.py hbnprops` compares .HBN points with the centres of the small objects of an exported field model."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def hbn(pts):
    d = struct.pack('<II', 0x45678901, 0x10003) + struct.pack('<16I', 0, 0x20, 0, 0x14, len(pts), 0x14, 0, 0x14, 0, 0x14, 0, 0x20, 0, 0x14, 0, 0x14)
    for k, (x, z) in enumerate(pts):
        d += struct.pack('<IffffI', 0x3C00 + k, x, 3.0, z, 0.0, 0)[:20]
    return d
def obj(centres):
    out = []
    for i, (x, z) in enumerate(centres):
        out.append('o prop_%d' % i)
        for dx, dz in ((-5, -5), (5, -5), (5, 5), (-5, 5)):
            out.append('v %f 0 %f' % (x + dx, z + dz))
    return '\n'.join(out) + '\n'
with tempfile.TemporaryDirectory() as t:
    for n, pts in ((1, [(100, 200), (300, 400)]), (2, [(-500, 50), (700, -700)])):
        d = os.path.join(t, 'F%03d_001.PAC.d' % n); os.makedirs(d)
        open(os.path.join(d, 'f%03d_001.HBN' % n), 'wb').write(hbn(pts))
        m = os.path.join(t, 'models', 'f%03d_001' % n); os.makedirs(m)
        open(os.path.join(m, 'a.obj'), 'w').write(obj(pts))
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'hbnprops', t, os.path.join(t, 'models'), '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert '2 | 4 | 4 | 0 | 0' in txt, txt
print('ok   hbnprops matches HBN points to prop centres')
