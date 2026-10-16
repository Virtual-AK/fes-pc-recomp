#!/usr/bin/env python3
"""`p3fes_field.py fbnchars` lists character ids of .FBN records per variant."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def fbn(recs):
    d = struct.pack('<6I', 0x12345678, 0x10001, len(recs), 0x70, 0, 0x60)
    for slot, ch in recs:
        r = [0] * 28; r[1] = (ch << 16) | 5; r[2] = 0xC00 + slot
        d += struct.pack('<28I', *r)
    return d
with tempfile.TemporaryDirectory() as t:
    d = os.path.join(t, 'F006_003.PAC.d'); os.makedirs(d)
    open(os.path.join(d, 'f006_003_110.FBN'), 'wb').write(fbn([(60, 0x1E79), (1, 1)]))
    open(os.path.join(d, 'f006_006_110.FBN'), 'wb').write(fbn([(61, 0x1E79), (2, 0x1111)]))
    out = os.path.join(t, 'o.txt')
    p = subprocess.run([sys.executable, '-I', TOOL, 'fbnchars', t, '-o', out], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    txt = open(out).read()
    assert 'character ids in every scene: 1E79' in txt and 'slot60:1E79' in txt, txt
print('ok   fbnchars lists character ids')
