#!/usr/bin/env python3
"""
p3fes_cvm.py - Phase 0 archive inspection tool for the Persona 3 FES native port.

Persona 3 FES keeps almost all of its data inside a few big ".CVM" archive files
on the disc. This tool opens your own disc image (.iso), finds every .CVM file,
works out where the file table inside each one starts, and reports:

  * the first bytes of each CVM (its header), so we can learn the format
  * how many files are inside, how big they are, and how they are organised
  * for each file type (extension): counts, sizes and the most common first
    4 bytes ("magic"), which helps identify the formats inside

It only READS your image. The reports contain file names, sizes and 4-byte
format markers only. No game data is copied out. Standard library only,
Python 3.8+.

Usage (from a Command Prompt in the folder that holds this script):
    py p3fes_cvm.py "C:\\path\\to\\game.iso"
    py p3fes_cvm.py "C:\\path\\to\\game.iso" --full

--full also writes one CSV per CVM listing every file (name, size, start sector,
first 4 bytes). Those files can be large, so only use it if asked.

Reports are written next to this script.
"""

import argparse
import collections
import csv
import json
import os
import struct
import sys
import time

SECTOR = 2048
HEADER_SCAN_LIMIT = 1024 * 1024  # look this far into a CVM for the file table


class ToolError(Exception):
    pass


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0


def ascii_of(b):
    return "".join(chr(c) if 32 <= c < 127 else "." for c in b)


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
        if pos < 0 or pos >= self.size:
            return b""
        n = min(n, self.size - pos)
        self.f.seek(self.base + pos)
        return self.f.read(n)


def has_pvd(win, offset):
    return win.read_at(offset, 6) == b"\x01CD001"


def parse_dir(win, lba, size, path, visited, out):
    """Collect file entries from an ISO9660 directory (recursively)."""
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


def scan_cvm(f, entry, full, csv_path):
    cvm = Window(f, entry["lba"] * SECTOR, entry["size"])
    head = cvm.read_at(0, 256)
    info = {
        "name": entry["path"],
        "size": entry["size"],
        "header_ascii_first_16": ascii_of(head[:16]),
        "header_hex_first_256": head.hex(),
    }

    # Find where the inner file system starts: its volume descriptor sits
    # 16 sectors after the start of the file system.
    base = None
    off = 16 * SECTOR
    limit = min(cvm.size, HEADER_SCAN_LIMIT)
    while off + 6 <= limit:
        if has_pvd(cvm, off):
            base = off - 16 * SECTOR
            break
        off += SECTOR
    if base is None:
        info["note"] = ("No ISO9660 structure found in the first 1 MB. The archive "
                        "may use a different layout or be encrypted; the header "
                        "bytes above are what we need to look at next.")
        return info

    info["inner_filesystem_offset"] = f"0x{base:X}"
    inner = Window(cvm.f, cvm.base + base, cvm.size - base)
    files = list_files(inner)
    info["file_count"] = len(files)
    info["file_bytes_total"] = sum(e["size"] for e in files)

    # Read the first 8 bytes of every file to learn its format marker.
    for i, e in enumerate(files):
        if i % 500 == 0:
            progress(f"Reading headers in {entry['path']}", i, len(files))
        e["magic"] = inner.read_at(e["lba"] * SECTOR, 4).hex() if e["size"] else ""
    progress(f"Reading headers in {entry['path']}", len(files), len(files))

    by_ext = {}
    for e in files:
        ext = os.path.splitext(e["path"])[1].lower() or "(none)"
        d = by_ext.setdefault(ext, {"count": 0, "bytes": 0,
                                    "magics": collections.Counter()})
        d["count"] += 1
        d["bytes"] += e["size"]
        if e["magic"]:
            d["magics"][e["magic"]] += 1
    info["by_extension"] = {
        ext: {"count": d["count"], "bytes": d["bytes"],
              "top_magics": [{"hex": m, "ascii": ascii_of(bytes.fromhex(m)), "count": c}
                             for m, c in d["magics"].most_common(5)]}
        for ext, d in sorted(by_ext.items(), key=lambda kv: -kv[1]["bytes"])
    }

    top = collections.Counter()
    top2 = collections.Counter()
    for e in files:
        parts = e["path"].strip("/").split("/")
        top[parts[0] if len(parts) > 1 else "(root)"] += 1
        if len(parts) > 2:
            top2["/".join(parts[:2])] += 1
    info["top_level_folders"] = dict(top.most_common(60))
    info["second_level_folders"] = dict(top2.most_common(60))
    info["largest_files"] = [
        {"path": e["path"], "size": e["size"], "magic": e["magic"]}
        for e in sorted(files, key=lambda e: -e["size"])[:50]
    ]
    info["sample_files"] = [
        {"path": e["path"], "size": e["size"], "magic": e["magic"]}
        for e in sorted(files, key=lambda e: e["path"])[:150]
    ]

    if full:
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["path", "size", "start_sector", "first_4_bytes_hex"])
            for e in sorted(files, key=lambda e: e["path"]):
                w.writerow([e["path"], e["size"], e["lba"], e["magic"]])
        info["full_listing_csv"] = os.path.basename(csv_path)
    return info


