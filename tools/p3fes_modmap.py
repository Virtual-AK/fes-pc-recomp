#!/usr/bin/env python3
"""
p3fes_modmap.py - find where a mod's loose files belong inside your own Persona 3 FES disc image.

Most mods are loose files laid out like the folders p3fes_unpack.py makes: a file from BTL.CVM keeps the path
BTL.CVM/..., and a file inside a container (.PAC .PAK .BIN .CPK) sits in the container's ".d" folder, for example
    BTL.CVM/BATTLE/PANEL/BP_TUTORIAL.BIN.d/bp_tutorial1.bmd
(p3fes_text.py repack writes exactly this layout.) This tool reads your disc image, works out for each mod file the
exact place in the image it would replace, and tells you whether it fits there (same size or smaller).

  check    py p3fes_modmap.py check game.iso MOD_FOLDER [MORE_FOLDERS...]   (later folders win for the same file)
           Only reads. Prints one line per file: where it goes and whether it fits.
  overlay  py p3fes_modmap.py overlay game.iso MOD_FOLDER -o mods.ovl
           Writes a small list of (position, bytes) for the runner. The disc image is not touched.
  find     py p3fes_modmap.py find game.iso TEXT   (lists image files and container entries containing TEXT)
  tint     py p3fes_modmap.py tint game.iso -o FOLDER [--move]   (makes a red-portraits test mod from your own disc)
  reads    py p3fes_modmap.py reads game.iso active.ovl.reads.log   (which disc files the game read, in order)
  movetest py p3fes_modmap.py movetest game.iso -o copy.iso   (relocation test: moves small files unchanged; -o x.ovl writes a mod overlay instead of a copy)
  apply    py p3fes_modmap.py apply game.iso MOD_FOLDER -o modded_copy.iso
           Writes a COPY of the image with the files put in place (needs the disc's size in free space).
           For testing only: the original image is never changed. Do not share the copy.

A whole file larger than the one it replaces is moved to the end of the image and its directory entry is pointed there\n(untested in game until the first relocation test). A larger file inside a container is reported and skipped.
A smaller file is written at the start of the old file's space and the old bytes after it are left as they were.
Standard library only, Python 3.8+.
"""
import argparse
import io
import os
import shutil
import re, struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3fes_unpack as U
import p3fes_patch as P

MAGIC = b"P3OVL001"


def locate(iso_path):
    """Returns (files, containers, recs): files maps UPPER path -> (absolute offset, size); containers maps UPPER path -> list of (extracted name, absolute offset, size); recs maps UPPER path of a whole file -> (absolute offset of its directory record, absolute offset of the file system it is listed in)."""
    files = {}
    recs = {}
    with open(iso_path, "rb") as f:
        outer = U.Window(f, 0, os.fstat(f.fileno()).st_size)
        for e in U.list_files(outer):
            if e["path"].upper().endswith(".CVM"):
                opened = U.open_cvm(f, e)
                if opened is None:
                    continue
                inner, inner_files = opened
                top = e["path"].strip("/")
                for x in inner_files:
                    files[("/" + top + x["path"]).upper()] = (inner.base + x["lba"] * U.SECTOR, x["size"], inner)
                    recs[("/" + top + x["path"]).upper()] = (inner.base + x["recpos"], inner.base)
            else:
                files[e["path"].upper()] = (e["lba"] * U.SECTOR, e["size"], outer)
                recs[e["path"].upper()] = (e["recpos"], 0)
        containers = {}
        for path, (off, size, win) in files.items():
            if os.path.splitext(path)[1].lower() in U.PAK_EXTS and size >= 256:
                view = U.Window(f, off, size)
                r = U.analyse_pak(view)
                if r["ok"] and r["entries"]:
                    used = set()
                    out = []
                    for (name, elen), st in zip(r["entries"], r["starts"]):
                        ep = U.unique("/".join(U.safe_parts(name)), used)
                        out.append((ep.upper(), off + st + 256, elen))
                    containers[path] = out
        # textures inside .SPR sprite files that sit in a container: stored as containers["<container> :: <entry>"] = [("#0", offset, size), ...]
        extra = {}
        for cp, ents in containers.items():
            for ename, o, s in ents:
                if ename.endswith(".SPR") and 64 <= s <= 8 * 1024 * 1024:
                    f.seek(o)
                    data = f.read(s)
                    found = []
                    at = data.find(b"TMX0")
                    while at != -1:
                        st = at - 8
                        if st >= 0:
                            n = struct.unpack_from("<I", data, st + 4)[0]
                            if 32 < n and st + n <= s:
                                found.append(("#%d" % len(found), o + st, n))
                        at = data.find(b"TMX0", at + 4)
                    if found:
                        extra[cp + " :: " + ename] = found
        containers.update(extra)
    return {p: (o, s) for p, (o, s, _w) in files.items()}, containers, recs


def _asc(name):
    """Entry names with Japanese characters come out differently depending on who extracted them (the image holds Shift-JIS, a zip may hold cp437 or UTF-8). Only the plain ASCII letters are compared."""
    return "".join(ch for ch in name if ord(ch) < 128 and ch not in " _-").upper()


def _entry_index(entries, name):
    """Index of the container entry called `name`: exact first, otherwise the one entry whose ASCII part is the same."""
    for ix, e in enumerate(entries):
        if e[0] == name:
            return ix
    if any(ord(ch) > 127 for ch in name) or any(any(ord(ch) > 127 for ch in e[0]) for e in entries):
        want = _asc(name)
        hits = [ix for ix, e in enumerate(entries) if _asc(e[0]) == want]
        if len(hits) == 1:
            return hits[0]
    return None


