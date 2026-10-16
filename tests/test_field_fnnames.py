#!/usr/bin/env python3
"""The field tools find calls whether the script listing prints a function by its number name (field_33) or by the name in script_names.txt."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
names = {}
for ln in open(os.path.join(os.path.dirname(HERE), 'tools', 'script_names.txt'), encoding='utf-8'):
    t = ln.split('#')[0].split()
    if len(t) >= 2 and t[0].isdigit():
        names[int(t[0])] = t[1]
assert names.get(33) and names.get(137), 'script_names.txt must name functions 33 and 137 for this test'
def run(*a):
    r = subprocess.run([sys.executable, '-I', TOOL] + list(a), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
for label, f33, f137 in (('number names', 'field_33', 'field_137'), ('script_names.txt names', names[33], names[137])):
    with tempfile.TemporaryDirectory() as t:
        s = os.path.join(t, 'scripts', 'F006_003.PAC.d'); os.makedirs(s)
        open(os.path.join(s, 'x.bf.script.txt'), 'w').write('proc homeroom_r:\n  %s(10241, 1, 0, 1)\n  %s(6, 3, 1, 0)\n' % (f137, f33))
        f = os.path.join(t, 'fields', 'F006_003.PAC.d'); os.makedirs(f)
        open(os.path.join(f, 'h006_003.bin'), 'wb').write(b'\0' * 8)
        out = os.path.join(t, 'dn.txt'); run('doornorec', os.path.join(t, 'scripts'), os.path.join(t, 'fields'), '-o', out)
        a = open(out).read(); assert a.startswith('1 distinct door procs'), (label, a)
        out = os.path.join(t, 'ew.txt'); run('entrywhere', os.path.join(t, 'scripts'), os.path.join(t, 'fields'), '6:3', '-o', out)
        a = open(out).read(); assert 'entry 1:' in a and 'proc homeroom_r' in a, (label, a)
        out = os.path.join(t, 'cp.txt'); run('callprocs', os.path.join(t, 'scripts'), 'field_137', 'field_33', '-o', out)
        a = open(out).read(); assert 'field_137: 1 distinct first arguments' in a and 'field_33: 1 distinct first arguments' in a, (label, a)
print('ok   field tools accept both number names and script_names.txt names')
