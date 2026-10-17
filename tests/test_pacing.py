#!/usr/bin/env python3
"""p3fes_pacing scan: finds a WaitSema wrapper, a GS CSR read, a loop around a call and a 1/60 constant in a synthetic ELF."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'tools')
BASE = 0x100000

def jal(a): return (3 << 26) | ((a >> 2) & 0x3FFFFFF)

def build():
    words = [0] * 0x100
    # wrapper at 0x80: li v1,-0x44 ; syscall ; jr ra ; nop   (WaitSema)
    words[0x20:0x24] = [0x2403FFBC, 0x0000000C, 0x03E00008, 0]
    # vsync function at 0xA0: addiu sp ; lui v0,0x1200 ; lw v1,0x1000(v0) ; jal wrapper ; jr ra
    words[0x28:0x2D] = [0x27BDFFE0, 0x3C021200, 0x8C431000, jal(BASE + 0x80), 0x03E00008]
    # caller at 0xD0: addiu sp ; jal vsync (loop top) ; nop ; beq zero,zero,-3 (back to jal) ; nop
    words[0x34:0x39] = [0x27BDFFE0, jal(BASE + 0xA0), 0, 0x1000FFFD, 0]
    # constant 1/60 at 0xF0: lui v0,0x3C88 ; ori v0,v0,0x8889
    words[0x3C:0x3E] = [0x3C023C88, 0x34428889]
    body = bytearray(struct.pack('<%dI' % len(words), *words))
    body[0x200:0x20D] = b'wait vsync ok\x00'
    hdr = bytearray(0x34); hdr[:4] = b'\x7fELF'
    struct.pack_into('<I', hdr, 0x1C, 0x34); struct.pack_into('<HH', hdr, 0x2A, 32, 1)
    ph = struct.pack('<8I', 1, 0x1000, BASE, BASE, len(body), len(body), 5, 0x1000)
    return bytes(hdr) + ph + bytes(0x1000 - 0x34 - 32) + bytes(body)

with tempfile.TemporaryDirectory() as t:
    exe = os.path.join(t, 'x.elf'); open(exe, 'wb').write(build())
    out = os.path.join(t, 'r.txt')
    r = subprocess.run([sys.executable, os.path.join(TOOLS, 'p3fes_pacing.py'), 'scan', exe, '-o', out], capture_output=True, text=True)
    s = open(out).read() if os.path.exists(out) else ''
    ok = (r.returncode == 0 and 'WaitSema' in s and 'GS CSR (sync flag)' in s and 'IN A LOOP' in s and
          '1/60 x1' in s and 'wait vsync ok' in s)
    if not ok:
        print(r.stdout[-800:], r.stderr[-800:], s)
print('ok   pacing finds sync waits, loops around them and frame-time constants' if ok else 'FAIL pacing')
sys.exit(0 if ok else 1)
