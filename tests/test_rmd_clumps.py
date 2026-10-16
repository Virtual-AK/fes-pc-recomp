#!/usr/bin/env python3
"""export --all-clumps / --clump write one .obj per model of a file that holds several (field .RWS files do)."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rmd_synth import model
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_rmd.py')
d = model()
size = struct.unpack_from('<I', d, 14 + 4)[0]
clump = d[14:14 + 12 + size]
two = d[:14] + clump + clump + d[14 + 12 + size:]
with tempfile.TemporaryDirectory() as t:
    p = os.path.join(t, 'f.rws')
    open(p, 'wb').write(two)
    out = os.path.join(t, 'o')
    r = subprocess.run([sys.executable, '-I', TOOL, 'export', p, '-o', out, '--all-clumps', '--no-textures'], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    names = sorted(os.listdir(out))
    assert 'f.obj' in names and 'f_clump1.obj' in names, names
    r = subprocess.run([sys.executable, '-I', TOOL, 'export', p, '-o', out, '--clump', '5', '--no-textures'], capture_output=True, text=True)
    assert r.returncode != 0 or 'only 2 clump' in r.stdout + r.stderr, r.stdout + r.stderr
print('ok   export --all-clumps writes one .obj per model of a multi-model file')
