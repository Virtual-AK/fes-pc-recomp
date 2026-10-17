#!/usr/bin/env python3
"""Message files whose table is not in file order rebuild byte-identical; extra zero bytes before the pointer table are kept."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
import p3fes_text as T

def make(endpad=0):
    blobs = [(b'M%d' % i).ljust(24, b'\0') + bytes(range(8 * (i + 1))) for i in range(4)]
    f = {"msgs": [{"kind": "raw", "name": "M%d" % i, "type": 2, "blob": b} for i, b in enumerate(blobs)],
         "reloc": b"\x02", "word": 0x20000, "gap": bytes(16), "ftype": 7, "endpad": endpad}
    return T.build_bmd(f)[0]

def swap_table(data, a, b):
    d = bytearray(data)
    ea, eb = d[32 + 8 * a: 40 + 8 * a], d[32 + 8 * b: 40 + 8 * b]
    d[32 + 8 * a: 40 + 8 * a], d[32 + 8 * b: 40 + 8 * b] = eb, ea
    return bytes(d)

ok = True
plain = make()
loose = swap_table(plain, 0, 2)
f = T.parse_bmd(loose)
ok = ok and f["ordered"] is False and T.build_bmd(f)[0] == loose
# two entries sharing one message
shared = bytearray(plain)
shared[32 + 8 * 3: 40 + 8 * 3] = shared[32 + 8 * 1: 40 + 8 * 1]
shared = bytes(shared)
g = T.parse_bmd(shared)
ok = ok and T.build_bmd(g)[0] == shared
# extra zero bytes before the pointer table
padded = make(endpad=4)
h = T.parse_bmd(padded)
ok = ok and struct.unpack_from("<I", padded, 16)[0] == struct.unpack_from("<I", plain, 16)[0] + 4 and T.build_bmd(h)[0] == padded
# zero bytes after a dialog message are kept
def dlg(i):
    return {"kind": "dialog", "name": "D%d" % i, "type": 0, "speaker": 1, "pad": 0, "lines": [b"Hi" + bytes([i]) + b"\xf1\x04"], "tail": b""}
ff = {"msgs": [dlg(0), dlg(1)], "reloc": b"\x02", "word": 0x20000, "gap": bytes(16), "ftype": 7, "endpad": 0}
base = T.build_bmd(ff)[0]
ff["msgs"][0]["zpad"] = 4
padded0 = T.build_bmd(ff)[0]
g2 = T.parse_bmd(padded0)
ok = ok and len(padded0) == len(base) + 4 and g2["msgs"][0].get("zpad") == 4 and T.build_bmd(g2)[0] == padded0
print('ok   unordered message files and end padding rebuild byte-identical' if ok else 'FAIL unordered message files')
sys.exit(0 if ok else 1)
