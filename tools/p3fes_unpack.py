#!/usr/bin/env python3
"""
p3fes_unpack.py - extract the files from your own Persona 3 FES disc image.

This copies every file out of the disc image (and out of the three .CVM archives)
into a folder on your computer, so you can look at them, test with them and,
later, build mods. With --containers it also splits the .PAC/.PAK/.BIN/.CPK
container files into the files inside them.

IMPORTANT: the extracted files are the game's own data. They are for your own use.
Never upload them anywhere, including to the project's GitHub repository.

It only READS your image. It writes only inside the output folder. Standard
library only, Python 3.8+.

Usage (from a Command Prompt in the folder that holds this script):
    py p3fes_unpack.py "C:\\path\\to\\game.iso" --dry-run
    py p3fes_unpack.py "C:\\path\\to\\game.iso" -o "C:\\p3fes\\extracted" --containers
    py p3fes_unpack.py "C:\\path\\to\\game.iso" --only /MODEL --only /FIELD --skip-video

Options:
    -o FOLDER        where to write (default: a folder next to this script)
    --containers     also split container files into the files inside them
    --only PREFIX    only extract files whose path starts with PREFIX (repeatable),
                     for example /DATA.CVM/FIELD or /BTL.CVM/MODEL
    --skip-video     do not extract the 42 .SFD videos (saves about 2 GB)
    --dry-run        count the files and the space needed, write nothing
"""

import argparse
import csv
import os
import shutil
import struct
import sys
import time

SECTOR = 2048
HEADER_SCAN_LIMIT = 1024 * 1024
CHUNK = 4 * 1024 * 1024
PAK_EXTS = {".pac", ".pak", ".bin", ".cpk"}


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


def _stray_empty(view, eh, cand, size):
    """True when a size-0 header at `cand` is really a 16-byte filler (for example 'npc_00') in front of the next entry: another
    valid header starts 16 to 240 bytes later (inside this one's name field) and nothing valid follows at cand + 256. Found in the
    field containers, where such fillers made the unpacker skip the real entry that follows (its .HBN, .CMR or .ENV file)."""
    if eh[1] != 0 or cand + 256 >= size:
        return False
    after = view.read_at(cand + 256, 256)
    if len(after) == 256 and entry_header(after, size - cand - 512) is not None:
        return False
    for k in range(1, 16):
        q = cand + 16 * k
        if q + 256 > size:
            break
        if entry_header(view.read_at(q, 256), size - q - 256) is not None:
            return True
    return False


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
                if _stray_empty(view, entry_header(h, size - cand - 256), cand, size):
                    continue
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




# ---------------------------------------------------------------- extraction

def safe_parts(path):
    """Turn a path from the disc into safe folder/file names (no '..', no absolute paths)."""
    parts = []
    for p in path.replace("\\", "/").split("/"):
        p = p.strip()
        if p in ("", ".", ".."):
            continue
        parts.append("".join(c if c not in '<>:"|?*\\' and ord(c) >= 32 else "_" for c in p))
    return parts or ["unnamed"]


def unique(path, used):
    base, n = path, 1
    root, ext = os.path.splitext(path)
    while path.lower() in used:
        n += 1
        path = f"{root}__{n}{ext}"
    used.add(path.lower())
    return path


