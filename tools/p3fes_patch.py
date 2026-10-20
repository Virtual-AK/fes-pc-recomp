#!/usr/bin/env python3
"""
p3fes_patch.py - put changed files back into a COPY of your disc image (step 1: in-place patching).

You give it your original disc image and a folder of changed files, laid out exactly like
the folder p3fes_unpack.py made (for example C:\\p3fes\\mod_files\\BTL.CVM\\BATTLE\\PANEL\\
BP_TUTORIAL.BIN.d\\bp_tutorial1.bmd). It makes a NEW disc image with those files replaced. Your
original image is never changed.

What it can do now:
  * replace a plain file inside a CVM archive, and
  * replace a file inside a container (.BIN/.PAC/.PAK/.CPK, shown as a ".d" folder),
    rebuilding the container and shifting the files after it inside the container.
The changed file or container must still fit in the space it already has on the disc (the rest
of its last 2048-byte sector, plus any free space before the next file). If it does not fit, the
tool says so and by how much, and writes nothing. Making room is the next step of this tool.

Always run with --dry-run first: it only prints what would happen.

Usage (from a Command Prompt in the folder that holds the tool scripts):
    py p3fes_patch.py "C:\\path\\to\\game.iso" "C:\\p3fes\\mod_files" --dry-run
    py p3fes_patch.py "C:\\path\\to\\game.iso" "C:\\p3fes\\mod_files" -o "C:\\p3fes\\modded.iso"

Options:
    -o FILE      the new disc image to write (required unless --dry-run)
    --dry-run    show the plan, change nothing
    --force      overwrite the output file if it exists
    --learn-align  scan every container on the disc and report which entry alignments they use
                 (takes a few minutes; send me the two result lines)
    --align N    the alignment of entries inside containers (16, 32, 64, 128...). Only needed when the
                 tool says it cannot tell. Use the number you trust, e.g. from p3fes_formats.py's report.
The new image needs as much free disk space as the original (about 4.2 GB).
Test the result in an emulator before relying on it. Standard library only, Python 3.8+.
"""
import argparse
import os
import shutil
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3fes_unpack as U  # noqa: E402  (must sit in the same folder)

SECTOR = U.SECTOR


class ToolError(Exception):
    pass


def align_up(n, a):
    return (n + a - 1) // a * a


# ------------------------------------------------------------ reading the image

def list_with_positions(win):
    """Like U.list_files, but also returns where each directory record sits (offset inside win)."""
    pvd = win.read_at(16 * SECTOR, SECTOR)
    if len(pvd) < 190 or pvd[1:6] != b"CD001":
        raise ToolError("no ISO9660 volume descriptor found")
    root_extent = struct.unpack_from("<I", pvd, 156 + 2)[0]
    root_size = struct.unpack_from("<I", pvd, 156 + 10)[0]
    out, visited = [], set()

    def walk(lba, size, path):
        if (lba, size) in visited or size <= 0 or size > 64 * 1024 * 1024:
            return
        visited.add((lba, size))
        data = win.read_at(lba * SECTOR, size)
        pos = 0
        while pos < len(data):
            n = data[pos]
            if n == 0:
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            if n < 34 or pos + n > len(data):
                break
            rec = data[pos:pos + n]
            extent = struct.unpack_from("<I", rec, 2)[0]
            length = struct.unpack_from("<I", rec, 10)[0]
            flags = rec[25]
            name = rec[33:33 + rec[32]]
            at = lba * SECTOR + pos
            pos += n
            if name in (b"\x00", b"\x01"):
                continue
            name = name.decode("ascii", "replace").split(";")[0]
            full = path + "/" + name
            if flags & 0x02:
                walk(extent, length, full)
            else:
                out.append({"path": full, "lba": extent, "size": length, "rec_at": at})

    walk(root_extent, root_size, "")
    out.sort(key=lambda e: e["lba"])
    return out


def open_image(f, fsize):
    top = Window_(f, 0, fsize)
    return top, list_with_positions(top)


def Window_(f, base, size):
    return U.Window(f, base, size)


def find_cvm(f, top_files, name):
    for e in top_files:
        if e["path"].upper() == "/" + name.upper():
            cvm = U.Window(f, e["lba"] * SECTOR, e["size"])
            off = 16 * SECTOR
            limit = min(cvm.size, U.HEADER_SCAN_LIMIT)
            while off + 6 <= limit:
                if U.has_pvd(cvm, off):
                    inner = U.Window(f, cvm.base + off - 16 * SECTOR, cvm.size - (off - 16 * SECTOR))
                    return e, inner, list_with_positions(inner)
                off += SECTOR
            raise ToolError("%s does not look like a CVM archive" % name)
    return None


