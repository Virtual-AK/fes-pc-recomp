#!/usr/bin/env python3
"""`p3fes_field.py calcalls` checks script ids against calendar group numbers and entry codes."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def table(group, code):
    rows = [(1,) + (0xFFFFFFFF,) * 7, ((5 << 16) | 4, 1, 0xFFFFFFFF, group, 0, 0, 0, 0),
            (0xFFFF, 0, 0, 0, 0xFFFFFFFF, 0, 0, 0), (0x50000, code, 7, 0xFFFFFFFF, 0, 0, 0, 0), (0xFFFF, 0, 0, 0, 0xFFFFFFFF, 0, 0, 0)]
    return b''.join(struct.pack('<8I', *r) for r in rows)
with tempfile.TemporaryDirectory() as t:
    for n, g, c in ((1, 105, 206), (2, 110, 157)):
        name = 'F%03d_001' % n
        for root in ('s', 'f'):
            os.makedirs(os.path.join(t, root, name + '.PAC.d'))
        open(os.path.join(t, 'f', name + '.PAC.d', 'n%03d_001.bin' % n), 'wb').write(table(g, c))
        open(os.path.join(t, 's', name + '.PAC.d', 'a.txt'), 'w').write('field_357(%d, %d)\nfield_313(5, %d)\n' % (n, g, c))
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'calcalls', os.path.join(t, 's'), os.path.join(t, 'f'), '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert '357 id is a group of field F' in txt and 'field_357(1, 105)' in txt, txt
print('ok   calcalls ties script ids to calendar groups and codes')
