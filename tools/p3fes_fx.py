#!/usr/bin/env python3
"""Survey of the .BED (BED4) files, which look like battle effect data (floats: positions, colours, timings).

  py p3fes_fx.py survey extracted        write fx_survey.txt: layout census, record size guesses, word tables of a few files
  py p3fes_fx.py dump FILE [-b N] [-s START] [-n COUNT]   print one blob as words (hex, float or integer)
  py p3fes_fx.py show FILE                 print the effect elements of one file (names, transforms, parameter blocks)
  py p3fes_fx.py nodes extracted           write fx_nodes.txt: census of effect element types and their parameter blocks

Reads only your own files; the report holds numbers, not game content beyond short word tables of a few files.
"""
import argparse, collections, glob, math, os, struct, sys

ROWS1, ROWS2, ROW = 0x1C, 0x330, 24


def walk(root):
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            if fn.lower().endswith(".bed"):
                yield os.path.join(dp, fn)


def parse_bed(d):
    """Return dict: header numbers, rows (type, offset, flags) for used rows, blobs [(start, end)]."""
    if d[:4] != b"BED4" or len(d) < 0x630:
        return None
    rows = []
    for base in (ROWS1, ROWS2):
        for r in range(32):
            o = base + ROW * r
            t, off, fl = struct.unpack_from("<3I", d, o)
            if t != 0xFE:
                rows.append((t, off, fl, struct.unpack_from("<3I", d, o + 12)))
    hdr1 = struct.unpack_from("<5I", d, 8)
    hdr2 = struct.unpack_from("<5I", d, 0x31C)
    offs = sorted(set(r[1] for r in rows if 0 < r[1] <= len(d)))
    blobs = [(a, b) for a, b in zip(offs, offs[1:] + [len(d)])]
    return {"hdr1": hdr1, "hdr2": hdr2, "rows": rows, "blobs": blobs}


def words(d, start, end):
    n = (end - start) // 4
    return struct.unpack_from("<%dI" % n, d, start) if n > 0 else ()


def as_float(w):
    x = struct.unpack("<f", struct.pack("<I", w))[0]
    return x if math.isfinite(x) and (x == 0 or 1e-4 <= abs(x) <= 1e7) else None


def classify(w):
    if w == 0:
        return "zero"
    if w == 0xFFFFFFFF:
        return "none"
    f = as_float(w)
    if w < 0x10000:
        return "int"
    return "float" if f is not None else "other"


def word_table(d, start, end, limit=64):
    out = []
    ws = words(d, start, end)
    for i in range(0, min(len(ws), limit * 4), 4):
        grp = ws[i:i + 4]
        cells = []
        for w in grp:
            f = as_float(w)
            cells.append("%g" % f if f is not None and w >= 0x10000 else ("%d" % w if w < 0x10000 else "%08X" % w))
        out.append("%05X  %s | %s" % (start + 4 * i, " ".join("%08X" % w for w in grp), " ".join(cells)))
    return "\n".join(out)


