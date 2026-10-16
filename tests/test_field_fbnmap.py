#!/usr/bin/env python3
"""`p3fes_field.py fbnmap` draws a scene's base .FBN against a variant."""
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
    open(os.path.join(d, 'f006_003_110.FBN'), 'wb').write(fbn([(0, 10, 10), (1, 99, 20), (2, 0, 71)]))
    out = os.path.join(t, 'o')
    r = subprocess.run([sys.executable, '-I', TOOL, 'fbnmap', t, '6:3', '110', '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(os.path.join(out, 'fbnmap.txt')).read()
    assert '1 moved vs base, 1 unchanged, 1 only in variant, 1 placeholders' in txt, txt
    assert open(os.path.join(out, 'f006_003_110_vs_000.png'), 'rb').read(8) == b'\x89PNG\r\n\x1a\n'
print('ok   fbnmap draws base vs variant')
