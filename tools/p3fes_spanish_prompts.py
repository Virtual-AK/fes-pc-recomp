#!/usr/bin/env python3
"""
p3fes_spanish_prompts.py - the button prompts on the Spanish translation's pictures.

The Button Prompts mod redraws the PlayStation icons of the game's own pictures (keyboard keys, Xbox or Switch buttons, as the launcher's
Button Prompts setting says). The Spanish translation replaces many of those same files with its own pictures, which still show the
PlayStation icons, and because a translation has priority over the prompts, the icons came back everywhere it changes a picture.

This tool does the same job on the translation's pictures: it finds the icons in the Spanish copies of the picture folders (searching with the
original's icon cut-outs), redraws them with the same style, keys and buttons, and keeps only the files the translation mod really changes.
The result is a small file mod that sits between the translation and the prompts. Run it again whenever the prompts' style or keys change.

  py p3fes_spanish_prompts.py ORIGINAL_SRC SPANISH_SRC TRANSLATION_FILES OUT --style keyboard [--keys keys.txt] [--hits hits_es.json]
    ORIGINAL_SRC / SPANISH_SRC : the picture folders read out of the original disc and out of the translated disc (p3fes_unpack.py --containers)
    TRANSLATION_FILES          : the translation mod's "files" folder (only files that it changes get a prompts version)
    OUT                        : the new mod folder (its files go to OUT/files)
Needs numpy and opencv-python (like p3fes_prompts.py).
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def build(original_src, spanish_src, translation_files, out, style, keys=None, pad=None, hits=None):
    """-> (hits, report lines, number of files written). hits: an earlier result (skips the search)."""
    import p3fes_prompts as P
    report = []
    if hits is None:
        hits = P.scan(spanish_src, template_root=original_src)
    tmp = tempfile.mkdtemp(prefix="spanish_prompts_")
    try:
        hits, rep, _n = P.build(spanish_src, tmp, style, keys, pad, hits)
        made = 0
        shutil.rmtree(out, ignore_errors=True)
        base = os.path.join(tmp, "files")
        for dp, _d, names in os.walk(base):
            for nm in names:
                src = os.path.join(dp, nm)
                rel = os.path.relpath(src, base).replace(os.sep, "/")
                top, _s, rest = rel.partition("/")
                cvm = top if top.upper().endswith(".CVM") else top + ".CVM"
                if not os.path.isfile(os.path.join(translation_files, cvm, *rest.split("/"))):
                    continue                  # the translation leaves this file alone: the prompts mod's own version shows
                dst = os.path.join(out, "files", cvm, *rest.split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
                made += 1
        report.append("%d icons redrawn on the translation's pictures, %d files written" % (sum(1 for r in rep if not r.startswith(("SKIP", "font"))), made))
        report += [r for r in rep if r.startswith("SKIP")]
        return hits, report, made
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original_src")
    ap.add_argument("spanish_src")
    ap.add_argument("translation_files")
    ap.add_argument("out")
    ap.add_argument("--style", choices=("keyboard", "xbox", "switch"), default="keyboard")
    ap.add_argument("--keys", help="launcher keys file (lines like 'cross = Z')")
    ap.add_argument("--hits", help="file to keep the search result in")
    a = ap.parse_args()
    keys, pad = {}, {}
    if a.keys and os.path.isfile(a.keys):
        for line in open(a.keys):
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                k, v = (x.strip() for x in line.split("=", 1))
                (pad.__setitem__(k[4:].lower(), v.lower()) if k.startswith("pad.") else keys.__setitem__(k.lower(), v))
    import p3fes_prompts as P
    hits = None
    if a.hits and os.path.isfile(a.hits):
        try:
            d = json.load(open(a.hits))
            if d.get("version") == P.HITS_VERSION:
                hits = {rel: [(k, [(n, b, s) for n, b, s in hl]) for k, hl in per] for rel, per in d["hits"].items()}
        except Exception:
            hits = None
    hits, report, _n = build(a.original_src, a.spanish_src, a.translation_files, a.out, a.style, keys, pad, hits)
    if a.hits:
        json.dump({"version": P.HITS_VERSION, "hits": hits}, open(a.hits, "w"))
    print("\n".join(report))


if __name__ == "__main__":
    main()
