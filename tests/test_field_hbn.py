#!/usr/bin/env python3
"""`p3fes_field.py hbn` reads the 8-section header of .hbn files and reports per-section statistics."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def hbn(n):
    d = struct.pack('<II', 0x45678901, 0x10003)
    counts = (n, 0x20, 0, 0x14, 0, 0x14, 0, 0x14, 0, 0x14, 0, 0x14, 0, 0x20, 0, 0x14)
    d += struct.pack('<16I', *counts)
    for k in range(n):
        d += struct.pack('<II6f', 0x3400 + k, 0xA80000FF, -1322.0, 5.73, -1800.0, 233.0, -535.0, -40.0)
    return d + b'draw_proc\0'
with tempfile.TemporaryDirectory() as t:
    for i, n in enumerate((2, 3)):
        d = os.path.join(t, 'F001_00%d.PAC.d' % i); os.makedirs(d)
        open(os.path.join(d, 'f001_00%d.hbn' % i), 'wb').write(hbn(n))
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'hbn', t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert '2 .hbn files; 2 fit the header rule' in txt and '0 | 2 | 5 | 0x20' in txt and 'draw_proc x2' in txt, txt
print('ok   hbn reports sections, words and strings')
