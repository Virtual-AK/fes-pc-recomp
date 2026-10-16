#!/usr/bin/env python3
"""`p3fes_field.py emptyfiles` tells empty entries (header size 0) from extraction gaps."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def entry(name, data):
    h = name.encode().ljust(252, b'\0') + struct.pack('<I', len(data))
    b = h + data
    return b + b'\0' * (-len(b) % 16)
pak = entry('a.FBN', b'x' * 40) + entry('SCR_1A_NPC001_01f006_003.HBN', b'') + entry('c.bin', b'y' * 16) + b'\0' * 256
with tempfile.TemporaryDirectory() as t:
    c = os.path.join(t, 'F006_003.FPC'); open(c, 'wb').write(pak)
    d = c + '.d'; os.makedirs(d)
    open(os.path.join(d, 'a.FBN'), 'wb').write(b'x' * 40)
    open(os.path.join(d, 'SCR_1A_NPC001_01f006_003.HBN'), 'wb').write(b'')
    open(os.path.join(d, 'c.bin'), 'wb').write(b'y' * 8)       # short: a gap
    open(os.path.join(d, 'stray.bin'), 'wb').write(b'')         # empty, not in the container
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'emptyfiles', t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    a = open(out).read()
    assert 'containers read: 1' in a and 'entries: 3' in a, a
    assert 'entries with header size 0: 1 (by type: .hbn 1)' in a, a
    assert 'differs from the header size or is missing: 1' in a and 'c.bin (header size 16, file on disk 8)' in a, a
    assert 'empty files on disk that no entry explains: 1' in a and 'stray.bin' in a, a
print('ok   emptyfiles separates real empties from gaps')