class BytesView:
    def __init__(self, data):
        self.data = data
        self.size = len(data)

    def read_at(self, pos, n):
        return self.data[pos:pos + n]


# ------------------------------------------------------------ containers

def valid_rules(starts, ends):
    return [x for x in (16, 32, 64, 128, 256, 512, 1024, 2048, 4096)
            if all(starts[k + 1] == align_up(ends[k], x) for k in range(len(starts) - 1))]


def learn_align(f, fsize):
    """Count, over every container on the disc, which entry alignments each one is consistent with."""
    top, top_files = open_image(f, fsize)
    decisive, ambiguous, none, unreadable, scanned = {}, 0, 0, 0, 0
    for e in top_files:
        if not e["path"].upper().endswith(".CVM"):
            continue
        got = find_cvm(f, top_files, e["path"][1:])
        if not got:
            continue
        _, inner, inner_files = got
        todo = [x for x in inner_files if os.path.splitext(x["path"])[1].lower() in U.PAK_EXTS and 256 < x["size"] <= 64 * 1024 * 1024]
        for k, x in enumerate(todo):
            data = inner.read_at(x["lba"] * SECTOR, x["size"])
            info = U.analyse_pak(BytesView(data))
            scanned += 1
            if not info.get("ok") or len(info["entries"]) < 2:
                unreadable += 1
                continue
            st = info["starts"]
            en = [st[i] + 256 + info["entries"][i][1] for i in range(len(st))]
            v = valid_rules(st, en)
            if len(v) == 1:
                decisive[v[0]] = decisive.get(v[0], 0) + 1
            elif v:
                ambiguous += 1
            else:
                none += 1
            if k % 200 == 0:
                sys.stderr.write("\r  %s %d/%d" % (e["path"], k, len(todo)))
                sys.stderr.flush()
    sys.stderr.write("\r" + " " * 60 + "\r")
    print("Containers scanned: %d (%d with a single entry or unreadable, %d ambiguous, %d fit no simple rule)" % (
        scanned, unreadable, ambiguous, none))
    print("Containers where exactly one alignment fits: " + (", ".join("%d: %d" % kv for kv in sorted(decisive.items())) or "none"))


def container_layout(data, forced=0, guess=False):
    """Understand a container well enough to rebuild it. Returns a dict or raises ToolError.

    The entries sit at positions rounded up to some alignment (64, 128...). The file shows which
    alignments are consistent with it; if more than one is, the tool cannot know which one the
    game uses, so it refuses unless you pass --align."""
    view = BytesView(data)
    info = U.analyse_pak(view)
    if not info.get("ok"):
        raise ToolError("container layout not understood (%s)" % info.get("reason", "?"))
    entries, starts = info["entries"], info["starts"]
    if not entries:
        raise ToolError("container has no entries")
    ends = [starts[i] + 256 + entries[i][1] for i in range(len(entries))]
    valid = valid_rules(starts, ends)
    if forced:
        if forced not in valid:
            raise ToolError("--align %d does not match how this container is laid out (consistent: %s)" % (
                forced, ", ".join(map(str, valid)) or "none"))
        rule = forced
    elif not valid:
        raise ToolError("the spacing between entries does not follow a simple alignment rule")
    elif len(valid) > 1 and guess:
        rule = min(valid)
    elif len(valid) > 1:
        raise ToolError("cannot tell the alignment (could be %s); run again with --align N" % ", ".join(map(str, valid)))
    else:
        rule = valid[0]
    if starts[0] != 0:
        raise ToolError("first entry does not start at 0")
    term_start = align_up(ends[-1], rule)
    extra = len(data) - (term_start + 256)
    if extra < 0:
        term_start = len(data) - 256
        extra = 0
        if term_start < ends[-1] or data[term_start] != 0:
            raise ToolError("end-of-container layout not understood")
    if any(data[term_start + 256:]):
        raise ToolError("there is data after the end-of-container header")
    return {"entries": entries, "starts": starts, "ends": ends, "rule": rule,
            "term": data[term_start:term_start + 256], "extra": extra}


def rebuild_container(data, lay, replacements):
    """New container bytes with {entry index: new data} applied."""
    out = bytearray()
    for i, (name, length) in enumerate(lay["entries"]):
        s = lay["starts"][i]
        hdr = bytearray(data[s:s + 256])
        body = replacements.get(i)
        if body is None:
            body = data[s + 256:s + 256 + length]
        else:
            struct.pack_into("<I", hdr, 252, len(body))
        if i == 0:
            out += b"\0" * s
        else:
            out += b"\0" * (align_up(len(out), lay["rule"]) - len(out))
        out += hdr + body
    out += b"\0" * (align_up(len(out), lay["rule"]) - len(out))
    out += lay["term"]
    out += b"\0" * lay["extra"]
    return bytes(out)