def print_cvm(info):
    print("=" * 70)
    print(f"{info['name']}  ({human(info['size'])})")
    print(f"Header starts: {info['header_ascii_first_16']!r}")
    if "note" in info:
        print(info["note"])
        return
    print(f"File table starts at offset {info['inner_filesystem_offset']} inside the archive")
    print(f"Files: {info['file_count']}  ({human(info['file_bytes_total'])} of data)")
    print("Top-level folders:")
    for name, n in list(info["top_level_folders"].items())[:15]:
        print(f"  {name:<24} {n:>7} files")
    print("By file type (count, size, most common first 4 bytes):")
    for ext, d in list(info["by_extension"].items())[:20]:
        magic = ", ".join(f"{m['hex']} '{m['ascii']}' x{m['count']}" for m in d["top_magics"][:2])
        print(f"  {ext:<10} {d['count']:>6}  {human(d['bytes']):>10}   {magic}")
    print("Largest files:")
    for e in info["largest_files"][:10]:
        print(f"  {human(e['size']):>10}  {e['path']}")


def main():
    ap = argparse.ArgumentParser(description="Inspect the CVM archives in a PS2 disc image you own.")
    ap.add_argument("iso", help="path to your .iso dump")
    ap.add_argument("--full", action="store_true",
                    help="also write a CSV listing every file in each CVM")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    stem = os.path.splitext(os.path.basename(args.iso))[0]
    t0 = time.time()
    try:
        with open(args.iso, "rb") as f:
            size = os.fstat(f.fileno()).st_size
            outer = Window(f, 0, size)
            if not has_pvd(outer, 16 * SECTOR):
                raise ToolError(
                    "This tool needs a plain 2048-byte-sector .iso. No ISO9660 marker "
                    "was found where expected; run p3fes_inspect.py first to check the image.")
            cvms = [e for e in list_files(outer) if e["path"].upper().endswith(".CVM")]
            if not cvms:
                raise ToolError("No .CVM files found on this disc image.")
            results = []
            for e in cvms:
                csv_path = os.path.join(here, f"{stem}.{os.path.basename(e['path'])}.files.csv")
                info = scan_cvm(f, e, args.full, csv_path)
                print_cvm(info)
                results.append(info)
    except ToolError as e:
        sys.exit(f"Error: {e}")
    except FileNotFoundError as e:
        sys.exit(f"Error: file not found: {e.filename}")

    out = os.path.join(here, stem + ".cvm.report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"image": os.path.basename(args.iso), "archives": results}, fh, indent=1)
    print("=" * 70)
    print(f"Report written to: {out}  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