def write_range(view_win, pos, length, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as out:
        done = 0
        while done < length:
            chunk = view_win.read_at(pos + done, min(CHUNK, length - done))
            if not chunk:
                raise ToolError(f"Unexpected end of data while writing {dest}")
            out.write(chunk)
            done += len(chunk)


def main():
    ap = argparse.ArgumentParser(description="Extract the files from a PS2 disc image you own.")
    ap.add_argument("iso", help="path to your .iso dump")
    ap.add_argument("-o", "--out", help="output folder")
    ap.add_argument("--containers", action="store_true", help="also split .PAC/.PAK/.BIN/.CPK containers")
    ap.add_argument("--only", action="append", default=[], help="only paths starting with this (repeatable)")
    ap.add_argument("--skip-video", action="store_true", help="skip .SFD videos")
    ap.add_argument("--dry-run", action="store_true", help="count only, write nothing")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    stem = os.path.splitext(os.path.basename(args.iso))[0]
    out_dir = os.path.abspath(args.out) if args.out else os.path.join(here, stem + "_extracted")
    only = [o.replace("\\", "/").upper() for o in args.only]
    t0 = time.time()

    try:
        with open(args.iso, "rb") as f:
            size = os.fstat(f.fileno()).st_size
            outer = Window(f, 0, size)
            if not has_pvd(outer, 16 * SECTOR):
                raise ToolError("This tool needs a plain 2048-byte-sector .iso. Run p3fes_inspect.py first to check the image.")
            jobs = []  # (display path, window, file offset, length, is_cvm_inner_window)
            for e in list_files(outer):
                if e["path"].upper().endswith(".CVM"):
                    opened = open_cvm(f, e)
                    if opened is None:
                        print(f"Skipping {e['path']}: no readable file system inside.")
                        continue
                    inner, files = opened
                    top = e["path"].strip("/")
                    for x in files:
                        jobs.append((("/" + top + x["path"]), inner, x["lba"] * SECTOR, x["size"]))
                else:
                    jobs.append((e["path"], outer, e["lba"] * SECTOR, e["size"]))

            def wanted(p):
                u = p.upper()
                if args.skip_video and u.endswith(".SFD"):
                    return False
                return not only or any(u.startswith(o) for o in only)

            jobs = [j for j in jobs if wanted(j[0])]
            total = sum(j[3] for j in jobs)
            print(f"{len(jobs)} files, {human(total)} on the disc image (before splitting containers).")
            if args.dry_run:
                print("Dry run: nothing written.")
                return
            os.makedirs(out_dir, exist_ok=True)
            free = shutil.disk_usage(out_dir).free
            if total * 1.05 > free:
                raise ToolError(f"Not enough free space in {out_dir}: need about {human(total)}, have {human(free)}. "
                                "Use --only or --skip-video, or choose another folder with -o.")
            manifest = []
            used = set()
            done_bytes = 0
            n_split = 0
            for i, (path, win, pos, length) in enumerate(jobs):
                parts = safe_parts(path)
                dest = unique(os.path.join(out_dir, *parts), used)
                write_range(win, pos, length, dest)
                manifest.append([path, "", length, os.path.relpath(dest, out_dir)])
                done_bytes += length
                if args.containers and os.path.splitext(path)[1].lower() in PAK_EXTS and length >= 256:
                    view = Window(win.f, win.base + pos, length)
                    r = analyse_pak(view)
                    if r["ok"] and r["entries"]:
                        n_split += 1
                        cdir = unique(dest + ".d", used)
                        cused = set()
                        for (name, elen), st in zip(r["entries"], r["starts"]):
                            ep = unique(os.path.join(cdir, *safe_parts(name)), cused)
                            write_range(view, st + 256, elen, ep)
                            manifest.append([path, name, elen, os.path.relpath(ep, out_dir)])
                if i % 50 == 0:
                    progress("Extracting", done_bytes, total)
            progress("Extracting", total, total)
    except ToolError as e:
        sys.exit(f"Error: {e}")
    except FileNotFoundError as e:
        sys.exit(f"Error: file not found: {e.filename}")

    mpath = os.path.join(out_dir, "manifest.csv")
    with open(mpath, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source_path", "name_inside_container", "size", "extracted_to"])
        w.writerows(manifest)
    print("=" * 70)
    print(f"Extracted {len(jobs)} files ({human(done_bytes)})"
          + (f" and split {n_split} containers" if args.containers else "")
          + f" in {time.time() - t0:.0f}s")
    print(f"Output folder: {out_dir}")
    print(f"File list: {mpath}")
    print("Reminder: these are the game's own files. Keep them on your computer; never upload them.")


if __name__ == "__main__":
    main()
