#!/usr/bin/env python3
"""The sound sequence survey finds .BED files and BED4 magic and writes a report."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_bed.py')
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, 'A', 'x.PAC.d'))
    for i in range(3):
        body = b'BED4' + struct.pack('<4I', 64 + i, 0x20, 100 + i, 7) + bytes(48 + 4 * i)
        open(os.path.join(d, 'A', 'x.PAC.d', 'S%d.BED' % i), 'wb').write(body)
    open(os.path.join(d, 'A', 'other.RMD'), 'wb').write(b'\xf0\x00\xf0\xf0' + bytes(20))
    rep = os.path.join(d, 'rep.txt')
    r = subprocess.run([sys.executable, TOOL, 'survey', d, '-o', rep], capture_output=True, text=True)
    t = open(rep).read() if os.path.exists(rep) else ''
    ok = r.returncode == 0 and '3 sequence files found' in t and 'BED4' in t and 'w00' in t
    h = subprocess.run([sys.executable, TOOL, 'hex', os.path.join(d, 'A', 'x.PAC.d', 'S0.BED')], capture_output=True, text=True)
    ok = ok and h.returncode == 0 and '32-bit words' in h.stdout
    se = b''.join(struct.pack('<252sI', n, len(b)) + b + bytes(-len(b) % 16) for n, b in ((b'174.hd', b'\x01' * 40), (b'174.bd', b'\x02' * 100)))
    open(os.path.join(d, 'A', '174.SE'), 'wb').write(se + bytes(256))
    sp = subprocess.run([sys.executable, TOOL, 'split', d, '-o', os.path.join(d, 'se.txt')], capture_output=True, text=True)
    ok = ok and sp.returncode == 0 and os.path.exists(os.path.join(d, 'A', '174.SE.d', '174.bd')) and '.hd' in open(os.path.join(d, 'se.txt')).read()
    sm = subprocess.run([sys.executable, TOOL, 'samples', d, '-o', os.path.join(d, 'sm.txt')], capture_output=True, text=True)
    ok = ok and sm.returncode == 0 and 'BED4 samples (3 files)' in open(os.path.join(d, 'sm.txt')).read()
    print(r.stderr, sp.stderr, sm.stderr)
print('ok   sound sequence survey reports BED files' if ok else 'FAIL sound sequence survey')
sys.exit(0 if ok else 1)
