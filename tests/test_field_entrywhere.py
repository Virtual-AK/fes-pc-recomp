#!/usr/bin/env python3
"""`p3fes_field.py entrywhere` lists section 1 records of a scene's .hbn and the calls and door records that name each entry."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
d = struct.pack('<2I', 0x45678901, 1) + b''.join(struct.pack('<II', c, 0x14) for c in [0, 2, 0, 0, 0, 0, 0, 0])
d = d.ljust(0x48, b'\0')
for i, (x, z) in enumerate([(100.0, 200.0), (-50.0, 10.0)]):
    d += struct.pack('<I4f', 0x3800 + i, x, 3.0, z, 180.0 * i)
rec = [0xFFFFFFFF, 0x0D0401, 0, (1 << 16) | 2, 10251, 0, 0, 0, 0, 0, 0]
with tempfile.TemporaryDirectory() as t:
    f = os.path.join(t, 'fields', 'F006_002.PAC.d'); os.makedirs(f)
    open(os.path.join(f, 'f006_002.HBN'), 'wb').write(d)
    open(os.path.join(f, 'h006_003.bin'), 'wb').write(struct.pack('<11I', *rec))
    s = os.path.join(t, 'scripts', 'F006_003.PAC.d'); os.makedirs(s)
    open(os.path.join(s, 'x.bf.script.txt'), 'w').write('proc gate_in:\n  field_33(6, 2, 1, 0)\nproc other:\n  field_33(6, 2, 0, 0)\n  field_33(7, 2, 1, 0)\n')
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'entrywhere', os.path.join(t, 'scripts'), os.path.join(t, 'fields'), '6:2', '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    a = open(out).read()
    assert 'entry 0: section 1 record: id 0x3800, x 100.0' in a, a
    assert 'entry 1: section 1 record: id 0x3801, x -50.0 y 3.0 z 10.0 angle 180.0' in a, a
    assert 'proc gate_in' in a and a.count('called from') == 2 and 'proc other' in a, a
    assert 'door id 10251' in a and 'label 0xd' in a, a
print('ok   entrywhere lists records, callers and door records')
