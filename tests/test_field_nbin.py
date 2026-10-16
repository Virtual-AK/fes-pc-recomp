#!/usr/bin/env python3
"""`p3fes_field.py nbin` reads the n###_###.bin tables as 0x20-byte records."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
with tempfile.TemporaryDirectory() as t:
    open(os.path.join(t, 'n006_001.bin'), 'wb').write(struct.pack('<16I', *([1] + [0xFFFFFFFF] * 7 + [21, 0, 0, 0, 0, 0, 0, 0])))
    r = subprocess.run([sys.executable, '-I', TOOL, 'nbin', t, '-o', os.path.join(t, 'o.txt')], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(os.path.join(t, 'o.txt')).read()
    assert '1 n*.bin files' in txt and 'Records: 2' in txt and '0020  00000015' in txt, txt
print('ok   nbin statistics of the n*.bin tables')