def resolve(rel, files, containers):
    """rel: path of a mod file relative to the mod folder, with '/' separators. Returns (offset, size, what) or (None, None, reason)."""
    key = "/" + rel.strip("/").upper()
    if key in files:
        o, s = files[key]
        return o, s, "whole file", None
    parts = key.strip("/").split("/")
    for i in range(len(parts) - 1, 0, -1):
        if parts[i - 1].endswith(".D"):
            cpath = "/" + "/".join(parts[:i - 1] + [parts[i - 1][:-2]])
            name = "/".join(parts[i:])
            if cpath not in containers:
                return None, None, "container %s not found in the image" % cpath, None
            ix = _entry_index(containers[cpath], name)
            if ix is not None:
                _n, o, s = containers[cpath][ix]
                return o, s, "inside " + cpath, {"c": cpath, "i": ix, "t": None, "eo": o, "es": s}
            return None, None, "no file %s inside %s" % (name, cpath), None
    # mod-manager layout: a container is a folder without its extension (AGS2_BP_ALL for AGS2_BP_ALL.BIN), its entries follow,
    # and a .SPR entry is a folder (without .SPR) holding its textures, named ...a.tmx, ...b.tmx in order
    stems = {}
    for p in files:
        stem, ext = os.path.splitext(p)
        if ext.lower() in U.PAK_EXTS and p in containers:
            stems.setdefault(stem, p)
    for i in range(len(parts) - 1, 0, -1):
        cpath = stems.get("/" + "/".join(parts[:i]))
        if not cpath:
            continue
        rest = parts[i:]
        ix0 = _entry_index(containers[cpath], "/".join(rest))
        if ix0 is not None:
            _n, o, s = containers[cpath][ix0]
            return o, s, "inside " + cpath, {"c": cpath, "i": ix0, "t": None, "eo": o, "es": s}
        for ix, (ename, o, s) in enumerate(containers[cpath]):
            es = ename.rsplit(".", 1)[0] if "." in ename.rsplit("/", 1)[-1] else ename
            if ename == "/".join(rest):
                return o, s, "inside " + cpath, {"c": cpath, "i": ix, "t": None, "eo": o, "es": s}
            n = len(es.split("/"))
            # the image names these entries I_F_FACE01SPR.SPR while mod folders say i_f_face01: accept both
            names = [es.split("/")]
            if es.endswith("SPR"):
                names.append((es[:-3].rstrip("_") ).split("/"))
            if ename.endswith(".SPR") and any(rest[:len(nm)] == nm for nm in names) and len(rest) == n + 1:
                tex = containers.get(cpath + " :: " + ename)
                if not tex:
                    return None, None, "no textures found inside %s" % ename, None
                stem = os.path.splitext(rest[-1])[0]
                if len(tex) == 1:
                    idx = 0
                elif stem[-1:].isalpha() and 0 <= ord(stem[-1].lower()) - 97 < len(tex):
                    idx = ord(stem[-1].lower()) - 97
                elif re.search(r"\d([a-z])(?:[^a-z0-9]|$)", "".join(ch for ch in stem.lower() if ord(ch) < 128)) and 0 <= ord(re.search(r"\d([a-z])(?:[^a-z0-9]|$)", "".join(ch for ch in stem.lower() if ord(ch) < 128)).group(1)) - 97 < len(tex):
                    idx = ord(re.search(r"\d([a-z])(?:[^a-z0-9]|$)", "".join(ch for ch in stem.lower() if ord(ch) < 128)).group(1)) - 97
                else:
                    return None, None, "cannot tell which of the %d textures in %s this is" % (len(tex), ename), None
                _n, to, ts = tex[idx]
                return to, ts, "texture %d of %s inside %s" % (idx + 1, ename, cpath), {"c": cpath, "i": ix, "t": idx, "eo": o, "es": s, "tex": [(a - o, b) for _n, a, b in tex]}
        return None, None, "no file %s inside %s" % ("/".join(rest), cpath), None
    return None, None, "no such file in the image", None


def mod_files(folder):
    for dp, _d, names in os.walk(folder):
        for n in sorted(names):
            p = os.path.join(dp, n)
            yield os.path.relpath(p, folder).replace(os.sep, "/"), p


def alias(rel, files):
    """Mod folders are usually named DATA, BTL ... while the image calls them DATA.CVM, BTL.CVM. Returns rel with that first part fixed."""
    parts = rel.strip("/").split("/")
    up = parts[0].upper()
    if not up.endswith(".CVM") and ("/" + up + ".CVM") in {"/" + k.split("/")[1] for k in files if k.count("/") >= 2}:
        parts[0] = parts[0] + ".CVM"
    return "/".join(parts)


def swz(i):
    """The PS2 swaps bits 3 and 4 of a 256-colour palette index."""
    return (i & 0xE7) | ((i & 0x08) << 1) | ((i & 0x10) >> 1)


def tmx_convertible(orig_size, mod_size):
    """True when a 32-bit texture (64-byte header + 4 bytes a pixel) can be turned into the original's 8-bit form
    (64-byte header + 1024-byte palette + a byte a pixel) with the same number of pixels, and the pixels form a square."""
    n = orig_size - 64 - 1024
    return n > 0 and mod_size == 64 + 4 * n and int(round(n ** 0.5)) ** 2 == n


W = (1.0, 1.2, 0.8, 1.6)


