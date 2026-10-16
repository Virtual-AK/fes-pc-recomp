#!/usr/bin/env python3
"""`p3fes_field.py doorwhere` finds script ids in the small field files."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
with tempfile.TemporaryDirectory() as t:
    for f, idv in ((5, 10241), (6, 10242)):
        sd = os.path.join(t, 's', 'F%03d_001.PAC.d' % f); os.makedirs(sd)
        open(os.path.join(sd, 'x.txt'), 'w').write("proc a:\n field_137(%d, 0, 0, 0, 1)\n" % idv)
        fd = os.path.join(t, 'd', 'F%03d_001.PAC.d' % f); os.makedirs(fd)
        open(os.path.join(fd, 'h001.bin'), 'wb').write(struct.pack('<8I', 1, 2, 3, 4, idv, 6, 7, 8))
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'doorwhere', os.path.join(t, 's'), os.path.join(t, 'd'), '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert '.bin  u32  own     2  control     0' in txt, txt
print('ok   doorwhere finds ids in small files')
