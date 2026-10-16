#!/usr/bin/env python3
"""`p3fes_field.py hbnlink` checks .HBN points against .FBN positions of the same field."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def hbn(x, z):
    d = struct.pack('<II', 0x45678901, 0x10003) + struct.pack('<16I', 0, 0x20, 1, 0x14, 0, 0x14, 0, 0x14, 0, 0x14, 0, 0x20, 0, 0x14, 0, 0x14)
    return d + struct.pack('<IffffI', 0x3800, x, 3.0, z, 90.0, 0)[:20] + b'ENEMY\0'
def fbn(x, z):
    r = [0] * 28; r[2] = 0xC03
    r[20:23] = struct.unpack('<3I', struct.pack('<3f', x, 3.0, z))
    return struct.pack('<6I', 0x12345678, 0x10001, 1, 0x70, 0, 0x60) + struct.pack('<28I', *r)
with tempfile.TemporaryDirectory() as t:
    for n, (x, z) in ((1, (100.0, 200.0)), (2, (-50.0, 75.0))):
        d = os.path.join(t, 'F%03d_001.PAC.d' % n); os.makedirs(d)
        open(os.path.join(d, 'f%03d_001_050.FBN' % n), 'wb').write(fbn(x, z))
        open(os.path.join(d, 'f%03d_001.HBN' % n), 'wb').write(hbn(x, z))
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'hbnlink', t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert '1 | 2 | 2 | 0' in txt and 'ENEMY' in txt and '1:2' in txt, txt
print('ok   hbnlink matches HBN points to FBN positions')
