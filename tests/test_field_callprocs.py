#!/usr/bin/env python3
"""`p3fes_field.py callprocs` lists calls with their proc."""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
with tempfile.TemporaryDirectory() as t:
    d = os.path.join(t, 'F006_001.PAC.d'); os.makedirs(d)
    open(os.path.join(d, 'f006.bf.script.txt'), 'w').write("      proc homeroom_l:\n 1   field_137(10242, 0, 0, 0, 1)\n 2   field_33(6, 3, 0, 0)\n      proc homeroom_r:\n 3   field_137(10241, 0, 0, 0, 1)\n")
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'callprocs', t, 'field_137', 'field_33', '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert '10242 -> f006:homeroom_l(0, 0, 0, 1)' in txt and '6 -> f006:homeroom_l(3, 0, 0)' in txt, txt
print('ok   callprocs lists calls with procs')
