#!/usr/bin/env python3
"""`p3fes_text.py extract` must refuse to overwrite an existing text folder unless --overwrite is given."""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_text.py')
with tempfile.TemporaryDirectory() as d:
    src = os.path.join(d, 'extracted'); os.makedirs(src)
    out = os.path.join(d, 'extracted_text'); os.makedirs(out)
    mine = os.path.join(out, 'my_edit.bmd.txt')
    open(mine, 'w').write('my edited text')
    r = subprocess.run([sys.executable, '-I', TOOL, 'extract', src], capture_output=True, text=True)
    refused = r.returncode != 0 and 'already has text files' in (r.stdout + r.stderr)
    kept = open(mine).read() == 'my edited text'
    r2 = subprocess.run([sys.executable, '-I', TOOL, 'extract', src, '--overwrite'], capture_output=True, text=True)
    allowed = 'already has text files' not in (r2.stdout + r2.stderr)
    ok = refused and kept and allowed
    if not ok:
        print(r.stdout, r.stderr, r2.stdout, r2.stderr)
    print('ok   text extract refuses to overwrite edited text unless --overwrite' if ok else 'FAIL text overwrite guard')
    sys.exit(0 if ok else 1)
