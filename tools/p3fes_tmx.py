#!/usr/bin/env python3
"""
p3fes_tmx.py - convert the game's .TMX textures to ordinary .PNG pictures.

Run this on the folder that p3fes_unpack.py made (with --containers, so the
textures inside the container files are there too). It finds every .TMX file,
converts it to a .PNG in a separate output folder, and can build an index.html
gallery page you open in your web browser to look through the pictures.

The .PNG files are copies of the game's own art. They are for your own use.
Never upload them anywhere, including to the project's GitHub repository.

It only READS the extracted folder. Standard library only, Python 3.8+.

Usage (from a Command Prompt in the folder that holds this script):
    py p3fes_tmx.py "C:\\p3fes\\extracted" --limit 40 --gallery
    py p3fes_tmx.py "C:\\p3fes\\extracted" -o "C:\\p3fes\\textures" --gallery

Options:
    -o FOLDER            where to write the pictures (default: <input>_png next to the input)
    --limit N            only convert the first N textures (good for a first look)
    --only TEXT          only textures whose path contains TEXT (repeatable), e.g. --only bust
    --palette MODE       "swizzle" (default) or "linear": how 256-colour palettes are ordered.
                         If the colours in the pictures look scrambled, try the other one.
                         "both" writes each picture twice (the second with _linear in its
                         name) so you can compare them side by side in the gallery.
    --pixels MODE        "linear" (default) or "gs" (the PS2's graphics-memory order), or "all" to
                         write every palette and pixel-order combination for comparison
    --inspect FILE       print header and palette statistics of one .tmx file (no pictures)
    --gallery            also write index.html in the output folder
"""

import argparse
import html
import os
import struct
import sys
import time
import zlib


class ToolError(Exception):
    pass


# --------------------------------------------------------------------------- TMX

PIXEL_BYTES = {0x00: 4.0, 0x01: 3.0, 0x02: 2.0, 0x13: 1.0, 0x14: 0.5}
PIXEL_NAMES = {0x00: "32-bit", 0x01: "24-bit", 0x02: "16-bit", 0x13: "8-bit palette", 0x14: "4-bit palette"}
HEADER_SIZE = 0x40


def palette_entry_bytes(fmt):
    return 2 if fmt == 0x02 else 4


def swizzle_index(i):
    """The PS2 stores 256-colour palettes with the middle two bits of the index swapped."""
    return (i & 0xE7) | ((i & 0x08) << 1) | ((i & 0x10) >> 1)


