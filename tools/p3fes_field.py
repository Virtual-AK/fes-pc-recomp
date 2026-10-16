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


def objids(scripts_root, model_root, out):
    """Which model files do the object numbers in the scripts' field_313 / field_357 calls point at?
    Counts every literal id, then checks it against the numbers in the model file names (N00206.RMD -> N, 206)."""
    call = re.compile(r"field_(313|357)\((-?\d+), (-?\d+)\)")
    ids = collections.defaultdict(collections.Counter)         # (func, first arg) -> id -> calls
    nscripts = 0
    for dp, _, fns in os.walk(scripts_root):
        for fn in fns:
            if not fn.lower().endswith(".txt"):
                continue
            nscripts += 1
            with open(os.path.join(dp, fn), errors="replace") as fh:
                for m in call.finditer(fh.read()):
                    ids[(m.group(1), int(m.group(2)))][int(m.group(3))] += 1
    fam = collections.defaultdict(set)                          # (folder, prefix) -> numbers in file names
    nfiles = 0
    for dp, _, fns in os.walk(model_root):
        folder = os.path.basename(dp).upper()
        if folder.endswith(".PAC.D"):
            folder = "(pack folders)"
        for fn in fns:
            m = re.match(r"([A-Za-z_]*?)(\d+)([A-Za-z]?)\.rmd$", fn, re.I)
            if m:
                fam[(folder, m.group(1).upper())].add(int(m.group(2)))
                nfiles += 1
    lines = ["Scripts read: %d text files; model files with a number in the name: %d" % (nscripts, nfiles), "",
             "Model name families (folder, letters before the number): count, smallest..largest number"]
    for k, v in sorted(fam.items()):
        lines.append("  %-12s %-6s %5d files  %d..%d" % (k[0], k[1], len(v), min(v), max(v)))
    for k, v in sorted(fam.items()):
        if len(v) >= 50:
            lines.append("  numbers of %s %s up to 1000: %s" % (k[0], k[1], " ".join(str(n) for n in sorted(v) if n <= 1000)))
    lines += ["", "Literal ids in the scripts, and how many of them appear as a number in each model family:"]
    for (f, a), c in sorted(ids.items()):
        lines.append("")
        lines.append("field_%s(%d, id): %d distinct ids, %d calls; ids %d..%d" % (f, a, len(c), sum(c.values()), min(c), max(c)))
        top = max(c)
        for k, v in sorted(fam.items()):
            hit = [i for i in c if i in v]
            if hit:
                base = sum(1 for n in v if n <= top) / (top + 1)
                lines.append("    %-14s %-6s: %d of %d ids exist as a model number (a random id would match %.0f%% of the time)" % (
                    k[0], k[1], len(hit), len(c), 100 * base))
                if len(hit) >= len(c) * 0.6 and len(hit) < len(c):
                    lines.append("        not found: " + ", ".join(str(i) for i in sorted(c) if i not in v))
        lines.append("    most used: " + ", ".join("%d x%d" % (i, n) for i, n in c.most_common(12)))
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text)
    print("\nwritten to " + out)


