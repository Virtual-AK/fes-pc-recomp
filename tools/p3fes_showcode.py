"""Show the recompiled C++ around game addresses (research tool, see docs/known-issues.md).

  python3 p3fes_showcode.py DIR 0x003293B8 0x003138A0 [--before 40 --after 60] > code.txt

DIR is the folder with the generated unit_XXXX.cpp files (search is recursive). For every address it finds the unit that holds it and prints
the code from a few labels before it to a few after it, with the label lines (L_00329360: ...) as address marks. Read-only.
"""
import os, re, sys

args = sys.argv[1:]
before, after = 40, 60
for flag in ('--before', '--after'):
    if flag in args:
        i = args.index(flag)
        v = int(args[i + 1])
        if flag == '--before': before = v
        else: after = v
        del args[i:i + 2]
if len(args) < 2:
    print(__doc__)
    raise SystemExit(1)
root, addrs = args[0], [int(a, 16) for a in args[1:]]
lab = re.compile(r'^L_([0-9A-F]{8}):')
files = []
for dp, _, fn in os.walk(root):
    for f in fn:
        if f.startswith('unit_') and f.endswith('.cpp'):
            files.append(os.path.join(dp, f))
if not files:
    print("no unit_*.cpp files under " + root)
    raise SystemExit(1)
index = []
for p in files:
    with open(p, errors='replace') as fh:
        lines = fh.read().split('\n')
    labels = [(int(m.group(1), 16), i) for i, l in enumerate(lines) for m in [lab.match(l)] if m]
    if labels:
        index.append((labels[0][0], labels[-1][0], p, lines, labels))
for a in addrs:
    hit = [x for x in index if x[0] <= a <= x[1] + 0x400]
    print("=" * 78 + "\n== address 0x%08X" % a)
    if not hit:
        print("(not found in any unit)")
        continue
    lo, hi, p, lines, labels = hit[0]
    prev = [i for ad, i in labels if ad <= a]
    at = prev[-1] if prev else labels[0][1]
    print("== %s   (line %d is the last label at or before it; code between labels is in address order)" % (os.path.basename(p), at + 1))
    for i in range(max(0, at - before), min(len(lines), at + after)):
        print(("%5d%s %s" % (i + 1, '>' if i == at else ' ', lines[i])).rstrip())