def fs_names(entries, folder):
    """The file names p3fes_unpack.py gives to container entries."""
    used, names = set(), []
    for name, _ in entries:
        n = U.safe_parts(name)[-1]
        names.append(os.path.basename(U.unique(folder + "/" + n, used)))
    return names


# ------------------------------------------------------------ planning

def collect_mod_files(mod_root):
    files = []
    for dp, _, names in os.walk(mod_root):
        for n in names:
            p = os.path.join(dp, n)
            parts = os.path.relpath(p, mod_root).replace("\\", "/").split("/")
            files.append((parts, p))
    return files


def plan(f, fsize, mod_root, forced=0):
    """Work out the writes. Returns (patches, report_lines, problems)."""
    top, top_files = open_image(f, fsize)
    report, problems, patches = [], [], []
    jobs = {}                        # cvm name -> {inner path upper -> {"loose": path | None, "entries": {name: path}}}
    for parts, path in collect_mod_files(mod_root):
        if len(parts) < 2 or not parts[0].upper().endswith(".CVM"):
            problems.append((parts, "only files inside a CVM archive are supported (first folder must be e.g. DATA.CVM)"))
            continue
        cvm, rest = parts[0].upper(), parts[1:]
        cont = None
        for i, p in enumerate(rest):
            if p.lower().endswith(".d") and i == len(rest) - 2:
                cont = i
        if cont is not None:
            key = "/" + "/".join(rest[:cont] + [rest[cont][:-2]])
            jobs.setdefault(cvm, {}).setdefault(key.upper(), {"loose": None, "entries": {}})["entries"][rest[-1]] = path
        elif any(p.lower().endswith(".d") for p in rest[:-1]):
            problems.append((parts, "nested containers are not supported yet"))
        else:
            key = "/" + "/".join(rest)
            jobs.setdefault(cvm, {}).setdefault(key.upper(), {"loose": None, "entries": {}})["loose"] = path
    for cvm_name, items in sorted(jobs.items()):
        got = find_cvm(f, top_files, cvm_name)
        if not got:
            for k in items:
                problems.append(([cvm_name, k], "this CVM is not on the disc"))
            continue
        cvm_entry, inner, inner_files = got
        by_path = {e["path"].upper(): e for e in inner_files}
        lbas = sorted(set(e["lba"] for e in inner_files))
        for key, job in sorted(items.items()):
            e = by_path.get(key)
            label = cvm_name + key
            if e is None:
                problems.append(([label], "no such file inside the CVM"))
                continue
            nxt = next((l for l in lbas if l > e["lba"]), None)
            capacity = (nxt - e["lba"]) * SECTOR if nxt is not None else align_up(e["size"], SECTOR)
            orig = inner.read_at(e["lba"] * SECTOR, e["size"])
            if job["loose"] is not None:
                with open(job["loose"], "rb") as fh:
                    new = fh.read()
                if new == orig:
                    report.append("%s: identical, skipped" % label)
                    continue
            else:
                try:
                    lay = container_layout(orig, forced)
                    names = fs_names(lay["entries"], label + ".d")
                    lowered = {n.lower(): i for i, n in enumerate(names)}
                    repl = {}
                    for fname, path in job["entries"].items():
                        i = lowered.get(fname.lower())
                        if i is None:
                            raise ToolError("no entry called %s" % fname)
                        with open(path, "rb") as fh:
                            body = fh.read()
                        s = lay["starts"][i]
                        if body != orig[s + 256:s + 256 + lay["entries"][i][1]]:
                            repl[i] = body
                    if not repl:
                        report.append("%s: nothing changed, skipped" % label)
                        continue
                    new = rebuild_container(orig, lay, repl)
                    # self-check: the rule must reproduce the original positions when nothing changes
                    same = rebuild_container(orig, lay, {})
                    if len(same) != len(orig) or any(
                            same[lay["starts"][k]:lay["ends"][k]] != orig[lay["starts"][k]:lay["ends"][k]]
                            for k in range(len(lay["entries"]))):
                        raise ToolError("could not reproduce the original container layout; not safe to rebuild")
                except ToolError as ex:
                    problems.append(([label], str(ex)))
                    continue
            if len(new) > capacity:
                problems.append(([label], "does not fit: new size %d bytes, room for %d (%d bytes too big)" % (
                    len(new), capacity, len(new) - capacity)))
                continue
            report.append("%s: %d -> %d bytes (room for %d)%s" % (
                label, e["size"], len(new), capacity,
                "" if job["loose"] is not None else ", %d entr%s replaced" % (len(repl), "y" if len(repl) == 1 else "ies")))
            base = inner.base + e["lba"] * SECTOR
            padded = new + b"\0" * (max(e["size"], len(new)) - len(new))
            patches.append((base, padded))
            rec_at = inner.base + e["rec_at"]
            patches.append((rec_at + 10, struct.pack("<I", len(new)) + struct.pack(">I", len(new))))
    return patches, report, problems, jobs


