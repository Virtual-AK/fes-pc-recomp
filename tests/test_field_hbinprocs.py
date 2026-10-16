#!/usr/bin/env python3
"""`p3fes_field.py hbinprocs` looks up h*.bin record numbers in the field script's procs."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def rec(w2, idv=0, w6=1):
    return struct.pack('<11I', 0xFFFFFFFF, 0x401, w2, 0, idv, 0xFFFFFFFF, w6, 0, 0, 0, 0)
with tempfile.TemporaryDirectory() as t:
    sd = os.path.join(t, 's', 'F006_001.PAC.d'); os.makedirs(sd)
    open(os.path.join(sd, 'f006.bf.script.txt'), 'w').write(chr(10).join(['proc init:', ' end', 'proc door_a:', ' end', 'proc comu_b:', ' end', '']))
    fd = os.path.join(t, 'd', 'F006_001.PAC.d'); os.makedirs(fd)
    open(os.path.join(fd, 'h006_001.bin'), 'wb').write(bytes(8) + rec(2) + rec(9))
    out = os.path.join(t, 'o.txt')
    p = subprocess.run([sys.executable, '-I', TOOL, 'hbinprocs', os.path.join(t, 's'), os.path.join(t, 'd'), '-o', out], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    txt = open(out).read()
    assert 'proc[2]=comu_b' in txt and 'proc[1]=door_a' in txt and 'below the proc count of the field script: 1' in txt, txt
print('ok   hbinprocs looks up proc names')
