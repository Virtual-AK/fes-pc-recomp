#!/usr/bin/env python3
"""`p3fes_field.py entrycount` compares entry numbers with .hbn section sizes."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def hbn(counts):
    d = struct.pack('<II', 0x45678901, 1) + b''.join(struct.pack('<II', c, 0x14) for c in counts) + bytes(0)
    for k, c in enumerate(counts):
        for r in range(c):
            d += struct.pack('<5I', (k << 12) + r, 0, 0, 0, 0)
    return d
with tempfile.TemporaryDirectory() as t:
    sd = os.path.join(t, 's', 'F006_001.PAC.d'); os.makedirs(sd)
    lines = ['proc a:']
    for sc in range(3, 9):
        lines += [' field_33(6, %d, 0, 0)' % sc, ' field_33(6, %d, 1, 0)' % sc]
    open(os.path.join(sd, 'f006.bf.script.txt'), 'w').write(chr(10).join(lines + ['']))
    fd = os.path.join(t, 'd', 'F006_001.PAC.d'); os.makedirs(fd)
    for sc in range(3, 9):
        open(os.path.join(fd, 'f006_%03d.hbn' % sc), 'wb').write(hbn([0, 2, 5, 0, 0, 0, 0, 0]))
    out = os.path.join(t, 'o.txt')
    p = subprocess.run([sys.executable, '-I', TOOL, 'entrycount', os.path.join(t, 's'), os.path.join(t, 'd'), '-o', out], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    txt = open(out).read()
    assert 's1 6/' in txt and 'Scenes with entries and an .hbn: 6' in txt, txt
print('ok   entrycount compares entries with sections')
