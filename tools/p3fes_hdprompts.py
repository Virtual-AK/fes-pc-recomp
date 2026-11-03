#!/usr/bin/env python3
"""
p3fes_hdprompts.py - the battle menu's button prompt in the HD pictures (keyboard keys / Xbox / Switch buttons drawn smoothly).

The game's own battle sheets (the wheel, its icon sheet and the "RUSH" strip) show a PlayStation button. p3fes_prompts.py redraws it in the game's small
sheets, but then the sheets no longer match the HD pictures of the widescreen pack (the pack finds a picture by what is in it), so the menu fell back to the
blocky original size. Instead the three sheets are left alone (the HD pictures keep matching) and the button is drawn into the HD pictures here.

  build(table, hd_root, out_dir, style, keys=None, pad=None) -> number of pictures written

out_dir gets <pack id>/<path inside the pack> (the same layout as the table's last column) and p3fes_hdtex.build_map(..., overlay=out_dir) uses
those first. The pack's own files are never touched. Needs numpy and Pillow; nothing of the game's or the pack's art is stored here.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3fes_prompt_glyphs as GL

# table key of the HD picture -> (sprite file, picture number) in p3fes_prompts.FIXED (the sheet whose button is drawn into the HD picture)
SHEETS = {
    "42cef07c6acfab53": ("i_battle01.spr", 3),
    "823ff24a93e2ab83": ("i_battle02.spr", 1),
    "b614847cee45e44d": ("i_battle04.spr", 0),
}
# where the button sits on each sheet, in the game's own pixels (left, top, right, bottom); same numbers as FIXED in p3fes_prompts.py
BOXES = {
    ("i_battle04.spr", 0): (8, 7, 24, 23),
    ("i_battle02.spr", 1): (54, 83, 70, 99),
    ("i_battle01.spr", 3): (3, 103, 19, 120),
}
RING = (114, 181, 253)
RING_DARK = (82, 142, 198)
FILL = (1, 40, 66)
INK = (114, 181, 253)
SS = 4   # drawing at 4x and shrinking: smooth edges


def table_rows(table):
    """{key: (pack id, path inside the pack, sd width)} for the sheets above."""
    out = {}
    for line in open(table, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\r\n").split("\t")
        if len(f) >= 10 and f[0] in SHEETS:
            pid, _, rel = f[9].partition(":")
            out[f[0]] = (pid, rel, int(f[1]))
    return out


def find_picture(hd_root, pid, rel):
    """The pack's picture on disk (a folder under hd_root whose name starts with the pack id), or None."""
    try:
        names = sorted(os.listdir(hd_root))
    except OSError:
        return None
    for d in names:
        if d == pid or d.startswith(pid):
            c = os.path.join(hd_root, d, *rel.split("/"))
            if os.path.isfile(c):
                return c
    return None


def available(table, hd_root):
    """{key: picture path} of the battle sheets the pack really has."""
    got = {}
    for k, (pid, rel, _) in table_rows(table).items():
        p = find_picture(hd_root, pid, rel)
        if p:
            got[k] = p
    return got


def _font(size):
    try:
        return ImageFont.load_default(size=max(6, int(size)))
    except TypeError:
        return ImageFont.load_default()


