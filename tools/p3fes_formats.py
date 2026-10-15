#!/usr/bin/env python3
"""
p3fes_formats.py - Phase 0 file-format survey tool for the Persona 3 FES native port.

p3fes_cvm.py told us WHAT is inside the game's archives. This tool looks at HOW the
main file types are put together, so developers know which formats are simple
containers and which need real reverse engineering. It checks:

  * "PAK" containers (.PAC .PAK .BIN .CPK): tests the theory that they are a plain
    list of [256-byte name+size header][data] entries, and reports how many files fit
    that theory, how many entries they hold and what kinds of files sit inside
  * AFS archives (.AFS): entry counts, sizes and whether they carry a name table
  * ADX audio (.ADX): codec, channels, sample rates
  * SFD video (.SFD): picture size and frame rate (this matters for resolution work)
  * every other file type: size ranges and the first few header bytes of example files

It only READS your disc image. The report contains file names, sizes and short
header samples (at most 32 bytes per example), never the game's content.
Standard library only, Python 3.8+.

Usage (from a Command Prompt in the folder that holds this script):
    py p3fes_formats.py "C:\\path\\to\\game.iso"
    py p3fes_formats.py "C:\\path\\to\\game.iso" --no-video     (skip reading the SFD videos)

The report is written next to this script as <image name>.formats.report.json.
"""

import argparse
import collections
import json
import os
import struct
import sys
import time

SECTOR = 2048
HEADER_SCAN_LIMIT = 1024 * 1024
PAK_EXTS = {".pac", ".pak", ".bin", ".cpk"}
SFD_READ = 512 * 1024


class ToolError(Exception):
    pass


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0


def progress(msg, done, total):
    if total <= 0:
        return
    sys.stderr.write(f"\r  {msg}: {100.0 * done / total:5.1f}%")
    sys.stderr.flush()
    if done >= total:
        sys.stderr.write("\n")


class Window:
    """A read-only view of part of a file: bytes [base, base+size)."""

    def __init__(self, f, base, size):
        self.f = f
        self.base = base
        self.size = size

    def read_at(self, pos, n):
        if pos < 0 or pos >= self.size or n <= 0:
            return b""
        n = min(n, self.size - pos)
        self.f.seek(self.base + pos)
        return self.f.read(n)


def has_pvd(win, offset):
    return win.read_at(offset, 6) == b"\x01CD001"


def parse_dir(win, lba, size, path, visited, out):
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
        name_len = rec[32]
        name = rec[33:33 + name_len]
        pos += n
        if name in (b"\x00", b"\x01"):
            continue
        name = name.decode("ascii", "replace").split(";")[0]
        full = path + "/" + name
        if flags & 0x02:
            parse_dir(win, extent, length, full, visited, out)
        else:
            out.append({"path": full, "lba": extent, "size": length})


def list_files(win):
    pvd = win.read_at(16 * SECTOR, SECTOR)
    if len(pvd) < 190 or pvd[1:6] != b"CD001":
        raise ToolError("No ISO9660 volume descriptor found.")
    root_extent = struct.unpack_from("<I", pvd, 156 + 2)[0]
    root_size = struct.unpack_from("<I", pvd, 156 + 10)[0]
    out = []
    parse_dir(win, root_extent, root_size, "", set(), out)
    out.sort(key=lambda e: e["lba"])
    return out


def open_cvm(f, entry):
    """Return (inner window, file list) for a CVM, or None if unreadable."""
    cvm = Window(f, entry["lba"] * SECTOR, entry["size"])
    limit = min(cvm.size, HEADER_SCAN_LIMIT)
    off = 16 * SECTOR
    base = None
    while off + 6 <= limit:
        if has_pvd(cvm, off):
            base = off - 16 * SECTOR
            break
        off += SECTOR
    if base is None:
        return None
    inner = Window(cvm.f, cvm.base + base, cvm.size - base)
    return inner, list_files(inner)


class FileView:
    """Read bytes of one file inside an inner file system."""

    def __init__(self, inner, entry):
        self.win = Window(inner.f, inner.base + entry["lba"] * SECTOR, entry["size"])
        self.size = entry["size"]

    def read_at(self, pos, n):
        return self.win.read_at(pos, n)


# ---------------------------------------------------------------- PAK containers

def printable_name(raw):
    """Decode a NUL-terminated ASCII name, or return None if it does not look like one."""
    end = raw.find(b"\0")
    if end == 0:
        return None
    name = raw if end < 0 else raw[:end]
    if not name or any(c < 0x20 or c > 0x7E for c in name):
        return None
    return name.decode("ascii")


NAME_OK = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_./-")
SEARCH_WINDOW = 8192


