#!/usr/bin/env python3
"""`p3fes_field.py warpcalls` checks the third number of field_33 against .FBN file names of the destination scene."""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
with tempfile.TemporaryDirectory() as t:
    d = os.path.join(t, 'F014_003.PAC.d'); os.makedirs(d)
    for name in ('f014_003_002.FBN', 'f014_004_005.FBN'):
        open(os.path.join(d, name), 'wb').write(b'x' * 24)
    s = os.path.join(t, 's', 'F014_001.PAC.d'); os.makedirs(s)
    open(os.path.join(s, 'a.txt'), 'w').write('   446   field_33(14, 3, 2, 0)\\n   447   field_33(14, 4, 5, 0)\\n   448   field_33(14, 4, 9, 0)\\n'.replace('\\\\n', '\\n'))
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'warpcalls', os.path.join(t, 's'), t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert 'destination: 2 of 3' in txt, txt
print('ok   warpcalls ties field_33 numbers to FBN file names')
