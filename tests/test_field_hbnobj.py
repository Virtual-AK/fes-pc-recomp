#!/usr/bin/env python3
"""`p3fes_field.py hbnobj` writes the points of a scene's .hbn as marker .obj files."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
counts = [0, 2, 0, 0, 0, 0, 0, 0]
d = struct.pack('<2I', 0x45678901, 1) + b''.join(struct.pack('<II', c, 0x14) for c in counts)
d += struct.pack('<I', 0) * 0
d = d.ljust(0x48, b'\0')
for i, (x, y, z, a) in enumerate([(100.0, 3.0, 200.0, 90.0), (-50.0, 3.0, 10.0, 0.0)]):
    d += struct.pack('<I4f', 0x3800 + i, x, y, z, a)
with tempfile.TemporaryDirectory() as t:
    p = os.path.join(t, 'F006_002.PAC.d'); os.makedirs(p)
    open(os.path.join(p, 'f006_002.HBN'), 'wb').write(d)
    out = os.path.join(t, 'o')
    r = subprocess.run([sys.executable, '-I', TOOL, 'hbnobj', t, '6:2', '1', '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    a = open(os.path.join(out, 'f006_002_hbn.obj')).read()
    assert 'o s1_0_id00' in a and 'o s1_1_id01' in a and a.count('\nl ') == 2, a
    assert 'v 280.000 33.000 200.000' in a, a   # point 0 faces +x at 90 degrees: 100 + 6*30
    r = subprocess.run([sys.executable, '-I', TOOL, 'hbnobj', t, '6:9', '-o', out], capture_output=True, text=True)
    assert r.returncode != 0 and 'no f006_009.HBN' in (r.stdout + r.stderr)
print('ok   hbnobj writes point markers with a facing line')
