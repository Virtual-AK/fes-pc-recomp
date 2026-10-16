#!/usr/bin/env python3
"""`p3fes_field.py datecheck` compares the date of a calendar group with the date_in_range before a field_357 call."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def table(day, month, group):
    rows = [(1,) + (0xFFFFFFFF,) * 7, ((day << 16) | month, 1, 0xFFFFFFFF, group, 0, 0, 0, 0),
            (0xFFFF, 0, 0, 0, 0xFFFFFFFF, 0, 0, 0)]
    return b''.join(struct.pack('<8I', *r) for r in rows)
with tempfile.TemporaryDirectory() as t:
    for root in ('s', 'f'):
        os.makedirs(os.path.join(t, root, 'F006_001.PAC.d'))
    open(os.path.join(t, 'f', 'F006_001.PAC.d', 'n006_001.bin'), 'wb').write(table(26, 4, 3))
    open(os.path.join(t, 's', 'F006_001.PAC.d', 'f006.bf.script.txt'), 'w').write(
        '  if (date_in_range?(4, 6, 4, 26) == 1):\n  lvar0 = field_357(6, 403)\n  lvar0 = field_357(6, 103)\n')
    open(os.path.join(t, 's', 'F006_001.PAC.d', 'g.txt'), 'w').write('  if (field_132(4, 6, 4, 26) == 1):\n  lvar0 = field_357(6, 403)\n')
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'datecheck', os.path.join(t, 's'), os.path.join(t, 'f'), '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert txt.count('-> inside') == 3 and 'group date inside the range' in txt and 'tested' in txt and '-> inside' in txt, txt
print('ok   datecheck compares group dates with date_in_range')
