#!/usr/bin/env python3
"""Survey of the field (map) data: which file types sit in the FIELD folders, how big they are and how they start.

  py p3fes_field.py survey extracted        write field_survey.txt
  py p3fes_field.py names extracted         write field_names.txt: the entry names inside the field packs, grouped by pattern
  py p3fes_field.py check extracted          write field_check.txt: tests the size rules of .FBN and .HBN files on every file
  py p3fes_field.py fbn extracted            write field_fbn.txt: every .FBN record (id word, position) of every file
  py p3fes_field.py dump FILE                print one .FBN/.HBN/.ENV/.CMR file as header and rows of words (hex and float)
  py p3fes_field.py split extracted          split every .FPC file into a folder <name>.FPC.d and write field_split.txt (what is inside)
  py p3fes_field.py rws extracted [-o DIR]    list the textures inside every .RWS file (field_rws.txt, fast); with -o also decode them and write PNG files (slow)
  py p3fes_field.py words extracted EXT     write field_words_<ext>.txt: every 4-byte position of .env/.cmr/.hbn/.fbn files with its common values

Reads only your own extracted files. The report holds file names, sizes and the first few numbers of each file type,
not the game's content.
"""
import argparse, collections, math, os, re, struct, sys

EXTRA = {".env", ".cmr", ".fbn", ".hbn"}


def ext_of(name):
    return os.path.splitext(name)[1].lower() or "(none)"


def field_files(root):
    """Files under a folder whose path contains FIELD, plus any file of the extra field types anywhere."""
    for dp, _, fns in os.walk(root):
        in_field = "field" in dp.lower().replace("\\", "/").split("/") or any(
            p.lower().startswith("field") or p.lower().startswith("f0") for p in dp.replace("\\", "/").split("/")
        )
        for fn in sorted(fns):
            if in_field or ext_of(fn) in EXTRA:
                yield os.path.join(dp, fn)


def first_words(d, n=4):
    d = d[:4 * n].ljust(4 * n, b"\0")
    return struct.unpack("<%dI" % n, d)