def _fit_text(draw, text, box_w, box_h):
    """Largest size whose text fits box_w x box_h; returns (font, stroke)."""
    size = box_h
    while size > 6:
        f = _font(size)
        l, t, r, b = draw.textbbox((0, 0), text, font=f, stroke_width=max(2, size // 9), anchor="ls")
        if r - l <= box_w and b - t <= box_h:
            return f, max(2, size // 9)
        size -= 2
    return _font(6), 1


def _key_layer(size, label, style, action):
    """RGBA (straight alpha, 255 = drawn) picture of one button, size x size pixels."""
    n = size * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pill = False
    if style in ("xbox", "switch"):
        fill, ring, ink = FILL + (255,), RING + (255,), INK + (255,)
        if style == "xbox":
            fill = GL.PAD_COLOURS["xbox"].get(label, (95, 95, 105, 255))
            ring = tuple(int(c * 0.55) for c in fill[:3]) + (255,)
            ink = (255, 255, 255, 255)
        else:
            fill, ring, ink = (232, 232, 236, 255), (70, 70, 80, 255), (40, 40, 48, 255)
        d.ellipse((0, 0, n - 1, n - 1), fill=ring)
        m = int(n * 0.07)
        d.ellipse((m, m, n - 1 - m, n - 1 - m), fill=fill)
        inner = n - 2 * m
        radius = None
    else:
        fill, ring, ink = FILL + (255,), RING + (255,), INK + (255,)
        radius = int(n * 0.2)
        d.rounded_rectangle((0, 0, n - 1, n - 1), radius=radius, fill=RING_DARK + (255,))
        m1 = int(n * 0.06)
        d.rounded_rectangle((m1, m1, n - 1 - m1, n - 1 - m1), radius=max(2, radius - m1), fill=ring)
        m2 = int(n * 0.13)
        d.rounded_rectangle((m2, m2, n - 1 - m2, n - 1 - m2), radius=max(2, radius - m2), fill=fill)
        inner = n - 2 * m2
    text = str(label)
    plain = text.isalnum() and len(text) <= 3
    cx = cy = n / 2.0
    if plain:
        f, sw = _fit_text(d, text, inner * 0.74, inner * 0.68)
        d.text((cx, cy), text, font=f, fill=ink, anchor="mm", stroke_width=sw, stroke_fill=ink)
    else:
        rows = GL.bitmap(text, 11, 11)
        if rows:
            h, w = len(rows), max(len(r) for r in rows)
            cell = max(1, int(inner * 0.66 / max(w, h)))
            gx, gy = cx - w * cell / 2.0, cy - h * cell / 2.0
            for y, row in enumerate(rows):
                for x, c in enumerate(row):
                    if c == "#":
                        d.rectangle((gx + x * cell, gy + y * cell, gx + (x + 1) * cell - 1, gy + (y + 1) * cell - 1), fill=ink)
    return img.resize((size, size), Image.LANCZOS)


def paint(img, box, label, style, action="triangle"):
    """Replace the PlayStation button inside box (left, top, right, bottom, HD pixels) of the RGBA PIL picture `img`."""
    x0, y0, x1, y1 = box
    a = np.array(img, dtype=np.float32)
    h, w = a.shape[:2]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    bw, bh = x1 - x0, y1 - y0
    reg = a[y0:y1, x0:x1]
    # the dark round backing: its colour is the commonest opaque-ish colour of the box
    cols = reg.reshape(-1, 4)
    sel = cols[cols[:, 3] > 90]
    if len(sel):
        q = np.round(sel / 4.0).astype(np.int32)
        keys, counts = np.unique(q, axis=0, return_counts=True)
        back = keys[counts.argmax()].astype(np.float32) * 4.0
    else:
        back = np.array([50, 68, 78, 127], np.float32)
    yy, xx = np.mgrid[0:bh, 0:bw]
    ex, ey = (bw - 1) / 2.0, (bh - 1) / 2.0
    rx, ry = bw / 2.0 - 0.06 * bw, bh / 2.0 - 0.06 * bh
    inside = ((xx - ex) / rx) ** 2 + ((yy - ey) / ry) ** 2 <= 1.0
    reg[inside] = back
    corner = ~inside & (reg[..., 3] > 10) & (reg[..., :3].mean(axis=2) > 70)   # the triangle's tips reach past the round backing
    reg[corner] = (39, 81, 93, 30)
    a[y0:y1, x0:x1] = reg
    side = int(min(rx, ry) * 2 * 0.80)
    side -= side % 2
    layer = np.array(_key_layer(side, label, style, action), dtype=np.float32)
    ox, oy = x0 + (bw - side) // 2, y0 + (bh - side) // 2
    cov = layer[..., 3:4] / 255.0
    opaque = max(float(back[3]), 1.0)               # the pack draws "solid" at about half alpha (the console's 0x80)
    dst = a[oy:oy + side, ox:ox + side]
    dst[..., :3] = dst[..., :3] * (1 - cov) + layer[..., :3] * cov
    dst[..., 3:4] = dst[..., 3:4] * (1 - cov) + opaque * cov
    a[oy:oy + side, ox:ox + side] = dst
    return Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8), "RGBA")


def save_dds(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    img.save(tmp, format="DDS", pixel_format="DXT5")
    os.replace(tmp, path)


def build(table, hd_root, out_dir, style="keyboard", keys=None, pad=None):
    """Write the battle pictures with the button for `style` into out_dir. Returns the sheets (sprite file, picture number) whose HD picture was written
    (empty when the pack lacks them): those sheets must stay as the game has them."""
    import p3fes_prompts as P
    labels = P.prompt_labels(style, keys, pad)
    label = labels["triangle"]
    rows = table_rows(table)
    done = []
    for key, src in available(table, hd_root).items():
        pid, rel, sd_w = rows[key]
        box = BOXES[SHEETS[key]]
        im = Image.open(src).convert("RGBA")
        s = im.width / float(sd_w)
        hd_box = tuple(int(round(v * s)) for v in box)
        save_dds(paint(im, hd_box, label, style), os.path.join(out_dir, pid, *rel.split("/")))
        done.append(SHEETS[key])
    return done


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--table", required=True)
    ap.add_argument("--mods", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--style", default="keyboard")
    a = ap.parse_args()
    print("%d pictures written" % len(build(a.table, a.mods, a.out, a.style)))
