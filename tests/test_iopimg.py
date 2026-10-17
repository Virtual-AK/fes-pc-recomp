#!/usr/bin/env python3
"""p3fes_iopimg scan: lists the entries of a synthetic ROM directory image."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'tools')

def ent(name, ext, size):
    return name.encode().ljust(10, b'\0') + struct.pack('<HI', ext, size)

files = [('RESET', 0, 16), ('ROMDIR', 0, 16 * 6), ('EXTINFO', 0, 16), ('SYSMEM', 8, 20), ('LOADCORE', 8, 40)]
img = bytearray()
directory = b''.join(ent(*f) for f in files) + b'\0' * 16
files[1] = ('ROMDIR', 0, len(directory))
directory = b''.join(ent(*f) for f in files) + b'\0' * 16
img += b'RESET\0\0\0\0\0' + b'\0' * 6          # RESET code area doubles as the directory start
reset = bytearray(16); reset[:10] = b'RESET\0\0\0\0\0'
body = bytes(reset) + directory
body += b'\0' * ((16 - len(body) % 16) % 16)
# directory sits right at the start of the image
body = directory + b'\0' * 64
with tempfile.TemporaryDirectory() as t:
    p = os.path.join(t, 'IOPRP310.IMG'); open(p, 'wb').write(body)
    out = os.path.join(t, 'r.txt')
    r = subprocess.run([sys.executable, os.path.join(TOOLS, 'p3fes_iopimg.py'), 'scan', t, '-o', out], capture_output=True, text=True)
    s = open(out).read() if os.path.exists(out) else ''
    ok = r.returncode == 0 and 'Directory entries: 5' in s and 'SYSMEM' in s and 'LOADCORE' in s and 'not an ELF' in s
    if not ok:
        print(r.stdout[-600:], r.stderr[-600:], s)
print('ok   iopimg lists the entries of a ROM directory image' if ok else 'FAIL iopimg')
sys.exit(0 if ok else 1)
