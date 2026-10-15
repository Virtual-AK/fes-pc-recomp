#!/usr/bin/env python3
"""
p3fes_textcodes.py - counts the control codes ({F1 05} and the like) in the text files
that `p3fes_text.py extract` wrote, so the meaning of each code can be worked out.

Usage:
    py p3fes_textcodes.py C:\\p3fes\\extracted_text
Writes codes.txt next to the folder you give (inside it). Each code is listed with how
often it appears, in how many files, and up to 3 short examples of the text around it.
The examples are a few words of the game's own text; look at the file before sharing it.
"""

import os
import re
import sys

TOKEN = re.compile(r"\{([0-9A-Fa-f]{2}(?: [0-9A-Fa-f]{2})*)\}")


def main():
    if len(sys.argv) < 2 or not os.path.isdir(sys.argv[1]):
        sys.exit("Usage: py p3fes_textcodes.py <extracted_text folder>")
    root = os.path.abspath(sys.argv[1])
    stats = {}      # token -> [count, set(files), [examples]]
    lead = {}       # first byte -> count
    nfiles = 0
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if not fn.endswith(".txt") or fn in ("problems.txt", "diagnostics.txt", "codes.txt"):
                continue
            nfiles += 1
            rel = os.path.relpath(os.path.join(dp, fn), root)
            with open(os.path.join(dp, fn), encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.startswith("@") and not line.startswith("@speaker"):
                        continue
                    for m in TOKEN.finditer(line):
                        tok = m.group(1).upper()
                        st = stats.setdefault(tok, [0, set(), []])
                        st[0] += 1
                        st[1].add(rel)
                        lead[tok[:2]] = lead.get(tok[:2], 0) + 1
                        if len(st[2]) < 3:
                            a, b = max(0, m.start() - 18), min(len(line), m.end() + 18)
                            ex = line[a:b].rstrip("\n")
                            if ex not in st[2]:
                                st[2].append(ex)
    out = os.path.join(root, "codes.txt")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("Files scanned: %d\nDistinct codes: %d\n\n" % (nfiles, len(stats)))
        fh.write("By first byte (code family): " + ", ".join(
            "%s x%d" % kv for kv in sorted(lead.items(), key=lambda kv: -kv[1])) + "\n\n")
        for tok, (c, fs, ex) in sorted(stats.items(), key=lambda kv: (kv[0][:2], -kv[1][0])):
            fh.write("{%s}  count=%d files=%d\n" % (tok, c, len(fs)))
            for e in ex:
                fh.write("      %s\n" % e)
    print("Files scanned: %d; distinct codes: %d" % (nfiles, len(stats)))
    print("By first byte: " + ", ".join("%s x%d" % kv for kv in sorted(lead.items(), key=lambda kv: -kv[1])[:12]))
    print("Details written to: " + out)


if __name__ == "__main__":
    main()
