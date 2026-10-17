#!/usr/bin/env python3
"""p3fes_filecalls scan: finds a path string, the function that loads it and its callers in a synthetic ELF."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'tools')
BASE = 0x100000

def build():
    string_addr = BASE + 0x100
    func = BASE + 0x40
    words = [0] * 0x80
    # function at 0x40: addiu sp,sp,-32 ; lui a0,hi ; addiu a0,a0,lo ; jr ra ; nop
    f = [0x27BDFFE0, (0x0F << 26) | (4 << 16) | (string_addr >> 16),
         (0x09 << 26) | (4 << 21) | (4 << 16) | (string_addr & 0xFFFF), 0x03E00008, 0]
    for k, w in enumerate(f):
        words[0x10 + k] = w
    # two callers: jal func
    words[0x00] = (3 << 26) | ((BASE + 0x40) >> 2 & 0x3FFFFFF)
    words[0x01] = (3 << 26) | ((BASE + 0x40) >> 2 & 0x3FFFFFF)
    body = bytearray(struct.pack('<%dI' % len(words), *words))
    body[0x100:0x100 + 16] = b'cdrom0:\\DATA.CVM\x00'
    hdr = bytearray(0x34); hdr[:4] = b'\x7fELF'
    struct.pack_into('<I', hdr, 0x1C, 0x34); struct.pack_into('<HH', hdr, 0x2A, 32, 1)
    ph = struct.pack('<8I', 1, 0x1000, BASE, BASE, len(body), len(body), 5, 0x1000)
    return bytes(hdr) + ph + bytes(0x1000 - 0x34 - 32) + bytes(body)

with tempfile.TemporaryDirectory() as t:
    exe = os.path.join(t, 'x.elf'); open(exe, 'wb').write(build())
    out = os.path.join(t, 'r.txt')
    r = subprocess.run([sys.executable, os.path.join(TOOLS, 'p3fes_filecalls.py'), 'scan', exe, '-o', out], capture_output=True, text=True)
    s = open(out).read() if os.path.exists(out) else ''
    ok = (r.returncode == 0 and '0x00100100   1  cdrom0:' in s and '0x00100040     72 bytes' not in s and
          '0x00100040' in s and '   2 callers  cdrom0:' in s)
    if not ok:
        print(r.stdout[-800:], r.stderr[-800:], s)
print('ok   filecalls finds file strings, the functions that load them and their callers' if ok else 'FAIL filecalls')
sys.exit(0 if ok else 1)
