#!/usr/bin/env python3
"""`p3fes_field.py objwhere` finds script ids as 32-bit values in the field's own files, per script function."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
with tempfile.TemporaryDirectory() as t:
    for n, v in (('F001_001', 206), ('F002_001', 157)):
        for root in ('s', 'f'):
            os.makedirs(os.path.join(t, root, n + '.PAC.d'))
        open(os.path.join(t, 's', n + '.PAC.d', 'a.txt'), 'w').write('x = field_313(5, %d)\n' % v)
        open(os.path.join(t, 'f', n + '.PAC.d', 'h.hbn'), 'wb').write(struct.pack('<12I', *([0] * 5), v, *([0] * 6)))
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'objwhere', os.path.join(t, 's'), os.path.join(t, 'f'), '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert '313 kind 5' in txt and 'own     2  control     0' in txt, txt
print('ok   objwhere finds script ids per function in field files')