def entry_header(hdr, room):
    """Return (name, length) if hdr looks like an entry header that fits in `room` bytes of data."""
    raw = hdr[:252]
    end = raw.find(b"\0")
    name = raw if end < 0 else raw[:end]
    if len(name) < 2 or any(c not in NAME_OK for c in name):
        return None
    length = struct.unpack_from("<I", hdr, 252)[0]
    if length > room:
        return None
    return name.decode("ascii"), length


def analyse_pak(view):
    """Walk a file as repeated [252-byte name][u32 size][data] entries.

    Padding between entries is not assumed to be zeros (it can be leftover data), so the
    next entry is found by testing each 16-byte-aligned position after the previous entry
    for a valid header. A header whose name is empty and that fills the end of the file is
    the terminator. This reveals the real layout: the alignment of entry starts, and what
    sits at the end of the file.
    Returns a dict with ok=True/False.
    """
    size = view.size
    entries = []
    starts = []
    off = 0
    terminator = False
    tail = 0

    def fail(reason, at):
        return {"ok": False, "entries": entries, "stop_offset": at, "reason": reason,
                "bytes_at_stop_hex": view.read_at(at, 48).hex()}

    if size <= 65536 and size >= 256 and not any(view.read_at(0, size)):
        return {"ok": True, "entries": [], "starts": [], "start_alignment": "n/a",
                "tail_zero_bytes": size, "terminator": True}
    first = view.read_at(0, 256)
    if len(first) < 256 or entry_header(first, size - 256) is None:
        return fail("no valid entry header at the start", 0)
    while True:
        hdr = view.read_at(off, 256)
        eh = entry_header(hdr, size - off - 256)
        if eh is None:
            return fail("no valid entry header here", off)
        entries.append(eh)
        starts.append(off)
        if len(entries) > 200000:
            return fail("too many entries", off)
        end = off + 256 + eh[1]
        # find the next header (or the terminator) after the data
        lo = (end + 15) // 16 * 16
        window = view.read_at(lo, SEARCH_WINDOW + 256)
        nxt = None
        for rel in range(0, max(0, len(window) - 255), 16):
            cand = lo + rel
            h = window[rel:rel + 256]
            if h[0] == 0:
                if cand + 256 == size:
                    terminator = True
                    nxt = "end"
                    break
                continue
            if entry_header(h, size - cand - 256) is not None:
                nxt = cand
                break
        if nxt == "end":
            tail = size - end
            break
        if nxt is None and size - 256 >= end and view.read_at(size - 256, 1) == b"\0":
            terminator = True
            nxt = "end"
        if nxt == "end":
            tail = size - end
            break
        if nxt is None:
            rest = view.read_at(end, size - end) if size - end <= 1 << 20 else b"x"
            if not any(rest):
                tail = size - end
                break
            return fail("no valid next entry after the data", end)
        off = nxt
    align = 1 if len(starts) > 1 else "single entry"
    for a in (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096):
        if len(starts) > 1 and all(st % a == 0 for st in starts[1:]):
            align = a
        else:
            break
    return {"ok": True, "entries": entries, "starts": starts, "start_alignment": align,
            "tail_zero_bytes": tail, "terminator": terminator}


def inner_ext(name):
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    return os.path.splitext(base)[1].lower() or "(none)"


def survey_pak(files_by_ext, inner):
    out = {}
    for ext in sorted(PAK_EXTS):
        files = files_by_ext.get(ext, [])
        if not files:
            continue
        ok = 0
        terms = 0
        aligns = collections.Counter()
        tails = collections.Counter()
        inner_exts = collections.Counter()
        entry_counts = []
        examples = []
        failures = []
        for e in files:
            view = FileView(inner, e)
            r = analyse_pak(view)
            if not r["ok"]:
                if len(failures) < 8:
                    failures.append({"path": e["path"], "size": e["size"],
                                     "entries_before_stop": len(r["entries"]),
                                     "stopped_at_offset": r["stop_offset"],
                                     "reason": r["reason"],
                                     "bytes_at_stop_hex": r["bytes_at_stop_hex"]})
                continue
            ok += 1
            aligns[r["start_alignment"]] += 1
            tails[r["tail_zero_bytes"]] += 1
            terms += 1 if r.get("terminator") else 0
            entry_counts.append(len(r["entries"]))
            for name, _ in r["entries"]:
                inner_exts[inner_ext(name)] += 1
            if len(examples) < 6:
                examples.append({"path": e["path"], "size": e["size"], "entries": len(r["entries"]),
                                 "entry_starts": r["starts"][:6],
                                 "first_entries": [{"name": n, "size": s} for n, s in r["entries"][:6]]})
        out[ext] = {
            "files": len(files),
            "parsed_as_pak": ok,
            "entry_start_alignment": dict(aligns),
            "bytes_after_last_entry": dict(tails.most_common(8)),
            "with_terminator_header": terms,
            "entries_total": sum(entry_counts),
            "entries_min": min(entry_counts) if entry_counts else 0,
            "entries_max": max(entry_counts) if entry_counts else 0,
            "inner_file_types": dict(inner_exts.most_common(25)),
            "examples": examples,
            "not_parsed_examples": failures,
        }
    return out


