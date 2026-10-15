#!/usr/bin/env python3
"""
Builds a small SYNTHETIC test disc image (no game data) with the same kinds of
structures as the real game disc: a disc with a CVM archive that holds a container
file, an AFS archive, ADX audio and a TMX texture. Used by run_tests.py so that
the tools can be tested without anyone's game disc.

Usage:  python make_test_disc.py OUTPUT.iso
"""

import os
import sys
import struct

def rec(name, lba, size, is_dir=False):
    nb = name if isinstance(name, bytes) else name.encode()
    n = 33 + len(nb)
    if n % 2: n += 1
    r = bytearray(n)
    r[0] = n
    struct.pack_into('<I', r, 2, lba); struct.pack_into('>I', r, 6, lba)
    struct.pack_into('<I', r, 10, size); struct.pack_into('>I', r, 14, size)
    r[25] = 2 if is_dir else 0
    r[32] = len(nb)
    r[33:33+len(nb)] = nb
    return bytes(r)

def layout(tree, alloc):
    node = {"lba": alloc(1), "children": {}}
    for name, v in sorted(tree.items()):
        if isinstance(v, dict):
            node["children"][name] = ("dir", layout(v, alloc))
        else:
            node["children"][name] = ("file", alloc(max(1, (len(v) + 2047) // 2048)), v)
    return node

def put(sectors, lba, data):
    for i in range(0, len(data), 2048):
        sectors[lba + i // 2048] = data[i:i + 2048].ljust(2048, b'\0')

def write(node, parent_lba, sectors):
    recs = rec(b'\x00', node["lba"], 2048, True) + rec(b'\x01', parent_lba, 2048, True)
    for name, item in node["children"].items():
        if item[0] == "dir":
            child = item[1]
            recs += rec(name, child["lba"], 2048, True)
            write(child, node["lba"], sectors)
        else:
            _, lba, data = item
            recs += rec(name + ';1', lba, len(data))
            put(sectors, lba, data)
    put(sectors, node["lba"], recs)

def build_iso(tree):
    counter = [20]
    def alloc(n):
        l = counter[0]; counter[0] += n; return l
    root = layout(tree, alloc)
    sectors = {}
    write(root, root["lba"], sectors)
    pvd = bytearray(2048)
    pvd[0] = 1; pvd[1:6] = b'CD001'; pvd[6] = 1
    pvd[156:190] = rec(b'\x00', root["lba"], 2048, True)[:34].ljust(34, b'\0')
    sectors[16] = bytes(pvd)
    term = bytearray(2048); term[0] = 255; term[1:6] = b'CD001'; term[6] = 1
    sectors[17] = bytes(term)
    out = bytearray()
    for i in range(max(sectors) + 1):
        out += sectors.get(i, b'\0' * 2048)
    return bytes(out)



def container(entries, align=64):
    out = b""
    for name, data in entries:
        out += b"\0" * ((-len(out)) % align)
        out += name.encode().ljust(252, b"\0") + struct.pack("<I", len(data)) + data
    return out + b"\0" * 256


def afs(blobs):
    off, tbl, body = 0x800, b"", b""
    for b in blobs:
        tbl += struct.pack("<II", off + len(body), len(b))
        body += b + b"\0" * ((-len(b)) % 2048)
    names = b"".join(("v001_%03d.adx" % i).encode().ljust(32, b"\0") + b"\0" * 16 for i in range(len(blobs)))
    tbl += struct.pack("<II", off + len(body), len(names))
    return (b"AFS\0" + struct.pack("<I", len(blobs)) + tbl).ljust(off, b"\0") + body + names


def adx(channels=2, rate=24000, frames=40):
    total = frames * 32
    head = bytearray(32)
    head[0] = 0x80
    struct.pack_into(">H", head, 2, 28)          # copyright offset -> data starts at 32
    head[4], head[5], head[6], head[7] = 3, 18, 4, channels
    struct.pack_into(">II", head, 8, rate, total)
    struct.pack_into(">H", head, 16, 500)
    head[18] = 4
    body = b"".join(struct.pack(">H", 0x40) + bytes((i * 7 + j) & 0xFF for j in range(16))
                    for i in range(frames * channels))
    return bytes(head) + body


def tmx(width=32, height=32):
    h = bytearray(64)
    h[0] = 2
    h[8:12] = b"TMX0"
    h[16], h[17] = 1, 0
    struct.pack_into("<HH", h, 18, width, height)
    h[22] = 0x13
    pix = bytes((x + y) % 256 for y in range(height) for x in range(width))
    pal = b"".join(bytes((k, 255 - k, 128, 0x80)) for k in range(256))
    data = bytes(h) + pal + pix
    struct.pack_into("<I", data := bytearray(data), 4, len(data))
    return bytes(data)


def main():
    out = sys.argv[1]
    inner = build_iso({
        "MODEL": {"PACK": {"HERO.PAC": container([("hero.rmd", os.urandom(400)), ("hero.acx", os.urandom(90))])}},
        "BUSTUP": {"PORTRAIT.BIN": container([("portrait_a.tmx", tmx(32, 32)), ("portrait_b.tmx", tmx(16, 64))])},
        "SOUND": {"V001001.AFS": afs([adx(1, 24000, 20), adx(1, 24000, 30)])},
        "TABLE.BIN": b"\xff\0\0\0" + os.urandom(500),
    })
    cvm = b"CVMH" + b"\0" * (0x1800 - 4) + inner
    bgm_inner = build_iso({"01.ADX": adx(2, 48000, 60)})
    bgm = b"CVMH" + b"\0" * (0x1800 - 4) + bgm_inner
    cnf = b"BOOT2 = cdrom0:\\SLUS_000.00;1\r\nVER = 1.00\r\nVMODE = NTSC\r\n"
    with open(out, "wb") as f:
        f.write(build_iso({"SYSTEM.CNF": cnf, "DATA.CVM": cvm, "BGM.CVM": bgm}))
    print("Wrote", out)


if __name__ == "__main__":
    main()