def best_strides(ws, top=3):
    nz = [i for i, w in enumerate(ws) if w]
    if len(nz) < 20:
        return []
    res = []
    for s in range(2, min(129, len(ws) // 3)):
        same = sum(1 for i in nz if i + s < len(ws) and ws[i + s] == ws[i])
        res.append((same / float(len(nz)), s))
    res.sort(reverse=True)
    return res[:top]


# ---------------------------------------------------------------- effect element tree inside a blob
# Blob = root record (0x90 bytes) + N element records of 0xC0 bytes + parameter blocks.
# Root: row at +0x80 = (N, 0, 0x90, 0); row at +0x60 = (1.0, 0xFFFFFFFF, 0x80, 0).
# Element (0xC0 bytes): 16-byte rows: +0x00 and +0x10 four floats (0 0 0 1), +0x20 (1 1 1 1), +0x30 zeros, +0x40 four floats
# (position, 0 5 0 1), +0x50 (0 0 0 1), +0x60 (1.0, 0xFFFFFFFF, 0x80, 0), +0x70 four floats, +0x80 (a, b, c, 0),
# +0x90 = (offset of its parameter block from the blob start, 0, 0, then the name from +0x9C, zero ended).
ROOT, NODE = 0x90, 0xC0


def parse_nodes(d, s, e):
    """Return dict(count, nodes=[dict(index, name, offset, size, rows)], params_start) or None if the blob is not an element tree."""
    size = e - s
    if size < ROOT or struct.unpack_from("<I", d, s + 0x68)[0] != 0x80 or struct.unpack_from("<I", d, s + 0x88)[0] != 0x90:
        return None
    n = struct.unpack_from("<I", d, s + 0x80)[0]
    if n > 500 or ROOT + NODE * n > size:
        return None
    nodes = []
    for k in range(n):
        o = s + ROOT + NODE * k
        raw = d[o + 0x9C:o + NODE]
        name = raw.split(b"\0")[0].decode("latin-1")
        off = struct.unpack_from("<I", d, o + 0x90)[0]
        nodes.append({"index": k, "name": name, "offset": off, "start": o, "rows": struct.unpack_from("<48f", d, o),
                      "words": struct.unpack_from("<48I", d, o)})
    order = sorted(set(nd["offset"] for nd in nodes if ROOT + NODE * n <= nd["offset"] <= size))
    for nd in nodes:
        if nd["offset"] in order:
            i = order.index(nd["offset"])
            nd["size"] = (order[i + 1] if i + 1 < len(order) else size) - nd["offset"]
        else:
            nd["size"] = None
    return {"count": n, "nodes": nodes, "params_start": ROOT + NODE * n, "size": size}


PARAM_HEAD = 0x2C


def parse_params(d, s, tree, nd):
    """Decode the common header of an element's parameter block.
    Words: kind (0xD2 or 0xC8), value count, 0, group, header size (0x2C), body size, 0, mode, then at +0x20 the size of
    the whole block when the block is followed by another one (otherwise 0), +0x24 count of a trailing list.
    Returns None when the element has no usable block."""
    if nd.get("size") is None or nd["size"] < PARAM_HEAD:
        return None
    q = s + nd["offset"]
    w = struct.unpack_from("<12I", d, q)
    qs = struct.unpack_from("<6I", d, q + 0x30)
    stops = [(qs[0], 0.0), (qs[1], 1.0)]
    for col, pos in ((qs[2], qs[3]), (qs[4], qs[5])):
        if col:
            stops.append((col, as_float(pos) if as_float(pos) is not None else 0.0))
    return {"kind": w[0], "count": w[1], "group": w[3], "head": w[4], "body": w[5], "mode": w[7],
            "total": w[8], "tail": w[9], "style": struct.unpack_from("<I", d, q + 0x2C)[0],
            "colour_a": qs[0], "colour_b": qs[1], "colours": stops, "size": nd["size"]}


def fields(root, report_path, top=12):
    """For each element type, show every 4-byte position of the parameter block with its most common values."""
    types = collections.defaultdict(list)
    heads = collections.Counter()
    for p in sorted(glob.glob(os.path.join(root, "**", "*.BED"), recursive=True)):
        d = open(p, "rb").read()
        b = parse_bed(d)
        if not b:
            continue
        for (s, e) in b["blobs"]:
            tree = parse_nodes(d, s, e)
            if not tree:
                continue
            for nd in tree["nodes"]:
                h = parse_params(d, s, tree, nd)
                if not h:
                    continue
                heads[(nd["name"], h["kind"], h["group"], h["head"], h["body"], h["mode"])] += 1
                types[(nd["name"], nd["size"])].append(struct.unpack_from("<%dI" % (nd["size"] // 4), d, s + nd["offset"]))
    L = ["Parameter blocks by element type and block size. Each position is a 4-byte word: how many distinct values,",
         "the most common ones (as hex, plus the float reading when it is a plausible float), and the range as floats.", ""]
    for (name, size), blocks in sorted(types.items(), key=lambda kv: -len(kv[1]))[:top]:
        L.append("== %s, %d bytes, %d blocks" % (name, size, len(blocks)))
        for i in range(size // 4):
            col = [b[i] for b in blocks]
            c = collections.Counter(col)
            fl = [as_float(v) for v in col]
            fl = [f for f in fl if f is not None and abs(f) > 1e-6]
            common = ", ".join("%X%s x%d" % (v, " (%g)" % as_float(v) if as_float(v) is not None and v >= 0x10000 and abs(as_float(v)) > 1e-6 else "", n)
                               for v, n in c.most_common(4))
            rng = " range %g..%g" % (min(fl), max(fl)) if len(fl) > len(col) // 2 else ""
            L.append("  +%03X %4d distinct: %s%s" % (4 * i, len(c), common, rng))
        L.append("")
    L.append("Header combinations (name, kind, group, header size, body size, mode): count")
    for k, n in heads.most_common(40):
        L.append("  %s kind %X group %d head %X body %X mode %d: %d" % (k + (n,)) if False else
                 "  %s kind %X group %d head %X body %X mode %d: %d" % (k[0], k[1], k[2], k[3], k[4], k[5], n))
    open(report_path, "w").write("\n".join(L) + "\n")
    print("Wrote %s (%d element types)" % (report_path, len(types)))


def fmt_words(d, start, end, cols=4):
    ws = words(d, start, end)
    out = []
    for i in range(0, len(ws), cols):
        grp = ws[i:i + cols]
        cells = []
        for w in grp:
            f = as_float(w)
            cells.append("%g" % f if f is not None and w >= 0x10000 else "%d" % w if w < 0x10000 else "%08X" % w)
        out.append("  +%04X  %s | %s" % (start + 4 * i - start, " ".join("%08X" % w for w in grp), " ".join(cells)))
    return "\n".join(out)


def show(path):
    d = open(path, "rb").read()
    b = parse_bed(d)
    if not b:
        sys.exit("Not a BED4 file")
    print("%s: %d bytes, %d used rows, %d blobs" % (os.path.basename(path), len(d), len(b["rows"]), len(b["blobs"])))
    for t, off, fl, extra in b["rows"]:
        print("  row type %d -> blob at 0x%X, flags 0x%X" % (t, off, fl))
    for bi, (s, e) in enumerate(b["blobs"]):
        tree = parse_nodes(d, s, e)
        if not tree:
            print("\nblob %d at 0x%X, %d bytes: not an element tree" % (bi, s, e - s))
            continue
        print("\nblob %d at 0x%X, %d bytes: %d effect elements, parameter data from +0x%X" % (bi, s, e - s, tree["count"], tree["params_start"]))
        for nd in tree["nodes"]:
            r = nd["rows"]
            print("  element %2d  %-10s position (%g, %g, %g, %g)  rotation (%g, %g, %g, %g)  parameters at +0x%X, %s bytes" % (
                nd["index"], nd["name"], r[16], r[17], r[18], r[19], r[0], r[1], r[2], r[3], nd["offset"], nd["size"]))


def nodes_census(root, report_path):
    beds = []
    for p in walk(root):
        d = open(p, "rb").read()
        b = parse_bed(d)
        if b:
            beds.append((p, d, b))
    if not beds:
        sys.exit("No BED4 files found under %s" % root)
    by_flag = collections.defaultdict(lambda: [0, 0])
    per_name = collections.defaultdict(list)       # name -> [(size, file, blob start, node)]
    per_blob = collections.Counter()
    bad_examples = collections.defaultdict(list)
    files_with = collections.defaultdict(set)
    rowvals = collections.Counter()
    bad_off = 0
    flags_of = {}
    parent_ok = parent_bad = parent_zero = 0
    parent_bad_ex = []
    w84, w88, w94, w98, w68 = (collections.Counter() for _ in range(5))
    head_rows = collections.defaultdict(list)    # name -> first two header rows of the parameter block
    zero_off = collections.Counter()
    for p, d, b in beds:
        flag_by_off = {}
        for t, off, fl, extra in b["rows"]:
            flag_by_off.setdefault(off, fl)
        for s, e in b["blobs"]:
            fl = flag_by_off.get(s, -1)
            tree = parse_nodes(d, s, e)
            if not tree:
                by_flag[fl][1] += 1
                if len(bad_examples[fl]) < 2 and e - s >= 64:
                    bad_examples[fl].append((os.path.basename(p), s, e, d))
                continue
            by_flag[fl][0] += 1
            per_blob[tree["count"]] += 1
            for nd in tree["nodes"]:
                per_name[nd["name"]].append((nd["size"], os.path.basename(p), s, nd, d, tree))
                files_with[nd["name"]].add(p)
                if nd["size"] is None:
                    bad_off += 1
                    zero_off[(nd["name"][:7], "offset 0" if nd["offset"] == 0 else "offset outside")] += 1
                w = nd["words"]
                par = w[32]
                if par == 0:
                    parent_zero += 1
                elif par < nd["index"]:
                    parent_ok += 1
                else:
                    parent_bad += 1
                    if len(parent_bad_ex) < 6:
                        parent_bad_ex.append("%s element %d of %d has first +0x80 word %d" % (os.path.basename(p), nd["index"], tree["count"], par))
                w84[w[33]] += 1
                w88[w[34]] += 1
                w94[w[37]] += 1
                w98[w[38]] += 1
                w68[w[26]] += 1
                if nd["size"] is not None and nd["size"] >= 32:
                    q = s + nd["offset"]
                    head_rows[nd["name"]].append(struct.unpack_from("<8I", d, q))
                rowvals[tuple(round(x, 4) for x in nd["rows"][24:28])] += 1
    L = ["Effect element census: %d BED files" % len(beds), ""]
    L.append("Blobs by row flags: element tree / not an element tree")
    for fl, (ok, bad) in sorted(by_flag.items(), key=lambda kv: -sum(kv[1])):
        L.append("  flags 0x%X: %d / %d" % (fl & 0xFFFFFFFF, ok, bad))
    L.append("Elements per tree: " + ", ".join("%d x%d" % kv for kv in sorted(per_blob.items())[:25]))
    L.append("Element offsets that do not point into the blob: %d" % bad_off)
    L.append("")
    L.append("Element names: count, files, parameter block size (min / median / max, distinct sizes)")
    for name, lst in sorted(per_name.items(), key=lambda kv: -len(kv[1])):
        sz = sorted(x[0] for x in lst if x[0] is not None)
        if sz:
            L.append("  %-12s %5d  %4d files  %6d / %6d / %6d bytes, %d distinct" % (name, len(lst), len(files_with[name]), sz[0], sz[len(sz) // 2], sz[-1], len(set(sz))))
        else:
            L.append("  %-12s %5d  %4d files  (no sizes)" % (name, len(lst), len(files_with[name])))
    L.append("")
    L.append("")
    L.append("Hypothesis: the first word of the +0x80 row is the parent element number.")
    L.append("  0 (top level): %d, smaller than the element's own number: %d, not smaller: %d" % (parent_zero, parent_ok, parent_bad))
    for ex in parent_bad_ex:
        L.append("  counter-example: " + ex)
    L.append("Second word of +0x80 row: " + ", ".join("%d x%d" % kv for kv in w84.most_common(8)))
    L.append("Third word of +0x80 row: " + ", ".join("%d x%d" % kv for kv in w88.most_common(8)))
    L.append("Word at +0x94: " + ", ".join("%d x%d" % kv for kv in w94.most_common(10)))
    L.append("Word at +0x98: " + ", ".join("%d x%d" % kv for kv in w98.most_common(8)))
    L.append("Word at +0x68 (third word of the +0x60 row): " + ", ".join("0x%X x%d" % kv for kv in w68.most_common(8)))
    L.append("Elements without a usable parameter offset: " + ", ".join("%s %s x%d" % (k[0], k[1], c) for k, c in zero_off.most_common(10)))
    L.append("")
    L.append("First eight words of the parameter block per element type (the 12 most common types): distinct combinations")
    for name, lst in sorted(head_rows.items(), key=lambda kv: -len(kv[1]))[:12]:
        c = collections.Counter(tuple(x[:4]) + tuple(x[4:8]) for x in lst)
        L.append("  %s: %d blocks, %d distinct; most common: %s" % (name, len(lst), len(c), "; ".join(
            "%s x%d" % (" ".join("%X" % v for v in k), n) for k, n in c.most_common(3))))
    L.append("")
    L.append("Row +0x70 of elements (four floats), most common: " + "; ".join("%s x%d" % (k, c) for k, c in rowvals.most_common(6)))
    L.append("")
    L.append("Examples per element name (the 14 most common): the smallest parameter block and one of median size.")
    for name, lst in sorted(per_name.items(), key=lambda kv: -len(kv[1]))[:14]:
        sized = sorted((x for x in lst if x[0] is not None), key=lambda x: x[0])
        if not sized:
            continue
        for label, (size, fn, s, nd, d, tree) in (("smallest", sized[0]), ("median", sized[len(sized) // 2])):
            L.append("\n== %s (%s) in %s, element %d of %d, parameter block %d bytes at blob+0x%X" % (name, label, fn, nd["index"], tree["count"], size, nd["offset"]))
            L.append("element record:")
            L.append(fmt_words(d, nd["start"], nd["start"] + NODE))
            L.append("parameter block (first 192 bytes):")
            L.append(fmt_words(d, s + nd["offset"], s + nd["offset"] + min(size, 192)))
    L.append("\nBlobs that are not element trees (first 128 bytes), per flag value:")
    for fl, lst in sorted(bad_examples.items()):
        for fn, s, e, d in lst[:1]:
            L.append("\n== flags 0x%X: %s blob at 0x%X, %d bytes" % (fl & 0xFFFFFFFF, fn, s, e - s))
            L.append(fmt_words(d, s, min(e, s + 128)))
    text = "\n".join(L)
    open(report_path, "w").write(text + "\n")
    print(text[:3000])
    print("\nFull report written to %s" % report_path)


def survey(root, report_path):
    files = list(walk(root))
    beds = []
    for p in files:
        d = open(p, "rb").read()
        b = parse_bed(d)
        if b:
            beds.append((p, d, b))
    if not beds:
        sys.exit("No BED4 files found under %s" % root)
    L = ["BED survey: %d BED4 files of %d .bed files" % (len(beds), len(files)), ""]
    top = collections.Counter(os.path.relpath(p, root).split(os.sep)[0:3].__str__() for p, _, _ in beds)
    L.append("Per folder: " + "; ".join("%s %d" % (k, c) for k, c in top.most_common()))
    nrows = collections.Counter(len(b["rows"]) for _, _, b in beds)
    L.append("Used rows per file: " + ", ".join("%d x%d" % kv for kv in sorted(nrows.items())))
    types = collections.Counter(r[0] for _, _, b in beds for r in b["rows"])
    L.append("Row types: " + ", ".join("%d x%d" % kv for kv in sorted(types.items())))
    flags = collections.Counter(r[2] for _, _, b in beds for r in b["rows"])
    L.append("Row flags (hex): " + ", ".join("%X x%d" % kv for kv in flags.most_common(25)))
    extra = collections.Counter(r[3] for _, _, b in beds for r in b["rows"])
    L.append("Row last three words (non-zero cases): " + ", ".join("%s x%d" % (v, c) for v, c in extra.most_common(5)))
    h1 = collections.Counter(b["hdr1"] for _, _, b in beds)
    h2 = collections.Counter(b["hdr2"] for _, _, b in beds)
    L.append("Header 1 five words, most common: " + "; ".join("%s x%d" % ([hex(x) for x in k], c) for k, c in h1.most_common(6)))
    L.append("Header 2 five words, most common: " + "; ".join("%s x%d" % ([hex(x) for x in k], c) for k, c in h2.most_common(6)))
    rel = collections.Counter()
    for _, d, b in beds:
        offs = [r[1] for r in b["rows"]]
        rel["first data at 0x630" if offs and min(offs) == 0x630 else "first data elsewhere"] += 1
        rel["offsets all inside file" if all(0 < o <= len(d) for o in offs) else "offset outside file"] += 1
    L.append("Layout checks: " + ", ".join("%s x%d" % kv for kv in rel.items()))
    nblobs = collections.Counter(len(b["blobs"]) for _, _, b in beds)
    L.append("Blobs per file: " + ", ".join("%d x%d" % kv for kv in sorted(nblobs.items())))
    sizes = sorted(e - s for _, _, b in beds for s, e in b["blobs"])
    L.append("Blob sizes: min %d, median %d, max %d" % (sizes[0], sizes[len(sizes) // 2], sizes[-1]))
    pre = collections.Counter(d[s:s + 96] for _, d, b in beds for s, e in b["blobs"] if e - s >= 96)
    L.append("Blobs whose first 96 bytes are identical to another blob's: the most common prefix covers %d of %d blobs; %d distinct prefixes" % (
        pre.most_common(1)[0][1], sum(pre.values()), len(pre)))
    cls = collections.Counter()
    for _, d, b in beds:
        for s, e in b["blobs"]:
            for w in words(d, s, e):
                cls[classify(w)] += 1
    tot = float(sum(cls.values()))
    L.append("Blob words by kind: " + ", ".join("%s %.1f%%" % (k, 100 * v / tot) for k, v in cls.most_common()))
    st = collections.Counter()
    ex = {}
    for p, d, b in beds:
        for s, e in b["blobs"]:
            if e - s >= 1024:
                bs = best_strides(words(d, s, e), 1)
                if bs:
                    st[bs[0][1] * 4] += 1
                    ex.setdefault(bs[0][1] * 4, (os.path.basename(p), s, bs[0][0]))
    L.append("Best repeat distance in bytes for blobs of 1 KB or more (equal non-zero words that far apart): " +
             ", ".join("%d x%d" % kv for kv in st.most_common(10)))
    L.append("")
    # word tables: per folder group, the smallest non-trivial and a median blob
    groups = collections.defaultdict(list)
    for p, d, b in beds:
        g = os.path.relpath(p, root).split(os.sep)
        key = "/".join(g[:3]) if len(g) > 3 else "/".join(g[:-1])
        for s, e in b["blobs"]:
            if e - s >= 128 and any(words(d, s, e)):
                groups[key].append((e - s, p, s, e))
    L.append("Word tables (each row: offset, four 32-bit words in hex | the same as float or integer). One small and one median blob per folder.")
    for key, lst in sorted(groups.items()):
        lst.sort()
        pick = [lst[0]] + ([lst[len(lst) // 2]] if len(lst) > 2 else [])
        for size, p, s, e in pick:
            d = open(p, "rb").read()
            L.append("\n== %s: %s blob at 0x%X, %d bytes (first %d rows)" % (key, os.path.basename(p), s, size, 40))
            L.append(word_table(d, s, e, 40))
    text = "\n".join(L)
    open(report_path, "w").write(text + "\n")
    print(text[:3500])
    print("\nFull report written to %s" % report_path)


def dump(path, blob, start, count):
    d = open(path, "rb").read()
    b = parse_bed(d)
    if not b:
        sys.exit("Not a BED4 file")
    s, e = b["blobs"][blob]
    print("%s: %d bytes, blob %d of %d at 0x%X..0x%X" % (path, len(d), blob, len(b["blobs"]), s, e))
    print(word_table(d, s + start, e, count // 4 or 1))


def main():
    ap = argparse.ArgumentParser(description="Survey the .BED effect data files.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("survey")
    s.add_argument("folder")
    s.add_argument("-o", "--output", default="fx_survey.txt")
    sh = sub.add_parser("show")
    sh.add_argument("file")
    nd = sub.add_parser("nodes")
    nd.add_argument("folder")
    nd.add_argument("-o", "--output", default="fx_nodes.txt")
    fl = sub.add_parser("fields")
    fl.add_argument("folder")
    fl.add_argument("-o", "--output", default="fx_fields.txt")
    d = sub.add_parser("dump")
    d.add_argument("file")
    d.add_argument("-b", "--blob", type=int, default=0)
    d.add_argument("-s", "--start", type=int, default=0, help="byte offset inside the blob")
    d.add_argument("-n", "--count", type=int, default=256, help="bytes to show")
    a = ap.parse_args()
    if a.cmd == "survey":
        survey(os.path.abspath(a.folder), a.output)
    elif a.cmd == "show":
        show(a.file)
    elif a.cmd == "fields":
        fields(os.path.abspath(a.folder), a.output)
    elif a.cmd == "nodes":
        nodes_census(os.path.abspath(a.folder), a.output)
    else:
        dump(a.file, a.blob, a.start, a.count)


if __name__ == "__main__":
    main()
