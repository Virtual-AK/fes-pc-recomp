#!/usr/bin/env python3
"""`p3fes_field.py doornorec` lists door procs and whether a door record exists for them."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
rec = [0xFFFFFFFF, 0x0D0401, 0, 0, 10241, 0x1234, 0, 0, 0, 0, 0]
with tempfile.TemporaryDirectory() as t:
    f = os.path.join(t, 'fields', 'F006_003.PAC.d'); os.makedirs(f)
    open(os.path.join(f, 'h006_003.bin'), 'wb').write(struct.pack('<11I', *rec))
    for sc in (3, 4):
        s = os.path.join(t, 'scripts', 'F006_%03d.PAC.d' % sc); os.makedirs(s)
        open(os.path.join(s, 'x.bf.script.txt'), 'w').write('proc homeroom_r:\n  field_137(10241, 1, 0, 1)\n  field_33(6, 3, 1, 0)\nproc exit_gate:\n  field_137(10250, 0, 0, 1)\n  field_33(5, 1, 2, 0)\nproc plain:\n  field_33(6, 3, 0, 0)\n')
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'doornorec', os.path.join(t, 'scripts'), os.path.join(t, 'fields'), '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    a = open(out).read()
    assert a.startswith('2 distinct door procs') and 'with a record in their field' in a and 'leaving their field: 1, of which with a record: 0' in a, a
    assert 'homeroom_r' in a and 'label 0xd word5 0x1234' in a and 'scenes 3,4' in a, a
    assert 'exit_gate' in a and 'NO record' in a and 'plain' not in a.split(chr(10), 2)[2], a
print('ok   doornorec lists door procs with and without records')