def _cut(hist, total):
    """Median cut of {colour: count} into at most `total` boxes. Returns (palette, {colour: palette position})."""
    cols = list(hist)
    cnt = [hist[c] for c in cols]

    def stats(ids):
        n = sum(cnt[i] for i in ids)
        mean = [sum(cols[i][c] * cnt[i] for i in ids) / n for c in range(4)]
        var = [sum(cnt[i] * (cols[i][c] - mean[c]) ** 2 for i in ids) * W[c] ** 2 for c in range(4)]
        k = max(range(4), key=lambda c: var[c])
        return sum(var), k, mean
    first = list(range(len(cols)))
    boxes = [[first] + list(stats(first))]
    while len(boxes) < total:
        bi = max(range(len(boxes)), key=lambda j: boxes[j][1] if len(boxes[j][0]) > 1 else -1)
        ids, sse, k, mean = boxes.pop(bi)
        if len(ids) < 2 or sse == 0:
            boxes.append([ids, 0, k, mean])
            break
        ids.sort(key=lambda i: cols[i][k])
        half = sum(cnt[i] for i in ids) / 2
        run, cut = 0, 1
        for j, i in enumerate(ids):
            run += cnt[i]
            if run >= half:
                cut = min(max(j + 1, 1), len(ids) - 1)
                break
        for part in (ids[:cut], ids[cut:]):
            boxes.append([part] + list(stats(part)))
    pal = [tuple(int(round(v)) for v in bx[3]) for bx in boxes]
    which = {}
    for k, bx in enumerate(boxes):
        for i in bx[0]:
            which[cols[i]] = k
    if len(hist) * len(pal) < 600000:       # one k-means step when it is quick
        sums = [[0, 0, 0, 0, 0] for _ in pal]
        for c, n in hist.items():
            best, bd = 0, 1e18
            for k, q in enumerate(pal):
                d = W[0] * (c[0] - q[0]) ** 2 + W[1] * (c[1] - q[1]) ** 2 + W[2] * (c[2] - q[2]) ** 2 + W[3] * (c[3] - q[3]) ** 2
                if d < bd:
                    best, bd = k, d
            which[c] = best
            s = sums[best]
            for ch in range(4):
                s[ch] += c[ch] * n
            s[4] += n
        pal = [tuple(int(round(s[ch] / s[4])) for ch in range(4)) if s[4] else q for s, q in zip(sums, pal)]
    return pal, which


