#!/usr/bin/env python3
"""
p3fes_menutest.py - make a harmless, same-length text change for testing mod loading.

Edits the menu texts in one extracted script text file (the .bf.txt that p3fes_text.py extract wrote):
    Yes                     -> MOD
    Don't enter             -> MOD WORKS!!
    Check Social Link rank  -> MOD WORKS ON THIS TEST
Each replacement has exactly the same number of characters, so the file stays the same size. Only whole menu lines are
changed (a line that is exactly that text). Changes the file in place; run it once.

Usage:  py p3fes_menutest.py "C:\\p3fes\\extracted_text_bf\\DATA.CVM\\FIELD\\PACK\\F006_003.PAC.d\\f006.bf.txt"
Whole folder (writes a changed COPY of the folder, the original is left alone):
        py p3fes_menutest.py "C:\\p3fes\\extracted_text_bf" "C:\\p3fes\\tt_bf"
"""
import os
import re
import shutil
import sys

SUBS = [("Yes", "MOD"), ("Don't enter", "MOD WORKS!!"), ("Check Social Link rank", "MOD WORKS ON THIS TEST")]

def edit(s, quiet=False):
    total = 0
    for old, new in SUBS:
        assert len(old) == len(new)
        s, n = re.subn(r"(\{F1 3F\})" + re.escape(old) + r"(?=\r?\n)", lambda m: m.group(1) + new, s)
        if not quiet:
            print("%-24s -> %-24s %d line(s)" % (old, new, n))
        total += n
    return s, total


def main():
    if len(sys.argv) == 3 and os.path.isdir(sys.argv[1]):
        src, dst = sys.argv[1], sys.argv[2]
        if os.path.exists(dst):
            sys.exit("Error: %s already exists. Delete it or choose another name." % dst)
        shutil.copytree(src, dst)
        files = lines = 0
        for dp, _d, names in os.walk(dst):
            for n in names:
                if not n.lower().endswith(".txt"):
                    continue
                p = os.path.join(dp, n)
                t = open(p, encoding="utf-8", newline="").read()
                t2, c = edit(t, True)
                if c:
                    open(p, "w", encoding="utf-8", newline="").write(t2)
                    files += 1
                    lines += c
        print("changed %d line(s) in %d file(s) in the copy %s" % (lines, files, dst))
        return
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    p = sys.argv[1]
    s = open(p, encoding="utf-8", newline="").read()
    s, total = edit(s)
    if not total:
        sys.exit("Nothing changed (already done, or this is not the right file).")
    open(p, "w", encoding="utf-8", newline="").write(s)
    print("saved")


main()
