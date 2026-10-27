#!/usr/bin/env python3
"""
p3fes_prompts.py - draw keyboard button prompts into the game's own prompt pictures (proof of concept, grows with testing).

The game keeps each "press this button" picture inside a small sprite file (.spr: one or more 4-bit/8-bit .TMX pictures). The sprite files sit
inside bigger archives (.PAK/.BIN). This tool, run on a folder made by p3fes_unpack.py --containers (and the matching archives):
  1. learns what the PlayStation icons look like by cutting them out of YOUR OWN game files (nothing of the game's art is stored in this tool),
  2. finds the same icons in every sprite by picture matching,
  3. redraws each one as a keyboard key in the game's own style (the letter comes from your key settings),
  4. writes the archives back with exactly the same size, as a mod folder the launcher can lay over your disc.

It only READS your files. Needs numpy and opencv-python (pip install numpy opencv-python) and p3fes_tmx.py next to it.

Usage:
    py p3fes_prompts.py EXTRACTED_FOLDER -o OUT_FOLDER [--report report.txt] [--preview FOLDER]
"""
import argparse
import json
import os
import struct
import re
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3fes_tmx as T
import p3fes_prompt_glyphs as GL

# ---------------------------------------------------------------- the letters (5x7, '#' = on)
FONT = {
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "I": ["###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
    "<": ["...#", "..##", ".###", "####", ".###", "..##", "...#"],
    ">": ["#...", "##..", "###.", "####", "###.", "##..", "#..."],
}

# what each PlayStation icon becomes (the default key layout of the launcher)
KEYS = {"cross": "K", "circle": "L", "square": "J", "triangle": "I", "L1": "Q", "R1": "E", "dleft": "<", "dright": ">"}

# colours of the game's own keys (RGBA, as the picture decoder shows them)
RING = [(93, 170, 252, 255), (114, 181, 253, 255), (82, 142, 198, 255)]
FILL = (1, 40, 66, 255)
INK = (114, 181, 253, 255)

# Where each icon is cut out from, in the disc's folder tree: (path, picture number, left, top, right, bottom).
# Boxes include the soft edge around the icon.
HELP06 = "DATA.CVM/CAMP/CAMP_MAIN.PAK.d/main_all/i_new_camp_help06.spr"
HELP07 = "DATA.CVM/CAMP/CAMP_MAIN.PAK.d/main_all/i_new_camp_help07.spr"
SHOPKOT = "DATA.CVM/FACILITY/FCL_ANTIQUE.PAK.d/antique/spr/i_shopkot_01.spr"
GATTAI = "DATA.CVM/FACILITY/FCL_COMBINE.PAK.d/combine/spr/i_gattai01.spr"
SAVELOAD = "DATA.CVM/FACILITY/AGS_I_FILE_SAVELOAD01.SPR"
COMMU06 = "DATA.CVM/CAMP/CAMP_COMU.PAK.d/commu/i_new_camp_commu06.spr"
# "name:variant" - the same button is drawn a few different ways in different screens, each way needs its own cut-out
TEMPLATES = {
    "cross:a": (HELP06, 0, 2, 52, 25, 75),
    "circle:a": (HELP06, 0, 194, 29, 216, 51),
    "square:a": (HELP07, 0, 168, 3, 190, 25),
    "L1:a": (HELP06, 0, 69, 54, 96, 71),
    "R1:a": (HELP06, 0, 97, 54, 124, 71),
    "dleft:a": (HELP06, 0, 3, 5, 19, 21),
    "dright:a": (HELP06, 0, 20, 5, 37, 21),
    "circle:c": (GATTAI, 0, 139, 62, 160, 83),
    "triangle:c": (SHOPKOT, 1, 3, 2, 28, 27),
    "circle:d": (SHOPKOT, 1, 110, 5, 133, 28),
    "cross:s": (SAVELOAD, 4, 0, 3, 18, 21),
    "circle:s": (SAVELOAD, 4, 0, 27, 18, 45),
    "L1:s": (COMMU06, 1, 24, 24, 48, 37),
    "R1:s": (COMMU06, 1, 51, 24, 74, 37),
}
THRESHOLD = 0.93
DISC_THRESHOLD = {"circle": 0.85, "square": 0.85, "triangle": 0.85, "cross": 0.85}   # round icons differ a little from sheet to sheet


# ---------------------------------------------------------------- pictures
class Tex:
    """One TMX inside a sprite, decoded to RGBA and writable."""

    def __init__(self, data, offset):
        self.off = offset                      # start of the 0x40 header in the sprite file
        self.raw = bytearray(data[offset:])
        self.w, self.h, rgba, self.info = T.decode_tmx(bytes(self.raw))
        self.fmt = self.raw[22]
        self.rgba = np.frombuffer(rgba, np.uint8).reshape(self.h, self.w, 4).copy()
        self.size = self.info["expected_size"]
        self.dirty = False
        if self.fmt in (0x13, 0x14):
            n = 256 if self.fmt == 0x13 else 16
            pal = T.read_palette(self.raw, T.HEADER_SIZE, n, self.raw[17], True)
            self.pal = np.array(pal, np.int32)
            self.pix_off = T.HEADER_SIZE + n * T.palette_entry_bytes(self.raw[17])

    def gray(self):
        a = self.rgba[..., 3:4].astype(np.float32) / 255
        g = self.rgba[..., :3].astype(np.float32).mean(axis=2, keepdims=True)
        return (g * a + 128 * (1 - a))[..., 0].astype(np.float32)

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.rgba[y, x] = c
            self.dirty = True

    def encode(self):
        """Write the (changed) pixels back into the TMX bytes in the picture's own format."""
        out = self.raw
        if self.fmt in (0x13, 0x14):
            lut = {}
            for y in range(self.h):
                for x in range(self.w):
                    c = tuple(int(v) for v in self.rgba[y, x])
                    i = lut.get(c)
                    if i is None:
                        d = ((self.pal[:, :3] - np.array(c[:3])) ** 2).sum(axis=1) + 2 * (self.pal[:, 3] - c[3]) ** 2
                        i = lut[c] = int(d.argmin())
                    p = y * self.w + x
                    if self.fmt == 0x13:
                        out[self.pix_off + p] = i
                    else:
                        o = self.pix_off + (p >> 1)
                        out[o] = (out[o] & 0x0F) | (i << 4) if p & 1 else (out[o] & 0xF0) | i
        elif self.fmt == 0x00:
            for y in range(self.h):
                for x in range(self.w):
                    o = T.HEADER_SIZE + (y * self.w + x) * 4
                    r, g, b, a = (int(v) for v in self.rgba[y, x])
                    out[o:o + 4] = bytes((r, g, b, min(255, (a + 1) // 2)))
        return bytes(out[:self.size])


# icons that exist once and don't repeat anywhere: (file name, texture number) -> [(box, button)]
FIXED = {
    ("damage.tmx", 0): [((66, 94, 81, 108), "triangle")],
    ("i_battle04.spr", 0): [((8, 7, 24, 23), "triangle")],
    ("i_2d_pcj.tmx", 0): [((841, 91, 858, 108), "triangle")],
    # the battle wheel and target prompts (sheets used while the wheel is on screen)
    ("i_battle02.spr", 1): [((54, 83, 70, 99), "triangle")],
    ("i_battle01.spr", 3): [((3, 103, 19, 120), "triangle")],
    ("i_battle01.spr", 9): [((33, 3, 57, 25), "circle"), ((62, 3, 86, 25), "cross")],
    # the name entry screen: the greyed Del circle, the Start arrow in End (active and greyed) and the four L1 / R1 tabs (the whole tab text is redrawn)
    ("i_nameent01.spr", 0): [((325, 122, 343, 140), "circle"), ((324, 76, 344, 96), "start"), ((324, 191, 344, 211), "start"),
                             ((393, 70, 456, 88), "L1tab"), ((393, 93, 456, 111), "R1tab"), ((393, 184, 456, 202), "L1tab"), ((393, 207, 456, 225), "R1tab")],
}


def textures(spr):
    """Every TMX inside a sprite file: list of Tex."""
    out = []
    for m in re.finditer(b"TMX0", spr):
        o = m.start() - 8
        try:
            out.append(Tex(spr, o))
        except Exception:
            pass
    return out


def palette_roles(tex):
    """RING, FILL, INK colours. Sheets with a small palette (4-bit) may not hold our blues:
    then use the sheet's own darkest / lightest / mid colours so the key stays readable."""
    pal = getattr(tex, "pal", None)
    if pal is None or tex.fmt != 0x14:
        return RING, FILL, INK
    op = [tuple(int(v) for v in c) for c in pal if c[3] >= 200]
    if len(op) < 3:
        return RING, FILL, INK
    near = lambda c: min(op, key=lambda q: sum((a - b) ** 2 for a, b in zip(q[:3], c[:3])))
    lum = lambda c: 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
    f, i, r = near(FILL), near(INK), near(RING[1])
    fallback = lum(i) - lum(f) < 90
    if fallback:
        srt = sorted(op, key=lum)
        f, i = srt[0], srt[-1]
        mid = lum(f) + 0.6 * (lum(i) - lum(f))
        r = min(op, key=lambda q: abs(lum(q) - mid))
    return ([r, r, r] if fallback else [near(c) for c in RING]), f, i


def _bg_of(tex, box):
    """The commonest colour in the ring just outside box: what to paint over the old icon with."""
    x0, y0, x1, y1 = box
    ring = []
    for x in range(x0 - 1, x1 + 1):
        ring += [(x, y0 - 1), (x, y1)]
    for y in range(y0, y1):
        ring += [(x0 - 1, y), (x1, y)]
    cols = [tuple(int(v) for v in tex.rgba[y, x]) for x, y in ring if 0 <= x < tex.w and 0 <= y < tex.h]
    return max(set(cols), key=cols.count) if cols else (0, 0, 0, 0)


def _stamp(tex, rows, kx, ky, kw, kh, colour):
    """Draw a '#' bitmap in the middle of the kw x kh area at (kx, ky)."""
    gx, gy = kx + (kw - len(rows[0])) // 2, ky + (kh - len(rows)) // 2
    for dy, row in enumerate(rows):
        for dx, c in enumerate(row):
            if c == "#":
                tex.put(gx + dx, gy + dy, colour)


def draw_key(tex, box, label, style="keyboard", action="cross"):
    """Replace the icon inside box (left, top, right, bottom) with a prompt for `label`.
    style: 'keyboard' = a keycap, 'xbox' / 'switch' = that controller's button (round, or a pill for the shoulder buttons)."""
    x0, y0, x1, y1 = box
    bg = _bg_of(tex, box)
    for y in range(y0, y1):
        for x in range(x0, x1):
            tex.put(x, y, bg)
    w, h = x1 - x0, y1 - y0
    RING_, FILL_, INK_ = palette_roles(tex)
    small_sheet = tex.fmt == 0x14                      # 16 colours: only the sheet's own colours are available
    side = min(w, h) - (4 if min(w, h) >= 18 else 2)     # the keys are 17 wide for the 23 wide icons
    pill = action in ("L1", "R1", "L1tab", "R1tab", "L2", "R2")
    kw = w - (4 if min(w, h) >= 18 else 2) if pill else side
    kx, ky = x0 + (w - kw) // 2, y0 + (h - side) // 2
    if style in ("xbox", "switch") and not pill:       # a round button
        fill, ring, ink = FILL_, RING_[1], INK_
        if not small_sheet:
            if style == "xbox":
                fill = GL.PAD_COLOURS["xbox"].get(label, (95, 95, 105, 255))
                ring, ink = tuple(int(c * 0.55) for c in fill[:3]) + (255,), (255, 255, 255, 255)
            else:
                fill, ring, ink = (232, 232, 236, 255), (70, 70, 80, 255), (40, 40, 48, 255)
        c = (side - 1) / 2.0
        for yy in range(side):
            for xx in range(side):
                d = ((xx - c) ** 2 + (yy - c) ** 2) ** 0.5
                if d <= side / 2.0 - 0.1:
                    tex.put(kx + xx, ky + yy, ring if d > side / 2.0 - 1.4 else fill)
        rows = GL.bitmap(label, side - 5, side - 5)
        _stamp(tex, rows, kx, ky, side, side, ink)
        return
    if style in ("xbox", "switch"):                    # shoulder button: a dark pill
        base = (232, 232, 236, 255) if style == "switch" else (150, 150, 158, 255)
        fill, ring, ink = (FILL_, RING_[1], INK_) if small_sheet else ((70, 70, 78, 255), base, (255, 255, 255, 255))
        rings = [ring]
        t = 1
    else:
        fill, ink = FILL_, INK_
        rings = RING_ if side >= 16 else RING_[1:2]       # small keys: one light edge so the letter fits
        t = len(rings) + (1 if side >= 14 else 0)
    for k, c in enumerate(rings):
        for y in range(ky + k, ky + side - k):
            for x in range(kx + k, kx + kw - k):
                tex.put(x, y, c)
    for y in range(ky + t, ky + side - t):
        for x in range(kx + t, kx + kw - t):
            tex.put(x, y, fill)
    for cx, cy in ((kx, ky), (kx + kw - 1, ky), (kx, ky + side - 1), (kx + kw - 1, ky + side - 1)):
        tex.put(cx, cy, bg)
    rows = GL.bitmap(label, kw - 2 * t - 1, side - 2 * t - 1)
    _stamp(tex, rows, kx, ky, kw, side, ink)


def sig(rgba):
    """(pink, teal): do the pixels contain the pink of Circle/Square or the teal of Triangle? The grey picture alone confuses round buttons."""
    r, g, b, a = (rgba[..., i].astype(int) for i in range(4))
    solid = a > 100
    n = max(1, int(solid.sum()))
    pink = ((r > g + 65) & (r > b + 55) & solid).sum() / n > 0.03
    teal = ((g > r + 60) & (b > r + 60) & (g >= b - 10) & solid).sum() / n > 0.04
    return pink, teal


def find_hits(tex, tpls):
    """[(name, box, score)] of icons found in tex, best first, without overlaps."""
    hits = []
    g = tex.gray()
    mean = lambda a, k: cv2.boxFilter(a, -1, k, normalize=True, borderType=cv2.BORDER_REFLECT)
    for name, (t, tsig) in tpls.items():
        th, tw = t.shape
        if g.shape[0] < th or g.shape[1] < tw:
            continue
        r = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED)
        var = mean(g * g, (tw, th)) - mean(g, (tw, th)) ** 2            # flat areas (black, one colour) match anything: ignore them
        var = var[th // 2: th // 2 + r.shape[0], tw // 2: tw // 2 + r.shape[1]]
        th_ = DISC_THRESHOLD.get(name.split(':')[0], THRESHOLD)
        ys, xs = np.where((np.abs(r) >= th_) & (var > 150))
        for y, x in zip(ys, xs):
            ws = sig(tex.rgba[y:y + th, x:x + tw])
            if (ws[0] != tsig[0]) if name.startswith('cross') else (ws != tsig):      # crosses are tinted differently from shop to shop
                continue
            hits.append((name, (int(x), int(y), int(x) + tw, int(y) + th), float(abs(r[y, x]))))
    hits.sort(key=lambda h: -h[2])
    kept = []
    for h in hits:
        b = h[1]
        if all(b[2] <= k[1][0] or b[0] >= k[1][2] or b[3] <= k[1][1] or b[1] >= k[1][3] for k in kept):
            kept.append(h)
    return kept


def load_templates(root):
    tpls = {}
    for name, (path, k, x0, y0, x1, y1) in TEMPLATES.items():
        spr = open(os.path.join(root, *path.split("/")), "rb").read()
        tex = textures(spr)[k]
        tpls[name] = (tex.gray()[y0:y1, x0:x1], sig(tex.rgba[y0:y1, x0:x1]))
    return tpls


def patch_font(root, out, key):
    """The Persona list's STATUS prompt is a text glyph (a hollow square), not a picture.
    Put the key's letter inside that glyph in each system font that has one. Fonts carry
    only 16 levels of transparency, the game colours them. Returns [(file, glyph index)]."""
    done = []
    for name, size, gw, gh in (("SYSFONTALL.FNT", 144, 16, 18), ("ADVFONTALL.FNT", 312, 24, 26)):
        src = os.path.join(root, "DATA.CVM", "FONT", name)
        if not os.path.isfile(src):
            continue
        d = bytearray(open(src, "rb").read())
        n, sz, off = struct.unpack_from("<III", d, 4)[0], struct.unpack_from("<I", d, 8)[0], struct.unpack_from("<I", d, 16)[0]
        if sz != size or n * size + off != len(d):
            continue
        found = None
        for i in range(n):
            raw = np.frombuffer(bytes(d[off + i * size: off + (i + 1) * size]), np.uint8)
            px = np.empty(size * 2, np.uint8)
            px[0::2], px[1::2] = raw & 15, raw >> 4
            g = px.reshape(gh, gw)
            ys, xs = np.nonzero(g > 3)
            if len(xs) < 20:
                continue
            w, h = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
            sub = g[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            if 10 <= w <= gw and 10 <= h <= gh and abs(int(w) - int(h)) <= 1 and (sub[3:-3, 3:-3] > 3).mean() < 0.1 \
                    and (sub[0] > 2).mean() > 0.8 and (sub[-1] > 2).mean() > 0.8:
                found = (i, g, int(xs.min()), int(ys.min()), int(w), int(h))
                break
        if not found:
            continue
        i, g, x0, y0, w, h = found
        top = int(g.max())
        gl = FONT[key]
        gx, gy = x0 + (w - len(gl[0])) // 2, y0 + (h - len(gl)) // 2
        for dy, row in enumerate(gl):
            for dx, c in enumerate(row):
                if c == "#":
                    g[gy + dy, gx + dx] = top
        flat = g.reshape(-1)
        d[off + i * size: off + (i + 1) * size] = bytes((flat[0::2] | (flat[1::2] << 4)).tolist())
        dst = os.path.join(out, "files", "DATA", "FONT", name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "wb").write(bytes(d))
        done.append((name, i))
    return done


def container_of(rel):
    """'DATA.CVM/CAMP/CAMP_MAIN.PAK.d/main_all/x.spr' -> 'DATA.CVM/CAMP/CAMP_MAIN.PAK'; a loose sprite is its own container."""
    m = re.match(r"(.*?\.(?:PAK|BIN|PAC|CPK))\.d/", rel, re.I)
    return m.group(1) if m else rel


def prompt_labels(style, keys=None, pad=None):
    """What each PlayStation icon turns into: {icon: label}. keys / pad are the launcher's key and controller settings (names as in its keys file).
    style 'keyboard' uses the keys; 'xbox' / 'switch' use the controller buttons that are bound, named the way that controller names them.
    An icon that stays as the game draws it (the D-pad arrows on a controller) is left out."""
    keys = dict(KEY_DEFAULTS, **(keys or {}))
    pad = dict(PAD_DEFAULTS, **(pad or {}))
    out = {}
    for icon in ("cross", "circle", "square", "triangle", "L1", "R1", "L2", "R2", "start", "select"):
        if style == "keyboard":
            out[icon] = GL.key_label(keys[icon.lower()])
        else:
            out[icon] = GL.pad_label(style, pad[icon.lower()])
    # the name entry tabs read "<L1" and "R1>": the arrow stays next to the new label when it is short
    out["L1tab"] = "<" + out["L1"] if len(out["L1"]) <= 2 else out["L1"]
    out["R1tab"] = out["R1"] + ">" if len(out["R1"]) <= 2 else out["R1"]
    if style == "keyboard":
        out["dleft"], out["dright"] = "<", ">"
    return out


KEY_DEFAULTS = {"cross": "K", "circle": "L", "square": "J", "triangle": "I", "l1": "Q", "r1": "E", "l2": "1", "r2": "3", "start": "Return", "select": "Backspace"}
PAD_DEFAULTS = {"cross": "a", "circle": "b", "square": "x", "triangle": "y", "l1": "leftshoulder", "r1": "rightshoulder",
                "l2": "lefttrigger", "r2": "righttrigger", "start": "start", "select": "back"}
HITS_VERSION = 4


def scan(root, report=None, template_root=None):
    """Find every icon in every sprite under root: {relative path: [(texture number, [(name, box, score)])]}.
    template_root: take the icon cut-outs from this folder instead (another language's pictures are searched with the original's icons)."""
    tpls = load_templates(template_root or root)
    found = {}
    for dp, _, fs in os.walk(root):
        for f in sorted(fs):
            if not f.lower().endswith((".spr", ".tmx")):
                continue
            rel = os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/")
            spr = open(os.path.join(dp, f), "rb").read()
            per = []
            for k, tex in enumerate(textures(spr)):
                hits = find_hits(tex, tpls)
                for box, key in FIXED.get((f.lower(), k), []):
                    hits.append((key + ":fixed", box, 1.0))
                if hits:
                    per.append((k, [(n, list(b), s) for n, b, s in hits]))
            if per:
                found[rel] = per
    return found


def build(root, out, style="keyboard", keys=None, pad=None, hits=None, report=None, preview=None, font=False):
    """Redraw the icons found in root as `style` prompts and write the changed archives under out/files. hits = a result of scan() to skip the search.
    Returns (hits, report lines, archives written)."""
    report = [] if report is None else report
    labels = prompt_labels(style, keys, pad)
    if hits is None:
        hits = scan(root)
    patched, containers = {}, {}
    for rel, per in hits.items():
        path = os.path.join(root, *rel.split("/"))
        if not os.path.isfile(path):
            continue
        spr = open(path, "rb").read()
        new, n = bytearray(spr), 0
        texs = textures(spr)
        for k, hl in per:
            if k >= len(texs):
                continue
            tex, drawn = texs[k], 0
            for name, box, score in hl:
                icon = name.split(":")[0]
                if icon not in labels:
                    continue
                draw_key(tex, tuple(box), labels[icon], style, icon)
                report.append("%s #%d %s %s %.3f" % (rel, k, name, tuple(box), score))
                n += 1
                drawn += 1
            if drawn:
                new[tex.off:tex.off + tex.size] = tex.encode()
                if preview:
                    from PIL import Image
                    os.makedirs(preview, exist_ok=True)
                    Image.fromarray(tex.rgba).save(os.path.join(preview, "%s_%d.png" % (os.path.basename(rel), k)))
        if n:
            patched[rel] = (spr, bytes(new))
    # lay the changed sprites back into their archives
    for rel, (old, new) in patched.items():
        cont = container_of(rel)
        if cont == rel:                                   # a loose sprite file
            containers[rel] = new
            continue
        cpath = os.path.join(root, *cont.split("/"))
        if not os.path.isfile(cpath):
            continue
        if cont not in containers:
            containers[cont] = open(cpath, "rb").read()
        data = containers[cont]
        if data.count(old) != 1:
            report.append("SKIP %s: appears %d times in %s" % (rel, data.count(old), cont))
            continue
        containers[cont] = data.replace(old, new)
    for cont, data in containers.items():
        top, _, rest = cont.partition("/")
        dst = os.path.join(out, "files", top.replace(".CVM", "").replace(".cvm", ""), *rest.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "wb").write(data)
    if font and style == "keyboard":
        for fn, gi in patch_font(root, out, labels["square"]):
            report.append("font glyph %s #%d (hollow square) now carries %s" % (fn, gi, labels["square"]))
    return hits, report, len(containers)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("-o", "--out", default="keyboard_prompts")
    ap.add_argument("--report")
    ap.add_argument("--preview")
    ap.add_argument("--style", choices=("keyboard", "xbox", "switch"), default="keyboard",
                    help="keyboard keys (default), or the Xbox / Switch controller buttons")
    ap.add_argument("--keys", help="launcher keys file (lines like 'cross = Z'); default keys when left out")
    ap.add_argument("--hits", help="file to keep the search result in: the next run with the same file skips the (slow) search")
    ap.add_argument("--font", action="store_true",
                    help="also put the key letter in the system fonts' hollow square (experimental: no visible effect found in game)")
    a = ap.parse_args()
    keys, pad = {}, {}
    if a.keys and os.path.isfile(a.keys):
        for line in open(a.keys):
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                k, v = (x.strip() for x in line.split("=", 1))
                if k.startswith("pad."):
                    pad[k[4:].lower()] = v.lower()
                else:
                    keys[k.lower()] = v
    hits = None
    if a.hits and os.path.isfile(a.hits):
        try:
            d = json.load(open(a.hits))
            if d.get("version") == HITS_VERSION:
                hits = {rel: [(k, [(n, b, s) for n, b, s in hl]) for k, hl in per] for rel, per in d["hits"].items()}
        except Exception:
            hits = None
    report = []
    hits, report, n_arch = build(a.root, a.out, a.style, keys, pad, hits, report, a.preview, a.font)
    if a.hits:
        json.dump({"version": HITS_VERSION, "hits": hits}, open(a.hits, "w"))
    msg = "%d icons redrawn in %d sprites, %d archives written to %s" % (
        sum(1 for r in report if not r.startswith(("SKIP", "font glyph"))), len(hits), n_arch, a.out)
    print(msg)
    if a.report:
        open(a.report, "w").write("\n".join(report) + "\n" + msg + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
