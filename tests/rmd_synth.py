#!/usr/bin/env python3
"""Synthetic RenderWare model builders shared by the skeleton and glTF tests."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_rmd.py')
V = 0x1C020037

def ch(t, p, ver=V):
    return struct.pack('<III', t, len(p), ver) + p

def frame(parent):
    return struct.pack('<12f', 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0) + struct.pack('<iI', parent, 0)

def ext(*plugins):
    return ch(3, b''.join(plugins))

def hanim(node_id, nodes=()):
    p = struct.pack('<3I', 0x100, node_id, len(nodes))
    if nodes:
        p += struct.pack('<2I', 0, 36) + b''.join(struct.pack('<3I', *n) for n in nodes)
    return ch(0x11E, p)

def name(s):
    return ch(0x253F2FE, s.encode() + b'\0')

def skin(nverts, nbones, prefix=0, extra=0, split=False):
    p = struct.pack('<4B', nbones, nbones, 4, 0) + bytes(range(nbones))
    p += b''.join(bytes([i % nbones, 0, 0, 0]) for i in range(nverts))
    p += b''.join(struct.pack('<4f', 1, 0, 0, 0) for _ in range(nverts))
    for b in range(nbones):
        p += b'\0' * prefix + struct.pack('<16f', 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    if split:      # split-skin data seen on a real character: counts, remap table, range pairs
        nr = 2
        p += struct.pack('<3I', 64, 1, nr) + bytes([0, 1, 0xFF][:nbones]) + bytes([0, 1, 1, 2])
    return ch(0x116, p + b'\0' * extra)

def model(prefix=0, extra=0, split=False, anim2=None, anim1=None, anim1_type=1):
    frames = [frame(-1), frame(0), frame(1)]
    flist = ch(0x0E, ch(1, struct.pack('<I', 3) + b''.join(frames)) +
               ext(name('Root'), hanim(0, [(0, 0, 0), (1, 1, 0), (2, 2, 0)])) + ext(name('Spine'), hanim(1)) + ext(name('Head'), hanim(2)))
    gdata = struct.pack('<IIII', 0x2, 1, 3, 1) + struct.pack('<4H', 1, 0, 0, 2)
    gdata += struct.pack('<4f2I', 0, 0, 0, 1, 1, 0) + b''.join(struct.pack('<3f', *v) for v in ((0, 0, 0), (1, 0, 0), (0, 1, 0)))
    mat = ch(7, ch(1, struct.pack('<IIII', 0, 0xFFFFFFFF, 0, 0)))
    geo = ch(0x0F, ch(1, gdata) + ch(8, ch(1, struct.pack('<Ii', 1, -1)) + mat) + ext(skin(3, 3, prefix, extra, split)))
    glist = ch(0x1A, ch(1, struct.pack('<I', 1)) + geo)
    atomic = ch(0x14, ch(1, struct.pack('<4I', 0, 0, 5, 0)))
    clump = ch(0x10, ch(1, struct.pack('<3I', 1, 0, 0)) + flist + glist + atomic)
    a1 = ch(0x1B, (struct.pack('<4If', 0x100, anim1_type, 4, 0, 1.5) + anim1) if anim1 is not None else (struct.pack('<4If', 0x100, 1, 2, 0, 1.5) + b'\0' * 72))
    a2 = ch(0x1B, struct.pack('<4If', 0x100, 2, 5, 0, 2.0) + (anim2 if anim2 is not None else b'\0' * (22 * 5 + 24)))
    return struct.pack('<III', 0xF0F000F0, 2, 0x40000000) + b'\0\0' + clump + a1 + a2

