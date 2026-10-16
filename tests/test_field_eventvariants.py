#!/usr/bin/env python3
"""`p3fes_field.py eventvariants` tests event steps against variant files."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
with tempfile.TemporaryDirectory() as t:
    sd = os.path.join(t, 's', 'F006_001.PAC.d'); os.makedirs(sd)
    open(os.path.join(sd, 'f006.bf.script.txt'), 'w').write(chr(10).join(['proc a:', ' event_ctrl?(540, 112, 0)', ' field_33(6, 3, 0, 0)', '']))
    fd = os.path.join(t, 'd', 'F006_003.PAC.d'); os.makedirs(fd)
    for sc, no in ((3, 112), (3, 0), (4, 0)):
        open(os.path.join(fd, 'f006_%03d_%03d.FBN' % (sc, no)), 'wb').write(struct.pack('<6I', 0x12345678, 0x10001, 0, 0x70, 0, 0x60))
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'eventvariants', os.path.join(t, 's'), os.path.join(t, 'd'), '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert 'own 1 of 1' in txt and 'the field) 0 of 1' in txt, txt
print('ok   eventvariants tests steps against variants')