# ------------------------------------------------------------ verify

def verify(path, jobs, mod_root):
    bad = []
    with open(path, "rb") as f:
        fsize = os.fstat(f.fileno()).st_size
        top, top_files = open_image(f, fsize)
        for cvm_name, items in jobs.items():
            got = find_cvm(f, top_files, cvm_name)
            if not got:
                bad.append(cvm_name + " missing")
                continue
            _, inner, inner_files = got
            by_path = {e["path"].upper(): e for e in inner_files}
            for key, job in items.items():
                e = by_path.get(key)
                if e is None:
                    bad.append(cvm_name + key + " missing")
                    continue
                data = inner.read_at(e["lba"] * SECTOR, e["size"])
                if job["loose"] is not None:
                    with open(job["loose"], "rb") as fh:
                        if fh.read() != data:
                            bad.append(cvm_name + key + " differs from the changed file")
                else:
                    info = U.analyse_pak(BytesView(data))
                    if not info.get("ok"):
                        bad.append(cvm_name + key + " is not a readable container after patching")
                        continue
                    lay = {"entries": info["entries"], "starts": info["starts"]}
                    names = fs_names(lay["entries"], cvm_name + key + ".d")
                    lowered = {n.lower(): i for i, n in enumerate(names)}
                    for fname, p in job["entries"].items():
                        i = lowered[fname.lower()]
                        s = lay["starts"][i]
                        with open(p, "rb") as fh:
                            if fh.read() != data[s + 256:s + 256 + lay["entries"][i][1]]:
                                bad.append("%s%s/%s differs from the changed file" % (cvm_name, key, fname))
    return bad


def main():
    ap = argparse.ArgumentParser(description="Write changed files into a copy of the disc image.")
    ap.add_argument("image")
    ap.add_argument("modfolder", nargs="?")
    ap.add_argument("--learn-align", action="store_true", help="scan every container on the disc and report which entry alignments they use")
    ap.add_argument("-o", "--out")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--align", type=int, default=0, help="container entry alignment, only when the tool says it cannot tell")
    a = ap.parse_args()
    image, mod = os.path.abspath(a.image), os.path.abspath(a.modfolder or ".")
    if not os.path.isfile(image):
        sys.exit("Error: %s is not a file." % image)
    if a.learn_align:
        with open(image, "rb") as f:
            learn_align(f, os.fstat(f.fileno()).st_size)
        return
    if not a.modfolder or not os.path.isdir(mod):
        sys.exit("Error: give the folder of changed files.")
    if not a.dry_run:
        if not a.out:
            sys.exit("Error: give -o NEWIMAGE.iso, or use --dry-run.")
        out = os.path.abspath(a.out)
        if os.path.normcase(out) == os.path.normcase(image):
            sys.exit("Error: the output must be a different file from your original image.")
        if os.path.exists(out) and not a.force:
            sys.exit("Error: %s already exists (use --force to overwrite)." % out)
    t0 = time.time()
    with open(image, "rb") as f:
        fsize = os.fstat(f.fileno()).st_size
        try:
            patches, report, problems, jobs = plan(f, fsize, mod, a.align)
        except (ToolError, U.ToolError) as e:
            sys.exit("Error: %s" % e)
    print("=" * 70)
    for line in report:
        print("  OK   " + line)
    for parts, why in problems:
        print("  SKIP %s: %s" % ("/".join(parts), why))
    print("%d file(s) can be written, %d cannot." % (len(report) - sum(1 for r in report if "skipped" in r), len(problems)))
    if problems:
        print("Nothing is written while any file has a problem. Fix or remove those files and run again.")
        sys.exit(1)
    if a.dry_run or not patches:
        print("Dry run: nothing written." if a.dry_run else "Nothing to do.")
        return
    print("Copying the image (this takes a few minutes)...")
    tmp = out + ".part"
    shutil.copyfile(image, tmp)
    with open(tmp, "r+b") as f:
        for pos, data in patches:
            f.seek(pos)
            f.write(data)
    bad = verify(tmp, jobs, mod)
    if bad:
        os.remove(tmp)
        print("Verification FAILED; the new image was deleted:")
        for b in bad[:10]:
            print("  " + b)
        sys.exit(1)
    if os.path.exists(out):
        os.remove(out)
    os.replace(tmp, out)
    print("=" * 70)
    print("Done in %.0fs. New image: %s" % (time.time() - t0, out))
    print("Verified: every changed file reads back exactly as you supplied it. Your original image was not touched.")
    print("Test it in an emulator. Never share the image; it contains the game.")


if __name__ == "__main__":
    main()
