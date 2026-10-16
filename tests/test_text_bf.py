#!/usr/bin/env python3
"""Messages inside a .BF script: extract, repack unchanged, and rebuild the script around a longer message section."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'tools')
sys.path.insert(0, TOOLS)
import p3fes_text as T

def bmd(blob):
    f = {"msgs": [{"kind": "raw", "name": "M0", "type": 2, "blob": blob}], "reloc": b"", "word": 0x20000, "gap": bytes(16), "ftype": 7}
    return T.build_bmd(f)[0]

def script(msg):
    secs_data = [bytes(64), bytes(32), struct.pack('<4I', 7, 0, 0, 9), msg, b'S' * 20]
    kinds = [0, 1, 2, 3, 4]
    esz = [32, 32, 4, 1, 1]
    cnt = [2, 1, 4, len(msg), 20]
    start = 0x20 + 16 * 5
    table, body = b'', b''
    for k, e, c, dta in zip(kinds, esz, cnt, secs_data):
        table += struct.pack('<4I', k, e, c, start + len(body)); body += dta
    last = start + len(body) - 20
    return struct.pack('<2I4s5I', 0, last, b'FLW0', 0, 5, 1, 0, 0)[:0x20] + table + body

NM = b'M0'.ljust(24, b'\0')
old, new = bmd(NM + bytes(range(40))), bmd(NM + bytes(range(40)) * 3)
sc = script(old)
ok = T.message_bytes('x.bf', sc) == old
sc2 = T.put_message_bytes('x.bf', sc, new)
secs = T.bf_sections(sc2)
ok = ok and T.message_bytes('x.bf', sc2) == new and secs is not None and [x[0] for x in secs] == [0, 1, 2, 3, 4]
last = secs[4]
ok = ok and sc2[last[3]:last[3] + 20] == b'S' * 20 and struct.unpack_from('<I', sc2, 4)[0] == last[3] and len(sc2) == last[3] + 20
ok = ok and T.put_message_bytes('x.BMD', old, new) == new
with tempfile.TemporaryDirectory() as t:
    src = os.path.join(t, 'ex', 'A.PAC.d'); os.makedirs(src)
    open(os.path.join(src, 's.bf'), 'wb').write(sc)
    out = os.path.join(t, 'txt')
    r = subprocess.run([sys.executable, os.path.join(TOOLS, 'p3fes_text.py'), 'extract', os.path.join(t, 'ex'), '-o', out], capture_output=True, text=True)
    ok = ok and r.returncode == 0 and os.path.exists(os.path.join(out, 'A.PAC.d', 's.bf.txt'))
    mod = os.path.join(t, 'mod')
    r2 = subprocess.run([sys.executable, os.path.join(TOOLS, 'p3fes_text.py'), 'repack', out, os.path.join(t, 'ex'), '-o', mod], capture_output=True, text=True)
    ok = ok and r2.returncode == 0 and 'unchanged: 1' in r2.stdout
    print(r.stderr, r2.stderr)
print('ok   text in .BF scripts extracts and the script rebuilds around a new message section' if ok else 'FAIL text in .BF scripts')
sys.exit(0 if ok else 1)
