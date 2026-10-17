#!/usr/bin/env python3
"""
p3fes_contact.py - turn the test run's frame pictures (frame_NNNNN.ppm) into a few contact sheets (PNG), so many
frames can be looked at, or sent, as one picture. Each frame is shrunk and labelled with its frame number.

Usage:  python3 p3fes_contact.py games/p3fes/shots -o sheet            (writes sheet_1.png, sheet_2.png, ...)
        options: --cols 4  --shrink 2  --per-sheet 12  --from-frame 15000  --step 2
Standard library only. It only READS the pictures. The pictures are game content: keep them and the sheets on
your own computer, never in the repository.
"""
import argparse
import os
import re
import struct
import sys
import zlib

DIGITS = {
    "0": ("111", "101", "101", "101", "111"), "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"), "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"), "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"), "7": ("111", "001", "001", "001", "001"),
    "8": ("111", "101", "111", "101", "111"), "9": ("111", "101", "111", "001", "111"),
}


def read_ppm(path):
    with open(path, "rb") as fh:
        data = fh.read()
    m = re.match(rb"P6\s+(\d+)\s+(\d+)\s+(\d+)\s", data)
    if not m:
        raise ValueError("not a binary PPM: " + path)
    w, h = int(m.group(1)), int(m.group(2))
    return w, h, data[m.end():m.end() + w * h * 3]


def shrink(w, h, px, k):
    nw, nh = w // k, h // k
    out = bytearray(nw * nh * 3)
    for y in range(nh):
        row = (y * k) * w * 3
        for x in range(nw):
            o = row + (x * k) * 3
            n = (y * nw + x) * 3
            out[n:n + 3] = px[o:o + 3]
    return nw, nh, out


def label(img, W, x0, y0, text, scale=3):
    for ci, ch in enumerate(text):
        g = DIGITS.get(ch)
        if not g:
            continue
        for r, line in enumerate(g):
            for c, bit in enumerate(line):
                if bit == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            x = x0 + (ci * 4 + c) * scale + dx
                            y = y0 + r * scale + dy
                            o = (y * W + x) * 3
                            if o + 3 <= len(img):
                                img[o:o + 3] = b"\xff\xff\x00"


def write_png(path, w, h, rgb):
    raw = b"".join(b"\x00" + bytes(rgb[y * w * 3:(y + 1) * w * 3]) for y in range(h))

    def chunk(tag, body):
        c = struct.pack(">I", len(body)) + tag + body
        return c + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
                 chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def sheets(folder, out, cols=4, k=2, per=12, first=0, step=1):
    files = sorted(f for f in os.listdir(folder) if re.match(r"frame_\d+\.ppm$", f))
    files = [f for f in files if int(re.sub(r"\D", "", f)) >= first][::max(1, step)]
    made = []
    for s in range(0, len(files), per):
        part = files[s:s + per]
        tiles = []
        for f in part:
            w, h, px = read_ppm(os.path.join(folder, f))
            nw, nh, small = shrink(w, h, px, k)
            tiles.append((f, nw, nh, small))
        tw = max(t[1] for t in tiles) + 4
        th = max(t[2] for t in tiles) + 4
        rows = (len(tiles) + cols - 1) // cols
        W, H = cols * tw, rows * th
        img = bytearray(W * H * 3)
        for i, (f, nw, nh, small) in enumerate(tiles):
            x0, y0 = (i % cols) * tw + 2, (i // cols) * th + 2
            for y in range(nh):
                o = ((y0 + y) * W + x0) * 3
                img[o:o + nw * 3] = small[y * nw * 3:(y + 1) * nw * 3]
            label(img, W, x0 + 4, y0 + 4, re.sub(r"\D", "", f).lstrip("0") or "0")
        path = "%s_%d.png" % (out, s // per + 1)
        write_png(path, W, H, img)
        made.append(path)
    return made


def main():
    ap = argparse.ArgumentParser(description="Contact sheets of the test run's frame pictures.")
    ap.add_argument("folder")
    ap.add_argument("-o", "--out", default="sheet")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--shrink", type=int, default=2)
    ap.add_argument("--per-sheet", type=int, default=12)
    ap.add_argument("--from-frame", type=int, default=0, help="skip frames before this number")
    ap.add_argument("--step", type=int, default=1, help="use every Nth frame only")
    a = ap.parse_args()
    made = sheets(a.folder, a.out, a.cols, a.shrink, a.per_sheet, a.from_frame, a.step)
    if not made:
        raise SystemExit("no frame_*.ppm files in " + a.folder)
    print("wrote: " + ", ".join(made))


if __name__ == "__main__":
    main()
