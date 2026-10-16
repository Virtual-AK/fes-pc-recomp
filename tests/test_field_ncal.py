#!/usr/bin/env python3
"""`p3fes_field.py ncal` reads the n###_###.bin tables as calendars (dates and groups), as seen in n006_002.bin."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
dates = [(4, 5, 1, 1), (4, 21, 1, 2), (9, 25, 1, 21)]
rows = [(len(dates),) + (0xFFFFFFFF,) * 7]
for m, d, t, g in dates:
    rows.append(((d << 16) | m, t, 0xFFFFFFFF, g, 0, 0, 0, 0))
rows += [(0, 0, 0xFFFFFFFF, 0xFFFFFFFF, 0xA0F, 0, 0, 0), (0xFFFF, 0, 0, 0, 0xFFFFFFFF, 0, 0, 0),
         (0x50000, 7651, 6, 0xFFFFFFFF, 0xA0F, 0, 0, 0), (0x50001, 6251, 27, 0xFFFFFFFF, 0xA0F, 0, 0, 0),
         (0xFFFF, 0, 0, 0, 0xFFFFFFFF, 0, 0, 0)]
with tempfile.TemporaryDirectory() as t:
    open(os.path.join(t, 'n006_002.bin'), 'wb').write(b''.join(struct.pack('<8I', *r) for r in rows))
    r = subprocess.run([sys.executable, '-I', TOOL, 'ncal', t, '-o', os.path.join(t, 'o.txt')], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(os.path.join(t, 'o.txt')).read()
    assert 'valid month 1-12 and day 1-31: 3, invalid: 0' in txt and '9/25:1->g21' in txt and 'group 1: 0 7651 6 0xA0F' in txt, txt
print('ok   ncal reads the n*.bin tables as calendars')