def read_palette(data, off, count, fmt, swizzle):
    size = palette_entry_bytes(fmt)
    raw = []
    for i in range(count):
        p = data[off + i * size: off + (i + 1) * size]
        if len(p) < size:
            p = b"\x00" * size
        if size == 4:
            raw.append((p[0], p[1], p[2], min(255, p[3] * 2)))
        else:
            v = p[0] | (p[1] << 8)
            raw.append(((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31,
                        ((v >> 10) & 31) * 255 // 31, 255 if v & 0x8000 else 0))
    if swizzle and count == 256:
        raw = [raw[swizzle_index(i)] for i in range(256)]
    return raw


def unswizzle8(buf, width, height):
    """Undo the PS2 graphics-memory ordering of an 8-bit texture (width must be a multiple of 16,
    height a multiple of 4)."""
    out = bytearray(width * height)
    for y in range(height):
        row_block = (y & ~0xF) * width
        swap = (((y + 2) >> 2) & 1) * 4
        pos_y = (((y & ~3) >> 1) + (y & 1)) & 7
        col_row = pos_y * width * 2
        yb = ((y >> 1) & 1)
        base = y * width
        for x in range(width):
            src = row_block + (x & ~0xF) * 2 + col_row + ((x + swap) & 7) * 4 + yb + ((x >> 2) & 2)
            out[base + x] = buf[src] if src < len(buf) else 0
    return bytes(out)


def decode_tmx(data, palette_mode="swizzle", pixel_mode="linear"):
    """Return (width, height, rgba_bytes, info) or raise ToolError."""
    if len(data) == 0:
        raise ToolError("empty file (0 bytes), nothing to convert")
    if len(data) < HEADER_SIZE or data[8:12] != b"TMX0":
        raise ToolError("not a TMX0 file")
    pal_count = data[16]
    pal_fmt = data[17]
    width, height = struct.unpack_from("<HH", data, 18)
    pix_fmt = data[22]
    mips = data[23]
    if pix_fmt not in PIXEL_BYTES:
        raise ToolError("unknown pixel format 0x%02X" % pix_fmt)
    if width == 0 or height == 0 or width * height > 4096 * 4096:
        raise ToolError("odd size %dx%d" % (width, height))
    pix_bytes = int(width * height * PIXEL_BYTES[pix_fmt])
    pal_entries = 256 if pix_fmt == 0x13 else 16 if pix_fmt == 0x14 else 0
    pal_bytes = pal_entries * palette_entry_bytes(pal_fmt)
    expected = HEADER_SIZE + pix_bytes + pal_bytes
    info = {"format": PIXEL_NAMES[pix_fmt], "width": width, "height": height,
            "mipmaps": mips, "size_matches": len(data) == expected, "expected_size": expected}
    if len(data) < expected:
        raise ToolError("file is shorter (%d) than the header says (%d)" % (len(data), expected))
    pal_off = HEADER_SIZE                       # the palette comes first,
    pix_off = HEADER_SIZE + pal_bytes           # then the pixels
    pix = data[pix_off: pix_off + pix_bytes]
    out = bytearray(width * height * 4)
    n = width * height
    if pix_fmt == 0x00:
        for i in range(n):
            o = i * 4
            out[o] = pix[o]; out[o + 1] = pix[o + 1]; out[o + 2] = pix[o + 2]
            out[o + 3] = min(255, pix[o + 3] * 2)
    elif pix_fmt == 0x01:
        for i in range(n):
            o = i * 4
            out[o:o + 3] = pix[i * 3:i * 3 + 3]
            out[o + 3] = 255
    elif pix_fmt == 0x02:
        for i in range(n):
            v = pix[i * 2] | (pix[i * 2 + 1] << 8)
            o = i * 4
            out[o] = (v & 31) * 255 // 31
            out[o + 1] = ((v >> 5) & 31) * 255 // 31
            out[o + 2] = ((v >> 10) & 31) * 255 // 31
            out[o + 3] = 255 if v & 0x8000 else 0
    else:
        if pixel_mode == "gs":
            if pix_fmt != 0x13 or width % 16 or height % 4:
                raise ToolError("gs pixel order is only supported for 8-bit textures with a size divisible by 16x4")
            pix = unswizzle8(pix, width, height)
        pal = read_palette(data, pal_off, pal_entries, pal_fmt,
                           palette_mode == "swizzle")
        table = [bytes(c) for c in pal]
        if pix_fmt == 0x13:
            for i in range(n):
                out[i * 4:i * 4 + 4] = table[pix[i]]
        else:
            for i in range(n):
                b = pix[i >> 1]
                idx = (b >> 4) if (i & 1) else (b & 15)
                out[i * 4:i * 4 + 4] = table[idx]
    return width, height, bytes(out), info


# --------------------------------------------------------------------------- PNG

def png_bytes(width, height, rgba):
    def chunk(tag, body):
        c = struct.pack(">I", len(body)) + tag + body
        return c + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
    rows = bytearray()
    stride = width * 4
    for y in range(height):
        rows.append(0)
        rows += rgba[y * stride:(y + 1) * stride]
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
            + chunk(b"IEND", b""))


# --------------------------------------------------------------------------- main

def inspect_tmx(path):
    """Print the header, palette and a pixel-value summary of one texture (statistics only)."""
    with open(path, "rb") as fh:
        data = fh.read()
    print("File:", os.path.basename(path), "size", len(data))
    print("Header (first 64 bytes):")
    for i in range(0, 64, 16):
        print("  %02X: %s" % (i, data[i:i + 16].hex(" ")))
    if len(data) < HEADER_SIZE or data[8:12] != b"TMX0":
        print("Not a TMX0 file.")
        return
    width, height = struct.unpack_from("<HH", data, 18)
    pix_fmt = data[22]
    print("Size %dx%d, pixel format 0x%02X, palettes %d, palette format %d, mipmaps %d"
          % (width, height, pix_fmt, data[16], data[17], data[23]))
    if pix_fmt != 0x13:
        print("(summary below is only for 8-bit textures)")
        return
    n = width * height
    pix = data[HEADER_SIZE + 1024:HEADER_SIZE + 1024 + n]
    counts = {}
    for b in pix:
        counts[b] = counts.get(b, 0) + 1
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:16]
    print("Distinct pixel values: %d. Most common (value:count):" % len(counts))
    print("  " + "  ".join("%02X:%d" % kv for kv in top))
    print("Palette entries (R G B A), 16 per line, in file order:")
    pal = data[HEADER_SIZE:HEADER_SIZE + 1024]
    for i in range(0, 256, 8):
        row = []
        for k in range(i, i + 8):
            e = pal[k * 4:k * 4 + 4]
            row.append("%02X%02X%02X/%02X" % tuple(e) if len(e) == 4 else "--")
        print("  %3d: %s" % (i, " ".join(row)))
    print("First pixel row (first 48 values):", pix[:48].hex(" "))


def find_tmx(root, only):
    found = []
    for dirpath, _, names in os.walk(root):
        for n in names:
            if n.lower().endswith(".tmx"):
                p = os.path.join(dirpath, n)
                rel = os.path.relpath(p, root)
                if not only or any(o.lower() in rel.lower() for o in only):
                    found.append(rel)
    found.sort(key=str.lower)
    return found


def write_gallery(out_dir, items):
    parts = ["<!doctype html><meta charset='utf-8'><title>Texture gallery</title>",
             "<style>body{font-family:sans-serif;background:#222;color:#ddd;margin:16px}"
             "h2{font-size:14px;margin:18px 0 6px;color:#9cf}"
             ".g{display:flex;flex-wrap:wrap;gap:8px}"
             ".c{background:#333;padding:4px;font-size:11px;width:160px;word-break:break-all}"
             ".c img{max-width:152px;max-height:152px;display:block;margin-bottom:3px;"
             "background:repeating-conic-gradient(#555 0 25%,#444 0 50%) 0 0/12px 12px;image-rendering:pixelated}"
             "</style><h1>Texture gallery</h1><p>For your own use only. Do not share these pictures.</p>"]
    folder = None
    for rel_png, label, w, h in items:
        d = os.path.dirname(rel_png)
        if d != folder:
            if folder is not None:
                parts.append("</div>")
            parts.append("<h2>%s</h2><div class='g'>" % html.escape(d or "(top level)"))
            folder = d
        src = html.escape(rel_png.replace(os.sep, "/"), quote=True)
        parts.append("<div class='c'><a href='%s'><img loading='lazy' src='%s'></a>%s<br>%dx%d</div>"
                     % (src, src, html.escape(label), w, h))
    if folder is not None:
        parts.append("</div>")
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))