# ---------------------------------------------------------------- AFS

def survey_afs(files, inner):
    if not files:
        return None
    bad = []
    counts = []
    aligned = 0
    with_names = 0
    entry_sizes = []
    examples = []
    for e in files:
        view = FileView(inner, e)
        head = view.read_at(0, 8)
        if len(head) < 8 or head[:4] != b"AFS\x00":
            bad.append(e["path"])
            continue
        count = struct.unpack_from("<I", head, 4)[0]
        table = view.read_at(8, count * 8 + 8)
        if count == 0 or count > 100000 or len(table) < count * 8:
            bad.append(e["path"])
            continue
        entries = [struct.unpack_from("<II", table, i * 8) for i in range(count)]
        if any(o + s > e["size"] for o, s in entries):
            bad.append(e["path"])
            continue
        counts.append(count)
        entry_sizes.extend(s for _, s in entries)
        if all(o % SECTOR == 0 for o, _ in entries):
            aligned += 1
        if len(table) >= count * 8 + 8:
            name_off, name_len = struct.unpack_from("<II", table, count * 8)
            if 0 < name_off < e["size"] and name_len == count * 48:
                with_names += 1
        if len(examples) < 5:
            examples.append({"path": e["path"], "size": e["size"], "entries": count})
    return {
        "files": len(files),
        "valid_afs": len(counts),
        "invalid_examples": bad[:8],
        "entries_total": sum(counts),
        "entries_min": min(counts) if counts else 0,
        "entries_max": max(counts) if counts else 0,
        "entry_size_min": min(entry_sizes) if entry_sizes else 0,
        "entry_size_max": max(entry_sizes) if entry_sizes else 0,
        "all_entries_2048_aligned": aligned,
        "with_name_table": with_names,
        "examples": examples,
    }


# ---------------------------------------------------------------- ADX

def survey_adx(files, inner):
    if not files:
        return None
    combos = collections.Counter()
    versions = collections.Counter()
    bad = []
    seconds = 0.0
    for e in files:
        h = FileView(inner, e).read_at(0, 32)
        if len(h) < 20 or h[0] != 0x80 or h[1] != 0x00:
            bad.append(e["path"])
            continue
        enc, block, depth, ch = h[4], h[5], h[6], h[7]
        rate, total = struct.unpack_from(">II", h, 8)
        combos[(enc, ch, rate)] += 1
        versions[h[18]] += 1
        if rate:
            seconds += total / float(rate)
    return {
        "files": len(files),
        "bad_header_examples": bad[:8],
        "codec_channels_rate": [{"encoding": k[0], "channels": k[1], "sample_rate": k[2], "files": v}
                                for k, v in combos.most_common()],
        "adx_versions": {str(k): v for k, v in versions.items()},
        "total_minutes": round(seconds / 60.0, 1),
    }


# ---------------------------------------------------------------- SFD video

FPS_CODES = {1: "23.976", 2: "24", 3: "25", 4: "29.97", 5: "30", 6: "50", 7: "59.94", 8: "60"}


def survey_sfd(files, inner, skip):
    if not files:
        return None
    if skip:
        return {"files": len(files), "note": "skipped (--no-video)"}
    combos = collections.Counter()
    audio_ids = collections.Counter()
    per_file = []
    for i, e in enumerate(files):
        progress("Reading video headers", i, len(files))
        data = FileView(inner, e).read_at(0, SFD_READ)
        info = {"path": e["path"], "size": e["size"]}
        if data[:4] != b"\x00\x00\x01\xba":
            info["note"] = "no MPEG pack header at start"
            per_file.append(info)
            continue
        idx = data.find(b"\x00\x00\x01\xb3")
        if idx >= 0 and idx + 8 <= len(data):
            b = data[idx + 4: idx + 8]
            width = (b[0] << 4) | (b[1] >> 4)
            height = ((b[1] & 0x0F) << 8) | b[2]
            fps = FPS_CODES.get(b[3] & 0x0F, "code %d" % (b[3] & 0x0F))
            info.update({"width": width, "height": height, "fps": fps})
            combos[(width, height, fps)] += 1
        else:
            info["note"] = "no video sequence header in the first 512 KB"
        for sid in (0xBD, 0xC0, 0xC1):
            if data.find(b"\x00\x00\x01" + bytes([sid])) >= 0:
                audio_ids[hex(sid)] += 1
        per_file.append(info)
    progress("Reading video headers", len(files), len(files))
    return {
        "files": len(files),
        "total_bytes": sum(e["size"] for e in files),
        "picture_size_and_rate": [{"width": k[0], "height": k[1], "fps": k[2], "files": v}
                                  for k, v in combos.most_common()],
        "stream_ids_seen": dict(audio_ids),
        "files_detail": per_file[:60],
    }


