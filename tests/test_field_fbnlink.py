#!/usr/bin/env python3
"""`p3fes_field.py fbnlink` compares calendar slots/groups with the ids and file-name numbers of .FBN files."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def table(slot, group):
    rows = [(1,) + (0xFFFFFFFF,) * 7, ((5 << 16) | 4, 1, 0xFFFFFFFF, group, 0, 0, 0, 0),
            (0xFFFF, 0, 0, 0, 0xFFFFFFFF, 0, 0, 0), (0x50000 | slot, 100, 7, 0xFFFFFFFF, 0, 0, 0, 0), (0xFFFF, 0, 0, 0, 0xFFFFFFFF, 0, 0, 0)]
    return b''.join(struct.pack('<8I', *r) for r in rows)
def fbn(ident):
    return struct.pack('<6I', 0x12345678, 0x10001, 1, 0x70, 0, 0x60) + struct.pack('<28I', 0, 0, 0xC00 + ident, *([0] * 25))
with tempfile.TemporaryDirectory() as t:
    for n, slot, group in (('F001_001', 3, 105), ('F002_001', 5, 110)):
        d = os.path.join(t, n + '.PAC.d'); os.makedirs(d)
        open(os.path.join(d, 'n' + n[1:].lower() + '.bin'), 'wb').write(table(slot, group))
        open(os.path.join(d, n.lower() + '_%03d.FBN' % group), 'wb').write(fbn(slot))
    r = subprocess.run([sys.executable, '-I', TOOL, 'fbnlink', t, '-o', os.path.join(t, 'o.txt')], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(os.path.join(t, 'o.txt')).read()
    assert 'slots found among FBN ids' in txt and 'own      2  control      0' in txt, txt
print('ok   fbnlink compares calendar slots and groups with FBN files')