def quantize(pixels, colours=256):
    """Colour reduction for portraits and other art with soft, partly transparent edges. pixels: list of (r, g, b, a), a 0..128.
    Returns (palette of (r,g,b,a), one palette index per pixel). Median cut on the distinct colours weighted by how often they occur
    (green counts a little more, alpha a lot), one k-means step when quick. Fully transparent pixels get their own entry with alpha 0."""
    from collections import Counter
    edge = [p for p in pixels if 12 <= p[3] < 128]
    ec = tuple(sum(p[c] for p in edge) // len(edge) for c in range(3)) if edge else (0, 0, 0)
    fixed = []
    for r, g, b, a in pixels:
        if a < 12:                                   # haze you cannot see: fully transparent, so no faint box around the art
            fixed.append((ec[0], ec[1], ec[2], 0))
        elif a >= 124:
            fixed.append((r, g, b, 128))
        else:
            a = (a + 8) // 16 * 16                   # fewer alpha steps on the soft edge
            if a <= 32:                              # barely visible: one smooth colour, not speckle
                r, g, b = ec
            fixed.append((r, g, b, min(a, 128)))
    has_clear = any(p[3] == 0 for p in fixed)
    hist = Counter(p for p in fixed if p[3] > 0)
    total = colours - 1 if has_clear else colours
    if not hist:
        return [(ec[0], ec[1], ec[2], 0)] * colours, [0] * len(fixed)
    pal, where = _cut(hist, max(1, min(total, len(hist))))
    clear = len(pal)
    if has_clear:
        pal.append((ec[0], ec[1], ec[2], 0))
    pal += [(0, 0, 0, 0)] * (colours - len(pal))
    return pal, [clear if p[3] == 0 else where[p] for p in fixed]


def tmx_to_8bit(orig, mod):
    """Rebuild a 32-bit texture in the original's 8-bit form: the original's 64-byte header, a palette made from the mod's own colours
    (256 of them), one index a pixel. Whether the original stores its palette in the PS2's swapped order is read off the original
    (the way that makes its picture smoother)."""
    n = len(orig) - 64 - 1024
    side = int(round(n ** 0.5))
    pal = [tuple(orig[64 + 4 * k:68 + 4 * k]) for k in range(256)]
    idx = orig[64 + 1024:64 + 1024 + n]

    def roughness(order):
        tv = 0
        for y in range(0, side - 1, 2):
            for x in range(0, side - 1, 2):
                a = pal[order(idx[y * side + x])]
                b = pal[order(idx[y * side + x + 1])]
                c = pal[order(idx[(y + 1) * side + x])]
                tv += sum(abs(a[k] - b[k]) + abs(a[k] - c[k]) for k in range(3))
        return tv
    swapped = roughness(swz) < roughness(lambda i: i)
    pixels = [tuple(mod[64 + 4 * i:68 + 4 * i]) for i in range(n)]
    newpal, newidx = quantize(pixels)
    out = bytearray(orig[:64])
    table = bytearray(1024)
    for k, col in enumerate(newpal):
        pos = swz(k) if swapped else k
        table[4 * pos:4 * pos + 4] = bytes(col)
    out += table + bytes(newidx)
    return bytes(out)


def explode(iso, o, s, entries, path):
    """A mod that ships a whole container (BIN/PAK/PAC) of the same size: returns the entries that differ from the disc as in-place
    items, so another mod can change other entries of the same container (the merge Aemulus does). None when the layout differs."""
    if os.path.getsize(path) != s:
        return None
    with open(path, "rb") as f:
        mod = f.read()
    r = U.analyse_pak(U.Window(io.BytesIO(mod), 0, len(mod)))
    if not r["ok"] or len(r["entries"]) != len(entries):
        return None
    out = []
    with open(iso, "rb") as f:
        for (name, elen), st, (ename, eo, es) in zip(r["entries"], r["starts"], entries):
            if elen != es or st + 256 + elen > len(mod) or o + st + 256 != eo:
                return None
            new = mod[st + 256:st + 256 + elen]
            f.seek(eo)
            if f.read(es) != new:
                out.append((ename, eo, es, new))
    return out


def plan(iso, folder, move=False, loc=None):
    files, containers, recs = loc or locate(iso)
    layouts = {}
    out = []
    for rel, p in mod_files(folder):
        rel2 = alias(rel, files) if len(rel.split("/")) > 1 else rel
        o, s, what, tgt = resolve(rel2, files, containers)
        size = os.path.getsize(p)
        key = rel2.upper()
        rec = recs.get("/" + key.strip("/")) if what == "whole file" else None
        if o is None:
            out.append({"rel": rel, "path": p, "ok": False, "why": what, "key": key})
        elif rec and (size > s or move):
            out.append({"rel": rel, "path": p, "ok": True, "move": True, "rec": rec, "offset": o, "size": size, "orig": s, "what": what, "key": key})
        elif size > s and tgt and (tgt["t"] is not None or rel.lower().endswith(".tmx")) and tmx_convertible(s, size):
            it = {"rel": rel, "path": p, "ok": True, "offset": o, "size": s, "orig": s, "convert": True,
                  "what": what + ", reduced to 256 colours to fit", "key": key}
            out.append(it)
        elif size > s and not tgt:
            out.append({"rel": rel, "path": p, "ok": False, "why": "is %d bytes, the original is %d: too big" % (size, s), "key": key})
        elif size > s:
            c = tgt["c"]
            if c not in recs:
                out.append({"rel": rel, "path": p, "ok": False, "why": "is %d bytes, the original is %d, and its container sits inside another file" % (size, s), "key": key})
                continue
            if c not in layouts:
                try:
                    with open(iso, "rb") as f:
                        f.seek(locate_offset(files, c))
                        layouts[c] = P.container_layout(f.read(files[c][1]), guess=True)
                    layouts[c] = True
                except (P.ToolError, OSError) as e:
                    layouts[c] = str(e)
            if layouts[c] is not True:
                out.append({"rel": rel, "path": p, "ok": False, "why": "is %d bytes, the original is %d, and its container cannot be rebuilt (%s)" % (size, s, layouts[c]), "key": key})
                continue
            tgt = dict(tgt, rec=recs[c], co=files[c][0], cs=files[c][1])
            out.append({"rel": rel, "path": p, "ok": True, "grow": True, "tgt": tgt, "size": size, "orig": s, "what": what + " (container rebuilt)", "key": key})
        else:
            if what == "whole file" and size == s and ("/" + key.strip("/")) in containers:
                try:
                    parts = explode(iso, o, s, containers["/" + key.strip("/")], p)
                except Exception:
                    parts = None
                if parts is not None:
                    for ename, eo, es, data in parts:
                        out.append({"rel": rel + " :: " + ename, "path": p, "ok": True, "offset": eo, "size": es, "orig": es, "data": data,
                                    "what": "changed entry %s of the whole file" % ename, "key": key + " :: " + ename})
                    if not parts:
                        out.append({"rel": rel, "path": p, "ok": True, "offset": o, "size": 0, "orig": s, "data": b"", "what": "same as the disc", "key": key})
                    continue
            it = {"rel": rel, "path": p, "ok": True, "offset": o, "size": size, "orig": s, "what": what, "key": key}
            if tgt and tgt["c"] in recs:
                it["tgt"] = dict(tgt, rec=recs[tgt["c"]], co=files[tgt["c"]][0], cs=files[tgt["c"]][1])
            out.append(it)
    return out


def locate_offset(files, c):
    return files[c][0]


def spr_apply(spr, tex, repl):
    """New .SPR bytes with textures {index: bytes} replaced. tex: [(offset inside the sprite file, size)] in order. Values in the
    parts that are not textures (header, gaps, tail) that pointed at a texture start or end, or at the file size, are moved to match."""
    out = bytearray()
    new_at = {}
    spans = []          # parts that are not texture data, in the new file
    pos = 0
    for k, (ro, sz) in enumerate(tex):
        start = len(out)
        out += spr[pos:ro]
        spans.append((start, len(out)))
        new_at[ro] = len(out)
        body = repl.get(k)
        if body is None:
            body = spr[ro:ro + sz]
        elif sz % 16 == 0 and len(body) % 16:
            body += b"\0" * (-len(body) % 16)
        out += body
        pos = ro + sz
        new_at[pos] = len(out)
    start = len(out)
    out += spr[pos:]
    spans.append((start, len(out)))
    new_at.setdefault(len(spr), len(out))
    new_at.setdefault(len(spr) - 4, len(out) - 4)
    for a, b in spans:
        for q in range((a + 3) // 4 * 4, b - 3, 4):
            v = struct.unpack_from("<I", out, q)[0]
            if v > 0 and v in new_at and new_at[v] != v:
                struct.pack_into("<I", out, q, new_at[v])
    return bytes(out)


def rebuild_for(iso, group):
    """group: items whose tgt is in the same container. Returns the new container bytes."""
    t0 = group[0]["tgt"]
    with open(iso, "rb") as f:
        f.seek(t0["co"])
        data = f.read(t0["cs"])
    lay = P.container_layout(data, guess=True)
    repl = {}
    sprs = {}
    for it in group:
        body = open(it["path"], "rb").read()
        t = it["tgt"]
        if t["t"] is None:
            repl[t["i"]] = body
        else:
            sprs.setdefault(t["i"], (t, {}))[1][t["t"]] = body
    for i, (t, textures) in sprs.items():
        eo = t["eo"] - t["co"]
        spr = data[eo:eo + t["es"]]
        repl[i] = spr_apply(spr, t["tex"], textures)
    return P.rebuild_container(data, lay, repl)


def flatten(ents):
    """ents: (offset, bytes) in priority order, later wins. Returns non-overlapping (offset, bytes) pieces in offset order."""
    import bisect
    starts, segs = [], {}                      # segs: start -> bytes
    for off, data in ents:
        if not data:
            continue
        end = off + len(data)
        i = bisect.bisect_right(starts, off) - 1
        if i >= 0 and starts[i] + len(segs[starts[i]]) <= off:
            i += 1
        i = max(i, 0)
        new_starts = []
        j = i
        while j < len(starts) and starts[j] < end:
            s0 = starts[j]; d0 = segs.pop(s0); e0 = s0 + len(d0)
            if s0 < off:
                segs[s0] = d0[:off - s0]; new_starts.append(s0)
            if e0 > end:
                segs[end] = d0[end - s0:]; new_starts.append(end)
            j += 1
        starts[i:j] = new_starts
        segs[off] = data
        bisect.insort(starts, off)
    return [(s, segs[s]) for s in starts]


def write_overlay(items, iso_size, out_path, iso=None):
    """items: usable plan items. Writes the .ovl file; returns the number of entries."""
    ents, _end = entries_for(items, iso_size, iso)
    ents = flatten(ents)                       # mods that touch the same bytes: the later item wins
    tmp = out_path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(MAGIC + struct.pack("<I", len(ents)))
        for off, data in ents:
            f.write(struct.pack("<QI", off, len(data)) + data)
    os.replace(tmp, out_path)
    return len(ents)


def mod_root(folder, files):
    """Finds the folder inside an unpacked download that holds DATA / BTL / ... (zips often add a top folder). Returns it or None."""
    tops = {k.split("/")[1][:-4] if k.split("/")[1].endswith(".CVM") else k.split("/")[1] for k in files if k.count("/") >= 2}
    tops |= {t + ".CVM" for t in tops}
    best = None
    for dp, dn, _fn in os.walk(folder):
        depth = dp[len(folder):].count(os.sep)
        if depth > 4:
            dn[:] = []
            continue
        if any(d.upper() in tops for d in dn):
            if best is None or depth < best[0]:
                best = (depth, dp)
    return best[1] if best else None


def free_tail(iso):
    """The unused zero-filled sectors at the end of the disc volume, after the last file: (first byte, end byte), or None.
    A moved file is put there first: the game does not accept a start sector beyond the end of the volume (the PC window never
    asked for a file placed after the end of the image), but it reads anything inside it."""
    try:
        with open(iso, "rb") as f:
            outer = U.Window(f, 0, os.fstat(f.fileno()).st_size)
            ents = U.list_files(outer)
            if not ents:
                return None
            start = max(e["lba"] + (e["size"] + U.SECTOR - 1) // U.SECTOR for e in ents)
            f.seek(16 * U.SECTOR + 80)
            vol = struct.unpack("<I", f.read(4))[0]
            vol = min(vol, os.fstat(f.fileno()).st_size // U.SECTOR)
            s = start
            while s < vol:
                f.seek(s * U.SECTOR)
                chunk = f.read(min(64, vol - s) * U.SECTOR)
                if not chunk:
                    break
                if any(chunk):
                    for k in range(0, len(chunk), U.SECTOR):
                        if any(chunk[k:k + U.SECTOR]):
                            return (start * U.SECTOR, (s + k // U.SECTOR) * U.SECTOR) if s + k // U.SECTOR > start else None
                s += len(chunk) // U.SECTOR
            return (start * U.SECTOR, vol * U.SECTOR) if vol > start else None
    except (OSError, struct.error, Exception):
        return None


def pnach_data_pokes(program, text):
    """Data writes of a PCSX2 .pnach (patch=1,EE,ADDR,word|short|byte|extended,VALUE) as whole-word pokes for the PC window (PS2_POKE).
    The window can only write words, so each touched word is read from the program image (which holds the starting values of the data),
    changed, and written back. `extended` takes its size from the top digit of the address (0 byte, 1 half word, 2 word).
    Returns ([(address, word)], [messages]). Lines that write outside the program image are listed in the messages and skipped."""
    segs = []
    if program[:4] == b"\x7fELF":
        phoff, phsz, phn = struct.unpack_from("<I", program, 28)[0], struct.unpack_from("<H", program, 42)[0], struct.unpack_from("<H", program, 44)[0]
        for k in range(phn):
            t, off, va, _pa, fs, _ms = struct.unpack_from("<6I", program, phoff + k * phsz)
            if t == 1:
                segs.append((off, fs, va))
    words, notes = {}, []
    for line in text.splitlines():
        line = line.split("//")[0].strip()
        m = re.match(r"patch=\d+,EE,([0-9A-Fa-f]{1,8}),(word|short|byte|extended),([0-9A-Fa-f]+)$", line)
        if not m:
            continue
        addr, kind, val = int(m.group(1), 16), m.group(2), int(m.group(3), 16)
        if kind == "extended":
            size = (1, 2, 4)[min(addr >> 28, 2)]
            addr &= 0x0FFFFFFF
        else:
            size = {"byte": 1, "short": 2, "word": 4}[kind]
        for i in range(size):
            a = addr + i
            w = a & ~3
            if w not in words:
                off = next((o + w - v for o, fs, v in segs if v <= w and w + 4 <= v + fs), None)
                if off is None:
                    notes.append("address %08X is not inside the program image, line skipped" % addr)
                    break
                words[w] = bytearray(program[off:off + 4])
            words[w][a - w] = (val >> (8 * i)) & 0xFF
    return [(a, struct.unpack("<I", bytes(b))[0]) for a, b in sorted(words.items())], notes


def letterbox_pokes(program, mod_folder):
    """Simply Better FMVs removes the black bars from seven cutscenes, so those movies are 640x368 instead of 640x448 and the game must be told:
    its LetterBoxBe-Gone cheat changes a flag and the expected height in the game's movie table (data, no code). Applies the data writes of every
    cheats/*letterbox*.pnach of the mod folder."""
    out, notes = [], []
    for dp, _d, names in os.walk(mod_folder):
        if os.path.basename(dp).lower() != "cheats":
            continue
        for n in sorted(names):
            if n.lower().endswith(".pnach") and "letterbox" in n.lower():
                with open(os.path.join(dp, n), errors="replace") as f:
                    pk, nt = pnach_data_pokes(program, f.read())
                out += pk
                notes += nt
    return out, notes

LIMIT_SECTORS = (1 << 21) - 1     # a file inside a CVM must end before this sector of the CVM (4 GB): tested 27 Oct 2026, a movie placed beyond it
                                  # (CVM sector 2,145,346) made the PC window stall right after start-up, while files up to sector 1,88x,xxx worked
UNFIT = []                        # keys of moved files that could not be placed (filled by entries_for); they keep their place on the disc


def pack_extents(extents, needs):
    """Places files into free `extents` ([(first sector, end sector)]). needs: [(key, sectors, limit_end)]: no file may end after its own limit_end
    (None = no limit). Smallest file first, best fit, each extent filled from its start, so when the space runs short the biggest files are
    the ones left out. Returns ({key: first sector}, [keys that did not fit])."""
    free = []
    for a, b in sorted(extents):
        if b > a:
            if free and free[-1][1] >= a:       # next to each other: one extent
                free[-1][1] = max(free[-1][1], b)
            else:
                free.append([a, b])
    placed, out = {}, []
    for key, n, lim in sorted(needs, key=lambda k: (k[1], str(k[0]))):
        best = None
        for e in free:
            room = (e[1] if lim is None else min(e[1], lim)) - e[0]
            if room >= n and (best is None or room < best[0]):
                best = (room, e)
        if best is None:
            out.append(key)
            continue
        e = best[1]
        placed[key] = e[0]
        e[0] += n
    return placed, out


MOVES = []      # filled by entries_for: one dict per moved file (old and new start sector and size), see table_pokes


def table_pokes(program, moves):
    """The game keeps a table of the files it loads: size (4 bytes), 0 (4 bytes), start sector inside its CVM (4 bytes), then the name.
    It reads a file from those numbers, not from the directory, so a moved file also needs its table entry changed.
    program: the bytes of the game's boot program (an ELF). Returns ([(address, value)], [messages])."""
    segs = []
    if program[:4] == b"\x7fELF":
        phoff, phsz, phn = struct.unpack_from("<I", program, 28)[0], struct.unpack_from("<H", program, 42)[0], struct.unpack_from("<H", program, 44)[0]
        for k in range(phn):
            t, off, va, _pa, fs, _ms = struct.unpack_from("<6I", program, phoff + k * phsz)
            if t == 1:
                segs.append((off, fs, va))
    pokes, notes = [], []
    for m in moves:
        pat = struct.pack("<III", m["old_size"], 0, m["old_lba"])
        hits, at = [], program.find(pat)
        while at != -1:
            hits.append(at)
            at = program.find(pat, at + 1)
        if len(hits) != 1:
            notes.append("%s: %d table entries found (needs exactly 1), so the game will still read the old place" % (m.get("key", "?"), len(hits)))
            continue
        va = next((v + hits[0] - o for o, fs, v in segs if o <= hits[0] < o + fs), None)
        if va is None:
            notes.append("%s: table entry is not inside the program image" % m.get("key", "?"))
            continue
        pokes.append((va, m["new_size"]))
        pokes.append((va + 8, m["new_lba"]))
    return pokes, notes


def plan_moves(todo, free, end):
    """Where each moved file goes. Moved files go into the room their own old copies leave (a movie replaced by a bigger one frees its old
    place, and the old places of all the movies lie side by side), then into the unused end of the volume, then past the end of the image.
    Nothing may end beyond LIMIT_SECTORS of its CVM (see above), so what does not fit stays where it was.
    todo: items with "move" (and "data" or "path"), free: (first byte, end byte) of the unused tail or None, end: first byte past the image.
    Returns {id(item): first sector (of the whole disc)}; items missing from it did not fit."""
    S = U.SECTOR
    ext = []
    needs = []
    for i in todo:
        if i.get("move"):
            if i.get("offset") is not None and i.get("orig"):
                ext.append((i["offset"] // S, (i["offset"] + i["orig"] + S - 1) // S))
            n = len(i["data"]) if "data" in i else os.path.getsize(i["path"])
            needs.append((id(i), (n + S - 1) // S, i["rec"][1] // S + LIMIT_SECTORS))
    if free:
        ext.append((free[0] // S, free[1] // S))
    ext.append((end // S, end // S + (1 << 24)))
    placed, _no = pack_extents(ext, needs)
    return placed


def entries_for(items, iso_size, iso=None, reuse=True):
    """List of (absolute offset, bytes) to write. Moved files are appended after the end of the image
    (sector aligned) and their directory records are pointed at the new place. Containers that hold a file that grew are
    rebuilt from the original plus all edits to them (all mods together), and moved the same way."""
    out = []
    MOVES[:] = []
    end = (iso_size + U.SECTOR - 1) // U.SECTOR * U.SECTOR
    free = free_tail(iso) if iso else None      # [next free byte, end of the free area]
    free = list(free) if free else None
    reach = {}      # CVM base -> highest sector (inside that CVM) a moved file reaches
    groups = {}
    for i in items:
        if i.get("tgt"):
            groups.setdefault(i["tgt"]["c"], []).append(i)
    rebuilt = {c for c, g in groups.items() if any(x.get("grow") for x in g)}
    todo = [i for i in items if not (i.get("tgt") and i["tgt"]["c"] in rebuilt)]
    for c in sorted(rebuilt):
        g = groups[c]
        todo.append({"move": True, "rec": g[0]["tgt"]["rec"], "data": rebuild_for(iso, g), "offset": g[0]["tgt"]["co"], "orig": g[0]["tgt"]["cs"], "key": c})
    UNFIT[:] = []
    place = plan_moves(todo, free, end) if reuse and iso else None
    for i in todo:
        data = i["data"] if "data" in i else open(i["path"], "rb").read()
        if i.get("convert"):
            with open(iso, "rb") as f:
                f.seek(i["offset"])
                data = tmx_to_8bit(f.read(i["orig"]), data)
        if i.get("move"):
            rec_off, base = i["rec"]
            need = (len(data) + U.SECTOR - 1) // U.SECTOR * U.SECTOR
            if place is not None:
                if id(i) not in place:
                    UNFIT.append(i.get("key", ""))
                    continue
                at = place[id(i)] * U.SECTOR
            elif free and free[0] + need <= free[1]:
                at = free[0]
                free[0] += need
            else:
                at = end
                end += need
            lba = (at - base) // U.SECTOR
            reach[base] = max(reach.get(base, 0), lba + need // U.SECTOR)
            if i.get("offset") is not None and i.get("orig") is not None:
                MOVES.append({"key": i.get("key", ""), "base": base // U.SECTOR, "old_lba": (i["offset"] - base) // U.SECTOR, "old_size": i["orig"], "new_lba": lba, "new_size": len(data)})
            out.append((at, data + b"\0" * ((-len(data)) % U.SECTOR)))
            out.append((rec_off + 2, struct.pack("<I", lba) + struct.pack(">I", lba) + struct.pack("<I", len(data)) + struct.pack(">I", len(data))))
        else:
            out.append((i["offset"], data))
    # the game does not read beyond the volume size its CVM states (the first sector of the CVM's own volume descriptor says how big that is),
    # so a CVM that got a moved file past its old end is told it is bigger
    for base, top in reach.items():
        try:
            with open(iso, "rb") as f:
                f.seek(base + 16 * U.SECTOR)
                pvd = f.read(U.SECTOR)
            old_size = struct.unpack_from("<I", pvd, 80)[0]
            if pvd[1:6] == b"CD001" and top > old_size:
                out.append((base + 16 * U.SECTOR + 80, struct.pack("<I", top) + struct.pack(">I", top)))
        except (OSError, TypeError, struct.error):
            pass
        try:   # the same for the size the disc's directory gives the CVM file itself (the file system library may check against it)
            with open(iso, "rb") as f:
                for e in U.list_files(U.Window(f, 0, os.fstat(f.fileno()).st_size)):
                    if e["path"].upper().endswith(".CVM") and e["lba"] * U.SECTOR <= base < e["lba"] * U.SECTOR + e["size"]:
                        need_bytes = (base // U.SECTOR - e["lba"] + top) * U.SECTOR
                        if need_bytes > e["size"]:
                            out.append((e["recpos"] + 10, struct.pack("<I", need_bytes) + struct.pack(">I", need_bytes)))
                        break
        except Exception:
            pass
    return out, end


def movetest(a):
    """Moves every whole file smaller than 256 KB inside the CVMs to the end of a COPY of the image, content unchanged.
    If the game still works from that copy, the game follows moved directory entries."""
    if not a.out or not os.path.isfile(a.iso):
        sys.exit("Error: give a disc image and -o copy.iso")
    files, _c, recs = locate(a.iso)
    items = []
    with open(a.iso, "rb") as f:
        for p, (o, s) in sorted(files.items(), key=lambda kv: kv[1][0]):
            if p in recs and recs[p][1] and 0 < s < 256 * 1024:
                f.seek(o)
                items.append({"move": True, "rec": recs[p], "data": f.read(s)})
    ents, end = entries_for(items, os.path.getsize(a.iso), a.iso, reuse=False)
    if a.out.lower().endswith(".ovl"):
        with open(a.out, "wb") as f:
            f.write(MAGIC + struct.pack("<I", len(ents)))
            for off, data in ents:
                f.write(struct.pack("<QI", off, len(data)) + data)
    else:
        shutil.copyfile(a.iso, a.out)
        with open(a.out, "r+b") as f:
            for off, data in ents:
                if off > f.seek(0, 2):
                    f.write(b"\0" * (off - f.tell()))
                f.seek(off)
                f.write(data)
    print("moved %d files (%d MB) to the end of %s" % (len(items), (end - os.path.getsize(a.iso)) // 1048576, a.out))


def main():
    ap = argparse.ArgumentParser(description="Locate a mod's loose files inside a disc image.")
    ap.add_argument("mode", choices=["check", "overlay", "apply", "movetest", "find", "peek", "tint", "reads"])
    ap.add_argument("iso")
    ap.add_argument("folder", nargs="*", help="one or more mod folders (later ones win)")
    ap.add_argument("-o", "--out")
    ap.add_argument("--move", action="store_true", help="test aid: also move whole files that would fit, to the end of the image")
    a = ap.parse_args()
    if a.mode == "movetest":
        return movetest(a)
    if a.mode == "reads":
        # py p3fes_modmap.py reads game.iso active.ovl.reads.log   which files of the disc the game read, in the order it first touched them
        import bisect
        if not a.folder or not os.path.isfile(a.folder[0]):
            sys.exit("Error: give the disc image and the .reads.log file.")
        files, _c, _r = locate(a.iso)
        spans = sorted((o // U.SECTOR, (o + s + U.SECTOR - 1) // U.SECTOR, p) for p, (o, s) in files.items() if s)
        starts = [x[0] for x in spans]
        iso_sectors = os.path.getsize(a.iso) // U.SECTOR
        seen, order = {}, []
        for line in open(a.folder[0]):
            w = line.split()
            if len(w) < 5 or w[1] != "sector":
                continue
            sec, cnt = int(w[2]), int(w[4])
            names = []
            if sec >= iso_sectors:
                names = ["(appended mod data)"]
            else:
                k = max(0, bisect.bisect_right(starts, sec) - 1)
                while k < len(spans) and spans[k][0] < sec + cnt:
                    if spans[k][1] > sec:
                        names.append(spans[k][2])
                    k += 1
                if not names:
                    names = ["(outside any file)"]
            for nm in names:
                if nm not in seen:
                    seen[nm] = [0, 0, w[0]]
                    order.append(nm)
                seen[nm][0] += 1
                seen[nm][1] += cnt
        shown = [n for n in order if "BP_ALL" in n or n.startswith("(")]
        for n in shown:
            print("%s  %6d reads %8d sectors  %s" % (seen[n][2], seen[n][0], seen[n][1], n))
        print("%d files read in all; showing BP_ALL files and mod data (first read time, reads, sectors)" % len(order))
        print("last 12 files first read:")
        for n in order[-12:]:
            print("%s  %6d reads %8d sectors  %s" % (seen[n][2], seen[n][0], seen[n][1], n))
        return
    if a.mode == "tint":
        # py p3fes_modmap.py tint game.iso -o OUTFOLDER [--move]   makes a test mod from YOUR disc: every battle-panel portrait
        # texture with its colours turned red (--move also makes each texture 16 bytes bigger, which forces the rebuild path)
        if not a.out:
            sys.exit("Error: -o OUTFOLDER is needed.")
        files, containers, _r = locate(a.iso)
        n = 0
        needle = (a.folder[0] if a.folder else "/PANEL/").upper()
        with open(a.iso, "rb") as f:
            for cp in sorted(containers):
                if " :: " in cp or needle not in cp or not cp.endswith(".BIN"):
                    continue
                for ename, o, s in containers[cp]:
                    tex = containers.get(cp + " :: " + ename)
                    if not ename.endswith(".SPR") or not tex:
                        continue
                    for k, (_n, to, ts) in enumerate(tex):
                        f.seek(to)
                        d = bytearray(f.read(ts))
                        if ts != 17472:
                            continue
                        for q in range(64, 64 + 1024, 4):
                            d[q + 1] //= 4
                            d[q + 2] //= 4
                            d[q] = 255
                        if a.move:
                            d += b"\0" * 16
                        stem = os.path.splitext(ename)[0]
                        dest = os.path.join(a.out, *(cp.strip("/")[:-4].split("/") + stem.split("/") + ["t%s.tmx" % chr(97 + k)]))
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with open(dest, "wb") as g:
                            g.write(d)
                        n += 1
        print("wrote %d red test textures into %s" % (n, a.out))
        return
    if a.mode == "peek":
        # py p3fes_modmap.py peek game.iso NAME   shows the start of the first file or container entry whose path ends with NAME,
        # and where embedded TMX0 textures start (a layout survey; nothing is written)
        files, containers, _r = locate(a.iso)
        want = a.folder[0].upper()
        hit = None
        for p in sorted(files):
            if p.endswith(want):
                hit = (p, files[p][0], files[p][1])
                break
        if not hit:
            for cp in sorted(containers):
                for ename, o, s in containers[cp]:
                    if (cp + "/" + ename).endswith(want):
                        hit = (cp + " :: " + ename, o, s)
                        break
                if hit:
                    break
        if not hit:
            sys.exit("Nothing found ending with " + want)
        name, off, size = hit
        with open(a.iso, "rb") as f:
            f.seek(off)
            data = f.read(size)
        print("%s  %d bytes" % (name, size))
        for i in range(0, min(len(data), 256), 16):
            row = data[i:i + 16]
            print("%04X  %s  %s" % (i, " ".join("%02X" % b for b in row).ljust(47), "".join(chr(b) if 32 <= b < 127 else "." for b in row)))
        at = data.find(b"TMX0")
        while at != -1:
            st = at - 8
            print("TMX0 at %d (file would start at %d, header says size %d)" % (at, st, struct.unpack_from("<I", data, st + 4)[0] if st >= 0 else -1))
            at = data.find(b"TMX0", at + 4)
        return
    if a.mode == "find":
        # py p3fes_modmap.py find game.iso TEXT [TEXT...]   lists files and container entries whose path contains the text
        files, containers, _r = locate(a.iso)
        n = 0
        for word in a.folder:
            w = word.upper()
            for p in sorted(files):
                if w in p:
                    print("FILE  %s  (%d bytes)" % (p, files[p][1]))
                    n += 1
            for cp in sorted(containers):
                for ename, _o, s in containers[cp]:
                    if w in (cp + "/" + ename):
                        print("INSIDE %s :: %s  (%d bytes)" % (cp, ename, s))
                        n += 1
            if n > 60:
                break
        print("%d lines" % n)
        return
    if not a.folder or not os.path.isfile(a.iso) or not all(os.path.isdir(f) for f in a.folder):
        sys.exit("Error: give a disc image file and a mod folder.")
    if a.mode != "check" and not a.out:
        sys.exit("Error: -o is needed for this mode.")
    try:
        items = []
        seen = {}
        for fo in a.folder:
            for it in plan(a.iso, fo, a.move):
                if it["rel"].upper() in seen:
                    items[seen[it["rel"].upper()]] = it
                else:
                    seen[it["rel"].upper()] = len(items)
                    items.append(it)
    except U.ToolError as e:
        sys.exit("Error: %s" % e)
    good = [i for i in items if i["ok"]]
    for i in items:
        if i["ok"] and i.get("grow"):
            print("OK   %s -> grows (%d bytes, was %d): %s" % (i["rel"], i["size"], i["orig"], i["what"]))
        elif i["ok"] and i.get("move"):
            print("OK   %s -> moved to the end of the image (%d bytes, was %d), %s" % (i["rel"], i["size"], i["orig"], i["what"]))
        elif i["ok"] and i.get("convert"):
            print("OK   %s -> offset 0x%X, reduced to 256 colours to fit the original's %d bytes, %s" % (i["rel"], i["offset"], i["orig"], i["what"]))
        elif i["ok"]:
            note = "same size" if i["size"] == i["orig"] else "smaller (%d of %d bytes)" % (i["size"], i["orig"])
            print("OK   %s -> offset 0x%X, %s, %s" % (i["rel"], i["offset"], note, i["what"]))
        else:
            print("SKIP %s: %s" % (i["rel"], i["why"]))
    print("%d of %d files can be put in place." % (len(good), len(items)))
    files, _c2, _r2 = locate(a.iso)
    per = {}
    for i in good:
        if i.get("tgt"):
            c = i["tgt"]["c"]
            per.setdefault(c, [0, 0])
            per[c][0] += 1
            per[c][1] += 1 if i.get("grow") else 0
    for c, (n, g) in sorted(per.items()):
        co, cs = (files[c][0], files[c][1]) if c in files else (0, 0)
        print("ARCHIVE %s: %d changed files%s (on the disc at sector %d, %d sectors)" % (c, n, ", rebuilt and moved" if g else ", in place", co // U.SECTOR, (cs + 2047) // 2048))
    if a.mode == "check":
        return
    if not good:
        sys.exit("Nothing to write.")
    ents, end = entries_for(good, os.path.getsize(a.iso), a.iso)
    if a.mode == "overlay":
        with open(a.out, "wb") as f:
            f.write(MAGIC + struct.pack("<I", len(ents)))
            for off, data in ents:
                f.write(struct.pack("<QI", off, len(data)) + data)
        print("wrote %s" % a.out)
        return
    if os.path.abspath(a.out) == os.path.abspath(a.iso):
        sys.exit("Error: the output must be a different file from the disc image.")
    shutil.copyfile(a.iso, a.out)
    with open(a.out, "r+b") as f:
        for off, data in ents:
            if off > f.seek(0, 2):
                f.write(b"\0" * (off - f.tell()))
            f.seek(off)
            f.write(data)
    print("wrote %s (a modified COPY; the original is unchanged)" % a.out)


if __name__ == "__main__":
    main()
