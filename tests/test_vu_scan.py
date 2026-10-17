#!/usr/bin/env python3
"""p3fes_vu scan: finds COP2 use, a VU microcode block with an end marker, and an MPG upload in a synthetic ELF."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'tools')

def build():
    words = []
    # 12 COP2 instructions (VADD-like, bit 25 set), one lqc2, one sqc2
    words += [(0x12 << 26) | (1 << 25) | k for k in range(12)]
    words += [(0x36 << 26) | 5, (0x3E << 26) | 6]
    words += [0] * 200                                       # gap
    # a microprogram: 16 units, lower NOP in each, E bit on unit 14
    prog = []
    for u in range(16):
        up = 0x000002FF | (0x40000000 if u == 14 else 0)
        prog += [0x8000033C, up]
    # MPG command in front of it: 16 units to VU address 0x20
    if len(words) % 2 == 0:
        words += [0]                                          # the program behind the command must be 8-byte aligned
    words += [(0x4A << 24) | (16 << 16) | 0x20]
    words += prog
    body = struct.pack('<%dI' % len(words), *words)
    ph = struct.pack('<8I', 1, 0x1000, 0x100000, 0x100000, len(body), len(body), 5, 0x1000)
    hdr = bytearray(0x34)
    hdr[:4] = b'\x7fELF'
    struct.pack_into('<I', hdr, 0x1C, 0x34)
    struct.pack_into('<HH', hdr, 0x2A, 32, 1)
    return bytes(hdr) + ph + bytes(0x1000 - 0x34 - 32) + body

with tempfile.TemporaryDirectory() as t:
    exe = os.path.join(t, 'x.elf'); open(exe, 'wb').write(build())
    out = os.path.join(t, 'r.txt')
    r = subprocess.run([sys.executable, os.path.join(TOOLS, 'p3fes_vu.py'), 'scan', exe, '-o', out], capture_output=True, text=True)
    s = open(out).read() if os.path.exists(out) else ''
    ok = (r.returncode == 0 and '14 instructions in 1 separate places' in s and
          '1 blocks, 128 bytes, 1 program-end markers' in s and '(MPG) found in data with plausible program bytes behind them: 1' in s
          and '16 units (128 bytes) to VU address 0x0020' in s and 'Programs (upload sequences): 1, of which 1 different' in s and 'Different block contents: 1 of 1' in s)
    if not ok:
        print(r.stdout[-1500:], r.stderr[-800:], s)
print('ok   vu scan finds macro-mode use, microcode blocks and MPG uploads' if ok else 'FAIL vu scan')
sys.exit(0 if ok else 1)
