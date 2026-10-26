#!/usr/bin/env python3
"""
gen_subs_font.py - makes the small letter table that ps2run_subs_patch.py puts into the PC window (host/subs_font.inc).

It draws the letters of a font at one size, keeps only the shape (16 levels of transparency) and packs them. Latin (with accents), Greek and
Cyrillic are included; Japanese, Chinese and Korean are not (they need a big font). Run it only when the font or the letter list changes:

    py gen_subs_font.py [FONT.ttf] > font_blob.txt

The font that ships with this project's table is DejaVu Sans Bold (Bitstream Vera licence: free to use and embed; see docs/subtitles.md).
"""
import base64
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

SIZE = 30
RANGES = [(0x20, 0x7E), (0xA0, 0x17F), (0x391, 0x3A9), (0x3B1, 0x3C9), (0x401, 0x401), (0x410, 0x44F), (0x451, 0x451),
          (0x2013, 0x2014), (0x2018, 0x201E), (0x2022, 0x2022), (0x2026, 0x2026), (0x2039, 0x203A), (0x20AC, 0x20AC)]


def build(path):
    font = ImageFont.truetype(path, SIZE)
    asc, desc = font.getmetrics()
    glyphs = []
    data = bytearray()
    for lo, hi in RANGES:
        for cp in range(lo, hi + 1):
            ch = chr(cp)
            adv = int(round(font.getlength(ch)))
            im = Image.new("L", (SIZE * 2, SIZE * 2), 0)
            ImageDraw.Draw(im).text((SIZE // 2, SIZE // 2), ch, font=font, fill=255, anchor="ls" if False else None)
            bb = im.getbbox()
            if bb is None:
                glyphs.append((cp, adv, 0, 0, 0, 0, 0))
                continue
            x0, y0, x1, y1 = bb
            crop = im.crop(bb)
            w, h = crop.size
            off = len(data)
            px = [min(15, (v + 8) // 17) for v in crop.getdata()]
            if len(px) % 2:
                px.append(0)
            for i in range(0, len(px), 2):
                data.append(px[i] | (px[i + 1] << 4))
            # the text was drawn with its top-left at (SIZE//2, SIZE//2): the glyph starts (x0 - SIZE//2) right and (y0 - SIZE//2) below the line top
            glyphs.append((cp, adv, w, h, x0 - SIZE // 2, y0 - SIZE // 2, off))
    head = struct.pack("<HHH", len(glyphs), asc + desc, asc)
    tab = b"".join(struct.pack("<IBBBbbI", cp, min(adv, 255), w, h, xo, yo, off) for cp, adv, w, h, xo, yo, off in glyphs)
    return head + tab + bytes(data)


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    blob = build(p)
    sys.stderr.write("%d bytes\n" % len(blob))
    print(base64.b64encode(blob).decode())