# ---------------------------------------------------------------- everything else

HANDLED = PAK_EXTS | {".afs", ".adx", ".sfd"}


def survey_other(files_by_ext, inner):
    out = {}
    for ext, files in sorted(files_by_ext.items(), key=lambda kv: -sum(e["size"] for e in kv[1])):
        if ext in HANDLED:
            continue
        files = sorted(files, key=lambda e: e["size"])
        picks = []
        for e in (files[0], files[len(files) // 2], files[-1]):
            if e not in picks:
                picks.append(e)
        sample = []
        for e in picks:
            head = FileView(inner, e).read_at(0, 32)
            words = [struct.unpack_from("<I", head, i)[0]
                     for i in range(0, min(len(head), 32) - 3, 4)]
            sample.append({"path": e["path"], "size": e["size"], "first_32_hex": head.hex(),
                           "first_words_le": ["0x%08X" % w for w in words]})
        magics = collections.Counter()
        for e in files[:400]:
            magics[FileView(inner, e).read_at(0, 4).hex()] += 1
        out[ext] = {
            "files": len(files),
            "bytes": sum(e["size"] for e in files),
            "size_min": files[0]["size"],
            "size_max": files[-1]["size"],
            "common_first_4_bytes": [{"hex": m, "files": c} for m, c in magics.most_common(4)],
            "samples": sample,
        }
    return out


def print_summary(name, res):
    print("=" * 70)
    print(name)
    for ext, d in res.get("pak", {}).items():
        print(f"  {ext}: {d['parsed_as_pak']}/{d['files']} files fit the PAK theory, "
              f"{d['entries_total']} entries, start alignment {d['entry_start_alignment']}, "
              f"tail bytes {d['bytes_after_last_entry']}")
        top = ", ".join(f"{k}x{v}" for k, v in list(d["inner_file_types"].items())[:8])
        if top:
            print(f"      inside: {top}")
    if res.get("afs"):
        a = res["afs"]
        print(f"  .afs: {a['valid_afs']}/{a['files']} valid, {a['entries_total']} entries, "
              f"name tables: {a['with_name_table']}")
    if res.get("adx"):
        a = res["adx"]
        print(f"  .adx: {a['files']} files, about {a['total_minutes']} minutes; "
              f"{a['codec_channels_rate'][:3]}")
    if res.get("sfd") and "picture_size_and_rate" in res["sfd"]:
        print(f"  .sfd: {res['sfd']['picture_size_and_rate']}")
    if res.get("other"):
        print("  other types: " + ", ".join(
            f"{ext}({d['files']})" for ext, d in list(res["other"].items())[:15]))


def main():
    ap = argparse.ArgumentParser(description="Survey the file formats inside the CVM archives of a PS2 disc image you own.")
    ap.add_argument("iso", help="path to your .iso dump")
    ap.add_argument("--no-video", action="store_true", help="do not read the start of each SFD video")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    stem = os.path.splitext(os.path.basename(args.iso))[0]
    t0 = time.time()
    results = []
    try:
        with open(args.iso, "rb") as f:
            size = os.fstat(f.fileno()).st_size
            outer = Window(f, 0, size)
            if not has_pvd(outer, 16 * SECTOR):
                raise ToolError("This tool needs a plain 2048-byte-sector .iso. Run p3fes_inspect.py first to check the image.")
            cvms = [e for e in list_files(outer) if e["path"].upper().endswith(".CVM")]
            if not cvms:
                raise ToolError("No .CVM files found on this disc image.")
            for entry in cvms:
                opened = open_cvm(f, entry)
                if opened is None:
                    print(f"Skipping {entry['path']}: no readable file system inside.")
                    continue
                inner, files = opened
                by_ext = collections.defaultdict(list)
                for e in files:
                    by_ext[os.path.splitext(e["path"])[1].lower() or "(none)"].append(e)
                res = {
                    "archive": entry["path"],
                    "pak": survey_pak(by_ext, inner),
                    "afs": survey_afs(by_ext.get(".afs", []), inner),
                    "adx": survey_adx(by_ext.get(".adx", []), inner),
                    "sfd": survey_sfd(by_ext.get(".sfd", []), inner, args.no_video),
                    "other": survey_other(by_ext, inner),
                }
                print_summary(entry["path"], res)
                results.append(res)
    except ToolError as e:
        sys.exit(f"Error: {e}")
    except FileNotFoundError as e:
        sys.exit(f"Error: file not found: {e.filename}")

    out = os.path.join(here, stem + ".formats.report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"image": os.path.basename(args.iso), "archives": results}, fh, indent=1)
    print("=" * 70)
    print(f"Report written to: {out}  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
