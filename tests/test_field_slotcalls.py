#!/usr/bin/env python3
"""`p3fes_field.py slotcalls` compares field_312 numbers with .FBN slot numbers of the same scene."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def fbn(ids):
    d = struct.pack('<6I', 0x12345678, 0x10001, len(ids), 0x70, 0, 0x60)
    for i in ids:
        r = [0] * 28; r[2] = 0xC00 + i
        d += struct.pack('<28I', *r)
    return d
with tempfile.TemporaryDirectory() as t:
    for n, ids in ((1, [3, 14]), (2, [5, 16])):
        name = 'F%03d_001' % n
        d = os.path.join(t, name + '.PAC.d'); os.makedirs(d)
        open(os.path.join(d, name.lower() + '_050.FBN'), 'wb').write(fbn(ids))
        open(os.path.join(d, 'a.txt'), 'w').write('  field_312(field_311(0), %d)\n  field_312(lvar1, %d)\n' % tuple(ids))
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'slotcalls', t, t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert 'all n, FBN slots | 4 | 4 | 0' in txt, txt
print('ok   slotcalls ties field_312 numbers to FBN slots')
