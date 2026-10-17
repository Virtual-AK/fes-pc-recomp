#!/usr/bin/env python3
"""
p3fes_iop.py - the IOP modules (programs for the PS2's second processor) the game uses. Phase 1 question 1.5.

Reports names, sizes, counts and addresses only (no code is copied):
  * from the boot executable: the module file names it mentions (.IRX and similar) and how many places in the code
    load each name, plus any module image embedded in the executable itself
  * from the disc files: every .IRX under a folder: the module name and version, its size, the libraries it
    EXPORTS (what other programs can call) and IMPORTS (what it needs), with function counts

Usage:  py p3fes_iop.py scan extracted3 -o iop_report.txt
        (the folder from p3fes_unpack.py; it must contain SLUS_216.21 and the .IRX files)
Standard library only. It only READS files.
"""
import argparse
import os
import re
import struct
import sys

import p3fes_filecalls as FC

IRX_PATTERN = re.compile(r"\.irx|\.irp|ioprp|rom0:|rom1:|moddata|\.img", re.I)

# Names from the public PS2 SDK, for the record; other modules (the CRI ones) are described only by what they import and export.
KNOWN = {
    "sio2man": "serial I/O hub (controllers and memory cards)", "padman": "controller", "mcman": "memory card (file layer)",
    "mcserv": "memory card (EE side service)", "libsd": "sound hardware library", "sdrdrv": "sound hardware, EE side",
    "cdvdman": "disc drive", "cdvdfsv": "disc drive, EE side", "sifman": "EE to IOP communication", "sifcmd": "EE to IOP commands",
    "loadcore": "module loader", "sysmem": "IOP memory", "intrman": "interrupts", "thbase": "threads", "thevent": "events",
    "thsemap": "semaphores", "ioman": "IOP file system", "fileio": "file service for the EE", "iomanx": "IOP file system, extended",
    "sysclib": "C library", "stdio": "C library output", "timrman": "timers", "vblank": "vertical blank events",
    "modload": "module loader service", "heaplib": "heap", "sdhd": "sound bank player", "sdmusic": "sound music player",
}


def cstr_at(b, off, n):
    return b[off:off + n].split(b"\0")[0].decode("ascii", "replace")


def parse_irx(data):
    R = dict(size=len(data), name=None, version=None, text=None, data=None, bss=None, exports=[], imports=[])
    if data[:4] != b"\x7fELF":
        R["error"] = "not an ELF file"
        return R
    shoff = struct.unpack_from("<I", data, 0x20)[0]
    shent, shnum = struct.unpack_from("<HH", data, 0x2E)
    for i in range(shnum):
        o = shoff + i * shent
        if o + 40 > len(data):
            break
        typ, off, size = struct.unpack_from("<I", data, o + 4)[0], struct.unpack_from("<I", data, o + 16)[0], struct.unpack_from("<I", data, o + 20)[0]
        if typ == 0x70000080:                       # .iopmod
            sec = data[off:off + size]
            if len(sec) >= 26:
                R["text"], R["data"], R["bss"] = struct.unpack_from("<3I", sec, 12)
                R["version"] = struct.unpack_from("<H", sec, 24)[0]
                R["name"] = cstr_at(sec, 26, 40)
    # export and import tables are found by their magic words
    for m in re.finditer(rb"\x00\x00\xc0\x41\x00\x00\x00\x00", data):
        o = m.start()
        ver = struct.unpack_from("<I", data, o + 8)[0]
        name = cstr_at(data, o + 12, 8)
        n, p = 0, o + 20
        while p + 4 <= len(data) and struct.unpack_from("<I", data, p)[0] != 0 and n < 1000:
            n += 1
            p += 4
        R["exports"].append((name, ver & 0xFFFF, n))
    for m in re.finditer(rb"\x00\x00\xe0\x41\x00\x00\x00\x00", data):
        o = m.start()
        ver = struct.unpack_from("<I", data, o + 8)[0]
        name = cstr_at(data, o + 12, 8)
        n, p = 0, o + 20
        while p + 8 <= len(data) and struct.unpack_from("<I", data, p)[0] == 0x03E00008 and n < 1000:
            n += 1
            p += 8
        R["imports"].append((name, ver & 0xFFFF, n))
    return R


