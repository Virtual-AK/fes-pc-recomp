#!/usr/bin/env python3
"""
p3fes_textfind.py - search the extracted game text (.bmd.txt message files and .bf.txt script text) for a word or phrase.

Run it on the folder p3fes_text.py extract made (for example C:\\p3fes\\extracted_text). For every
match it prints the file, the message name, the line number inside the message, and a short snippet
of the readable text. Case does not matter. It only READS.

Usage (from a Command Prompt in the folder that holds this script):
    py p3fes_textfind.py "C:\\p3fes\\extracted_text" "Tactics"
    py p3fes_textfind.py "C:\\p3fes\\extracted_text" "attack" --max 40

Options:
    --max N     stop after N matches (default 60)
The text is the game's own; keep the results to yourself. Standard library only.
"""
import argparse, os, re, sys


def main():
    ap = argparse.ArgumentParser(description="Search the extracted message text.")
    ap.add_argument("folder")
    ap.add_argument("phrase")
    ap.add_argument("--max", type=int, default=60)
    a = ap.parse_args()
    if not os.path.isdir(a.folder):
        sys.exit("Error: %s is not a folder." % a.folder)
    want = a.phrase.lower()
    shown, files = 0, set()
    for dp, _, names in os.walk(a.folder):
        for n in sorted(names):
            if not n.lower().endswith((".bmd.txt", ".bf.txt")):
                continue
            p = os.path.join(dp, n)
            rel = os.path.relpath(p, a.folder)
            msg, line, buf = "?", 0, []
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                continue
            for raw in text.split("\n") + ["@end"]:
                if raw.startswith("@msg ") or raw.startswith("@end") or raw.startswith("@line ") or raw.startswith("@raw "):
                    if buf:
                        body = " ".join(buf)
                        plain = re.sub(r"\{[0-9A-Fa-f ]*\}", "", body)
                        if want in plain.lower():
                            i = plain.lower().find(want)
                            snip = plain[max(0, i - 40): i + len(want) + 60].replace("\n", " ")
                            print("%s | %s | line %d | ...%s..." % (rel, msg, line, snip))
                            shown += 1
                            files.add(rel)
                            if shown >= a.max:
                                print("(stopped after %d matches; use --max for more)" % a.max)
                                return
                        buf = []
                    if raw.startswith("@msg "):
                        msg = raw.split()[2] if len(raw.split()) > 2 else "?"
                    elif raw.startswith("@line "):
                        line = int(raw.split()[1])
                elif raw.startswith("#") or raw.startswith("@"):
                    continue
                else:
                    buf.append(raw)
    print("%d match(es) in %d file(s)." % (shown, len(files)))


if __name__ == "__main__":
    main()
