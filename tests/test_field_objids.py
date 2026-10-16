#!/usr/bin/env python3
"""`p3fes_field.py objids` compares script object ids with the numbers in model file names."""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
with tempfile.TemporaryDirectory() as t:
    os.makedirs(os.path.join(t, 's')); os.makedirs(os.path.join(t, 'm', 'NPC'))
    open(os.path.join(t, 's', 'a.script.txt'), 'w').write('x = field_313(5, 130)\ny = field_313(5, 131)\nz = field_357(-1, 0)\n')
    open(os.path.join(t, 'm', 'NPC', 'N00130.RMD'), 'wb').close()
    r = subprocess.run([sys.executable, '-I', TOOL, 'objids', os.path.join(t, 's'), os.path.join(t, 'm'), '-o', os.path.join(t, 'o.txt')], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(os.path.join(t, 'o.txt')).read()
    assert 'field_313(5, id): 2 distinct ids' in txt and '1 of 2 ids exist as a model number' in txt, txt
print('ok   objids compares script object ids with model file names')
