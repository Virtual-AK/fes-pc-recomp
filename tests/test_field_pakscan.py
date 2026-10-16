#!/usr/bin/env python3
"""`p3fes_field.py pakscan` lists a container and reports headers hidden inside size-0 entries (none, once the unpacker handles fillers)."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
def entry(name, data):
    b = name.encode().ljust(252, b'\0') + struct.pack('<I', len(data)) + data
    return b + b'\0' * (-len(b) % 16)
A = entry('a.FBN', b'x' * 32)
stale = bytearray(240); stale[:6] = b'npc_00'
true_hdr = b'f006_006.CMR'.ljust(252, b'\0') + struct.pack('<I', 64) + b'C' * 64
true = bytes(stale) + true_hdr
true += b'\0' * (-len(true) % 16)
pak = A + true + entry('z.bin', b'y' * 16) + b'\0' * 256
with tempfile.TemporaryDirectory() as t:
    c = os.path.join(t, 'F006_006.PAC'); open(c, 'wb').write(pak)
    out = os.path.join(t, 'o.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'pakscan', c, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    a = open(out).read()
    # the unpacker now steps over the filler, so the real entry is found and no size-0 entry hides a header
    assert 'size-0 entries: 0, of which another valid header starts 16 to 256 bytes into them: 0' in a, a
    assert 'f006_006.CMR size 64' in a and 'npc_00' not in a, a
print('ok   pakscan reports no hidden headers once the unpacker skips fillers')
