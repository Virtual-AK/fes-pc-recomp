#!/usr/bin/env python3
"""`p3fes_field.py hbinw5` tabulates word 5 of the door records against the field of the file."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def rec(label, entry, scene, did, w5):
    return struct.pack('<11I', 0xFFFFFFFF, (label << 16) | 0x0401, 0, (entry << 16) | scene, did, w5, 4, 0, 0, 0, 0)
with tempfile.TemporaryDirectory() as t:
    f = os.path.join(t, 'F006_003.PAC.d'); os.makedirs(f)
    open(os.path.join(f, 'h006_003.bin'), 'wb').write(rec(0, 1, 3, 10241, 6) + rec(0, 0, 3, 10242, 7) + rec(0, 0, 0, 0, 5))
    open(os.path.join(f, 'h006_004.bin'), 'wb').write(rec(0x51, 0, 5, 10441, 0xFFFFFFFF))
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'hbinw5', t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    a = open(out).read()
    assert a.startswith('door records: 3; word 5 equals the field of the file: 1, is 0xFFFFFFFF: 1, other: 1'), a
    assert 'id 10242 entry 0 scene-word 3 word5 7' in a, a
print('ok   hbinw5 tabulates word 5')
