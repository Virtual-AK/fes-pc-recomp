#!/usr/bin/env python3
"""p3fes_iop scan: reads module name, exports and imports of a synthetic .IRX and the module names in a synthetic executable."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'tools')
BASE = 0x100000

def irx():
    mod = struct.pack('<6I', 0, 0, 0, 100, 20, 8) + struct.pack('<H', 0x0102) + b'mymod\0'
    body = bytearray()
    body += struct.pack('<IIIII', 0x41c00000, 0, 0x0101, 0, 0)[:12] + b'mylib\0\0\0'
    body += struct.pack('<2I', 0x1000, 0x1010) + struct.pack('<I', 0)
    body += struct.pack('<III', 0x41e00000, 0, 0x0101) + b'sysclib\0'
    for k in range(3):
        body += struct.pack('<2I', 0x03E00008, 0x24000000 | (4 + k))
    body += struct.pack('<I', 0)
    off_mod = 52
    off_body = off_mod + len(mod)
    shoff = off_body + len(body)
    sh = bytes(40) + struct.pack('<10I', 0, 0x70000080, 0, 0, off_mod, len(mod), 0, 0, 0, 0)
    hdr = bytearray(52); hdr[:7] = b'\x7fELF\x01\x01\x01'
    struct.pack_into('<H', hdr, 16, 0xFF80); struct.pack_into('<I', hdr, 0x20, shoff); struct.pack_into('<HH', hdr, 0x2E, 40, 2)
    return bytes(hdr) + mod + bytes(body) + sh

def exe():
    s = b'cdrom0:\\LIB31\\MYMOD.IRX;1\0'
    code = [0x27BDFFE0, (0x0F << 26) | (4 << 16) | ((BASE + 0x100) >> 16), (0x09 << 26) | (4 << 21) | (4 << 16) | ((BASE + 0x100) & 0xFFFF), 0x03E00008, 0]
    body = bytearray(0x200)
    body[0:20] = struct.pack('<5I', *code)
    body[0x100:0x100 + len(s)] = s
    hdr = bytearray(0x34); hdr[:4] = b'\x7fELF'
    struct.pack_into('<I', hdr, 0x1C, 0x34); struct.pack_into('<HH', hdr, 0x2A, 32, 1)
    ph = struct.pack('<8I', 1, 0x1000, BASE, BASE, len(body), len(body), 5, 0x1000)
    return bytes(hdr) + ph + bytes(0x1000 - 0x34 - 32) + bytes(body)

with tempfile.TemporaryDirectory() as t:
    os.makedirs(os.path.join(t, 'LIB31'))
    open(os.path.join(t, 'LIB31', 'MYMOD.IRX'), 'wb').write(irx())
    open(os.path.join(t, 'SLUS_216.21'), 'wb').write(exe())
    out = os.path.join(t, 'r.txt')
    r = subprocess.run([sys.executable, os.path.join(TOOLS, 'p3fes_iop.py'), 'scan', t, '-o', out], capture_output=True, text=True)
    s = open(out).read() if os.path.exists(out) else ''
    ok = (r.returncode == 0 and "module 'mymod' version 1.2" in s and 'exports: mylib v1.1 (2)' in s and 'imports: sysclib (3)' in s
          and '1 places  cdrom0:\\LIB31\\MYMOD.IRX;1' in s and 'sysclib' in s.split('no module on the disc exports')[-1])
    if not ok:
        print(r.stdout[-800:], r.stderr[-800:], s)
print('ok   iop scan reads module names, exports, imports and the executable references' if ok else 'FAIL iop scan')
sys.exit(0 if ok else 1)
