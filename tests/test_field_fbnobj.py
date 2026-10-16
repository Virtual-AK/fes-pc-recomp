#!/usr/bin/env python3
"""`p3fes_field.py fbnobj` writes the slots of a scene as marker .obj files."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def fbn(recs):
    d = struct.pack('<6I', 0x12345678, 0x10001, len(recs), 0x70, 0, 0x60)
    for i, x, z in recs:
        r = [0] * 28; r[2] = 0xC00 + i
        r[20:23] = struct.unpack('<3I', struct.pack('<3f', x, 3.0, z))
        d += struct.pack('<28I', *r)
    return d
with tempfile.TemporaryDirectory() as t:
    d = os.path.join(t, 'F006_003.PAC.d'); os.makedirs(d)
    open(os.path.join(d, 'f006_003_000.FBN'), 'wb').write(fbn([(0, 10, 10), (1, 20, 20)]))
    open(os.path.join(d, 'f006_003_110.FBN'), 'wb').write(fbn([(0, 0, 71)]))
    out = os.path.join(t, 'o')
    r = subprocess.run([sys.executable, '-I', TOOL, 'fbnobj', t, '6:3', '110', '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    a = open(os.path.join(out, 'f006_003_000_slots.obj')).read(); b = open(os.path.join(out, 'f006_003_110_slots.obj')).read()
    assert 'o slot_0' in a and 'o slot_1' in a and a.count('\nv ') == 10, a
    assert 'o slot_0_unset' in b, b
print('ok   fbnobj writes slot markers')
