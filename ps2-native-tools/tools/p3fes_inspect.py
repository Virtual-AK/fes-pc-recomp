#!/usr/bin/env python3
"""
p3fes_inspect.py - Phase 0 disc inspection tool for the Persona 3 FES native port.

Reads a PS2 disc image (.iso) that YOU dumped from a disc YOU own and reports:
  * disc region and boot executable (from SYSTEM.CNF)
  * the full file listing (path, start sector, size)
  * the boot ELF: entry point, segments, hashes
  * SHA-1 / MD5 of the whole image

It can also compare two images file by file, which shows what a modified
("deinterlaced", patched, etc.) image changed compared to an unmodified one.

It only READS your image. It never writes to it, never copies game data out
(except the small JSON report, which contains names, sizes and hashes only),
and needs nothing beyond Python 3.8+ (standard library only).

Usage (from a Command Prompt or PowerShell):
    python p3fes_inspect.py "C:\\path\\to\\game.iso"
    python p3fes_inspect.py "C:\\path\\to\\game.iso" --no-hash
    python p3fes_inspect.py "C:\\path\\to\\game.iso" --compare "C:\\path\\to\\other.iso"

A report is written next to the script as <imagename>.report.json
(or compare.report.json in compare mode).
"""

import argparse
import hashlib
import json
import os
import struct
import sys
import time

SECTOR = 2048
# (sector size on disk, offset of the 2048 data bytes inside each sector)
LAYOUTS = [(2048, 0), (2352, 16), (2352, 24), (2336, 8)]

REGION_PREFIXES = {
    "SLUS": "NTSC-U (North America)",
    "SCUS": "NTSC-U (North America)",
    "SLPM": "NTSC-J (Japan)",
    "SLPS": "NTSC-J (Japan)",
    "SCPS": "NTSC-J (Japan)",
    "SCAJ": "NTSC-J (Asia)",
    "SLAJ": "NTSC-J (Asia)",
    "SLES": "PAL (Europe/Australia)",
    "SCES": "PAL (Europe/Australia)",
    "SLKA": "NTSC-K (Korea)",
    "SCKA": "NTSC-K (Korea)",
}

ELF_TYPES = {0: "none", 1: "relocatable", 2: "executable", 3: "shared", 4: "core"}
PT_TYPES = {0: "NULL", 1: "LOAD", 2: "DYNAMIC", 3: "INTERP", 4: "NOTE",
            6: "PHDR", 0x70000000: "MIPS_REGINFO", 0x70000001: "MIPS_RTPROC",
            0x70000002: "MIPS_OPTIONS"}


class DiscError(Exception):
    pass


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0


def progress(msg, done, total):
    if total <= 0:
        return
    pct = 100.0 * done / total
    sys.stderr.write(f"\r  {msg}: {pct:5.1f}%")
    sys.stderr.flush()
    if done >= total:
        sys.stderr.write("\n")


