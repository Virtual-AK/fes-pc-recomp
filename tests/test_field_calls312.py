#!/usr/bin/env python3
"""`p3fes_field.py calls312` shows where the objects of field_312 calls come from and what follows."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
with tempfile.TemporaryDirectory() as t:
    d = os.path.join(t, 'F014_005.PAC.d'); os.makedirs(d)
    lines = ['   10   lvar2 = field_313(5, 130)', '   11   lvar3 = field_314(lvar2, 3)', '   12   field_312(lvar3, 18)',
             '   13   object_show?(lvar3, 1)', '   20   field_312(field_311(0), 2)', '   21   wait_frames(5)']
    open(os.path.join(d, 'f014.bf.script.txt'), 'w').write('\n'.join(lines) + '\n')
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'calls312', t, t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert 'n=18: 1  (created (314) 1)' in txt and 'n=2: 1  (party member (311) 1)' in txt and 'object_show?: 1' in txt, txt
print('ok   calls312 reports sources and following statements')
