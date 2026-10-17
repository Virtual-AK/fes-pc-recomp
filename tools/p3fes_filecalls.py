#!/usr/bin/env python3
"""
p3fes_filecalls.py - how the game's code reaches the files on the disc. Phase 1 question 1.3.

Reads the boot executable (SLUS_216.21) and reports ADDRESSES, COUNTS and the names of file-related strings only
(library function names, archive names, path patterns); no game code is copied into the report.

  * the file-related strings in the program (CRI file system names such as cvFs and ROFS, device names such as
    cdrom0:, archive and file-name patterns), with the address of each and how many places in the code load it
  * the functions that load those strings (a function = code starting with a stack-frame setup), with how many
    places call each one. A function that loads "cdrom0:" and is called from many places is a good candidate for
    "open a file".
  * the functions called most often from the places that load them (the likely wrappers around the disc calls)

Usage:  py p3fes_filecalls.py scan extracted3\\SLUS_216.21 -o filecalls.txt
Standard library only. It only READS the file.
"""
import argparse
import bisect
import collections
import re
import struct
import sys

import p3fes_vu as V

PATTERN = re.compile(
    r"cvfs|rofs|cvf_|\.cvm|cdrom|pfs_|sceCd|\.afs|\.pac|\.pak|\.fpc|\.cpk|\.bf\b|\.bin\b|\.tmx|\.rmd|\.bmd|\.sfd|\.adx|"
    r"\.se\b|\.bed|dvd|\\\\|\.iop|\.irx|host0|mc0|%s[/\\\\]|%s\.|\.\\\\", re.I)


def find_strings(img, base, pattern=None):
    out = {}
    for m in re.finditer(rb"[\x20-\x7e]{4,200}\x00", img):
        s = m.group()[:-1].decode("ascii")
        if (pattern or PATTERN).search(s):
            out[base + m.start()] = s
    return out


def scan(data, pattern=None):
    segs = V.load_segments(data)
    if len(segs) != 1:
        print("note: %d loadable segments; using the first" % len(segs), file=sys.stderr)
    va, off, fsz = segs[0]
    img = data[off:off + fsz]
    words = struct.unpack_from("<%dI" % (len(img) // 4), img)
    strings = find_strings(img, va, pattern)
    refs = collections.defaultdict(list)           # string address -> places that load it
    starts, jal = [], collections.Counter()
    for i, w in enumerate(words):
        pc = va + 4 * i
        op = w >> 26
        if op == 0x09 and (w >> 21) & 31 == 29 and (w >> 16) & 31 == 29 and w & 0x8000:      # addiu sp, sp, -N
            starts.append(pc)
        elif op == 3:
            jal[((w & 0x3FFFFFF) << 2) | (pc & 0xF0000000)] += 1
        elif op == 0x0F:
            rt = (w >> 16) & 31
            hi = w & 0xFFFF
            if not 0x10 <= hi <= 0x80:
                continue
            for k in range(1, 7):
                if i + k >= len(words):
                    break
                x = words[i + k]
                xop = x >> 26
                if xop in (0x09, 0x0D) and (x >> 21) & 31 == rt:
                    lo = x & 0xFFFF
                    if xop == 0x09 and lo & 0x8000:
                        lo -= 0x10000
                    a = (hi << 16) + lo if xop == 0x09 else (hi << 16) | lo
                    if a in strings:
                        refs[a].append(pc)
                    break
    funcs = collections.defaultdict(set)           # function start -> string addresses
    for a, places in refs.items():
        for p in places:
            k = bisect.bisect_right(starts, p) - 1
            if k >= 0 and p - starts[k] < 0x4000:
                funcs[starts[k]].add(a)
    return dict(base=va, size=len(img), words=words, strings=strings, refs=refs, starts=starts, jal=jal, funcs=funcs)


def report(R, name):
    S, refs, funcs, jal, starts = R["strings"], R["refs"], R["funcs"], R["jal"], R["starts"]
    L = ["File-call scan of " + name, ""]
    L.append("File-related strings: %d; loaded by code at least once: %d; functions (stack-frame starts) in the image: %d"
             % (len(S), len(refs), len(starts)))
    L.append("")
    L.append("Strings loaded by code (address, places that load it, text; first 120):")
    for a in sorted(refs, key=lambda a: -len(refs[a]))[:120]:
        L.append("  0x%08X %3d  %s" % (a, len(refs[a]), S[a][:100]))
    unref = [a for a in S if a not in refs]
    L.append("")
    L.append("Strings not loaded by any code found (may be data tables or loaded another way): %d" % len(unref))
    for a in sorted(unref)[:60]:
        L.append("  0x%08X  %s" % (a, S[a][:100]))
    L.append("")
    L.append("Functions that load file-related strings (start, size to the next function start, callers, strings loaded):")
    rows = []
    for f, sa in funcs.items():
        k = bisect.bisect_right(starts, f)
        size = (starts[k] - f) if k < len(starts) else 0
        rows.append((jal.get(f, 0), f, size, sorted(sa)))
    for callers, f, size, sa in sorted(rows, reverse=True)[:80]:
        L.append("  0x%08X %6d bytes %4d callers  %s" % (f, size, callers, " | ".join(S[a][:40] for a in sa[:4])))
    L.append("")
    L.append("Functions called from the file-string functions (jal inside them): callee, how many of those functions call it, total callers in the program (first 40):")
    called = collections.Counter()
    for f in funcs:
        k = bisect.bisect_right(starts, f)
        end = starts[k] if k < len(starts) else f + 0x400
        seen = set()
        for pc in range(f, min(end, f + 0x4000, R["base"] + 4 * len(R["words"])), 4):
            w = R["words"][(pc - R["base"]) // 4]
            if w >> 26 == 3:
                seen.add(((w & 0x3FFFFFF) << 2) | (pc & 0xF0000000))
        for tgt in seen:
            called[tgt] += 1
    for tgt, n in sorted(called.items(), key=lambda kv: (-kv[1], -jal.get(kv[0], 0)))[:40]:
        L.append("  0x%08X  from %3d of the functions above, %5d callers in all" % (tgt, n, jal.get(tgt, 0)))
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="How the game's code reaches files on the disc.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="find file-related strings and the functions that use them")
    s.add_argument("exe")
    s.add_argument("-o", "--out", default="filecalls.txt")
    a = ap.parse_args()
    with open(a.exe, "rb") as fh:
        data = fh.read()
    text = report(scan(data), a.exe)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text[:2500])
    print("Report: " + a.out)


if __name__ == "__main__":
    main()
