#!/usr/bin/env python3
"""
p3fes_iopimg.py - what is inside the IOP reboot image (IOPRP310.IMG). Phase 1 question 1.5, sound decision.

The game restarts the IOP with a replacement set of system modules taken from this image. This tool lists
the files in the image (a ROM directory: name, size) and, for each module, its name, version, size and the
libraries it exports and imports. Only names, sizes and counts are written; no code is copied.

With --disc <folder> it also adds the libraries the game's own .IRX modules import that no module on the disc and
no module in the image exports (what a native build would have to supply itself).

Usage:  py p3fes_iopimg.py scan extracted3\\IOPRP310.IMG -o iopimg_report.txt
        py p3fes_iopimg.py scan extracted3\\IOPRP310.IMG --disc extracted3 -o iopimg_report.txt
        (the first argument may also be the folder; the first IOPRP*.IMG found is used)
Needs p3fes_iop.py (and the files it needs) beside it. It only READS files.
"""
import argparse
import os
import struct
import sys

import p3fes_iop as I


def parse_romdir(img):
    """Returns (entries, error, start of the directory). entries: list of (name, extinfo_size, size, offset)."""
    k = img.find(b"RESET\0\0\0\0\0")
    if k < 0:
        return [], "no ROM directory (no RESET entry) found", 0
    out, p, off = [], k, 0
    while p + 16 <= len(img):
        name = img[p:p + 10].split(b"\0")[0].decode("ascii", "replace")
        ext, size = struct.unpack_from("<HI", img, p + 10)
        if not name:
            break
        out.append((name, ext, size, off))
        off += (size + 15) & ~15
        p += 16
    return out, None, k


def find_image(path):
    if os.path.isfile(path):
        return path
    for dp, _, names in os.walk(path):
        for n in sorted(names):
            if n.upper().startswith("IOPRP") and n.upper().endswith(".IMG"):
                return os.path.join(dp, n)
    return None


def report(img, name, disc=None):
    L = ["IOP image report for " + name, "", "Image size: %d bytes" % len(img)]
    entries, err, base = parse_romdir(img)
    if err:
        L.append(err)
        L.append("First 32 bytes: " + img[:32].hex())
        return "\n".join(L) + "\n"
    names = {e[0] for e in entries}
    L.append("Directory entries: %d" % len(entries))
    L.append("")
    exports, needs = {}, {}
    for nm, ext, size, off in entries:
        L.append("%-12s %8d bytes at 0x%06X, extra-info %d bytes" % (nm, size, off, ext))
        if nm in ("RESET", "ROMDIR", "EXTINFO"):
            continue
        d = img[base + off:base + off + size]
        r = I.parse_irx(d)
        if r.get("error"):
            L.append("    %s" % r["error"])
            continue
        L.append("    module '%s' version %s; code %s, data %s, bss %s%s" % (
            r["name"] or "?", "?" if r["version"] is None else "%d.%d" % (r["version"] >> 8, r["version"] & 255),
            r["text"], r["data"], r["bss"],
            ("  [SDK: " + I.KNOWN[(r["name"] or "").lower()] + "]") if (r["name"] or "").lower() in I.KNOWN else ""))
        L.append("    exports: " + (", ".join("%s v%d.%d (%d)" % (n, v >> 8, v & 255, c) for n, v, c in r["exports"]) or "none"))
        L.append("    imports: " + (", ".join("%s (%d)" % (n, c) for n, v, c in r["imports"]) or "none"))
        for n, v, c in r["exports"]:
            exports.setdefault(n, nm)
        for n, v, c in r["imports"]:
            needs[n] = needs.get(n, 0) + c
    L.append("")
    L.append("Libraries exported inside the image: " + (", ".join(sorted(exports)) or "none"))
    if disc:
        for f in I.find_irx(disc):
            with open(f, "rb") as fh:
                r = I.parse_irx(fh.read())
            for n, v, c in r["exports"]:
                exports.setdefault(n, os.path.basename(f))
            for n, v, c in r["imports"]:
                needs[n] = needs.get(n, 0) + c
    L.append("")
    L.append("Libraries imported by %s that nothing %s exports:" % (
        "the image's modules and the game's .IRX files" if disc else "the image's modules", "in the image or on the disc" if disc else "in the image"))
    miss = [n for n in sorted(needs) if n not in exports]
    for n in miss:
        L.append("  %-10s %4d imported functions in all" % (n, needs[n]))
    if not miss:
        L.append("  none")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="List the IOP reboot image.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="list the files and modules in the image")
    s.add_argument("image")
    s.add_argument("--disc", help="folder with the game's .IRX files (optional)")
    s.add_argument("-o", "--out", default="iopimg_report.txt")
    a = ap.parse_args()
    f = find_image(a.image)
    if not f:
        raise SystemExit("no IOPRP*.IMG found in " + a.image)
    with open(f, "rb") as fh:
        img = fh.read()
    text = report(img, f, a.disc)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text[:2500])
    print("Report: " + a.out)


if __name__ == "__main__":
    main()