class Disc:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        self.size = os.path.getsize(path)
        self.ss, self.off = self._detect_layout()
        self.files = None

    def close(self):
        self.f.close()

    def _detect_layout(self):
        for ss, off in LAYOUTS:
            pos = 16 * ss + off
            if pos + 6 > self.size:
                continue
            self.f.seek(pos)
            d = self.f.read(6)
            if d[0:1] == b"\x01" and d[1:6] == b"CD001":
                return ss, off
        raise DiscError(
            "This does not look like an ISO9660 disc image (no 'CD001' marker "
            "found). Is it a .iso file, and is it a complete dump?"
        )

    def read_sectors(self, lba, count):
        if self.ss == SECTOR and self.off == 0:
            self.f.seek(lba * SECTOR)
            return self.f.read(count * SECTOR)
        out = []
        for i in range(count):
            self.f.seek((lba + i) * self.ss + self.off)
            out.append(self.f.read(SECTOR))
        return b"".join(out)

    def read_file(self, lba, size, chunk_sectors=512):
        """Yield the file's bytes in chunks."""
        remaining = size
        cur = lba
        while remaining > 0:
            n_sec = min(chunk_sectors, (remaining + SECTOR - 1) // SECTOR)
            data = self.read_sectors(cur, n_sec)
            if len(data) < min(remaining, n_sec * SECTOR):
                raise DiscError("Image ends early: the dump looks truncated.")
            yield data[:remaining]
            remaining -= len(data[:remaining])
            cur += n_sec

    def read_whole(self, lba, size):
        return b"".join(self.read_file(lba, size))

    # ---- ISO9660 directory parsing ----
    def _parse_dir(self, lba, size, path, visited):
        if (lba, size) in visited:
            return []
        visited.add((lba, size))
        n_sec = (size + SECTOR - 1) // SECTOR
        data = self.read_sectors(lba, n_sec)[:size]
        out = []
        pos = 0
        while pos < size:
            n = data[pos]
            if n == 0:
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            if pos + n > len(data) or n < 34:
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
                out.extend(self._parse_dir(extent, length, full, visited))
            else:
                out.append({"path": full, "lba": extent, "size": length})
        return out

    def list_files(self):
        if self.files is not None:
            return self.files
        pvd = self.read_sectors(16, 1)
        root_extent = struct.unpack_from("<I", pvd, 156 + 2)[0]
        root_size = struct.unpack_from("<I", pvd, 156 + 10)[0]
        self.volume_id = pvd[40:72].decode("ascii", "replace").strip()
        self.files = sorted(
            self._parse_dir(root_extent, root_size, "", set()),
            key=lambda e: e["lba"],
        )
        return self.files

    def find(self, path_upper):
        for e in self.list_files():
            if e["path"].upper() == path_upper.upper():
                return e
        return None

    def find_name(self, name_upper):
        for e in self.list_files():
            if e["path"].upper().split("/")[-1] == name_upper.upper():
                return e
        return None


def hash_stream(chunks, algos=("sha1",), label=None, total=0):
    hs = [hashlib.new(a) for a in algos]
    done = 0
    for c in chunks:
        for h in hs:
            h.update(c)
        done += len(c)
        if label:
            progress(label, done, total)
    return {a: h.hexdigest() for a, h in zip(algos, hs)}


def hash_whole_image(disc):
    def chunks():
        disc.f.seek(0)
        while True:
            c = disc.f.read(4 * 1024 * 1024)
            if not c:
                break
            yield c
    return hash_stream(chunks(), ("sha1", "md5"), "Hashing image", disc.size)


def hash_entry(disc, e):
    return hash_stream(disc.read_file(e["lba"], e["size"]), ("sha1",))["sha1"]


def parse_system_cnf(disc):
    e = disc.find("/SYSTEM.CNF")
    if not e:
        return None
    text = disc.read_whole(e["lba"], e["size"]).decode("ascii", "replace")
    cnf = {}
    for line in text.replace("\r", "\n").split("\n"):
        if "=" in line:
            k, v = line.split("=", 1)
            cnf[k.strip().upper()] = v.strip()
    return cnf


def boot_info(cnf):
    boot = cnf.get("BOOT2") if cnf else None
    if not boot:
        return None
    exe = boot.replace("/", "\\").split("\\")[-1].split(";")[0].strip()
    prefix = exe[:4].upper()
    serial = None
    digits = "".join(ch for ch in exe[4:] if ch.isdigit())
    if len(digits) >= 5:
        serial = f"{prefix}-{digits[:5]}"
    return {
        "boot_line": boot,
        "exe_name": exe,
        "serial": serial,
        "region": REGION_PREFIXES.get(prefix, f"unknown (prefix '{prefix}')"),
    }


def analyze_elf(data):
    info = {}
    if data[:4] != b"\x7fELF":
        return {"valid": False, "note": "Not an ELF file (bad magic)."}
    info["valid"] = True
    info["class"] = {1: "32-bit", 2: "64-bit"}.get(data[4], "?")
    info["endian"] = {1: "little", 2: "big"}.get(data[5], "?")
    if data[4] != 1 or data[5] != 1:
        info["note"] = "Expected a 32-bit little-endian ELF (PS2 EE)."
        return info
    (e_type, e_machine, _ver, e_entry, e_phoff, e_shoff, e_flags, _ehsize,
     e_phentsize, e_phnum, e_shentsize, e_shnum, _shstrndx) = struct.unpack_from(
        "<HHIIIIIHHHHHH", data, 16)
    info["type"] = ELF_TYPES.get(e_type, str(e_type))
    info["machine"] = "MIPS" if e_machine == 8 else f"other ({e_machine})"
    info["entry"] = f"0x{e_entry:08X}"
    info["flags"] = f"0x{e_flags:08X}"
    info["section_headers"] = e_shnum
    segs = []
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        if o + 32 > len(data):
            break
        p_type, p_off, p_vaddr, _pa, p_filesz, p_memsz, p_flags, p_align = \
            struct.unpack_from("<8I", data, o)
        segs.append({
            "type": PT_TYPES.get(p_type, f"0x{p_type:X}"),
            "file_offset": f"0x{p_off:X}",
            "vaddr": f"0x{p_vaddr:08X}",
            "file_size": p_filesz,
            "mem_size": p_memsz,
            "flags": ("R" if p_flags & 4 else "-") + ("W" if p_flags & 2 else "-")
                     + ("X" if p_flags & 1 else "-"),
        })
    info["segments"] = segs
    return info


def inspect(path, do_hash):
    disc = Disc(path)
    report = {"image": os.path.basename(path), "image_size": disc.size,
              "sector_layout": f"{disc.ss}-byte sectors, data offset {disc.off}"}
    files = disc.list_files()
    report["volume_id"] = disc.volume_id
    report["file_count"] = len(files)

    cnf = parse_system_cnf(disc)
    report["system_cnf"] = cnf
    boot = boot_info(cnf)
    report["boot"] = boot

    if boot:
        e = disc.find_name(boot["exe_name"])
        if e:
            data = disc.read_whole(e["lba"], e["size"])
            elf = analyze_elf(data)
            elf["file"] = e["path"]
            elf["size"] = e["size"]
            elf["sha1"] = hashlib.sha1(data).hexdigest()
            elf["md5"] = hashlib.md5(data).hexdigest()
            report["boot_elf"] = elf
        else:
            report["boot_elf"] = {"valid": False,
                                  "note": f"{boot['exe_name']} not found on disc."}

    report["files"] = files
    exts = {}
    for e in files:
        ext = os.path.splitext(e["path"])[1].lower() or "(none)"
        d = exts.setdefault(ext, {"count": 0, "bytes": 0})
        d["count"] += 1
        d["bytes"] += e["size"]
    report["by_extension"] = exts

    if do_hash:
        report["image_hashes"] = hash_whole_image(disc)
    disc.close()
    return report


def print_report(r):
    print("=" * 70)
    print(f"Image:        {r['image']}  ({human(r['image_size'])})")
    print(f"Layout:       {r['sector_layout']}")
    print(f"Volume ID:    {r['volume_id']}")
    if r.get("boot"):
        b = r["boot"]
        print(f"Boot line:    {b['boot_line']}")
        print(f"Serial:       {b['serial']}")
        print(f"Region:       {b['region']}")
    else:
        print("Boot line:    SYSTEM.CNF missing or has no BOOT2 entry")
    if r.get("system_cnf"):
        for k in ("VER", "VMODE"):
            if k in r["system_cnf"]:
                print(f"{k + ':':<14}{r['system_cnf'][k]}")
    elf = r.get("boot_elf")
    if elf:
        print("-" * 70)
        print("Boot executable")
        if not elf.get("valid"):
            print(f"  {elf.get('note')}")
        else:
            print(f"  File:     {elf.get('file')}  ({human(elf['size'])})")
            print(f"  Type:     {elf.get('class')} {elf.get('endian')}-endian "
                  f"{elf.get('type')}, {elf.get('machine')}")
            print(f"  Entry:    {elf.get('entry')}")
            print(f"  Sections: {elf.get('section_headers')} (0 means stripped)")
            print(f"  SHA-1:    {elf['sha1']}")
            for s in elf.get("segments", []):
                print(f"  Segment   {s['type']:<8} vaddr {s['vaddr']}  "
                      f"file {s['file_size']:>9}  mem {s['mem_size']:>9}  {s['flags']}")
    print("-" * 70)
    print(f"Files: {r['file_count']}")
    big = sorted(r["files"], key=lambda e: -e["size"])[:15]
    print("Largest files:")
    for e in big:
        print(f"  {human(e['size']):>10}  {e['path']}")
    print("By extension:")
    for ext, d in sorted(r["by_extension"].items(), key=lambda kv: -kv[1]["bytes"]):
        print(f"  {ext:<10} {d['count']:>5} files  {human(d['bytes']):>10}")
    if r.get("image_hashes"):
        print("-" * 70)
        print(f"Image SHA-1: {r['image_hashes']['sha1']}")
        print(f"Image MD5:   {r['image_hashes']['md5']}")
        print("Compare these against a Redump database entry to see whether your")
        print("dump is an unmodified copy of a known-good disc.")
    print("=" * 70)


def diff_ranges(a, b, max_ranges=10):
    """Return (differing byte count, list of (start, length)) for equal-size data."""
    n = 0
    ranges = []
    start = None
    for i in range(len(a)):
        if a[i] != b[i]:
            n += 1
            if start is None:
                start = i
        elif start is not None:
            if len(ranges) < max_ranges:
                ranges.append((start, i - start))
            start = None
    if start is not None and len(ranges) < max_ranges:
        ranges.append((start, len(a) - start))
    return n, ranges


def compare(path_a, path_b):
    A, B = Disc(path_a), Disc(path_b)
    fa = {e["path"]: e for e in A.list_files()}
    fb = {e["path"]: e for e in B.list_files()}
    only_a = sorted(set(fa) - set(fb))
    only_b = sorted(set(fb) - set(fa))
    common = sorted(set(fa) & set(fb))

    differing, identical = [], 0
    total = len(common)
    for i, p in enumerate(common):
        progress("Comparing files", i + 1, total)
        ea, eb = fa[p], fb[p]
        if ea["size"] != eb["size"]:
            differing.append({"path": p, "size_a": ea["size"], "size_b": eb["size"],
                              "detail": "different size"})
            continue
        if hash_entry(A, ea) == hash_entry(B, eb):
            identical += 1
            continue
        item = {"path": p, "size_a": ea["size"], "size_b": eb["size"],
                "detail": "same size, different content"}
        if ea["size"] <= 64 * 1024 * 1024:
            da, db = A.read_whole(ea["lba"], ea["size"]), B.read_whole(eb["lba"], eb["size"])
            n, ranges = diff_ranges(da, db)
            item["bytes_differing"] = n
            item["first_ranges"] = [{"offset": f"0x{s:X}", "length": l} for s, l in ranges]
        differing.append(item)

    result = {"image_a": os.path.basename(path_a), "image_b": os.path.basename(path_b),
              "identical_files": identical, "differing_files": differing,
              "only_in_a": only_a, "only_in_b": only_b}
    A.close()
    B.close()
    return result


def print_compare(r):
    print("=" * 70)
    print(f"A: {r['image_a']}")
    print(f"B: {r['image_b']}")
    print(f"Identical files: {r['identical_files']}")
    print(f"Differing files: {len(r['differing_files'])}")
    for d in r["differing_files"]:
        print(f"  {d['path']}: {d['detail']} "
              f"(A {human(d['size_a'])}, B {human(d['size_b'])})")
        if "bytes_differing" in d:
            print(f"     {d['bytes_differing']} byte(s) differ; first ranges: "
                  + ", ".join(f"{x['offset']}+{x['length']}" for x in d["first_ranges"]))
    print(f"Only in A: {len(r['only_in_a'])}")
    for p in r["only_in_a"][:50]:
        print(f"  {p}")
    print(f"Only in B: {len(r['only_in_b'])}")
    for p in r["only_in_b"][:50]:
        print(f"  {p}")
    print("=" * 70)
    if not r["differing_files"] and not r["only_in_a"] and not r["only_in_b"]:
        print("The two images contain identical files.")


def main():
    ap = argparse.ArgumentParser(description="Inspect a PS2 disc image you own.")
    ap.add_argument("iso", help="path to your .iso dump")
    ap.add_argument("--compare", metavar="OTHER_ISO",
                    help="compare against a second image file by file")
    ap.add_argument("--no-hash", action="store_true",
                    help="skip hashing the whole image (faster)")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    t0 = time.time()
    try:
        if args.compare:
            r = compare(args.iso, args.compare)
            print_compare(r)
            out = os.path.join(here, "compare.report.json")
        else:
            r = inspect(args.iso, not args.no_hash)
            print_report(r)
            out = os.path.join(here, os.path.splitext(os.path.basename(args.iso))[0]
                               + ".report.json")
    except DiscError as e:
        sys.exit(f"Error: {e}")
    except FileNotFoundError as e:
        sys.exit(f"Error: file not found: {e.filename}")

    with open(out, "w", encoding="utf-8") as f:
        json.dump(r, f, indent=2)
    print(f"Report written to: {out}  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