def objdata(scripts_root, field_root, out, minid=20):
    """Do the object ids a field's scripts use appear as numbers inside that field's own small data files?
    Compares each field with the ids of a different field (control) to see whether any match is more than chance."""
    call = re.compile(r"field_(313|357)\((-?\d+), (-?\d+)\)")
    ids = collections.defaultdict(set)
    for dp, _, fns in os.walk(scripts_root):
        base = os.path.basename(dp)
        if not base.upper().endswith(".PAC.D"):
            continue
        for fn in fns:
            if fn.lower().endswith(".txt"):
                with open(os.path.join(dp, fn), errors="replace") as fh:
                    for m in call.finditer(fh.read()):
                        v = int(m.group(3))
                        if v >= minid:
                            ids[base.upper()].add(v)
    files = collections.defaultdict(list)
    for dp, _, fns in os.walk(field_root):
        base = os.path.basename(dp).upper()
        if base in ids:
            for fn in sorted(fns):
                if os.path.splitext(fn)[1].lower() in (".hbn", ".fbn", ".bin", ".env", ".cmr", ".epl"):
                    files[base].append(os.path.join(dp, fn))
    names = sorted(n for n in ids if files.get(n))
    if len(names) < 2:
        raise SystemExit("need scripts and data for at least 2 fields (found %d)" % len(names))
    own = collections.Counter()
    ctl = collections.Counter()
    examples = []
    for i, n in enumerate(names):
        other = names[(i + len(names) // 2) % len(names)]
        for path in files[n]:
            d = open(path, "rb").read()
            ext = os.path.splitext(path)[1].lower()
            for width, fmt in ((2, "<H"), (4, "<I")):
                vals = {}
                for off in range(0, len(d) - width + 1, width):
                    vals.setdefault(struct.unpack_from(fmt, d, off)[0], []).append(off)
                for v in ids[n]:
                    if v in vals:
                        own[(ext, width)] += 1
                        if len(examples) < 60:
                            examples.append("%s id %d in %s as %d-byte value at offset 0x%X" % (n, v, os.path.basename(path), width, vals[v][0]))
                for v in ids[other]:
                    if v in vals:
                        ctl[(ext, width)] += 1
    lines = ["Fields with scripts and data: %d. Ids below %d ignored." % (len(names), minid), "",
             "Hits (an id of the field's own scripts found as a number in its own files) versus a control (the ids of another field):"]
    for k in sorted(set(own) | set(ctl)):
        lines.append("  %-5s %d-byte values: own %5d, control %5d" % (k[0], k[1], own[k], ctl[k]))
    lines += ["", "First examples:"] + ["  " + e for e in examples]
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text)


def objwhere(scripts_root, field_root, out, minid=20):
    """Per script function (field_313 kind 5, kind 2, field_357): how often its ids are found as 32-bit values in the
    field's own .hbn/.fbn/.bin files versus a control field, and for .hbn hits the surrounding words (to see the record)."""
    call = re.compile(r"field_(313|357)\((-?\d+), (-?\d+)\)")
    ids = collections.defaultdict(lambda: collections.defaultdict(set))
    for dp, _, fns in os.walk(scripts_root):
        base = os.path.basename(dp).upper()
        if not base.endswith(".PAC.D"):
            continue
        for fn in fns:
            if fn.lower().endswith(".txt"):
                with open(os.path.join(dp, fn), errors="replace") as fh:
                    for m in call.finditer(fh.read()):
                        v = int(m.group(3))
                        if v >= minid:
                            key = "313 kind %s" % m.group(2) if m.group(1) == "313" else "357"
                            ids[base][key].add(v)
    files = collections.defaultdict(list)
    for dp, _, fns in os.walk(field_root):
        base = os.path.basename(dp).upper()
        if base in ids:
            for fn in sorted(fns):
                if os.path.splitext(fn)[1].lower() in (".hbn", ".fbn", ".bin"):
                    files[base].append(os.path.join(dp, fn))
    names = sorted(n for n in ids if files.get(n))
    if len(names) < 2:
        raise SystemExit("need scripts and data for at least 2 fields")
    own = collections.Counter(); ctl = collections.Counter(); tested = collections.Counter()
    offs = collections.defaultdict(collections.Counter)
    examples = []
    for i, n in enumerate(names):
        other = names[(i + len(names) // 2) % len(names)]
        for path in files[n]:
            d = open(path, "rb").read()
            ext = os.path.splitext(path)[1].lower()
            vals = {}
            for off in range(0, len(d) - 3, 4):
                vals.setdefault(struct.unpack_from("<I", d, off)[0], []).append(off)
            for key in ids[n]:
                for v in ids[n][key]:
                    tested[(key, ext)] += 1
                    if v in vals:
                        own[(key, ext)] += 1
                        offs[(key, ext)][vals[v][0] % 0x70 if ext == ".fbn" else vals[v][0] % 0x40] += 1
                        if ext == ".hbn" and len(examples) < 40:
                            o = vals[v][0]
                            ws = " ".join("%08X" % struct.unpack_from("<I", d, q)[0] for q in range(max(0, o - 16), min(len(d) - 3, o + 20), 4))
                            examples.append("%s %s id %d in %s at 0x%X: %s" % (n, key, v, os.path.basename(path), o, ws))
                for v in ids[other].get(key, ()):
                    if v in vals:
                        ctl[(key, ext)] += 1
    lines = ["Fields with scripts and data: %d. Ids below %d ignored." % (len(names), minid), "",
             "function / file type: own hits, control hits (ids tested)"]
    for k in sorted(tested):
        lines.append("  %-12s %-5s own %5d  control %5d  (of %d)" % (k[0], k[1], own[k], ctl[k], tested[k]))
    lines += ["", "Offset of own hits inside the record (.hbn: offset mod 0x40, .fbn: mod 0x70, .bin: mod 0x40), most common:"]
    for k, c in sorted(offs.items()):
        lines.append("  %-12s %-5s %s" % (k[0], k[1], ", ".join("0x%X:%d" % kv for kv in c.most_common(6))))
    lines += ["", "HBN examples (words around the hit; hit is the 5th word):"] + ["  " + e for e in examples]
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text)


def calcalls(scripts_root, field_root, out):
    """Test of the objwhere lead: field_357(F, id) -> id is a date-group number in field F's calendar (n*.bin, word 3);
    field_313(5, id) -> id is a calendar entry code (word 1, low 16 bits) of the script's own field."""
    cal = {}
    for dp, _, fns in os.walk(field_root):
        base = os.path.basename(dp).upper()
        for fn in fns:
            if re.match(r"n\d+_\d+\.bin$", fn, re.I) and base.endswith(".PAC.D"):
                try:
                    r = parse_ncal(open(os.path.join(dp, fn), "rb").read())
                except Exception:
                    continue
                cal[base] = ({x[4] for x in r["dates"]}, {w[1] & 0xFFFF for g in r["groups"] for w in g})
    bynum = collections.defaultdict(lambda: (set(), set()))
    for b, (g, c) in cal.items():
        m = re.match(r"F(\d+)_", b)
        if m:
            bynum[int(m.group(1))][0].update(g); bynum[int(m.group(1))][1].update(c)
    nums = sorted(bynum)
    call = re.compile(r"field_(313|357)\((-?\d+), (-?\d+)\)")
    res = collections.Counter(); misses = collections.Counter(); hitsx = collections.Counter(); hundreds = collections.Counter()
    for dp, _, fns in os.walk(scripts_root):
        base = os.path.basename(dp).upper()
        mm = re.match(r"F(\d+)_", base)
        if not mm or not base.endswith(".PAC.D"):
            continue
        for fn in fns:
            if not fn.lower().endswith(".txt"):
                continue
            for m in call.finditer(open(os.path.join(dp, fn), errors="replace").read()):
                fnc, a, v = m.group(1), int(m.group(2)), int(m.group(3))
                if v < 20:
                    continue
                if fnc == "357":
                    f = a if a >= 0 else int(mm.group(1))
                    if f not in bynum or len(nums) < 2:
                        res["357 field has no calendar"] += 1
                        continue
                    ctl = nums[(nums.index(f) + len(nums) // 2) % len(nums)]
                    res["357 tested"] += 1
                    if v in bynum[f][0]:
                        res["357 id is a group of field F"] += 1; hitsx[(f, v)] += 1
                    else:
                        misses[(a, v)] += 1
                        if v >= 100:
                            res["357 other ids >= 100 tested"] += 1
                            if v % 100 in bynum[f][0]:
                                res["  ... of which id mod 100 is a group of field F"] += 1
                            if v % 100 in bynum[ctl][0]:
                                res["  ... of which id mod 100 is a group of control field"] += 1
                            hundreds[v // 100] += 1
                    if v in bynum[ctl][0]:
                        res["357 id is a group of control field"] += 1
                elif a == 5 and base in cal:
                    ctl = nums[(nums.index(int(mm.group(1))) + len(nums) // 2) % len(nums)] if int(mm.group(1)) in nums else nums[0]
                    res["313 kind 5 tested"] += 1
                    if v in cal[base][1]:
                        res["313 kind 5 id is an entry code of own field"] += 1
                    if v in bynum[ctl][1]:
                        res["313 kind 5 id is an entry code of control field"] += 1
    lines = ["Calendars read: %d (fields: %d)" % (len(cal), len(nums)), ""] + ["  %-48s %d" % kv for kv in sorted(res.items())]
    lines += ["", "Hundreds digit of the other 357 ids: " + ", ".join("%d00s:%d" % kv for kv in sorted(hundreds.items()))]
    lines += ["", "Matching 357 (field, id) pairs, most used:"] + ["  field_357(%d, %d) x%d" % (f, v, c) for (f, v), c in hitsx.most_common(25)]
    lines += ["", "Non-matching 357 (arg, id), most used:"] + ["  field_357(%d, %d) x%d" % (a, v, c) for (a, v), c in misses.most_common(25)]
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text)


def datecheck(scripts_root, field_root, out, window=60):
    """Prediction test: in a script, `date_in_range?(m1, d1, m2, d2)` is followed by `field_357(F, 100*k + g)`; the
    calendar date(s) of group g in field F's n*.bin tables should then lie inside that range. Base rate: the share of
    all calendar dates of field F inside the same range."""
    dates = collections.defaultdict(lambda: collections.defaultdict(set))   # field number -> group -> {(month, day)}
    alld = collections.defaultdict(set)
    fdates = collections.defaultdict(lambda: collections.defaultdict(set))   # folder -> group -> dates (the scene's own table)
    for dp, _, fns in os.walk(field_root):
        base = os.path.basename(dp).upper()
        mm = re.match(r"F(\d+)_", base)
        if not mm or not base.endswith(".PAC.D"):
            continue
        for fn in fns:
            if re.match(r"n\d+_\d+\.bin$", fn, re.I):
                try:
                    r = parse_ncal(open(os.path.join(dp, fn), "rb").read())
                except Exception:
                    continue
                for (month, day, tm, w2, group, rest) in r["dates"]:
                    dates[int(mm.group(1))][group].add((month, day))
                    fdates[base][group].add((month, day))
                    alld[int(mm.group(1))].add((month, day))
    rng = re.compile(r"(?:date_in_range\?|field_132)\((\d+), (\d+), (\d+), (\d+)\)")  # exported listings may use the number name
    call = re.compile(r"field_357\((-?\d+), (\d+)\)")
    def inside(md, a):
        x, lo, hi = md[0] * 100 + md[1], a[0] * 100 + a[1], a[2] * 100 + a[3]
        return lo <= x <= hi if lo <= hi else (x >= lo or x <= hi)
    res = collections.Counter(); base_sum = 0.0; ex = []; fbase = 0.0
    for dp, _, fns in os.walk(scripts_root):
        base = os.path.basename(dp).upper()
        mm = re.match(r"F(\d+)_", base)
        if not mm or not base.endswith(".PAC.D"):
            continue
        for fn in fns:
            if not fn.lower().endswith(".txt"):
                continue
            last = None; at = -999
            for i, line in enumerate(open(os.path.join(dp, fn), errors="replace")):
                m = rng.search(line)
                if m:
                    last, at = tuple(int(x) for x in m.groups()), i
                for c in call.finditer(line):
                    f = int(c.group(1)) if int(c.group(1)) >= 0 else int(mm.group(1))
                    v = int(c.group(2))
                    g = v % 100 if v >= 100 else v
                    res["calls"] += 1
                    if last is None or i - at > window:
                        res["no date range just before"] += 1
                        continue
                    ds = dates[f].get(g)
                    if not ds or not alld[f]:
                        res["group not in a calendar"] += 1
                        continue
                    res["tested"] += 1
                    own = fdates[base].get(g)
                    if own:
                        res["same-folder table has the group"] += 1
                        res["  ... and its date is inside the range"] += any(inside(d, last) for d in own)
                        fbase += sum(any(inside(d, last) for d in o) for o in fdates[base].values()) / len(fdates[base])
                    hit = any(inside(d, last) for d in ds)
                    res["group date inside the range"] += hit
                    base_sum += sum(any(inside(d, last) for d in other) for other in dates[f].values()) / len(dates[f])
                    if len(ex) < 30:
                        ex.append("%s %s field_357(%d, %d): range %s, group %d dates %s -> %s" % (base, fn, f, v, last, g, sorted(ds)[:4], "inside" if hit else "outside"))
    lines = ["Prediction: the group's calendar date lies inside the date_in_range just before the call.", ""]
    lines += ["  %-34s %d" % kv for kv in sorted(res.items())]
    if res["tested"]:
        lines.append("  %-34s %.1f  (expected by chance: the share of the field's groups with any date inside the range)" % ("expected inside by chance", base_sum))
    if res["same-folder table has the group"]:
        lines.append("  %-34s %.1f  (chance for the same-folder test)" % ("expected inside by chance", fbase))
    lines += ["", "Examples:"] + ["  " + e for e in ex]
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text)


def hbn_sections(d):
    """Header of an .HBN: magic, version, then 8 (count, record size) pairs from +8; sections follow from 0x48.
    Returns [(count, size, start)] or None when it does not fit the file."""
    if len(d) < 0x48 or struct.unpack_from("<I", d, 0)[0] != 0x45678901:
        return None
    pairs = [struct.unpack_from("<II", d, 8 + 8 * k) for k in range(8)]
    pos, out = 0x48, []
    for c, sz in pairs:
        out.append((c, sz, pos))
        pos += c * sz
    return out if pos <= len(d) and all(sz < 0x1000 for _, sz in pairs) else None


def hbn(root, out, examples=6):
    """Per-section statistics of all .hbn files: which sections are used, per word position the common values,
    the ASCII strings, and a few small files decoded record by record."""
    files = [p for p in field_files(root) if ext_of(p) == ".hbn"]
    if not files:
        raise SystemExit("no .hbn files found under " + root)
    parsed = {}; bad = 0
    for pth in files:
        d = open(pth, "rb").read()
        sec = hbn_sections(d)
        if sec is None:
            bad += 1
        else:
            parsed[pth] = (d, sec)
    lines = ["%d .hbn files; %d fit the header rule; %d do not" % (len(files), len(parsed), bad), ""]
    sizes = collections.Counter(tuple(sz for _, sz, _ in sec) for _, sec in parsed.values())
    lines.append("record sizes per section (files): " + "; ".join("%s: %d" % (",".join("%X" % x for x in k), v) for k, v in sizes.most_common(5)))
    used = collections.Counter(); total = collections.Counter()
    cols = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for d, sec in parsed.values():
        for k, (c, sz, st) in enumerate(sec):
            if c:
                used[k] += 1; total[k] += c
            for r in range(c):
                for j in range(sz // 4):
                    cols[k][j][struct.unpack_from("<I", d, st + r * sz + 4 * j)[0]] += 1
    lines += ["", "section | files using it | records | record size"]
    for k in range(8):
        sz = max((sec[k][1] for _, sec in parsed.values()), default=0)
        lines.append("  %d | %d | %d | 0x%X" % (k, used[k], total[k], sz))
    for k in range(8):
        if not total[k]:
            continue
        lines += ["", "Section %d, word by word (value x count; floats shown as numbers):" % k]
        for j in sorted(cols[k]):
            c = cols[k][j]
            tops = []
            for v, n in c.most_common(5):
                f = struct.unpack("<f", struct.pack("<I", v))[0]
                tops.append(("0x%X" % v if kind(v) in ("int", "zero", "none", "other") else "%.4g" % f) + " x%d" % n)
            fl = [struct.unpack("<f", struct.pack("<I", v))[0] for v in c if kind(v) == "float"]
            lines.append("  +0x%02X: %s%s" % (4 * j, ", ".join(tops), ("  [floats %.4g..%.4g]" % (min(fl), max(fl))) if fl else ""))
    strs = collections.Counter()
    for d, _ in parsed.values():
        for m in re.finditer(rb"[A-Za-z0-9_./]{4,}", d):
            strs[m.group().decode()] += 1
    lines += ["", "ASCII strings (text x files), most common 40:"] + ["  %s x%d" % kv for kv in strs.most_common(40)]
    shown = collections.Counter()
    lines += ["", "Small files decoded (words per record):"]
    for pth, (d, sec) in sorted(parsed.items(), key=lambda kv: len(kv[1][0])):
        key = tuple(bool(c) for c, _, _ in sec)
        if shown[key] or sum(shown.values()) >= examples:
            continue
        shown[key] += 1
        lines.append("  " + os.path.basename(pth) + " (%d bytes)" % len(d))
        for k, (c, sz, st) in enumerate(sec):
            for r in range(min(c, 4)):
                w = struct.unpack_from("<%dI" % (sz // 4), d, st + r * sz)
                lines.append("    s%d r%d: %s" % (k, r, " ".join("%X" % x if kind(x) != "float" else "%.5g" % struct.unpack("<f", struct.pack("<I", x))[0] for x in w)))
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text)


def hbnlink(root, out, tol=1.0):
    """Do the points in .HBN records sit on the positions of the .FBN placements of the same field (same coordinate system)?
    Also: which strings go with which sections. Control: the FBN positions of another field."""
    fb = collections.defaultdict(list); hb = collections.defaultdict(list)
    for pth in field_files(root):
        e = ext_of(pth)
        m = re.search(r"f(\d{3})_\d{3}", os.path.basename(pth), re.I)
        if not m or e not in (".fbn", ".hbn"):
            continue
        d = open(pth, "rb").read()
        if e == ".fbn" and len(d) >= 12:
            fb[int(m.group(1))] += [(r[2], r[4]) for r in fbn_records(d)]
        elif e == ".hbn":
            sec = hbn_sections(d)
            if sec:
                pts = []
                for k, (c, sz, st) in enumerate(sec):
                    for r in range(c):
                        w = struct.unpack_from("<%dI" % (sz // 4), d, st + r * sz)
                        f = [struct.unpack("<f", struct.pack("<I", x))[0] for x in w]
                        if sz == 0x20:   # id, colour, x, y, z, x2, z2, value
                            if len(f) >= 7 and all(math.isfinite(v) for v in f[2:7]):
                                pts.append((k, f[2], f[4])); pts.append((k, f[5], f[6]))
                        elif len(f) >= 4 and all(math.isfinite(v) for v in f[1:4]):   # id, x, y, z, angle
                            pts.append((k, f[1], f[3]))
                hb[int(m.group(1))].append((pth, pts, d, sec))
    fields_ = sorted(set(fb) & set(hb))
    if len(fields_) < 2:
        raise SystemExit("need fields with both .FBN and .HBN files")
    near = lambda x, z, ref: any(abs(x - a) <= tol and abs(z - b) <= tol for a, b in ref)
    own = collections.Counter(); ctl = collections.Counter(); tot = collections.Counter()
    for i, f in enumerate(fields_):
        other = fields_[(i + len(fields_) // 2) % len(fields_)]
        for _, pts, _, _ in hb[f]:
            for k, x, z in pts:
                tot[k] += 1
                own[k] += near(x, z, fb[f])
                ctl[k] += near(x, z, fb[other])
    lines = ["Fields with both .FBN and .HBN: %d. A point counts when it lies within %.1f units (x and z) of an .FBN position." % (len(fields_), tol), "",
             "section | points | on an FBN position of the own field | on one of a control field"]
    for k in sorted(tot):
        lines.append("  %d | %d | %d | %d" % (k, tot[k], own[k], ctl[k]))
    names = ("ENEMY", "REMAIN", "list", "draw_proc", "EDIT", "wind", "wall01")
    bysec = {n: collections.Counter() for n in names}; withs = collections.Counter(); alls = 0
    for f in hb:
        for _, _, d, sec in hb[f]:
            alls += 1
            for n in names:
                if n.encode() in d:
                    withs[n] += 1
                    for k, (c, _, _) in enumerate(sec):
                        if c:
                            bysec[n][k] += 1
    lines += ["", "Strings versus sections (files containing the string; of those, files using section k):"]
    for n in names:
        lines.append("  %-9s %4d files; sections: %s" % (n, withs[n], ", ".join("%d:%d" % kv for kv in sorted(bysec[n].items()))))
    lines.append("  (all parsed .hbn files: %d)" % alls)
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text)


def _png(path, w, h, px):
    import zlib
    raw = b"".join(b"\x00" + bytes(px[y * w * 3:(y + 1) * w * 3]) for y in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def hbnmap(root, out_dir, match=None, limit=40, size=700, models=None):
    """One top-down picture per .hbn file: its points by section colour (lines for the 0x20-byte sections), a tick for the
    angle, and the .FBN positions of the same field as white crosses. Axes through (0, 0) in grey."""
    colours = {0: (255, 60, 60), 1: (255, 160, 0), 2: (255, 235, 0), 3: (60, 220, 60), 4: (0, 220, 220), 5: (60, 255, 120), 6: (90, 130, 255), 7: (255, 80, 255)}
    fb = collections.defaultdict(list); files = []
    for pth in field_files(root):
        e = ext_of(pth); m = re.search(r"f(\d{3})_\d{3}", os.path.basename(pth), re.I)
        if not m or e not in (".fbn", ".hbn"):
            continue
        if e == ".fbn":
            d = open(pth, "rb").read()
            if len(d) >= 12:
                fb[int(m.group(1))] += [(r[2], r[4]) for r in fbn_records(d)]
        elif not match or match.lower() in os.path.basename(pth).lower():
            files.append((int(m.group(1)), pth))
    objs = []
    if models:
        for dp, _, fns in os.walk(models):
            objs += [os.path.join(dp, fn) for fn in fns if fn.lower().endswith(".obj")]
    def footprint(pth, fnum):
        base = re.search(r"f\d{3}_\d{3}", os.path.basename(pth), re.I).group(0).lower()
        pick = [o for o in objs if base in o.lower().replace("\\", "/")] or [o for o in objs if ("f%03d_" % fnum) in o.lower().replace("\\", "/")]
        out_pts = []
        for o in pick[:30]:
            with open(o, errors="replace") as fh:
                for i, ln in enumerate(l for l in fh if l.startswith("v ")):
                    if i % 3 == 0:
                        t = ln.split()
                        out_pts.append((float(t[1]), float(t[3])))
        footprint.info = (len(pick), len(objs))
        return out_pts[:80000]
    os.makedirs(out_dir, exist_ok=True)
    done = 0; lines = ["file | points per section | picture", "legend: red=0 orange=1 yellow=2 green=3 cyan=4 lightgreen=5 blue=6 magenta=7, white cross = .FBN position, grey = axes through 0,0"]
    seen = set()
    for fnum, pth in sorted(files):
        if limit and done >= limit:
            break
        d = open(pth, "rb").read(); sec = hbn_sections(d)
        if (os.path.basename(pth).lower(), d) in seen:   # the same file sits in several scene folders
            continue
        seen.add((os.path.basename(pth).lower(), d))
        if not sec:
            continue
        items = []
        for k, (c, sz, st) in enumerate(sec):
            for r in range(c):
                w = struct.unpack_from("<%dI" % (sz // 4), d, st + r * sz)
                f = [struct.unpack("<f", struct.pack("<I", x))[0] for x in w]
                if len(f) >= 5 and all(math.isfinite(v) and abs(v) < 1e5 for v in f[1:5]):
                    items.append((k, sz, f))
        if len(items) < 3:
            continue
        pts = []
        for k, sz, f in items:
            pts.append((f[2], f[4]) if sz == 0x20 else (f[1], f[3]))
            if sz == 0x20 and len(f) > 6 and math.isfinite(f[5]) and math.isfinite(f[6]):
                pts.append((f[5], f[6]))
        pts += fb[fnum]
        fp = footprint(pth, fnum) if objs else []
        note = ""
        if models:
            if not objs:
                note = " | NO .obj files found under the --models folder"
            elif not fp:
                note = " | no .obj matched this file name (%d .obj files in the folder)" % footprint.info[1]
            else:
                fx = [a for a, _ in fp]; fz = [b for _, b in fp]
                note = " | model: %d .obj files, x %.0f..%.0f, z %.0f..%.0f" % (footprint.info[0], min(fx), max(fx), min(fz), max(fz))
                note += " | points: x %.0f..%.0f, z %.0f..%.0f" % (min(a for a, _ in pts), max(a for a, _ in pts), min(b for _, b in pts), max(b for _, b in pts))
        xs = [a for a, _ in pts]; zs = [b for _, b in pts]
        lo_x, hi_x, lo_z, hi_z = min(xs + [0]), max(xs + [0]), min(zs + [0]), max(zs + [0])
        span = max(hi_x - lo_x, hi_z - lo_z, 1.0) * 1.1
        cx, cz = (lo_x + hi_x) / 2, (lo_z + hi_z) / 2
        px = bytearray(b"\x10" * (size * size * 3))
        def to(a, b):
            return int((a - cx) / span * size + size / 2), int(size / 2 - (b - cz) / span * size)
        def dot(x, y, col, r=3):
            for yy in range(max(0, y - r), min(size, y + r + 1)):
                for xx in range(max(0, x - r), min(size, x + r + 1)):
                    px[(yy * size + xx) * 3:(yy * size + xx) * 3 + 3] = bytes(col)
        def line(a, b, col):
            (x0, y0), (x1, y1) = a, b
            n = max(abs(x1 - x0), abs(y1 - y0), 1)
            for i in range(n + 1):
                dot(x0 + (x1 - x0) * i // n, y0 + (y1 - y0) * i // n, col, 0)
        for a, b in fp:
            x, y = to(a, b)
            if 0 <= x < size and 0 <= y < size:
                for yy in (y, min(size - 1, y + 1)):
                    for xx in (x, min(size - 1, x + 1)):
                        px[(yy * size + xx) * 3:(yy * size + xx) * 3 + 3] = bytes((95, 95, 130))
        ox, oy = to(0, 0)
        line((0, oy), (size - 1, oy), (70, 70, 70)); line((ox, 0), (ox, size - 1), (70, 70, 70))
        for a, b in fb[fnum]:
            x, y = to(a, b); line((x - 5, y), (x + 5, y), (255, 255, 255)); line((x, y - 5), (x, y + 5), (255, 255, 255))
        counts = collections.Counter()
        for k, sz, f in items:
            counts[k] += 1; col = colours[k]
            if sz == 0x20 and len(f) > 6 and math.isfinite(f[5]) and math.isfinite(f[6]):
                line(to(f[2], f[4]), to(f[5], f[6]), col)
            x, y = to(f[2], f[4]) if sz == 0x20 else to(f[1], f[3])
            dot(x, y, col)
            if sz == 0x14:
                ang = math.radians(f[4]); line((x, y), (int(x + 14 * math.sin(ang)), int(y - 14 * math.cos(ang))), col)
        name = os.path.splitext(os.path.basename(pth))[0] + "_hbn.png"
        _png(os.path.join(out_dir, name), size, size, px)
        lines.append("%s | %s | %s%s" % (os.path.basename(pth), ", ".join("%d:%d" % kv for kv in sorted(counts.items())), name, note))
        done += 1
    text = "\n".join(lines)
    open(os.path.join(out_dir, "hbnmap.txt"), "w").write(text + "\n")
    print(text)


def hbnprops(root, models, out, radius=100.0, maxsize=600.0):
    """Do the .HBN points sit at the centres of the small objects of the field model? Objects are the `o` groups of the
    exported .obj files (one per atomic); only those with a bounding box under `maxsize` count as props. Tested as
    exported and mirrored in x; control: the objects of a different scene."""
    objs_by = {}
    for dp, _, fns in os.walk(models):
        for fn in fns:
            if fn.lower().endswith(".obj"):
                objs_by.setdefault(os.path.join(dp, fn), None)
    def load(path):
        res, cur = [], None
        with open(path, errors="replace") as fh:
            for ln in fh:
                if ln.startswith("o "):
                    cur = []; res.append(cur)
                elif ln.startswith("v ") and cur is not None:
                    t = ln.split(); cur.append((float(t[1]), float(t[3])))
        out_c = []
        for vs in res:
            if vs:
                xs = [a for a, _ in vs]; zs = [b for _, b in vs]
                if max(xs) - min(xs) <= maxsize and max(zs) - min(zs) <= maxsize:
                    out_c.append((sum(xs) / len(xs), sum(zs) / len(zs)))
        return out_c
    cache = {}
    def centres(base):
        if base not in cache:
            c = []
            for path in objs_by:
                if base in path.lower().replace("\\", "/"):
                    c += load(path)
            cache[base] = c
        return cache[base]
    pts = []
    for pth in field_files(root):
        if ext_of(pth) != ".hbn":
            continue
        m = re.search(r"f\d{3}_\d{3}", os.path.basename(pth), re.I)
        d = open(pth, "rb").read(); sec = hbn_sections(d)
        if not m or not sec:
            continue
        P = []
        for k, (c, sz, st) in enumerate(sec):
            if sz != 0x14:
                continue
            for r in range(c):
                f = struct.unpack_from("<5f", d, st + r * sz)
                if all(math.isfinite(v) and abs(v) < 1e5 for v in f[1:4]):
                    P.append((k, f[1], f[3]))
        if P:
            pts.append((m.group(0).lower(), os.path.basename(pth), P))
    seen = set(); work = []
    for base, fn, P in pts:
        if (fn, tuple(P)) in seen or not centres(base):
            continue
        seen.add((fn, tuple(P))); work.append((base, fn, P))
    if len(work) < 2:
        raise SystemExit("need .hbn files whose scene has an exported model (found %d)" % len(work))
    near = lambda x, z, C: min(((x - a) ** 2 + (z - b) ** 2) ** 0.5 for a, b in C)
    res = collections.defaultdict(collections.Counter); lines = []
    for i, (base, fn, P) in enumerate(work):
        C = centres(base); oc = centres(work[(i + len(work) // 2) % len(work)][0])
        row = collections.Counter()
        for k, x, z in P:
            for tag, CC, sg in (("own", C, 1), ("mirrored", C, -1), ("control", oc, 1)):
                if near(sg * x, z, CC) <= radius:
                    res[k][tag] += 1; row[tag] += 1
            res[k]["points"] += 1
        if i < 40:
            lines.append("  %s: %d props, %d points; within %.0f of a prop centre: own %d, mirrored %d, control %d" % (fn, len(C), len(P), radius, row["own"], row["mirrored"], row["control"]))
    text = ["Files with an exported scene model: %d. Radius %.0f units; props = objects under %.0f units wide." % (len(work), radius, maxsize), "",
            "section | points | near a prop centre: own | mirrored in x | control scene"]
    for k in sorted(res):
        text.append("  %d | %d | %d | %d | %d" % (k, res[k]["points"], res[k]["own"], res[k]["mirrored"], res[k]["control"]))
    text += ["", "Per file (first 40):"] + lines
    t = "\n".join(text)
    open(out, "w").write(t + "\n")
    print(t)


def slotcalls(scripts_root, field_root, out):
    """`field_312(object, n)` sets an object up at a numbered spot. Are those numbers the .FBN slot numbers (id - 0xC00)
    of the same scene, or the running numbers of the .HBN records? Control: another scene."""
    call = re.compile(r"(?:field_312|object_setup\?)\(.*, (\d+)\)\s*$")
    scenes = {}
    for dp, _, fns in os.walk(field_root):
        for fn in fns:
            m = re.match(r"(f\d{3}_\d{3})(?:_\d+)?\.(fbn|hbn)$", fn, re.I)
            if not m:
                continue
            d = open(os.path.join(dp, fn), "rb").read()
            sc = scenes.setdefault(m.group(1).upper(), {"fbn": set(), "hbn": collections.defaultdict(set)})
            fld = scenes.setdefault(m.group(1).upper()[:4], {"fbn": set(), "hbn": collections.defaultdict(set)})
            if m.group(2).lower() == "fbn" and len(d) >= 12:
                ids_ = {r[0] - 0xC00 for r in fbn_records(d) if 0xC00 <= r[0] < 0xD00}
                sc["fbn"] |= ids_; fld["fbn"] |= ids_
            elif m.group(2).lower() == "hbn":
                sec = hbn_sections(d)
                for k, (c, sz, st) in enumerate(sec or []):
                    for r in range(c):
                        i = struct.unpack_from("<I", d, st + r * sz)[0]
                        sc["hbn"][k].add(i & 0xFF)
    calls = collections.defaultdict(set)
    for dp, _, fns in os.walk(scripts_root):
        base = os.path.basename(dp).upper()
        m = re.match(r"(F\d{3}_\d{3})\.PAC\.D$", base)
        if not m:
            continue
        for fn in fns:
            if fn.lower().endswith(".txt"):
                for ln in open(os.path.join(dp, fn), errors="replace"):
                    c = call.search(ln)
                    if c:
                        calls[m.group(1)].add(int(c.group(1)))
    names = sorted(n for n in calls if n in scenes and len(n) == 8)
    if len(names) < 2:
        raise SystemExit("need scenes with field_312 calls and .FBN/.HBN files (found %d)" % len(names))
    tot = collections.Counter(); own = collections.Counter(); ctl = collections.Counter()
    for i, n in enumerate(names):
        o = scenes[names[(i + len(names) // 2) % len(names)]]
        for v in calls[n]:
            for big in (False, True):
                if big and v < 12:
                    continue
                tag = "n >= 12" if big else "all n"
                tot[tag] += 1
                own[(tag, "FBN slots")] += v in scenes[n]["fbn"]; ctl[(tag, "FBN slots")] += v in o["fbn"]
                own[(tag, "FBN slots of any scene of the field")] += v in scenes[n[:4]]["fbn"]
                ctl[(tag, "FBN slots of any scene of the field")] += v in scenes[names[(i + len(names) // 2) % len(names)][:4]]["fbn"]
                for k in range(8):
                    own[(tag, "HBN section %d" % k)] += v in scenes[n]["hbn"].get(k, ()); ctl[(tag, "HBN section %d" % k)] += v in o["hbn"].get(k, ())
    lines = ["Scenes with field_312 calls and field files: %d (distinct numbers per scene counted once)" % len(names), "",
             "set tested | calls | own scene | control scene"]
    for key in sorted(own):
        lines.append("  %s, %s | %d | %d | %d" % (key[0], key[1], tot[key[0]], own[key], ctl[key]))
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text)


def calls312(scripts_root, field_root, out, samples=25):
    """Context of every `field_312(object, n)` call: where the object comes from (party member, created by 314, other),
    which statement follows, and for n >= 12 whether n is an .FBN slot of the scene. Samples of the unmatched ones."""
    fbn = {}
    for dp, _, fns in os.walk(field_root):
        for fn in fns:
            m = re.match(r"(f\d{3}_\d{3})(?:_\d+)?\.fbn$", fn, re.I)
            if m:
                d = open(os.path.join(dp, fn), "rb").read()
                if len(d) >= 12:
                    fbn.setdefault(m.group(1).upper(), set()).update(r[0] - 0xC00 for r in fbn_records(d) if 0xC00 <= r[0] < 0xD00)
    call = re.compile(r"(?:field_312|object_setup\?)\((.*), (\d+)\)\s*$")
    stmt = re.compile(r"^\s*\d+\s+(.*)$")
    fname = re.compile(r"([A-Za-z_][A-Za-z_0-9?]*)\(")
    src = collections.defaultdict(collections.Counter); nxt = collections.Counter(); byn = collections.Counter()
    matched = collections.Counter(); ex = []; done = set()
    for dp, _, fns in os.walk(scripts_root):
        m = re.match(r"(F\d{3}_\d{3})\.PAC\.D$", os.path.basename(dp).upper())
        if not m:
            continue
        for fn in fns:
            if not fn.lower().endswith(".txt"):
                continue
            lines = open(os.path.join(dp, fn), errors="replace").read().split("\n")
            for i, ln in enumerate(lines):
                c = call.search(ln)
                if not c:
                    continue
                key = (fn, i, m.group(1))
                n = int(c.group(2)); arg = c.group(1).strip()
                if "field_311" in arg or "object_player" in arg:
                    kind = "party member (311)"
                else:
                    kind = "other"
                    if re.fullmatch(r"[li]var\d+", arg):
                        for q in range(i - 1, max(0, i - 8), -1):
                            if re.search(re.escape(arg) + r" = (?:field_314|object_create)", lines[q]):
                                kind = "created (314)"; break
                            if re.search(re.escape(arg) + r" = ", lines[q]):
                                kind = "assigned from something else"; break
                src[n][kind] += 1; byn[n] += 1
                nx = next((fname.search(lines[q]).group(1) for q in range(i + 1, min(len(lines), i + 4)) if fname.search(lines[q])), "(none)")
                nxt[nx] += 1
                hit = n in fbn.get(m.group(1), ())
                if n >= 12:
                    matched["n>=12 slot of the scene"] += hit; matched["n>=12 total"] += 1
                    if not hit and len(ex) < samples and (fn, n, m.group(1)[:4]) not in done:
                        done.add((fn, n, m.group(1)[:4]))
                        ex.append("  %s %s n=%d:\n      %s" % (m.group(1), fn, n, "\n      ".join(x.strip() for x in lines[max(0, i - 3):i + 4])))
    lines_out = ["field_312 calls: %d. Where the object comes from, per number n (count: sources):" % sum(byn.values())]
    for n in sorted(byn):
        lines_out.append("  n=%d: %d  (%s)" % (n, byn[n], ", ".join("%s %d" % kv for kv in src[n].most_common())))
    lines_out += ["", "Statement after the call (name: count): " + ", ".join("%s: %d" % kv for kv in nxt.most_common(12)), "",
                  "n >= 12: %d calls, %d with n a .FBN slot of the scene" % (matched["n>=12 total"], matched["n>=12 slot of the scene"]), "", "Samples of n >= 12 that are not a slot of the scene:"] + ex
    text = "\n".join(lines_out)
    open(out, "w").write(text + "\n")
    print(text)


def warpcalls(scripts_root, field_root, out):
    """`field_33(field, scene, k, 0)` moves the player to another scene. Is k the number of an .FBN file of the destination
    (f<field>_<scene>_<k>.FBN)? Control: the same k with a different destination scene of the same field."""
    have = set(); scenes = collections.defaultdict(set)
    for dp, _, fns in os.walk(field_root):
        for fn in fns:
            m = re.match(r"f(\d{3})_(\d{3})_(\d{3})\.fbn$", fn, re.I)
            if m:
                have.add(tuple(int(x) for x in m.groups())); scenes[int(m.group(1))].add(int(m.group(2)))
    call = re.compile(r"(?:field_33|scene_change\?)\((\d+), (\d+), (\d+), (\d+)\)")
    calls = collections.Counter()
    for dp, _, fns in os.walk(scripts_root):
        if not os.path.basename(dp).upper().endswith(".PAC.D"):
            continue
        for fn in fns:
            if fn.lower().endswith(".txt"):
                for c in call.finditer(open(os.path.join(dp, fn), errors="replace").read()):
                    calls[tuple(int(x) for x in c.groups())] += 1
    tot = own = ctl = nof = 0; ks = collections.Counter(); miss = []
    for (f, sc, k, z), n in calls.items():
        if sc not in scenes.get(f, ()):
            nof += 1; continue
        tot += 1; ks[k] += 1
        if (f, sc, k) in have:
            own += 1
        elif len(miss) < 25:
            miss.append((f, sc, k, z))
        others = sorted(scenes[f] - {sc})
        if others and (f, others[0], k) in have:
            ctl += 1
    lines = ["distinct field_33 calls with an FBN-bearing destination scene: %d (calls to scenes without any .FBN file: %d)" % (tot, nof), "",
             "k is the number of an FBN file of the destination: %d of %d" % (own, tot),
             "same k with another scene of that field (control): %d of %d" % (ctl, tot), "",
             "k values (value: calls): " + ", ".join("%d: %d" % kv for kv in sorted(ks.items())), "",
             "Examples without a matching FBN file (field, scene, k, last): " + "; ".join("%d,%d,%d,%d" % m for m in miss)]
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text)


def variantargs(scripts_root, field_root, out, minvalue=50, mincalls=15):
    """Which script function takes the number of an .FBN variant file (the last number of f<field>_<scene>_<NNN>.FBN)?
    For every (function, argument position) with literal numbers: the share of distinct values that are such a number
    in the script's own field, against another field. Values below `minvalue` are ignored (small numbers overlap by chance)."""
    suff = collections.defaultdict(set)
    for dp, _, fns in os.walk(field_root):
        for fn in fns:
            m = re.match(r"f(\d{3})_\d{3}_(\d{3})\.fbn$", fn, re.I)
            if m:
                suff[int(m.group(1))].add(int(m.group(2)))
    fields_ = sorted(suff)
    if len(fields_) < 2:
        raise SystemExit("need .FBN files of at least 2 fields")
    call = re.compile(r"([A-Za-z_][A-Za-z_0-9]*\??)\(((?:-?\d+)(?:, -?\d+)*)\)")
    vals = collections.defaultdict(set)   # (field, func, pos) -> values
    for dp, _, fns in os.walk(scripts_root):
        m = re.match(r"F(\d{3})_\d{3}\.PAC\.D$", os.path.basename(dp).upper())
        if not m:
            continue
        f = int(m.group(1))
        for fn in fns:
            if fn.lower().endswith(".txt"):
                for ln in open(os.path.join(dp, fn), errors="replace"):
                    for c in call.finditer(ln):
                        for pos, v in enumerate(int(x) for x in c.group(2).split(", ")):
                            if v >= minvalue:
                                vals[(f, c.group(1), pos)].add(v)
    agg = collections.defaultdict(lambda: [0, 0, 0])   # (func,pos) -> [values, own hits, control hits]
    for (f, fnc, pos), vs in vals.items():
        if f not in suff:
            continue
        o = fields_[(fields_.index(f) + len(fields_) // 2) % len(fields_)]
        a = agg[(fnc, pos)]
        a[0] += len(vs); a[1] += len(vs & suff[f]); a[2] += len(vs & suff[o])
    rows = sorted(((a[1] - a[2], k, a) for k, a in agg.items() if a[0] >= mincalls), reverse=True)
    lines = ["Distinct values of %d and up per (function, argument position), found among the .FBN variant numbers of the same field (own) and of another field (control):" % minvalue, "",
             "function(arg position) | values | own | control"]
    for _, (fnc, pos), a in rows[:40]:
        lines.append("  %s(%d) | %d | %d | %d" % (fnc, pos, a[0], a[1], a[2]))
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text)


def variantcalls(scripts_root, field_root, out, specs, per=12):
    """For chosen `function:argument position` pairs (from `variantargs`): every distinct value of 50 and up per field,
    whether it is an .FBN variant number of that field, and sample call sites with surrounding lines."""
    suff = collections.defaultdict(set)
    for dp, _, fns in os.walk(field_root):
        for fn in fns:
            m = re.match(r"f(\d{3})_\d{3}_(\d{3})\.fbn$", fn, re.I)
            if m:
                suff[int(m.group(1))].add(int(m.group(2)))
    call = re.compile(r"([A-Za-z_][A-Za-z_0-9]*\??)\(((?:-?\d+)(?:, -?\d+)*)\)")
    want = {}
    for sp_ in specs:
        name, _, pos = sp_.rpartition(":")
        want[name] = int(pos)
    seen = set(); rows = collections.defaultdict(dict); ctx = collections.defaultdict(lambda: {True: [], False: []})
    for dp, _, fns in os.walk(scripts_root):
        m = re.match(r"F(\d{3})_\d{3}\.PAC\.D$", os.path.basename(dp).upper())
        if not m:
            continue
        f = int(m.group(1))
        for fn in fns:
            if not fn.lower().endswith(".txt") or (f, fn) in seen:
                continue
            seen.add((f, fn))
            lines = open(os.path.join(dp, fn), errors="replace").read().split("\n")
            for i, ln in enumerate(lines):
                for c in call.finditer(ln):
                    if c.group(1) in want:
                        nums = [int(x) for x in c.group(2).split(", ")]
                        pos = want[c.group(1)]
                        if pos < len(nums) and nums[pos] >= 50:
                            hit = nums[pos] in suff.get(f, ())
                            rows[c.group(1)][(f, nums[pos])] = hit
                            if len(ctx[c.group(1)][hit]) < per:
                                ctx[c.group(1)][hit].append("  field %d, %s:\n      %s" % (f, fn, "\n      ".join(x.strip() for x in lines[max(0, i - 3):i + 3])))
    out_l = []
    for name in want:
        r = rows[name]
        out_l += ["== %s, argument %d: %d distinct (field, value) pairs of 50 and up; %d are an .FBN variant number of the field" % (name, want[name], len(r), sum(r.values()))]
        out_l.append("   matching: " + ", ".join("%d:%d" % k for k, v in sorted(r.items()) if v)[:900])
        out_l.append("   not matching: " + ", ".join("%d:%d" % k for k, v in sorted(r.items()) if not v)[:900])
        for hit in (True, False):
            out_l.append("   -- samples, %s an .FBN variant number:" % ("is" if hit else "is not"))
            out_l += ctx[name][hit]
        out_l.append("")
    text = "\n".join(out_l)
    open(out, "w").write(text + "\n")
    print(text)


def fbnvariants(field_root, out, tol=0.5):
    """How the variant files of a scene (f<field>_<scene>_<NNN>.FBN) differ: per scene the number of variants and records;
    each variant compared with the lowest-numbered one (slots in both, slots at the same position, slots only in one);
    and one table of the scene with the most variants (slot by variant: x, z)."""
    scenes = collections.defaultdict(dict)
    for dp, _, fns in os.walk(field_root):
        for fn in fns:
            m = re.match(r"f(\d{3})_(\d{3})_(\d{3})\.fbn$", fn, re.I)
            if m:
                d = open(os.path.join(dp, fn), "rb").read()
                if len(d) >= 12:
                    scenes[(int(m.group(1)), int(m.group(2)))][int(m.group(3))] = {r[0] - 0xC00: (r[2], r[4], r[6]) for r in fbn_records(d)}
    if not scenes:
        raise SystemExit("no .FBN files found")
    same = both = only_v = only_b = nvar = 0; sizes = collections.Counter(); per = []
    for sc, vs in sorted(scenes.items()):
        keys = sorted(vs); base = vs[keys[0]]
        sizes[len(keys)] += 1
        for k in keys[1:]:
            nvar += 1
            v = vs[k]
            common = set(v) & set(base)
            both += len(common); only_v += len(set(v) - set(base)); only_b += len(set(base) - set(v))
            same += sum(abs(v[i][0] - base[i][0]) <= tol and abs(v[i][1] - base[i][1]) <= tol for i in common)
        per.append((len(keys), sc, keys))
    lines = ["Scenes with .FBN files: %d. Variants per scene (variants: scenes): %s" % (len(scenes), ", ".join("%d: %d" % kv for kv in sorted(sizes.items()))), "",
             "Each non-base variant against the lowest-numbered variant of its scene (%d comparisons):" % nvar,
             "  slots in both: %d, of which at the same position (within %.1f): %d" % (both, tol, same),
             "  slots only in the variant: %d, only in the base: %d" % (only_v, only_b), ""]
    per.sort(reverse=True)
    for n, sc, keys in per[:6]:
        lines.append("  field %d scene %d: %d variants: %s" % (sc[0], sc[1], n, ", ".join("%03d" % k for k in keys)))
    n, sc, keys = per[0]
    vs = scenes[sc]
    slots = sorted(set().union(*[set(vs[k]) for k in keys]))
    lines += ["", "Scene with the most variants: field %d scene %d. Rows: slot; columns: variants %s; cells: x/z (angle), '-' = slot not in that file" % (sc[0], sc[1], " ".join("%03d" % k for k in keys[:12]))]
    for i in slots[:40]:
        cells = []
        for k in keys[:12]:
            r = vs[k].get(i)
            cells.append("%.0f/%.0f(%.0f)" % r if r else "-")
        lines.append("  slot %3d: %s" % (i, "  ".join(cells)))
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text)


def fbnmap(field_root, out_dir, scene, variants, size=700):
    """Top-down picture of one scene's .FBN files: the base file (lowest number) as white squares, each other named variant as
    coloured dots, with a line from the base position to the variant position of the same slot. Slots at 0/0 or 0/71 (probably
    'unset') are grey. scene = 'field:scene' (6:3); variants = file numbers (110 112). Writes one PNG per variant + fbnmap.txt."""
    fnum, snum = [int(x) for x in scene.split(":")]
    files = {}
    for dp, _, fns in os.walk(field_root):
        for fn in fns:
            m = re.match(r"f(\d{3})_(\d{3})_(\d{3})\.fbn$", fn, re.I)
            if m and int(m.group(1)) == fnum and int(m.group(2)) == snum:
                d = open(os.path.join(dp, fn), "rb").read()
                if len(d) >= 12:
                    files[int(m.group(3))] = {r[0] - 0xC00: (r[2], r[4]) for r in fbn_records(d)}
    if not files:
        raise SystemExit("no .FBN files for scene %s" % scene)
    base_no = min(files); base = files[base_no]
    os.makedirs(out_dir, exist_ok=True)
    text = ["scene %s: %d files (%s). Base = %03d with %d slots." % (scene, len(files), " ".join("%03d" % k for k in sorted(files)), base_no, len(base))]
    cols = [(255, 80, 80), (80, 220, 80), (80, 160, 255), (255, 220, 0), (255, 80, 255), (0, 220, 220)]
    for vi, vn in enumerate(variants):
        if vn not in files:
            text.append("variant %03d: no such file" % vn); continue
        v = files[vn]; col = cols[vi % len(cols)]
        allp = list(base.values()) + list(v.values()) + [(0, 0)]
        lo_x = min(a for a, _ in allp); hi_x = max(a for a, _ in allp); lo_z = min(b for _, b in allp); hi_z = max(b for _, b in allp)
        span = max(hi_x - lo_x, hi_z - lo_z, 1.0); pad = 30; sc = (size - 2 * pad) / span
        W = H = size; px = bytearray([20, 20, 28] * (W * H))
        def P(x, z): return int(pad + (x - lo_x) * sc), int(H - pad - (z - lo_z) * sc)
        def put(x, y, c, r=0):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if 0 <= x + dx < W and 0 <= y + dy < H:
                        o = ((y + dy) * W + x + dx) * 3; px[o:o + 3] = bytes(c)
        def line(a, b, c):
            n = max(abs(b[0] - a[0]), abs(b[1] - a[1]), 1)
            for t in range(n + 1): put(a[0] + (b[0] - a[0]) * t // n, a[1] + (b[1] - a[1]) * t // n, c)
        ox, oy = P(0, 0)
        line((0, oy), (W - 1, oy), (60, 60, 60)); line((ox, 0), (ox, H - 1), (60, 60, 60))
        unset = lambda q: (abs(q[0]) < 0.5 and abs(q[1]) < 0.5) or (abs(q[0]) < 0.5 and abs(q[1] - 71) < 0.5)
        for i, q in base.items(): put(*P(*q), (255, 255, 255), 3)
        moved = same = new = placeholder = 0; rows = []
        for i, q in sorted(v.items()):
            c = (130, 130, 130) if unset(q) else col
            if unset(q): placeholder += 1
            if i in base:
                if not unset(q):
                    line(P(*base[i]), P(*q), c)
                if abs(base[i][0] - q[0]) <= 0.5 and abs(base[i][1] - q[1]) <= 0.5: same += 1
                else: moved += 1
                rows.append("  slot %3d: base %.0f/%.0f -> %.0f/%.0f%s" % (i, base[i][0], base[i][1], q[0], q[1], "  (placeholder)" if unset(q) else ""))
            else:
                new += 1; rows.append("  slot %3d: only in variant at %.0f/%.0f%s" % (i, q[0], q[1], "  (placeholder)" if unset(q) else ""))
            put(*P(*q), c, 3)
        path = os.path.join(out_dir, "f%03d_%03d_%03d_vs_%03d.png" % (fnum, snum, vn, base_no))
        _png(path, W, H, px)
        text.append("variant %03d: %d slots (%d moved vs base, %d unchanged, %d only in variant, %d placeholders) -> %s" % (vn, len(v), moved, same, new, placeholder, os.path.basename(path)))
        text += rows
    text.append("white square = base slot, coloured dot = variant slot, line = base to variant position, grey dot = placeholder (0/0 or 0/71), grey lines = axes through 0,0")
    open(os.path.join(out_dir, "fbnmap.txt"), "w").write("\n".join(text) + "\n")
    print("\n".join(text))


def fbnobj(field_root, out_dir, scene, variants, size=30.0):
    """Writes the .FBN slots of a scene as marker .obj files (one small pyramid per slot, group name slot_<n>, slot_<n>_unset for
    the placeholder positions 0/0 and 0/71). One file for the base (lowest number) and one per named variant. Same axes as the
    model .obj files, so import them with the same settings and they line up with the room."""
    fnum, snum = [int(x) for x in scene.split(":")]
    files = {}
    for dp, _, fns in os.walk(field_root):
        for fn in fns:
            m = re.match(r"f(\d{3})_(\d{3})_(\d{3})\.fbn$", fn, re.I)
            if m and int(m.group(1)) == fnum and int(m.group(2)) == snum:
                d = open(os.path.join(dp, fn), "rb").read()
                if len(d) >= 12:
                    files[int(m.group(3))] = [(r[0] - 0xC00, r[2], r[3], r[4]) for r in fbn_records(d)]
    if not files:
        raise SystemExit("no .FBN files for scene %s" % scene)
    os.makedirs(out_dir, exist_ok=True)
    for no in [min(files)] + [v for v in variants if v in files and v != min(files)]:
        lines = ["# .FBN slots of f%03d_%03d_%03d, one pyramid per slot" % (fnum, snum, no)]; vi = 0
        for i, x, y, z in sorted(files[no]):
            unset = abs(x) < 0.5 and (abs(z) < 0.5 or abs(z - 71) < 0.5)
            lines.append("o slot_%d%s" % (i, "_unset" if unset else ""))
            for dx, dy, dz in ((-size, 0, -size), (size, 0, -size), (size, 0, size), (-size, 0, size), (0, size * 3, 0)):
                lines.append("v %.3f %.3f %.3f" % (x + dx, y + dy, z + dz))
            b = vi
            lines += ["f %d %d %d %d" % (b + 1, b + 2, b + 3, b + 4)] + ["f %d %d %d" % (b + k, b + k % 4 + 1, b + 5) for k in (1, 2, 3, 4)]
            vi += 5
        path = os.path.join(out_dir, "f%03d_%03d_%03d_slots.obj" % (fnum, snum, no))
        open(path, "w").write("\n".join(lines) + "\n")
        print("wrote %s (%d slots)" % (path, len(files[no])))


def callprocs(scripts_root, out, names, limit=400):
    """Every call of the named script functions with its arguments and the proc it sits in (listing lines 'proc <name>:').
    Identical script files (the same script in many scene folders) are read once. Grouped by function and first argument,
    with the procs that use each value: shows what an id such as field_137(10241, ...) belongs to."""
    import hashlib
    want = set(names); seen = set(); rows = collections.defaultdict(lambda: collections.defaultdict(set))
    call = re.compile(r"([A-Za-z_][A-Za-z_0-9]*\??)\(([^()]*)\)")
    for dp, _, fns in os.walk(scripts_root):
        for fn in sorted(fns):
            if not fn.lower().endswith(".txt"):
                continue
            txt = open(os.path.join(dp, fn), errors="replace").read()
            h = hashlib.md5(txt.encode("utf-8", "replace")).hexdigest()
            if h in seen:
                continue
            seen.add(h); proc = "?"
            for ln in txt.split("\n"):
                m = re.match(r"\s*proc (\S+):", ln)
                if m:
                    proc = m.group(1); continue
                for c in call.finditer(ln):
                    if c.group(1) in want:
                        args = [a.strip() for a in c.group(2).split(",")]
                        rows[c.group(1)][args[0]].add("%s:%s(%s)" % (fn.replace(".bf.script.txt", ""), proc, ", ".join(args[1:])))
    lines = []
    for name in names:
        lines.append("%s: %d distinct first arguments" % (name, len(rows[name])))
        for a, v in sorted(rows[name].items(), key=lambda kv: (len(kv[0]), kv[0]))[:limit]:
            lines.append("  %s -> %s" % (a, "; ".join(sorted(v)[:6]) + (" ... (%d)" % len(v) if len(v) > 6 else "")))
        lines.append("")
    text = "\n".join(lines)
    open(out, "w").write(text)
    print(text[:3000])


def doorwhere(scripts_root, field_root, out, function="field_137", minid=10000):
    """Where do the ids a script function takes as first argument (default field_137, door ids like 10241) appear in the field's
    small files? Per file type: own-field hits against a control field, for the id as a 32-bit word and as a 16-bit word, plus
    the offset of hits inside their record and a few examples (words around the hit)."""
    call = re.compile(re.escape(function) + r"\((\d+)[,)]")
    ids = collections.defaultdict(set)
    for dp, _, fns in os.walk(scripts_root):
        m = re.match(r"F(\d{3})_\d{3}\.PAC\.D$", os.path.basename(dp).upper())
        if m:
            for fn in fns:
                if fn.lower().endswith(".txt"):
                    for c in call.finditer(open(os.path.join(dp, fn), errors="replace").read()):
                        if int(c.group(1)) >= minid:
                            ids[int(m.group(1))].add(int(c.group(1)))
    files = collections.defaultdict(list)
    for dp, _, fns in os.walk(field_root):
        m = re.match(r"F(\d{3})_\d{3}\.PAC\.D$", os.path.basename(dp).upper())
        if m and int(m.group(1)) in ids:
            for fn in sorted(fns):
                if os.path.splitext(fn)[1].lower() in (".hbn", ".fbn", ".bin"):
                    files[int(m.group(1))].append(os.path.join(dp, fn))
    names = sorted(f for f in ids if files.get(f))
    if len(names) < 2:
        raise SystemExit("need scripts and data for at least 2 fields")
    own = collections.Counter(); ctl = collections.Counter(); tested = collections.Counter()
    offs = collections.defaultdict(collections.Counter); examples = collections.defaultdict(list)
    for i, f in enumerate(names):
        other = names[(i + len(names) // 2) % len(names)]
        seen_in = collections.defaultdict(set)
        for path in files[f]:
            d = open(path, "rb").read(); ext = os.path.splitext(path)[1].lower()
            w32 = collections.defaultdict(list); w16 = collections.defaultdict(list)
            for off in range(0, len(d) - 3, 4):
                w32[struct.unpack_from("<I", d, off)[0]].append(off)
            for off in range(0, len(d) - 1, 2):
                w16[struct.unpack_from("<H", d, off)[0]].append(off)
            for kind, tab in (("u32", w32), ("u16", w16)):
                for v in ids[f]:
                    if (ext, kind, v) in seen_in[(ext, kind)]:
                        continue
                    if v in tab:
                        seen_in[(ext, kind)].add((ext, kind, v)); own[(ext, kind)] += 1
                        o = tab[v][0]; offs[(ext, kind)][o % (0x70 if ext == ".fbn" else 0x40)] += 1
                        if len(examples[(ext, kind)]) < 6:
                            ws = " ".join("%08X" % struct.unpack_from("<I", d, q)[0] for q in range(max(0, o - 16) & ~3, min(len(d) - 3, o + 20), 4))
                            examples[(ext, kind)].append("field %d id %d in %s at 0x%X: %s" % (f, v, os.path.basename(path), o, ws))
                    for v2 in ids[other]:
                        if v2 in tab and (ext, kind, "c", v2) not in seen_in[(ext, kind)]:
                            seen_in[(ext, kind)].add((ext, kind, "c", v2)); ctl[(ext, kind)] += 1
        for ext in (".hbn", ".fbn", ".bin"):
            for kind in ("u32", "u16"):
                tested[(ext, kind)] += len(ids[f]) if any(os.path.splitext(x)[1].lower() == ext for x in files[f]) else 0
    lines = ["%s first arguments of %d and up: %d fields with scripts and data; %d distinct ids in all." % (function, minid, len(names), sum(len(ids[f]) for f in names)), "",
             "file type / word size: own hits, control hits (ids tested)"]
    for k in sorted(tested):
        lines.append("  %-5s %-4s own %5d  control %5d  (of %d)" % (k[0], k[1], own[k], ctl[k], tested[k]))
    lines += ["", "Offset of own hits inside the record (mod 0x70 for .fbn, mod 0x40 otherwise), most common:"]
    for k, c in sorted(offs.items()):
        lines.append("  %-5s %-4s %s" % (k[0], k[1], ", ".join("0x%X:%d" % kv for kv in c.most_common(6))))
    lines += ["", "Examples:"]
    for k, ex in sorted(examples.items()):
        lines += ["  " + e for e in ex]
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text)


def hbin_records(d):
    """Door-like records of an h*.bin: 11 words (0x2C bytes) that start with FFFFFFFF and whose second word ends in 0x0401.
    Returns [(offset, words)]."""
    ws = struct.unpack_from("<%dI" % (len(d) // 4), d, 0)
    out = []; i = 0
    while i + 11 <= len(ws):
        if ws[i] == 0xFFFFFFFF and (ws[i + 1] & 0xFFFF) == 0x0401:
            out.append((i * 4, ws[i:i + 11])); i += 11
        else:
            i += 1
    return out


def hbinrecs(scripts_root, field_root, out, limit=60):
    """Decode the 0x2C-byte records of the h*.bin files (found by doorwhere to hold the door ids of field_137) and test them
    against the scripts: for each proc that calls field_137(id, ...) and then field_33(field, scene, k, 0), does the record
    of that id (in any h file of the field) hold k in the high half of word 3, and the destination scene in the low half of
    word 3? Control: the record with the same id in another field."""
    recs = collections.defaultdict(lambda: collections.defaultdict(list)); lines = []; gaps = collections.Counter(); nfiles = 0
    for dp, _, fns in os.walk(field_root):
        for fn in sorted(fns):
            m = re.match(r"h(\d{3})_(\d{3})\.bin$", fn, re.I)
            if not m:
                continue
            d = open(os.path.join(dp, fn), "rb").read()
            rs = hbin_records(d)
            if not rs:
                continue
            nfiles += 1
            for a, b in zip(rs, rs[1:]):
                gaps[b[0] - a[0]] += 1
            for off, w in rs:
                recs[int(m.group(1))][w[4]].append((fn, off, w))
            if len(lines) < limit:
                lines.append("%s: %d records, first at 0x%X, header words: %s" % (fn, len(rs), rs[0][0], " ".join("%08X" % x for x in struct.unpack_from("<%dI" % min(rs[0][0] // 4, 6), d, 0))))
                for off, w in rs[:6]:
                    lines.append("   0x%03X  id %d  w1 %08X  w2 %04X/%04X  w3 %04X/%04X  w5 %08X  w6 %08X  rest %s" % (off, w[4], w[1], w[2] >> 16, w[2] & 0xFFFF, w[3] >> 16, w[3] & 0xFFFF, w[5], w[6], "zero" if not any(w[7:]) else " ".join("%X" % x for x in w[7:])))
    call137 = re.compile(r"field_137\((\d+),"); call33 = re.compile(r"field_33\((\d+), (\d+), (\d+), (\d+)\)")
    seen = set(); pairs = []
    for dp, _, fns in os.walk(scripts_root):
        m = re.match(r"F(\d{3})_\d{3}\.PAC\.D$", os.path.basename(dp).upper())
        if not m:
            continue
        f = int(m.group(1))
        for fn in sorted(fns):
            if not fn.lower().endswith(".txt") or (f, fn) in seen:
                continue
            seen.add((f, fn)); cur = None; proc = None
            for ln in open(os.path.join(dp, fn), errors="replace").read().split("\n"):
                pm = re.match(r"\s*proc (\S+):", ln)
                if pm:
                    proc = pm.group(1); cur = None; continue
                a = call137.search(ln)
                if a and int(a.group(1)) >= 10000:
                    cur = int(a.group(1))
                b = call33.search(ln)
                if b and cur is not None:
                    pairs.append((f, cur, int(b.group(1)), int(b.group(2)), int(b.group(3)), proc)); cur = None
    flds = sorted(recs)
    own_k = ctl_k = own_s = ctl_s = own_b = ctl_b = n = nc = 0; ex = []; x_n = x_own = x_ctl = x_nc = 0
    for f, idv, df, ds, k, proc in pairs:
        r = recs[f].get(idv)
        other = next((g for g in flds if g != f and recs[g].get(idv)), None)
        if not r:
            continue
        n += 1
        own_k += any((w[3] >> 16) == k for _, _, w in r); own_s += any((w[3] & 0xFFFF) == ds for _, _, w in r); own_b += any((w[3] >> 16) == k and (w[3] & 0xFFFF) == ds for _, _, w in r)
        if df != f:
            x_n += 1; x_own += any(w[5] == df for _, _, w in r)
            if other:
                x_nc += 1; x_ctl += any(w[5] == df for _, _, w in recs[other][idv])
        if other:
            nc += 1; o = recs[other][idv]
            ctl_k += any((w[3] >> 16) == k for _, _, w in o); ctl_s += any((w[3] & 0xFFFF) == ds for _, _, w in o); ctl_b += any((w[3] >> 16) == k and (w[3] & 0xFFFF) == ds for _, _, w in o)
        if len(ex) < 25:
            ex.append("  field %d %s: field_137 id %d then field_33(%d, %d, %d) -> records: %s" % (f, proc, idv, df, ds, k, "; ".join("%s w2 %04X/%04X w3 %04X/%04X" % (fn, w[2] >> 16, w[2] & 0xFFFF, w[3] >> 16, w[3] & 0xFFFF) for fn, _, w in r[:3])))
    head = ["h*.bin files with records: %d. Gaps between records (bytes: count): %s" % (nfiles, ", ".join("0x%X: %d" % kv for kv in gaps.most_common(5))), "",
            "Procs with field_137(id) followed by field_33(f, s, k): %d, of which the id has a record in the field's h files: %d" % (len(pairs), n),
            "  k equals the high half of word 3: own %d of %d, control (same id, another field) %d of %d" % (own_k, n, ctl_k, nc),
            "  destination scene s equals the low half of word 3: own %d of %d, control %d of %d" % (own_s, n, ctl_s, nc),
            "  both (k in the high half and s in the low half of word 3): own %d of %d, control %d of %d" % (own_b, n, ctl_b, nc), "  word 5 equals the destination field, calls that leave the field only: own %d of %d, control %d of %d" % (x_own, x_n, x_ctl, x_nc), "", "Examples:"] + ex + ["", "Records:"]
    text = "\n".join(head + lines)
    open(out, "w").write(text + "\n")
    print("\n".join(head))


def eventvariants(scripts_root, field_root, out):
    """Does the step number of event_ctrl?(event, step, sub) pick the .FBN variant of the scene the proc goes to? For every proc
    that calls event_ctrl? with a step of 50 and up and field_33(field, scene, k, 0): is there a variant file with that number
    in that scene (own), against the same step in a different scene of the field (control). Also lists, per step, the scenes
    of the field that have a variant of that number."""
    var = collections.defaultdict(lambda: collections.defaultdict(set))
    for dp, _, fns in os.walk(field_root):
        for fn in fns:
            m = re.match(r"f(\d{3})_(\d{3})_(\d{3})\.fbn$", fn, re.I)
            if m:
                var[int(m.group(1))][int(m.group(2))].add(int(m.group(3)))
    ev = re.compile(r"event_ctrl\?\((\d+), (\d+), (\d+)\)"); wa = re.compile(r"field_33\((\d+), (\d+), (\d+), (\d+)\)")
    seen = set(); rows = []
    for dp, _, fns in os.walk(scripts_root):
        m = re.match(r"F(\d{3})_\d{3}\.PAC\.D$", os.path.basename(dp).upper())
        if not m:
            continue
        f = int(m.group(1))
        for fn in sorted(fns):
            if not fn.lower().endswith(".txt") or (f, fn) in seen:
                continue
            seen.add((f, fn)); proc = None; evs = []; wps = []
            def flush():
                for e, st in evs:
                    for df, ds in wps:
                        rows.append((f, proc, e, st, df, ds))
            for ln in open(os.path.join(dp, fn), errors="replace").read().split("\n"):
                pm = re.match(r"\s*proc (\S+):", ln)
                if pm:
                    flush(); proc = pm.group(1); evs = []; wps = []; continue
                for c in ev.finditer(ln):
                    if int(c.group(2)) >= 50:
                        evs.append((int(c.group(1)), int(c.group(2))))
                for c in wa.finditer(ln):
                    wps.append((int(c.group(1)), int(c.group(2))))
            flush()
    n = own = ctl = nc = 0; ex = []
    for f, proc, e, st, df, ds in rows:
        scenes = var.get(df)
        if not scenes or ds not in scenes:
            continue
        n += 1; hit = st in scenes[ds]; own += hit
        others = [x for x in sorted(scenes) if x != ds]
        if others:
            nc += 1; ctl += st in scenes[others[(st + e) % len(others)]]
        if len(ex) < 40:
            ex.append("  field %d %s: event_ctrl?(%d, %d, ..) and field_33(%d, %d, ..): scene %d has variants %s%s" % (f, proc, e, st, df, ds, ds, "yes" if hit else "no", "" if hit else " (variants of that scene: %s)" % " ".join("%03d" % v for v in sorted(scenes[ds]))))
    steps = collections.defaultdict(set)
    for f, proc, e, st, df, ds in rows:
        steps[(f, st)].add(tuple(sorted(s_ for s_, v in var.get(f, {}).items() if st in v)))
    lines = ["Procs with event_ctrl?(event, step >= 50, ..) and field_33(field, scene, ..): %d pairs, of which the destination scene has .FBN files: %d" % (len(rows), n),
             "  the scene has a variant file numbered like the step: own %d of %d, control (another scene of the field) %d of %d" % (own, n, ctl, nc), "", "Examples:"] + ex + ["", "Scenes that have a variant of each step (field, step: scenes):"]
    for (f, st), sc in sorted(steps.items()):
        lines.append("  field %d step %d: %s" % (f, st, " | ".join(" ".join(str(x) for x in t) or "none" for t in sorted(sc))))
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print("\n".join(lines[:6]))


def fbndump(field_root, out, scene, variants):
    """Every word of every record of the named .FBN variant files of a scene, as hex with the float reading next to it
    (words that are all zero are skipped), to see which fields besides the position tell an NPC or object apart."""
    fnum, snum = [int(x) for x in scene.split(":")]
    found = {}
    for dp, _, fns in os.walk(field_root):
        for fn in fns:
            m = re.match(r"f(\d{3})_(\d{3})_(\d{3})\.fbn$", fn, re.I)
            if m and int(m.group(1)) == fnum and int(m.group(2)) == snum and int(m.group(3)) in variants:
                found[int(m.group(3))] = open(os.path.join(dp, fn), "rb").read()
    lines = []
    for no in sorted(found):
        d = found[no]
        lines.append("== f%03d_%03d_%03d.FBN: %d bytes, header words: %s" % (fnum, snum, no, len(d), " ".join("%08X" % x for x in struct.unpack_from("<6I", d, 0))))
        for k in range(struct.unpack_from("<I", d, 8)[0]):
            b = 0x18 + 0x70 * k
            if b + 0x70 > len(d):
                break
            ws = struct.unpack_from("<28I", d, b)
            lines.append("  record %d: id %d (slot %d)" % (k, ws[2], ws[2] - 0xC00))
            for i, w in enumerate(ws):
                if w:
                    f = struct.unpack("<f", struct.pack("<I", w))[0]
                    lines.append("     +0x%02X  %08X  %-12d %s" % (i * 4, w, w if w < 0x80000000 else w - (1 << 32), ("%.3f" % f) if math.isfinite(f) and 1e-4 < abs(f) < 1e6 else ""))
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print("wrote %s (%d files, %d lines)" % (out, len(found), len(lines)))


def fbnchars(field_root, out, field=6, variants=(110, 111, 112, 113, 114, 115, 150)):
    """The high half of the word at +4 of an .FBN record looks like a character or model id (the same value follows one person
    from slot to slot and from variant to variant). For the named variants of one field: per scene the character ids with their
    slot and position, and the ids that occur in every scene having that variant. Tests whether a variant number names a person."""
    sc = collections.defaultdict(dict)
    for dp, _, fns in os.walk(field_root):
        for fn in fns:
            m = re.match(r"f(\d{3})_(\d{3})_(\d{3})\.fbn$", fn, re.I)
            if m and int(m.group(1)) == field and int(m.group(3)) in variants:
                d = open(os.path.join(dp, fn), "rb").read()
                if len(d) >= 12:
                    sc[int(m.group(3))][int(m.group(2))] = [(r[0] - 0xC00, struct.unpack_from("<I", d, 0x18 + 0x70 * k + 4)[0] >> 16, r[2], r[4]) for k, r in enumerate(fbn_records(d))]
    lines = []
    for v in sorted(sc):
        scenes = sc[v]
        ids = [set(c for _, c, _, _ in recs if c > 1) for recs in scenes.values()]
        common = set.intersection(*ids) if ids else set()
        lines.append("== variant %d: scenes %s; character ids in every scene: %s" % (v, " ".join(str(x) for x in sorted(scenes)), " ".join("%04X" % c for c in sorted(common)) or "none"))
        for s_, recs in sorted(scenes.items()):
            lines.append("   scene %d: %s" % (s_, "  ".join("slot%d:%04X@%.0f/%.0f" % (sl, c, x, z) for sl, c, x, z in recs)))
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print("\n".join(l for l in lines if l.startswith("==")))


def nbin(root, out):
    """Statistics of the n###_###.bin tables, read as 0x20-byte records (8 words)."""
    files = []
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            if re.match(r"n\d+_\d+\.bin$", fn, re.I):
                files.append(os.path.join(dp, fn))
    if not files:
        raise SystemExit("no n###_###.bin files found under " + root)
    sizes = collections.Counter(os.path.getsize(f) for f in files)
    lines = ["%d n*.bin files; sizes (bytes: files): %s" % (len(files), ", ".join("%d:%d" % kv for kv in sorted(sizes.items())[:40])),
             "files whose size is a multiple of 0x20: %d" % sum(1 for f in files if os.path.getsize(f) % 32 == 0), ""]
    cols = [collections.Counter() for _ in range(8)]
    nrec = 0
    for f in files:
        d = open(f, "rb").read()
        for r in range(0, len(d) - 31, 32):
            nrec += 1
            for k in range(8):
                cols[k][struct.unpack_from("<I", d, r + 4 * k)[0]] += 1
    lines.append("Records: %d. Word position in the record: distinct values, most common (value x count)" % nrec)
    for k in range(8):
        lines.append("  +0x%02X: %6d distinct; %s" % (4 * k, len(cols[k]), ", ".join("0x%X x%d" % kv for kv in cols[k].most_common(8))))
    big = sorted(files, key=os.path.getsize, reverse=True)[:3]
    for f in big:
        d = open(f, "rb").read()
        lines += ["", "%s (%d bytes), records with a value other than 0 / 0xFFFFFFFF:" % (os.path.basename(f), len(d))]
        shown = 0
        for r in range(0, len(d) - 31, 32):
            w = struct.unpack_from("<8I", d, r)
            if any(x not in (0, 0xFFFFFFFF) for x in w) and shown < 70:
                lines.append("  %04X  %s" % (r, " ".join("%08X" % x for x in w)))
                shown += 1
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text[:3000])
    print("\nwritten to " + out)


def parse_ncal(d):
    """n###_###.bin as a calendar: header (count), `count` date records, then groups of entries.
    Date record (0x20 bytes): month (low half of word 0), day (high half), time-of-day word, 0xFFFFFFFF, group number.
    Group section: entries (word 0 = 0x0005_kkkk slot, word 1 code, word 2 parameter) ended by a 0x0000FFFF record."""
    n = len(d) // 32
    if n == 0:
        return None
    count = struct.unpack_from("<I", d, 0)[0]
    dates = []
    for i in range(1, min(n, count + 1)):
        w = struct.unpack_from("<8I", d, 32 * i)
        dates.append(((w[0] & 0xFFFF), (w[0] >> 16), w[1], w[2], w[3], w[4:]))
    groups = [[]]
    for i in range(count + 1, n):
        w = struct.unpack_from("<8I", d, 32 * i)
        if w[0] == 0xFFFF:
            groups.append([])
        else:
            groups[-1].append(w)
    return {"count": count, "records": n, "dates": dates, "groups": groups}


def ncal(root, out):
    files = []
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            if re.match(r"n\d+_\d+\.bin$", fn, re.I):
                files.append(os.path.join(dp, fn))
    if not files:
        raise SystemExit("no n###_###.bin files found under " + root)
    lines = []
    valid = bad = 0
    codes = collections.Counter()
    slots = collections.Counter()
    types = collections.Counter()
    fits_count = 0
    for f in files:
        d = open(f, "rb").read()
        r = parse_ncal(d)
        if not r:
            continue
        fits_count += r["count"] + 1 <= r["records"]
        ok = [x for x in r["dates"] if 1 <= x[0] <= 12 and 1 <= x[1] <= 31]
        valid += len(ok)
        bad += len(r["dates"]) - len(ok)
        for x in r["dates"]:
            types[x[2]] += 1
        for g in r["groups"]:
            for w in g:
                codes[w[1]] += 1
                slots[w[0]] += 1
        lines.append("%s: %d bytes, header count %d, %d date records (%d valid month/day), %d groups" % (
            os.path.basename(f), len(d), r["count"], len(r["dates"]), len(ok), len(r["groups"])))
    head = ["%d files; date records with a valid month 1-12 and day 1-31: %d, invalid: %d" % (len(files), valid, bad),
            "files where the header count fits inside the file: %d" % fits_count,
            "time-of-day word values (value x count): " + ", ".join("0x%X x%d" % kv for kv in types.most_common(12)),
            "entry word 0 values (slot): " + ", ".join("0x%X x%d" % kv for kv in slots.most_common(12)),
            "entry codes (word 1), most common: " + ", ".join("%d x%d" % kv for kv in codes.most_common(25)), ""]
    text = "\n".join(head + lines)
    # one readable example: the file with the most date records
    best = max(files, key=os.path.getsize)
    r = parse_ncal(open(best, "rb").read())
    ex = ["", "Example (%s): dates as month/day -> time word, group number" % os.path.basename(best)]
    ex.append("  " + "  ".join("%d/%d:%X->g%d" % (m, dd, t, g) for m, dd, t, _, g, _ in r["dates"][:80]))
    ex.append("First groups (slot code parameter flags):")
    for gi, g in enumerate(r["groups"][:12]):
        ex.append("  group %d: " % gi + "; ".join("%d %d %d 0x%X" % (w[0] & 0xFFFF, w[1], w[2] if w[2] != 0xFFFFFFFF else -1, w[4]) for w in g))
    text += "\n" + "\n".join(ex)
    open(out, "w").write(text + "\n")
    print(text[:3500])
    print("\nwritten to " + out)


def ncodes(scripts_root, field_root, out, minid=20):
    """Which numbers derived from the calendar entries (n*.bin) show up as object ids in the same field's scripts?
    Each entry code is tried as itself, as high/low 16 bits, and as (code-1)/50; the parameter word is tried too.
    A control (another field's scripts) shows what chance would give."""
    call = re.compile(r"field_(313|357)\((-?\d+), (-?\d+)\)")
    ids = collections.defaultdict(set)
    for dp, _, fns in os.walk(scripts_root):
        base = os.path.basename(dp).upper()
        if not base.endswith(".PAC.D"):
            continue
        for fn in fns:
            if fn.lower().endswith(".txt"):
                with open(os.path.join(dp, fn), errors="replace") as fh:
                    for m in call.finditer(fh.read()):
                        v = int(m.group(3))
                        if v >= minid:
                            ids[base].add(v)
    derived = collections.defaultdict(lambda: collections.defaultdict(set))   # field -> view -> values
    for dp, _, fns in os.walk(field_root):
        base = os.path.basename(dp).upper()
        for fn in fns:
            if re.match(r"n\d+_\d+\.bin$", fn, re.I) and base in ids:
                r = parse_ncal(open(os.path.join(dp, fn), "rb").read())
                if not r:
                    continue
                for g in r["groups"]:
                    for w in g:
                        c = w[1]
                        derived[base]["code"].add(c)
                        derived[base]["low16"].add(c & 0xFFFF)
                        derived[base]["high16"].add(c >> 16)
                        if c % 50 == 1:
                            derived[base]["(code-1)/50"].add((c - 1) // 50)
                        if w[2] != 0xFFFFFFFF:
                            derived[base]["param"].add(w[2])
                for x in r["dates"]:
                    derived[base]["date group"].add(x[4])
    names = sorted(n for n in derived if n in ids)
    if len(names) < 2:
        raise SystemExit("need at least 2 fields with scripts and an n table")
    views = ["code", "low16", "high16", "(code-1)/50", "param", "date group"]
    own = collections.Counter(); ctl = collections.Counter(); tot = collections.Counter(); ex = []
    for i, n in enumerate(names):
        other = names[(i + len(names) // 2) % len(names)]
        for v in views:
            vals = {x for x in derived[n][v] if x >= minid}
            tot[v] += len(ids[n])
            hit = vals & ids[n]
            own[v] += len(hit)
            ctl[v] += len(vals & ids[other])
            if hit and len(ex) < 40 and v in ("low16", "(code-1)/50", "code"):
                ex.append("%s %s: %s" % (n, v, sorted(hit)[:8]))
    lines = ["Fields with scripts and a calendar: %d. Script ids below %d ignored." % (len(names), minid), "",
             "View of the calendar entries -> script ids found among them (own field vs control field), out of all script ids of those fields:"]
    for v in views:
        lines.append("  %-12s own %5d  control %5d  (of %d script ids)" % (v, own[v], ctl[v], tot[v]))
    lines += ["", "Examples:"] + ["  " + e for e in ex]
    text = "\n".join(lines)
    open(out, "w").write(text + "\n")
    print(text)


def fbnlink(field_root, out, minid=0):
    """Compare a field's calendar (n*.bin) with its .FBN placement files: do the slot numbers match the FBN ids (0xC00+slot),
    and do the group / parameter numbers match the numbers in the FBN file names (f006_003_105.FBN -> 105)?"""
    folders = collections.defaultdict(dict)
    for dp, _, fns in os.walk(field_root):
        base = os.path.basename(dp).upper()
        if not base.endswith(".PAC.D"):
            continue
        for fn in fns:
            if re.match(r"n\d+_\d+\.bin$", fn, re.I):
                folders[base]["n"] = os.path.join(dp, fn)
            m = re.match(r"f\d+_\d+_(\d+)\.fbn$", fn, re.I)
            if m:
                folders[base].setdefault("fbn", {})[int(m.group(1))] = os.path.join(dp, fn)
    names = sorted(n for n in folders if "n" in folders[n] and folders[n].get("fbn"))
    if len(names) < 2:
        raise SystemExit("need folders with both an n table and .FBN files")
    lines = []
    tot = collections.Counter()
    ctl = collections.Counter()
    shown = 0
    info = {}
    for n in names:
        r = parse_ncal(open(folders[n]["n"], "rb").read())
        slots = {w[0] & 0xFFFF for g in r["groups"] for w in g}
        groups = {x[4] for x in r["dates"] if x[4] != 0xFFFFFFFF}
        params = {w[2] for g in r["groups"] for w in g if w[2] != 0xFFFFFFFF}
        suffix = set(folders[n]["fbn"])
        ids = set()
        for path in folders[n]["fbn"].values():
            d = open(path, "rb").read()
            cnt = struct.unpack_from("<I", d, 8)[0] if len(d) >= 12 else 0
            for k in range(cnt):
                o = 0x18 + 0x70 * k + 8
                if o + 4 <= len(d):
                    v = struct.unpack_from("<I", d, o)[0]
                    if 0xC00 <= v < 0xD00:
                        ids.add(v - 0xC00)
        keep = lambda S: {v for v in S if v >= minid}
        info[n] = (keep(slots), keep(groups), keep(params), keep(suffix), keep(ids))
    for i, n in enumerate(names):
        slots, groups, params, suffix, ids = info[n]
        o = info[names[(i + len(names) // 2) % len(names)]]
        tot["slots found among FBN ids"] += len(slots & ids); tot["slots"] += len(slots)
        ctl["slots found among FBN ids"] += len(slots & o[4])
        tot["date groups that are FBN name numbers"] += len(groups & suffix); tot["date groups"] += len(groups)
        ctl["date groups that are FBN name numbers"] += len(groups & o[3])
        tot["parameters that are FBN name numbers"] += len(params & suffix); tot["parameters"] += len(params)
        ctl["parameters that are FBN name numbers"] += len(params & o[3])
        for nm, S in (("date groups", groups), ("parameters", params)):
            k = nm + " that are FBN ids"
            tot[k] += len(S & ids); tot[nm + " (ids)"] += len(S)
            ctl[k] += len(S & o[4])
        if shown < 25:
            shown += 1
            lines.append("%s: slots %s | FBN ids %s | date groups %s | FBN name numbers %s | parameters %s" % (
                n, sorted(slots)[:14], sorted(ids)[:14], sorted(groups)[:14], sorted(suffix)[:14], sorted(params)[:14]))
    head = ["Folders with a calendar and .FBN files: %d" % len(names), "",
            "Overlaps (own field versus control = another field), with the number of values tested:"]
    for k in ("slots found among FBN ids", "date groups that are FBN name numbers", "parameters that are FBN name numbers", "date groups that are FBN ids", "parameters that are FBN ids"):
        tot_k = k.split(" found")[0].split(" that")[0]
        if k.endswith("FBN ids") and tot_k != "slots":
            tot_k += " (ids)"
        head.append("  %-42s own %6d  control %6d  (of %d)" % (k, tot[k], ctl[k], tot[tot_k]))
    text = "\n".join(head + [""] + lines)
    open(out, "w").write(text + "\n")
    print(text)


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
    oi = sp.add_parser("objids", help="check the object ids of field_313/field_357 calls against model file names")
    oi.add_argument("scripts", help="folder with the script listings (.script.txt)")
    oi.add_argument("models", help="folder with the extracted model files")
    oi.add_argument("-o", "--out", default="objids.txt")
    od = sp.add_parser("objdata", help="do the script object ids appear as numbers in the field's own small data files?")
    od.add_argument("scripts")
    od.add_argument("fields")
    od.add_argument("-o", "--out", default="objdata.txt")
    nb = sp.add_parser("nbin", help="statistics of the n###_###.bin tables read as 0x20-byte records")
    nb.add_argument("root")
    nb.add_argument("-o", "--out", default="nbin.txt")
    nc = sp.add_parser("ncal", help="read the n###_###.bin tables as calendars (dates, groups)")
    nc.add_argument("root")
    nc.add_argument("-o", "--out", default="ncal.txt")
    nk = sp.add_parser("ncodes", help="do numbers from the calendar entries match the object ids in the same field's scripts?")
    nk.add_argument("scripts")
    nk.add_argument("fields")
    nk.add_argument("-o", "--out", default="ncodes.txt")
    fk = sp.add_parser("fbnlink", help="compare each field's calendar with its .FBN placement files")
    fk.add_argument("fields")
    fk.add_argument("-o", "--out", default="fbnlink.txt")
    fk.add_argument("--minid", type=int, default=0, help="ignore values below this (small numbers overlap by chance)")
    ow = sp.add_parser("objwhere", help="where each script function's ids appear in the field data")
    ow.add_argument("scripts"); ow.add_argument("fields")
    ow.add_argument("-o", "--out", default="objwhere.txt")
    cc = sp.add_parser("calcalls", help="test whether field_357/313 ids are calendar group numbers / entry codes")
    cc.add_argument("scripts"); cc.add_argument("fields")
    cc.add_argument("-o", "--out", default="calcalls.txt")
    dc = sp.add_parser("datecheck", help="test whether field_357 group dates lie inside the date_in_range just before the call")
    dc.add_argument("scripts"); dc.add_argument("fields")
    dc.add_argument("-o", "--out", default="datecheck.txt")
    hb = sp.add_parser("hbn", help="section-by-section statistics of the .hbn files")
    hb.add_argument("fields")
    hb.add_argument("-o", "--out", default="hbn.txt")
    hl = sp.add_parser("hbnlink", help="do .HBN points sit on .FBN positions of the same field; strings versus sections")
    hl.add_argument("fields")
    hl.add_argument("-o", "--out", default="hbnlink.txt")
    hm = sp.add_parser("hbnmap", help="top-down pictures of the points in .hbn files")
    hm.add_argument("fields"); hm.add_argument("-o", "--out", default="hbnmap")
    hm.add_argument("--models", help="folder of exported field .obj files (from the `fields` command); draws their footprint under the points")
    hm.add_argument("--match", help="only files whose name contains this"); hm.add_argument("--limit", type=int, default=40)
    hp = sp.add_parser("hbnprops", help="do .HBN points sit at the centres of the small objects of the exported field model")
    hp.add_argument("fields"); hp.add_argument("models")
    hp.add_argument("-o", "--out", default="hbnprops.txt"); hp.add_argument("--radius", type=float, default=100.0)
    sc_ = sp.add_parser("slotcalls", help="are field_312 numbers the .FBN slot numbers or .HBN record numbers of the scene")
    sc_.add_argument("scripts"); sc_.add_argument("fields")
    sc_.add_argument("-o", "--out", default="slotcalls.txt")
    c3 = sp.add_parser("calls312", help="context of every field_312 call")
    c3.add_argument("scripts"); c3.add_argument("fields")
    c3.add_argument("-o", "--out", default="calls312.txt")
    wc = sp.add_parser("warpcalls", help="is the third number of field_33 the number of an .FBN file of the destination")
    wc.add_argument("scripts"); wc.add_argument("fields")
    wc.add_argument("-o", "--out", default="warpcalls.txt")
    va = sp.add_parser("variantargs", help="which script function takes the number of an .FBN variant file")
    va.add_argument("scripts"); va.add_argument("fields")
    va.add_argument("-o", "--out", default="variantargs.txt"); va.add_argument("--minvalue", type=int, default=50)
    vc = sp.add_parser("variantcalls", help="call sites of functions found by variantargs (name:argument position)")
    vc.add_argument("scripts"); vc.add_argument("fields"); vc.add_argument("specs", nargs="+")
    vc.add_argument("-o", "--out", default="variantcalls.txt")
    fv = sp.add_parser("fbnvariants", help="how the variant files of a scene differ")
    fv.add_argument("fields")
    fv.add_argument("-o", "--out", default="fbnvariants.txt")
    fm = sp.add_parser("fbnmap", help="picture of a scene's base .FBN against variants")
    fm.add_argument("fields"); fm.add_argument("scene", help="field:scene, e.g. 6:3"); fm.add_argument("variants", nargs="+", type=int)
    fm.add_argument("-o", "--out", default="fbnmap")
    fo = sp.add_parser("fbnobj", help="write a scene's .FBN slots as marker .obj files")
    fo.add_argument("fields"); fo.add_argument("scene", help="field:scene, e.g. 6:3"); fo.add_argument("variants", nargs="*", type=int)
    fo.add_argument("-o", "--out", default="fbnobj")
    cp = sp.add_parser("callprocs", help="calls of named functions with their arguments and the proc they sit in")
    cp.add_argument("scripts"); cp.add_argument("names", nargs="+"); cp.add_argument("-o", "--out", default="callprocs.txt")
    dw = sp.add_parser("doorwhere", help="where a function's big first-argument ids appear in the small field files")
    dw.add_argument("scripts"); dw.add_argument("fields"); dw.add_argument("-f", "--function", default="field_137")
    dw.add_argument("--minid", type=int, default=10000); dw.add_argument("-o", "--out", default="doorwhere.txt")
    hr = sp.add_parser("hbinrecs", help="decode the 0x2C-byte door records in h*.bin and test them against the scripts")
    hr.add_argument("scripts"); hr.add_argument("fields"); hr.add_argument("-o", "--out", default="hbinrecs.txt")
    evp = sp.add_parser("eventvariants", help="does event_ctrl? step pick the .FBN variant of the destination scene?")
    evp.add_argument("scripts"); evp.add_argument("fields"); evp.add_argument("-o", "--out", default="eventvariants.txt")
    fd = sp.add_parser("fbndump", help="every non-zero word of the records of named .FBN variants")
    fd.add_argument("fields"); fd.add_argument("scene"); fd.add_argument("variants", nargs="+", type=int); fd.add_argument("-o", "--out", default="fbndump.txt")
    fcp = sp.add_parser("fbnchars", help="character ids (+4 high half) of .FBN records per variant")
    fcp.add_argument("fields"); fcp.add_argument("-f", "--field", type=int, default=6); fcp.add_argument("-o", "--out", default="fbnchars.txt")
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
    elif a.cmd == "objids":
        objids(a.scripts, a.models, a.out)
    elif a.cmd == "objdata":
        objdata(a.scripts, a.fields, a.out)
    elif a.cmd == "nbin":
        nbin(a.root, a.out)
    elif a.cmd == "ncal":
        ncal(a.root, a.out)
    elif a.cmd == "ncodes":
        ncodes(a.scripts, a.fields, a.out)
    elif a.cmd == "fbnlink":
        fbnlink(a.fields, a.out, a.minid)
    elif a.cmd == "objwhere":
        objwhere(a.scripts, a.fields, a.out)
    elif a.cmd == "calcalls":
        calcalls(a.scripts, a.fields, a.out)
    elif a.cmd == "datecheck":
        datecheck(a.scripts, a.fields, a.out)
    elif a.cmd == "hbn":
        hbn(a.fields, a.out)
    elif a.cmd == "hbnlink":
        hbnlink(a.fields, a.out)
    elif a.cmd == "hbnmap":
        hbnmap(a.fields, a.out, a.match, a.limit, models=a.models)
    elif a.cmd == "hbnprops":
        hbnprops(a.fields, a.models, a.out, a.radius)
    elif a.cmd == "slotcalls":
        slotcalls(a.scripts, a.fields, a.out)
    elif a.cmd == "calls312":
        calls312(a.scripts, a.fields, a.out)
    elif a.cmd == "warpcalls":
        warpcalls(a.scripts, a.fields, a.out)
    elif a.cmd == "variantargs":
        variantargs(a.scripts, a.fields, a.out, a.minvalue)
    elif a.cmd == "variantcalls":
        variantcalls(a.scripts, a.fields, a.out, a.specs)
    elif a.cmd == "fbnvariants":
        fbnvariants(a.fields, a.out)
    elif a.cmd == "fbnmap":
        fbnmap(a.fields, a.out, a.scene, a.variants)
    elif a.cmd == "fbnobj":
        fbnobj(a.fields, a.out, a.scene, a.variants)
    elif a.cmd == "callprocs":
        callprocs(a.scripts, a.out, a.names)
    elif a.cmd == "doorwhere":
        doorwhere(a.scripts, a.fields, a.out, a.function, a.minid)
    elif a.cmd == "hbinrecs":
        hbinrecs(a.scripts, a.fields, a.out)
    elif a.cmd == "eventvariants":
        eventvariants(a.scripts, a.fields, a.out)
    elif a.cmd == "fbndump":
        fbndump(a.fields, a.out, a.scene, a.variants)
    elif a.cmd == "fbnchars":
        fbnchars(a.fields, a.out, a.field)
    elif a.cmd == "dump":
        dump(a.file)
    elif a.cmd == "names":
        names(a.root, a.out)
    elif a.cmd == "words":
        words(a.root, a.ext, a.out or "field_words_%s.txt" % a.ext.lower().lstrip("."))


if __name__ == "__main__":
    main()