def main():
    ap = argparse.ArgumentParser(description="Convert .TMX textures from an extracted folder to .PNG.")
    ap.add_argument("folder", help="the folder made by p3fes_unpack.py")
    ap.add_argument("-o", "--out", help="output folder")
    ap.add_argument("--limit", type=int, default=0, help="only convert the first N textures")
    ap.add_argument("--only", action="append", default=[], help="only paths containing this text")
    ap.add_argument("--palette", choices=("swizzle", "linear", "both"), default="swizzle")
    ap.add_argument("--gallery", action="store_true", help="write index.html")
    ap.add_argument("--pixels", choices=("linear", "gs", "all"), default="linear",
                    help='pixel order: "linear" (default), "gs" (PS2 memory order), or "all" '
                         '(write every palette/pixel combination for comparison)')
    ap.add_argument("--inspect", action="store_true",
                    help="instead of converting, print header and palette statistics of one .tmx file (give the file as the first argument)")
    args = ap.parse_args()

    if args.inspect:
        if not os.path.isfile(args.folder):
            sys.exit("Error: with --inspect, give the path of one .tmx file.")
        inspect_tmx(args.folder)
        return

    root = os.path.abspath(args.folder)
    if not os.path.isdir(root):
        sys.exit(f"Error: {root} is not a folder.")
    out_dir = os.path.abspath(args.out) if args.out else root.rstrip("\\/") + "_png"
    try:
        inside = os.path.commonpath([root, out_dir]) == root
    except ValueError:  # different drives
        inside = False
    if inside:
        sys.exit("Error: the output folder must not be inside the input folder.")
    files = find_tmx(root, args.only)
    if args.limit:
        files = files[:args.limit]
    if not files:
        sys.exit("No .TMX files found. Did you run p3fes_unpack.py with --containers?")
    print(f"Converting {len(files)} textures to {out_dir}")

    t0 = time.time()
    ok = 0
    bad = []
    mismatched = 0
    odd = []
    kinds = {}
    items = []
    os.makedirs(out_dir, exist_ok=True)
    for i, rel in enumerate(files):
        try:
            with open(os.path.join(root, rel), "rb") as fh:
                data = fh.read()
            if args.pixels == "all" or args.palette == "both":
                pals = ("swizzle", "linear") if args.palette == "both" or args.pixels == "all" else (args.palette,)
                pixs = ("linear", "gs") if args.pixels == "all" else (args.pixels,)
            else:
                pals, pixs = (args.palette,), (args.pixels,)
            variants = [(pm, px) for px in pixs for pm in pals]
            first = True
            for pm, px in variants:
                try:
                    w, h, rgba, info = decode_tmx(data, pm, px)
                except ToolError:
                    if first:
                        raise
                    continue
                if first:
                    if not info["size_matches"]:
                        mismatched += 1
                        odd.append((rel, "file is %d bytes, header says %d (%dx%d, %s)" % (
                            len(data), info["expected_size"], w, h, info["format"])))
                    kinds[info["format"]] = kinds.get(info["format"], 0) + 1
                if len(variants) > 1 and info["format"] != "8-bit palette" and not first:
                    continue              # palette and pixel order only matter for 8-bit textures
                suffix = "" if first else "_%s_pal_%s_px" % (pm, px)
                first = False
                rel_png = os.path.splitext(rel)[0] + suffix + ".png"
                dest = os.path.join(out_dir, rel_png)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as fh:
                    fh.write(png_bytes(w, h, rgba))
                items.append((rel_png, os.path.basename(rel) + suffix, w, h))
            ok += 1
        except (ToolError, OSError) as e:
            bad.append((rel, str(e)))
        if i % 100 == 0:
            sys.stderr.write(f"\r  {i}/{len(files)}")
            sys.stderr.flush()
    sys.stderr.write("\r" + " " * 30 + "\r")

    if args.gallery:
        write_gallery(out_dir, items)
    with open(os.path.join(out_dir, "problems.txt"), "w", encoding="utf-8") as fh:
        for rel, why in bad:
            fh.write(f"{rel}\tFAILED: {why}\n")
            try:
                with open(os.path.join(root, rel), "rb") as src:
                    head = src.read(64)
                    src.seek(0, 2)
                    fh.write("    size %d bytes, first 64 bytes: %s\n" % (src.tell(), head.hex(" ")))
            except OSError:
                pass
        for rel, why in odd:
            fh.write(f"{rel}\tODD SIZE (converted anyway): {why}\n")
    print("=" * 70)
    print(f"Converted {ok} of {len(files)} textures in {time.time() - t0:.0f}s")
    print("Formats: " + ", ".join(f"{k} x{v}" for k, v in sorted(kinds.items())))
    if mismatched:
        print(f"{mismatched} files had an unexpected size (converted anyway; listed in problems.txt)")
    if bad:
        print(f"{len(bad)} files could not be converted; see problems.txt. First few:")
        for rel, why in bad[:5]:
            print(f"  {rel}: {why}")
    if args.gallery:
        print("Open this page in your browser: " + os.path.join(out_dir, "index.html"))
    print("Reminder: these pictures are the game's own art. Keep them on your computer; never upload them.")


if __name__ == "__main__":
    main()
