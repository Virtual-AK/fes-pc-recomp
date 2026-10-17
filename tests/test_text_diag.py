#!/usr/bin/env python3
"""text diag: reports an out-of-order file and a size mismatch without printing text."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'tools')
sys.path.insert(0, TOOLS)
import p3fes_text as T

def bmd(order):
    blobs = [b'M%d' % i + bytes(22) + bytes(range(8)) for i in range(3)]
    f = {"msgs": [{"kind": "raw", "name": "M0", "type": 2, "blob": b} for b in blobs], "reloc": b"", "word": 0x20000, "gap": bytes(16), "ftype": 7}
    data, starts = T.build_bmd(f)
    if order:
        t = [struct.unpack_from('<II', data, 32 + 8 * i) for i in range(3)]
        t[0], t[1] = t[1], t[0]
        d = bytearray(data)
        for i, (a, b) in enumerate(t):
            struct.pack_into('<II', d, 32 + 8 * i, a, b)
        return bytes(d)
    return data

ok = True
with tempfile.TemporaryDirectory() as t:
    open(os.path.join(t, 'a.bmd'), 'wb').write(bmd(False))
    open(os.path.join(t, 'b.bmd'), 'wb').write(bmd(True))
    o = os.path.join(t, 'r.txt')
    r = subprocess.run([sys.executable, os.path.join(TOOLS, 'p3fes_text.py'), 'diag', t, 'a.bmd', 'b.bmd', '-o', o], capture_output=True, text=True)
    s = open(o).read() if os.path.exists(o) else ''
    ok = r.returncode == 0 and 'messages in file order: True' in s and 'messages in file order: False' in s and 'not at their file-order position: 2 of 3' in s
    print(r.stderr)
print('ok   text diag reports order and rebuild differences' if ok else 'FAIL text diag')
sys.exit(0 if ok else 1)
