#!/usr/bin/env python3
"""`p3fes_field.py hbnmap` writes a top-down PNG of the points of an .hbn file."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
d = struct.pack('<II', 0x45678901, 0x10003) + struct.pack('<16I', 1, 0x20, 0, 0x14, 4, 0x14, 0, 0x14, 0, 0x14, 0, 0x20, 0, 0x14, 0, 0x14)
d += struct.pack('<IIffffff', 0x3400, 0xA80000FF, -100.0, 3.0, -100.0, 100.0, -100.0, 0.0)
for k, (x, z) in enumerate(((400, 400), (400, -400), (-400, -400), (-400, 400))):
    d += struct.pack('<IffffI', 0x3C00 + k, x, 3.0, z, 90.0 * k, 0)[:20]
with tempfile.TemporaryDirectory() as t:
    f = os.path.join(t, 'F045_001.PAC.d'); os.makedirs(f)
    open(os.path.join(f, 'f045_001.HBN'), 'wb').write(d)
    out = os.path.join(t, 'maps')
    r = subprocess.run([sys.executable, '-I', TOOL, 'hbnmap', t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    png = os.path.join(out, 'f045_001_hbn.png')
    assert os.path.getsize(png) > 100 and open(png, 'rb').read(8) == b'\x89PNG\r\n\x1a\n', r.stdout
    assert '0:1, 2:4' in open(os.path.join(out, 'hbnmap.txt')).read()
print('ok   hbnmap draws the points of an .hbn file')
