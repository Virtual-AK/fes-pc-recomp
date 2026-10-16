#!/usr/bin/env python3
"""`p3fes_field.py variantargs` finds the script function whose argument is an .FBN variant file number."""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
with tempfile.TemporaryDirectory() as t:
    nums = {1: list(range(100, 120)), 2: list(range(120, 140))}
    for f, ns in nums.items():
        d = os.path.join(t, 'F%03d_001.PAC.d' % f); os.makedirs(d)
        for n in ns:
            open(os.path.join(d, 'f%03d_001_%03d.FBN' % (f, n)), 'wb').write(b'x')
        open(os.path.join(d, 'a.txt'), 'w').write('\\n'.join('   %d   variant_load?(%d, 1)' % (i, n) for i, n in enumerate(ns)).replace('\\\\n', '\\n') + '\\n')
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'variantargs', t, t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert 'variant_load?(0) | 40 | 40 | 0' in txt, txt
print('ok   variantargs finds the function that takes FBN variant numbers')
