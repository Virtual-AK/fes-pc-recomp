#!/usr/bin/env python3
"""
p3fes_ppm2png.py - turn raw picture files (PPM, as written by the runner for frames and texture dumps) into PNG files that
Windows can open. Usage:  python3 p3fes_ppm2png.py folder_or_files... [--out folder]
Each name.ppm becomes name.png next to it (or in --out). Standard library only. It only READS the pictures. The pictures are game
content: keep them on your own computer, never in the repository.
"""
import os
import re
import struct
import sys
import zlib


def read_ppm(path):
    with open(path, "rb") as fh:
        data = fh.read()
    m = re.match(rb"P6\s+(\d+)\s+(\d+)\s+(\d+)\s", data)
    if not m:
        raise ValueError("not a P6 PPM: " + path)
    w, h = int(m.group(1)), int(m.group(2))
    return w, h, data[m.end():m.end() + w * h * 3]


def write_png(path, w, h, rgb):
    raw = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(tag, body):
        c = struct.pack(">I", len(body)) + tag + body
        return c + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
                 chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def main(argv):
    out = None
    names = []
    i = 0
    while i < len(argv):
        if argv[i] == "--out" and i + 1 < len(argv):
            out = argv[i + 1]
            i += 2
            continue
        names.append(argv[i])
        i += 1
    files = []
    for n in names:
        if os.path.isdir(n):
            files += [os.path.join(n, f) for f in sorted(os.listdir(n)) if f.lower().endswith(".ppm")]
        else:
            files.append(n)
    if not files:
        print("no .ppm files given"); return 1
    if out:
        os.makedirs(out, exist_ok=True)
    for f in files:
        w, h, rgb = read_ppm(f)
        dest = os.path.join(out or os.path.dirname(f) or ".", os.path.splitext(os.path.basename(f))[0] + ".png")
        write_png(dest, w, h, rgb)
        print("wrote", dest, "(%dx%d)" % (w, h))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
