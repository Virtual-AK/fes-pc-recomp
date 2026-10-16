#!/usr/bin/env python3
"""Synthetic test for `p3fes_rmd.py skeleton`: bones, skin weights and animation headers."""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rmd_synth import model
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_rmd.py')

def run(data, *extra):
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, 'M.RMD'); open(f, 'wb').write(data)
        r = subprocess.run([sys.executable, TOOL, 'skeleton', f, *extra], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

ok = True
for label, kw in (('split-skin tail (real)', {'split': True}), ('plain skin tail', {}), ('4-byte prefix per matrix', {'prefix': 4}), ('12 trailing bytes', {'extra': 12})):
    code, out = run(model(**kw))
    checks = [code == 0, 'skeleton root: frame 0' in out, 'name Spine' in out, '3 bones' in out,
              'weights sum to 1 on 3 of 3' in out, 'layout exact' in out, '3 of 3 matrices look sane' in out, ('split-skin data' in out) == bool(kw.get('split')),
              'type 1: 1 animations' in out, 'type 2: 1 animations' in out, 'sizes consistent' in out]
    good = all(checks)
    print('  %-26s %s' % (label, 'ok' if good else 'FAIL %s' % checks))
    if not good:
        print(out)
    ok &= good
code, out = run(model(split=True), '--detail')
det = code == 0 and 'best place for 3 consecutive bone matrices: offset +0, stride 64' in out and '3 of 3 look like matrices' in out and 'block after the keyframes' in out and 'fit of the first 3 keyframes' in out and 'translation as int16' in out
print('  %-26s %s' % ('--detail output', 'ok' if det else 'FAIL'))
if not det:
    print(out)
ok &= det
print('ok   skeleton command reads bones, skin weights and animation headers' if ok else 'FAIL skeleton command')
sys.exit(0 if ok else 1)
