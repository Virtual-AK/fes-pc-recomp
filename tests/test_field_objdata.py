#!/usr/bin/env python3
"""`p3fes_field.py objdata` finds script object ids inside a field's own small files, against a control."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
with tempfile.TemporaryDirectory() as t:
    for n, v in (('F001_001', 130), ('F002_001', 206)):
        os.makedirs(os.path.join(t, 's', n + '.PAC.d')); os.makedirs(os.path.join(t, 'f', n + '.PAC.d'))
        open(os.path.join(t, 's', n + '.PAC.d', 'a.script.txt'), 'w').write('x = field_313(5, %d)\n' % v)
        open(os.path.join(t, 'f', n + '.PAC.d', 'a.hbn'), 'wb').write(struct.pack('<4I', 1, v, 2, 3))
    r = subprocess.run([sys.executable, '-I', TOOL, 'objdata', os.path.join(t, 's'), os.path.join(t, 'f'), '-o', os.path.join(t, 'o.txt')], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(os.path.join(t, 'o.txt')).read()
    assert '.hbn  4-byte values: own     2, control     0' in txt, txt
print('ok   objdata finds script ids in a field\'s own data files')
