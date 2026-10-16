#!/usr/bin/env python3
"""`p3fes_field.py ncodes` matches numbers derived from calendar entries with script object ids, against a control."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def table(code):
    rows = [(1,) + (0xFFFFFFFF,) * 7, ((5 << 16) | 4, 1, 0xFFFFFFFF, 1, 0, 0, 0, 0),
            (0, 0, 0xFFFFFFFF, 0xFFFFFFFF, 0, 0, 0, 0), (0xFFFF, 0, 0, 0, 0xFFFFFFFF, 0, 0, 0),
            (0x50000, code, 0xFFFFFFFF, 0xFFFFFFFF, 0, 0, 0, 0), (0xFFFF, 0, 0, 0, 0xFFFFFFFF, 0, 0, 0)]
    return b''.join(struct.pack('<8I', *r) for r in rows)
with tempfile.TemporaryDirectory() as t:
    for n, ident in (('F001_001', 403), ('F002_001', 206)):
        os.makedirs(os.path.join(t, 's', n + '.PAC.d')); os.makedirs(os.path.join(t, 'f', n + '.PAC.d'))
        open(os.path.join(t, 's', n + '.PAC.d', 'a.script.txt'), 'w').write('x = field_357(6, %d)\n' % ident)
        open(os.path.join(t, 'f', n + '.PAC.d', 'n' + n[1:].lower() + '.bin'), 'wb').write(table((2 << 16) | ident))
    r = subprocess.run([sys.executable, '-I', TOOL, 'ncodes', os.path.join(t, 's'), os.path.join(t, 'f'), '-o', os.path.join(t, 'o.txt')], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(os.path.join(t, 'o.txt')).read()
    assert 'low16        own     2  control     0' in txt, txt
print('ok   ncodes matches calendar entry numbers with script ids')
