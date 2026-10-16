#!/usr/bin/env python3
"""`p3fes_field.py variantcalls` lists call sites of a function whose argument may be an .FBN variant number."""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
with tempfile.TemporaryDirectory() as t:
    d = os.path.join(t, 'F001_001.PAC.d'); os.makedirs(d)
    open(os.path.join(d, 'f001_001_105.FBN'), 'wb').write(b'x')
    lines = ['   1   flag_set?(10)', '   2   event_ctrl?(302, 105, 0)', '   3   event_ctrl?(302, 77, 0)', '   4   end']
    open(os.path.join(d, 'a.txt'), 'w').write('\\n'.join(lines) + '\\n')
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'variantcalls', t, t, 'event_ctrl?:1', '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert '2 distinct (field, value) pairs of 50 and up; 1 are' in txt and 'matching: 1:105' in txt, txt
print('ok   variantcalls lists call sites and matches')