def survey(root, out):
    by_ext = collections.defaultdict(list)
    folders = collections.defaultdict(collections.Counter)
    for p in field_files(root):
        try:
            size = os.path.getsize(p)
            with open(p, "rb") as f:
                head = f.read(32)
        except OSError:
            continue
        e = ext_of(p)
        by_ext[e].append((p, size, head))
        folders[os.path.dirname(p)][e] += 1
    lines = ["Field data survey of %s" % root, "%d file types, %d folders" % (len(by_ext), len(folders)), ""]
    for e in sorted(by_ext, key=lambda k: -len(by_ext[k])):
        items = by_ext[e]
        sizes = sorted(s for _, s, _ in items)
        lines.append("%s: %d files, size %d / %d / %d (min / median / max)" % (e, len(items), sizes[0], sizes[len(sizes) // 2], sizes[-1]))
        magic = collections.Counter(h[:4] for _, _, h in items)
        lines.append("  first 4 bytes: " + ", ".join("%s x%d" % (m.hex() if len(m) < 4 or not m.isalnum() else m.decode(), c) for m, c in magic.most_common(6)))
        firsts = collections.Counter(first_words(h)[1] for _, _, h in items)
        lines.append("  second word: " + ", ".join("%#x x%d" % (w, c) for w, c in firsts.most_common(6)))
        for p, s, h in items[:2]:
            lines.append("  e.g. %s (%d bytes): %s" % (os.path.relpath(p, root), s, " ".join("%08x" % w for w in first_words(h, 6))))
        lines.append("")
    sigs = collections.defaultdict(list)
    for fo, c in folders.items():
        sigs[tuple(sorted(c.items()))].append(fo)
    lines.append("Folder contents (same file types together):")
    for sig, fos in sorted(sigs.items(), key=lambda kv: -len(kv[1]))[:30]:
        lines.append("  %d folders: %s    e.g. %s" % (len(fos), ", ".join("%s x%d" % kv for kv in sig), os.path.relpath(sorted(fos)[0], root)))
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("Wrote %s (%d file types)" % (out, len(by_ext)))


def pattern(name):
    """Normalise an entry name: digits become 9 (f004_002_050.FBN -> f999_999_999.FBN)."""
    return re.sub(r"\d", "9", name)


def names(root, out):
    """Group the entries of the field pack folders (*.PAC.d) by name pattern."""
    pats = collections.defaultdict(lambda: [0, 0, set(), None])
    for dp, _, fns in os.walk(root):
        if not dp.lower().endswith(".pac.d"):
            continue
        for fn in fns:
            size = os.path.getsize(os.path.join(dp, fn))
            e = pats[pattern(fn)]
            e[0] += 1
            e[1] += size > 0
            e[2].add(os.path.basename(dp))
            if e[3] is None:
                e[3] = os.path.join(os.path.basename(dp), fn)
    lines = ["Entry names inside the field packs, digits shown as 9", "pattern | entries | non-empty | folders | example", ""]
    for pat, (n, ne, fo, ex) in sorted(pats.items(), key=lambda kv: -kv[1][0]):
        lines.append("%s | %d | %d | %d | %s" % (pat, n, ne, len(fo), ex))
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("Wrote %s (%d name patterns)" % (out, len(pats)))


def kind(w):
    if w == 0:
        return "zero"
    if w == 0xFFFFFFFF:
        return "none"
    if w < 0x10000:
        return "int"
    f = struct.unpack("<f", struct.pack("<I", w))[0]
    return "float" if math.isfinite(f) and 1e-4 <= abs(f) <= 1e7 else "other"


def words(root, ext, out, limit=0x800):
    files = [p for p in field_files(root) if ext_of(p) == "." + ext.lower().lstrip(".")]
    if not files:
        raise SystemExit("no .%s files found" % ext)
    cols = collections.defaultdict(collections.Counter)
    sizes = collections.Counter()
    for p in files:
        d = open(p, "rb").read(limit)
        sizes[os.path.getsize(p)] += 1
        for i in range(len(d) // 4):
            cols[i][struct.unpack_from("<I", d, 4 * i)[0]] += 1
    lines = ["%d .%s files" % (len(files), ext), "sizes: " + ", ".join("%d x%d" % kv for kv in sizes.most_common(8)), "",
             "pos | offset | files | distinct | kinds | common values (value x count) | float range"]
    for i in sorted(cols):
        c = cols[i]
        total = sum(c.values())
        kinds = collections.Counter()
        fl = []
        for w, n in c.items():
            k = kind(w)
            kinds[k] += n
            if k == "float":
                fl.append(struct.unpack("<f", struct.pack("<I", w))[0])
        if len(c) == 1 and 0 in c:
            continue
        top = ", ".join("%#x x%d" % kv for kv in c.most_common(5))
        rng = "%.4g..%.4g" % (min(fl), max(fl)) if fl else ""
        lines.append("%d | %#x | %d | %d | %s | %s | %s" % (i, 4 * i, total, len(c), "/".join("%s %d" % kv for kv in kinds.most_common(3)), top, rng))
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("Wrote %s" % out)


def u32s(d):
    return struct.unpack("<%dI" % (len(d) // 4), d[:len(d) // 4 * 4])


def fmt(w):
    k = kind(w)
    if k == "float":
        return "%08x %-9.4g" % (w, struct.unpack("<f", struct.pack("<I", w))[0])
    return "%08x %-9s" % (w, w if k == "int" else ("-" if k == "zero" else ""))


def fits(size, need):
    """exact, or padded up to a multiple of 512"""
    return size == need or (size % 512 == 0 and (need + 511) // 512 * 512 == size)


def check(root, out):
    """Test size rules: FBN = 0x18 + count x 0x70; HBN = header + sum(count x size) over (count, size) pairs, for several pair counts."""
    fbn = collections.Counter()
    fbn_bad = []
    hbn_by_pairs = collections.defaultdict(collections.Counter)
    hbn_total = 0
    for p in field_files(root):
        e = ext_of(p)
        if e not in (".fbn", ".hbn"):
            continue
        d = open(p, "rb").read()
        if len(d) < 0x60:
            continue
        w = u32s(d[:0x60])
        if e == ".fbn":
            need = 0x18 + w[2] * 0x70
            ok = "exact" if len(d) == need else "padded to 512" if fits(len(d), need) else "other"
            fbn[ok] += 1
            if ok == "other" and len(fbn_bad) < 12:
                fbn_bad.append("  %s size %d count %d needs %d" % (os.path.relpath(p, root), len(d), w[2], need))
        else:
            hbn_total += 1
            for pairs in range(3, 12):
                need = 8 + 8 * pairs + sum(w[2 + 2 * i] * w[3 + 2 * i] for i in range(pairs))
                hbn_by_pairs[pairs]["exact" if len(d) == need else "padded" if fits(len(d), need) else "other"] += 1
    lines = ["FBN: size against 0x18 + count x 0x70: " + ", ".join("%s %d" % kv for kv in fbn.most_common())] + fbn_bad
    lines.append("")
    lines.append("HBN: %d files; size against 8 + 8 x pairs + sum(count x size), by number of (count, size) pairs:" % hbn_total)
    for pairs in sorted(hbn_by_pairs):
        lines.append("  %d pairs: %s" % (pairs, ", ".join("%s %d" % kv for kv in hbn_by_pairs[pairs].most_common())))
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("Wrote %s" % out)


def fbn_records(d):
    """Records of an .FBN: header 0x18 bytes, then count records of 0x70 bytes. Returns (id, number at +0xC, x, y, z, int at +0x60, float at +0x64)."""
    count = struct.unpack_from("<I", d, 8)[0]
    out = []
    for k in range(count):
        b = 0x18 + 0x70 * k
        if b + 0x70 > len(d):
            break
        i, v = struct.unpack_from("<If", d, b + 8)
        x, y, z = struct.unpack_from("<3f", d, b + 0x50)
        n, f = struct.unpack_from("<If", d, b + 0x60)
        out.append((i, v, x, y, z, n, f))
    return out


def fbn_table(root, out):
    lines = ["file | record | id (hex) | id | float at +0xC | x | y | z | int at +0x60 | float at +0x64"]
    ids = collections.Counter()
    nfiles = 0
    for p in field_files(root):
        if ext_of(p) != ".fbn" or os.path.getsize(p) < 0x18:
            continue
        d = open(p, "rb").read()
        nfiles += 1
        for k, (i, v, x, y, z, n, f) in enumerate(fbn_records(d)):
            ids[i] += 1
            lines.append("%s | %d | %#x | %d | %.4g | %.4g | %.4g | %.4g | %#x | %.4g" % (os.path.relpath(p, root), k, i, i, v, x, y, z, n, f))
    lines.append("")
    lines.append("%d files; id words by high part (id >> 8): %s" % (nfiles, ", ".join("%#x x%d" % kv for kv in sorted(collections.Counter(i >> 8 for i in ids.elements()).items()))))
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("Wrote %s (%d files)" % (out, nfiles))


def split(root, out):
    """Split the .FPC containers (same entry format as .PAC: 252-byte name, u32 size, data) into <file>.d folders."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from p3fes_unpack import analyse_pak, Window, safe_parts
    except ImportError:
        raise SystemExit("p3fes_unpack.py must be in the same folder as this tool")
    ok = bad = 0
    exts = collections.defaultdict(list)
    failed = []
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            if not fn.lower().endswith(".fpc"):
                continue
            path = os.path.join(dp, fn)
            size = os.path.getsize(path)
            if size < 256:
                continue
            with open(path, "rb") as f:
                view = Window(f, 0, size)
                r = analyse_pak(view)
                if not (r["ok"] and r["entries"]):
                    bad += 1
                    if len(failed) < 10:
                        failed.append("%s: %s" % (os.path.relpath(path, root), r.get("reason", "empty")))
                    continue
                ok += 1
                cdir = path + ".d"
                os.makedirs(cdir, exist_ok=True)
                used = set()
                for (name, elen), st in zip(r["entries"], r["starts"]):
                    dest = os.path.join(cdir, *safe_parts(name))
                    n = 1
                    base, ext = os.path.splitext(dest)
                    while dest.lower() in used:
                        n += 1
                        dest = "%s__%d%s" % (base, n, ext)
                    used.add(dest.lower())
                    with open(dest, "wb") as o:
                        o.write(view.read_at(st + 256, elen))
                    exts[ext_of(name)].append((elen, head4(view.read_at(st + 256, 16))))
    lines = ["Split %d .FPC files (%d could not be split)" % (ok, bad)] + failed + [""]
    for e in sorted(exts, key=lambda k: -len(exts[k])):
        items = exts[e]
        sizes = sorted(i[0] for i in items)
        magic = collections.Counter(i[1] for i in items)
        lines.append("%s: %d entries, size %d / %d / %d (min / median / max); starts: %s" % (e, len(items), sizes[0], sizes[len(sizes) // 2], sizes[-1], ", ".join("%s x%d" % kv for kv in magic.most_common(5))))
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))
    print("Wrote %s" % out)


def rws(root, out, png_dir=None, limit=0):
    """List (and optionally decode) the RenderWare texture dictionaries in the .RWS files, using the decoder of p3fes_rmd.py."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import p3fes_rmd as R
    except ImportError:
        raise SystemExit("p3fes_rmd.py must be in the same folder as this tool")
    lines = []
    nfiles = ntex = nok = nfail = 0
    sizes = collections.Counter()
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            if not fn.lower().endswith(".rws"):
                continue
            path = os.path.join(dp, fn)
            data = open(path, "rb").read()
            nfiles += 1
            try:
                off, top = R.find_stream(data)
            except R.ToolError as e:
                lines.append("%s: %s" % (os.path.relpath(path, root), e))
                continue
            texdict = next((c for c in top if c.type == 0x16), None)
            kinds = collections.Counter("%#x" % c.type for c in top)
            tex = texdict.find(0x15) if texdict else []
            lines.append("%s: %d bytes, stream at %d, top chunks %s, %d textures" % (os.path.relpath(path, root), len(data), off, dict(kinds), len(tex)))
            if nfiles % 50 == 0:
                print("  %d files ..." % nfiles, flush=True)
            for t, summ in zip(tex, R.texture_summaries(data, texdict)):
                ntex += 1
                strs = t.find(2)
                name = R.read_string(data, strs[0]) if strs else "?"
                if not png_dir or (limit and nfiles > limit):
                    st = t.find(1)
                    wd = None
                    if len(st) > 1 and st[1].size >= 28 and struct.unpack_from("<I", data, st[1].data_start)[0] == 1:
                        wd = struct.unpack_from("<4I", data, st[1].data_start + 12)
                    lines.append("   %s %s" % (name, "%dx%d, %d-bit" % (wd[0], wd[1], wd[2]) if wd else "(no size)"))
                    if wd:
                        sizes[(wd[0], wd[1])] += 1
                    continue
                try:
                    w, h, rgba = R.decode_native_texture(data, t)
                    nok += 1
                    sizes[(w, h)] += 1
                    lines.append("   %s %dx%d" % (name, w, h))
                    if png_dir and (not limit or nfiles <= limit):
                        d = os.path.join(png_dir, os.path.relpath(dp, root).replace(os.sep, "_"), fn)
                        os.makedirs(d, exist_ok=True)
                        R.write_png(os.path.join(d, name + ".png"), w, h, rgba)
                except (R.ToolError, struct.error, IndexError) as e:
                    nfail += 1
                    lines.append("   %s: cannot decode (%s)" % (name, e))
    head = ["%d .RWS files, %d textures%s" % (nfiles, ntex, " (%d decoded, %d not)" % (nok, nfail) if png_dir else " (sizes only; add -o FOLDER to decode and write PNG files)"),
            "sizes: " + ", ".join("%dx%d x%d" % (w, h, n) for (w, h), n in sizes.most_common(12)), ""]
    open(out, "w", encoding="utf-8").write("\n".join(head + lines) + "\n")
    print("\n".join(head))
    print("Wrote %s" % out)


def _fields_one(job):
    """Export every model of one field .RWS (and its textures) into its own folder. Runs in a worker process."""
    path, out_dir, textures = job
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import io, contextlib
    import p3fes_rmd as R
    rec = {"file": path, "status": "ok", "clumps": 0, "vertices": 0, "textures": 0, "problems": [], "kinds": [], "bad_tex": [], "clump_info": []}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            data = open(path, "rb").read()
            off, top = R.find_stream(data)
            nclumps = sum(1 for c in top if c.type == 0x10)
            texdict = next((c for c in top if c.type == 0x16), None)
            rec["clumps"] = nclumps
            if texdict:
                for t in texdict.find(0x15):
                    strs = t.find(2)
                    name = R.read_string(data, strs[0]) if strs else "?"
                    try:
                        parts = R.texture_parts(data, t)
                    except (R.ToolError, struct.error, IndexError) as e:
                        rec["bad_tex"].append("%s: %s" % (name, e))
                        continue
                    n = parts["rrw"] * parts["rrh"]
                    size = len(parts["stream"])
                    kind = "32-bit upload" if n * 4 == size else ("16-bit upload" if n * 2 == size else "other upload size")
                    rec["kinds"].append((parts["depth"], kind, name, parts["w"], parts["h"], parts["tbw"], parts["rrw"], parts["rrh"], size))
            if textures and texdict and not nclumps:           # pictures only, no model
                os.makedirs(out_dir, exist_ok=True)
                rec["textures"] = len(R.export_textures(data, texdict, out_dir, verbose=False))
            for ci in range(nclumps):
                try:
                    r = R.export_model(path, out_dir, False, textures and ci == 0, verbose=False, clump=ci)
                    sci = R.read_scene(data, ci)
                    rec["clump_info"].append((ci, len(sci["geos"]), len(sci["atomics"]), r["vertices"], r["materials"]))
                    rec["vertices"] += r["vertices"]
                    if ci == 0:
                        rec["textures"] = len(r["textures"])
                    for sk in r["skipped"]:
                        rec["problems"].append("clump %d skipped: %s" % (ci, sk.split(":", 1)[-1].strip()))
                except BaseException as e:
                    rec["problems"].append("clump %d failed: %s: %s" % (ci, type(e).__name__, e))
            if nclumps and not rec["vertices"]:
                rec["status"] = "empty"
    except BaseException as e:
        rec["status"] = "failed"
        rec["problems"].append("%s: %s" % (type(e).__name__, e))
    if rec["status"] == "ok" and rec["problems"]:
        rec["status"] = "partial"
    return rec


def fields(root, out, match=None, limit=0, jobs=1, textures=True):
    """Write the models and textures of every field .RWS as .obj/.mtl/.png, plus a report that holds no game content."""
    import concurrent.futures, json
    files = []
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            if fn.lower().endswith(".rws") and (not match or match.lower() in fn.lower()):
                files.append(os.path.join(dp, fn))
    files.sort()
    if limit:
        files = files[:limit]
    if not files:
        raise SystemExit("No .RWS files found in " + root + " (run the split command first)")
    work = []
    for f in files:
        parent = os.path.basename(os.path.dirname(f))
        parent = re.sub(r"\.fpc\.d$", "", parent, flags=re.I)
        work.append((f, os.path.join(out, parent, os.path.splitext(os.path.basename(f))[0]), textures))
    print("Exporting %d field files to %s with %d worker(s); progress every 25 files." % (len(work), out, jobs))
    results = []
    if jobs > 1:
        with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as ex:
            for i, rec in enumerate(ex.map(_fields_one, work, chunksize=2), 1):
                results.append(rec)
                if i % 25 == 0:
                    print("  %d / %d" % (i, len(work)))
    else:
        for i, w in enumerate(work, 1):
            results.append(_fields_one(w))
            if i % 25 == 0:
                print("  %d / %d" % (i, len(work)))
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "fields_report.json"), "w") as fh:
        json.dump(results, fh, indent=1)
    counts = collections.Counter(r["status"] for r in results)
    lines = ["Field files: %d  (%s)" % (len(results), ", ".join("%s %d" % kv for kv in sorted(counts.items())))]
    lines.append("Models (clumps): %d, vertices: %d, texture files written: %d" % (
        sum(r["clumps"] for r in results), sum(r["vertices"] for r in results), sum(r["textures"] for r in results)))
    kinds = collections.Counter((k[0], k[1]) for r in results for k in r["kinds"])
    lines += ["", "How textures are uploaded (bits per pixel, upload kind: count):"]
    for (d, k), n in sorted(kinds.items()):
        lines.append("  %d-bit, %-18s %d" % (d, k, n))
    odd = [(r["file"], k) for r in results for k in r["kinds"] if k[1] == "other upload size"]
    lines += ["", "Textures with an upload size the decoder does not know (%d); first 40:" % len(odd)]
    for f, k in odd[:40]:
        lines.append("  %s %s: %d-bit %dx%d TBW %d upload %dx%d, %d bytes" % (os.path.basename(f), k[2], k[0], k[3], k[4], k[5], k[6], k[7], k[8]))
    bad = [(r["file"], b) for r in results for b in r["bad_tex"]]
    lines += ["", "Textures that cannot be read at all (%d); first 40:" % len(bad)]
    for f, b in bad[:40]:
        lines.append("  %s %s" % (os.path.basename(f), b))
    reasons = collections.defaultdict(list)
    for r in results:
        for pr in r["problems"]:
            reasons[re.sub(r"\d+", "N", pr)].append(r["file"])
    lines += ["", "Problems with models, grouped (count, up to 3 example files):"]
    for k, v in sorted(reasons.items(), key=lambda kv: -len(kv[1])):
        lines.append("  %5d  %s" % (len(v), k))
        for f in v[:3]:
            lines.append("           " + os.path.basename(f))
    empties = [r for r in results if r["status"] == "empty"]
    lines += ["", "Files with models but no geometry (%d); first 15 (file: clumps, then per clump geometries/atomics/vertices):" % len(empties)]
    for r in empties[:15]:
        lines.append("  %s: %d clumps; %s" % (os.path.basename(r["file"]), r["clumps"],
                     " ".join("[%d: %d/%d/%d]" % (ci, g, at, v) for ci, g, at, v, m in r["clump_info"])))
    lines += ["", "What each clump position holds, over all files (position: files, average vertices, average materials, files where it is empty):"]
    for pos in range(12):
        rows = [ci for r in results for ci in r["clump_info"] if ci[0] == pos]
        if rows:
            lines.append("  clump %2d: %4d files, %7.0f vertices, %5.1f materials, %3d empty" % (
                pos, len(rows), sum(c[3] for c in rows) / len(rows), sum(c[4] for c in rows) / len(rows), sum(1 for c in rows if c[3] == 0)))
    clump_hist = collections.Counter(r["clumps"] for r in results)
    lines += ["", "Models per file: " + ", ".join("%d:%d" % kv for kv in sorted(clump_hist.items()))]
    text = "\n".join(lines)
    with open(os.path.join(out, "fields_report.txt"), "w") as fh:
        fh.write(text + "\n")
    print()
    print(text)
    print("\nReport: " + os.path.join(out, "fields_report.txt"))


def head4(b):
    return b[:4].hex() if not b[:4].isalnum() else b[:4].decode()


def dump(path):
    d = open(path, "rb").read()
    e = ext_of(path)
    w = u32s(d)
    start = {".fbn": 6, ".hbn": 18}.get(e, 0)
    print("%s: %d bytes" % (os.path.basename(path), len(d)))
    for i in range(0, min(start, len(w)), 4):
        print("  %04x  " % (4 * i) + " ".join(fmt(x) for x in w[i:i + 4]))
    if start:
        print("  --- data from %#x ---" % (4 * start))
    for r in range(start, len(w), 4):
        print("  %04x  " % (4 * r) + " ".join(fmt(x) for x in w[r:r + 4]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("survey")
    s.add_argument("root")
    s.add_argument("-o", "--out", default="field_survey.txt")
    n = sp.add_parser("names")
    n.add_argument("root")
    n.add_argument("-o", "--out", default="field_names.txt")
    c = sp.add_parser("check")
    c.add_argument("root")
    c.add_argument("-o", "--out", default="field_check.txt")
    fb = sp.add_parser("fbn")
    fb.add_argument("root")
    fb.add_argument("-o", "--out", default="field_fbn.txt")
    sl = sp.add_parser("split")
    sl.add_argument("root")
    sl.add_argument("-o", "--out", default="field_split.txt")
    rw = sp.add_parser("rws")
    rw.add_argument("root")
    rw.add_argument("-o", "--png-dir", help="also write the textures as PNG files into this folder")
    rw.add_argument("--first", type=int, default=0, help="with -o: only decode the first N files (default all)")
    rw.add_argument("--out", default="field_rws.txt")
    fl = sp.add_parser("fields", help="write every field .RWS as .obj/.mtl/.png (needs the split command's .FPC.d folders)")
    fl.add_argument("root")
    fl.add_argument("-o", "--out", required=True)
    fl.add_argument("--match", help="only files whose name contains this text, e.g. f001")
    fl.add_argument("--limit", type=int, default=0)
    fl.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    fl.add_argument("--no-textures", action="store_true")
    dm = sp.add_parser("dump")
    dm.add_argument("file")
    w = sp.add_parser("words")
    w.add_argument("root")
    w.add_argument("ext")
    w.add_argument("-o", "--out")
    a = ap.parse_args()
    if a.cmd == "survey":
        survey(a.root, a.out)
    elif a.cmd == "check":
        check(a.root, a.out)
    elif a.cmd == "fbn":
        fbn_table(a.root, a.out)
    elif a.cmd == "split":
        split(a.root, a.out)
    elif a.cmd == "rws":
        rws(a.root, a.out, a.png_dir, a.first)
    elif a.cmd == "fields":
        fields(a.root, a.out, a.match, a.limit, a.jobs, not a.no_textures)
    elif a.cmd == "dump":
        dump(a.file)
    elif a.cmd == "names":
        names(a.root, a.out)
    elif a.cmd == "words":
        words(a.root, a.ext, a.out or "field_words_%s.txt" % a.ext.lower().lstrip("."))


if __name__ == "__main__":
    main()
