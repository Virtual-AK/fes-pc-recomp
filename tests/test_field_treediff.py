#!/usr/bin/env python3
"""`p3fes_field.py treediff` compares two extraction folders."""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def put(root, rel, n):
    p = os.path.join(root, *rel.split('/')); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(b'x' * n)
with tempfile.TemporaryDirectory() as t:
    o, n = os.path.join(t, 'old'), os.path.join(t, 'new')
    for r, rel, size in ((o, 'FIELD/F1.PAC.d/a.FBN', 10), (n, 'field/f1.pac.d/A.fbn', 10),
                         (o, 'FIELD/F1.PAC.d/npc_00', 0), (n, 'FIELD/F1.PAC.d/f1.HBN', 92), (n, 'FIELD/F1.PAC.d/f1.CMR', 112),
                         (o, 'FIELD/F1.PAC.d/b.bin', 5), (n, 'FIELD/F1.PAC.d/b.bin', 6), (o, 'manifest.csv', 1)):
        put(r, rel, size)
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'treediff', o, n, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    a = open(out).read()
    assert 'old: 3 files, new: 4 files; in both: 2, only new: 2 (204 bytes), only old: 1 (of which empty: 1), size differs: 1' in a, a
    assert '.hbn' in a and '.cmr' in a and 'f1.HBN' in a.split('Only in the new folder')[1], a
print('ok   treediff compares two extraction folders')
