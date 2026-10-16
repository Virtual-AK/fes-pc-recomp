#!/usr/bin/env python3
"""`p3fes_field.py fbndump` lists the non-zero words of .FBN records."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
with tempfile.TemporaryDirectory() as t:
    d = os.path.join(t, 'F006_003.PAC.d'); os.makedirs(d)
    r = [0] * 28; r[2] = 0xC00 + 60; r[20:23] = struct.unpack('<3I', struct.pack('<3f', 32.0, 3.0, 100.0)); r[24] = 77
    open(os.path.join(d, 'f006_003_110.FBN'), 'wb').write(struct.pack('<6I', 0x12345678, 0x10001, 1, 0x70, 0, 0x60) + struct.pack('<28I', *r))
    out = os.path.join(t, 'o.txt')
    p = subprocess.run([sys.executable, '-I', TOOL, 'fbndump', t, '6:3', '110', '-o', out], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    txt = open(out).read()
    assert 'slot 60' in txt and '+0x60  0000004D  77' in txt and '32.000' in txt, txt
print('ok   fbndump lists record words')