def find_irx(folder):
    out = []
    for dp, _, names in os.walk(folder):
        for n in sorted(names):
            if n.lower().endswith(".irx"):
                out.append(os.path.join(dp, n))
    return sorted(out, key=str.lower)


def embedded(data):
    """Module images inside the executable: ELF headers of type 0xFF80 (IOP relocatable executable)."""
    out = []
    for m in re.finditer(rb"\x7fELF\x01\x01\x01", data):
        o = m.start()
        if o + 20 <= len(data) and struct.unpack_from("<H", data, o + 16)[0] in (0xFF80, 0xFF00):
            out.append(o)
    return out


def report(folder, exe_path):
    L = ["IOP module report for " + folder, ""]
    if exe_path:
        with open(exe_path, "rb") as fh:
            exe = fh.read()
        R = FC.scan(exe, IRX_PATTERN)
        S, refs = R["strings"], R["refs"]
        L.append("Module-related strings in the executable: %d; loaded by code: %d" % (len(S), len(refs)))
        for a in sorted(S):
            L.append("  0x%08X %3d places  %s" % (a, len(refs.get(a, [])), S[a][:100]))
        emb = embedded(exe)
        L.append("Module images embedded in the executable (ELF headers of IOP type): %d %s" % (len(emb), " ".join("0x%X" % o for o in emb[:20])))
        L.append("")
    files = find_irx(folder)
    L.append(".IRX files on the disc: %d" % len(files))
    L.append("")
    allexp = {}
    for f in files:
        with open(f, "rb") as fh:
            d = fh.read()
        r = parse_irx(d)
        rel = os.path.relpath(f, folder)
        if r.get("error"):
            L.append("%s: %d bytes, %s" % (rel, r["size"], r["error"]))
            continue
        nm = r["name"] or "?"
        L.append("%s: %d bytes; module '%s' version %s; code %s, data %s, bss %s%s" % (
            rel, r["size"], nm, "?" if r["version"] is None else "%d.%d" % (r["version"] >> 8, r["version"] & 255),
            r["text"], r["data"], r["bss"], ("  [SDK: " + KNOWN[nm.lower()] + "]") if nm.lower() in KNOWN else ""))
        L.append("    exports: " + (", ".join("%s v%d.%d (%d)" % (n, v >> 8, v & 255, c) for n, v, c in r["exports"]) or "none"))
        L.append("    imports: " + (", ".join("%s (%d)" % (n, c) for n, v, c in r["imports"]) or "none"))
        for n, v, c in r["exports"]:
            allexp.setdefault(n, rel)
    L.append("")
    L.append("Libraries imported by the game's modules that no module on the disc exports (they come from the console's built-in modules):")
    need = {}
    for f in files:
        with open(f, "rb") as fh:
            r = parse_irx(fh.read())
        for n, v, c in r["imports"]:
            need.setdefault(n, 0)
            need[n] += c
    for n in sorted(need):
        if n not in allexp:
            L.append("  %-10s %4d imported functions in all%s" % (n, need[n], ("  [SDK: " + KNOWN[n.lower()] + "]") if n.lower() in KNOWN else ""))
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="The IOP modules the game uses.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="list the module names in the executable and the .IRX files on the disc")
    s.add_argument("folder")
    s.add_argument("-o", "--out", default="iop_report.txt")
    a = ap.parse_args()
    folder = os.path.abspath(a.folder)
    exe = None
    for dp, _, names in os.walk(folder):
        for n in names:
            if n.upper().startswith("SLUS_") or n.upper().endswith(".ELF"):
                exe = os.path.join(dp, n)
                break
        if exe:
            break
    text = report(folder, exe)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text[:2500])
    print("Report: " + a.out)


if __name__ == "__main__":
    main()
