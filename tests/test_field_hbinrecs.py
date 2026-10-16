#!/usr/bin/env python3
"""`p3fes_field.py hbinrecs` decodes door records of h*.bin and joins them with scripts."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def rec(n, w2, w3, idv):
    return struct.pack('<11I', 0xFFFFFFFF, (n << 16) | 0x401, w2, w3, idv, 6, 4, 0, 0, 0, 0)
with tempfile.TemporaryDirectory() as t:
    sd = os.path.join(t, 's', 'F006_003.PAC.d'); os.makedirs(sd)
    open(os.path.join(sd, 'f006.bf.script.txt'), 'w').write(chr(10).join(['proc a:', ' field_137(10241, 1, 0, 0, 1)', ' field_33(6, 3, 1, 0)', '']))
    fd = os.path.join(t, 'd', 'F006_003.PAC.d'); os.makedirs(fd)
    open(os.path.join(fd, 'h006_003.bin'), 'wb').write(bytes(8) + rec(0, 0x0006FFFF, 0x00010004, 10241) + rec(1, 0x0006FFFF, 0x00000004, 10242))
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'hbinrecs', os.path.join(t, 's'), os.path.join(t, 'd'), '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert 'own 1 of 1' in txt and '0x2C: 1' in txt, txt
print('ok   hbinrecs decodes door records')
