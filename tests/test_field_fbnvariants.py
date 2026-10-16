#!/usr/bin/env python3
"""`p3fes_field.py fbnvariants` compares the variant files of a scene."""
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
    d = os.path.join(t, 'F006_002.PAC.d'); os.makedirs(d)
    open(os.path.join(d, 'f006_002_000.FBN'), 'wb').write(fbn([(0, 10, 10), (1, 20, 20)]))
    open(os.path.join(d, 'f006_002_110.FBN'), 'wb').write(fbn([(0, 10, 10), (1, 99, 20), (2, 5, 5)]))
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'fbnvariants', t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert 'slots in both: 2, of which at the same position (within 0.5): 1' in txt and 'only in the variant: 1' in txt, txt
print('ok   fbnvariants compares variant files')
