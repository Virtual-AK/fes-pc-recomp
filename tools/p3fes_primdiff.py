"""Compare two PS2_TRACE_PRIM files (for example one saved by the PC runner and one saved from the browser build) shape by shape, ignoring the frame
number each shape was counted in (the browser build counts it at a slightly different time). Prints how many shapes are identical, the first
place where the two lists stop matching, and the shapes that appear in only one of the files. Numbers only, no game content.
Usage: python3 p3fes_primdiff.py A.txt B.txt [--show N]
"""
import sys
from collections import Counter

def load(path):
    shapes, cur = [], None
    for line in open(path, errors='replace'):
        if line.startswith('[prim] f') and ' type=' in line:
            if cur is not None:
                shapes.append(cur)
            head = line.rstrip('\n').split(' ', 2)
            cur = [head[2] if len(head) > 2 else '', []]
        elif line.startswith('[prim]   v') and cur is not None:
            cur[1].append(line.rstrip('\n')[len('[prim]   '):])
    if cur is not None:
        shapes.append(cur)
    return [(h, tuple(v)) for h, v in shapes]

def fields(h):
    return dict(x.split('=', 1) for x in h.split() if '=' in x)

def show(sh):
    print('   ' + sh[0])
    for v in sh[1]:
        print('     ' + v)

def main(argv):
    if len(argv) < 3:
        print(__doc__); return 1
    n = 3
    if '--show' in argv:
        n = int(argv[argv.index('--show') + 1])
    a, b = load(argv[1]), load(argv[2])
    print("A: %d shapes   B: %d shapes" % (len(a), len(b)))
    same = 0
    while same < min(len(a), len(b)) and a[same] == b[same]:
        same += 1
    print("identical from the start: %d shapes" % same)
    if same < min(len(a), len(b)):
        print("first difference at shape %d:" % same)
        print(" A:"); show(a[same])
        print(" B:"); show(b[same])
        fa, fb = fields(a[same][0]), fields(b[same][0])
        diff = [k for k in fa if fa.get(k) != fb.get(k)]
        if diff:
            print(" header fields that differ: " + ", ".join("%s (A=%s B=%s)" % (k, fa[k], fb.get(k)) for k in diff))
        for i, (va, vb) in enumerate(zip(a[same][1], b[same][1])):
            if va != vb:
                print(" corner %d differs:\n   A %s\n   B %s" % (i, va, vb))
    ca, cb = Counter(a), Counter(b)
    only_a, only_b = ca - cb, cb - ca
    print("shapes only in A: %d   only in B: %d   (counting repeats)" % (sum(only_a.values()), sum(only_b.values())))
    for name, c in (("A", only_a), ("B", only_b)):
        for sh, k in c.most_common(n):
            print("only in %s (x%d):" % (name, k)); show(sh)
    return 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
