#!/usr/bin/env python3
"""Find memory words that tell two situations apart (research tool for docs/fast-forward.md).

Take memory dumps (F7 in the PC window, see ps2run_probe_patch.py) in two or more situations, for example
  A = a line of dialogue is on screen        B = a choice menu is open        C = walking around, no text
and list the places whose value is the same in every dump of one situation but different between situations.

  python3 p3fes_ramfind.py talk=ramdump_001_f10.bin,ramdump_002_f90.bin  choice=ramdump_003_f200.bin,ramdump_004_f400.bin
  options: --width 1|2|4 (default 4)   --limit N (default 60)   --only talk,choice (compare just these two)
Take several dumps per situation in different scenes: with one dump each almost everything looks like a candidate.
Prints address, then the value seen in each situation. Needs only Python 3; uses numpy when it is installed (much faster).
"""
import sys

args = [a for a in sys.argv[1:] if not a.startswith('--')]
opts = {}
it = iter(sys.argv[1:])
for a in it:
    if a.startswith('--'):
        opts[a[2:]] = next(it, '')
        if opts[a[2:]].startswith('--'):
            sys.exit("option %s needs a value" % a)
args = [a for a in args if '=' in a]
if len(args) < 2:
    sys.exit(__doc__)
width = int(opts.get('width', 4))
limit = int(opts.get('limit', 60))
if width not in (1, 2, 4):
    sys.exit("--width must be 1, 2 or 4")
groups = {}
for a in args:
    name, files = a.split('=', 1)
    groups[name] = [f for f in files.split(',') if f]
if 'only' in opts:
    keep = opts['only'].split(',')
    groups = {k: v for k, v in groups.items() if k in keep}
if len(groups) < 2:
    sys.exit("need at least two situations")
fmt = {1: 'B', 2: 'H', 4: 'I'}[width]

try:
    import numpy as np
except ImportError:
    np = None


def load(path):
    with open(path, 'rb') as f:
        data = f.read()
    data = data[:len(data) // width * width]
    if np is not None:
        return np.frombuffer(data, dtype={1: np.uint8, 2: np.uint16, 4: np.uint32}[width])
    import array
    arr = array.array(fmt)
    arr.frombytes(data)
    return arr


stable = {}
for name, files in groups.items():
    first = None
    same = None
    for fn in files:
        d = load(fn)
        if first is None:
            first = d
            same = np.ones(len(d), dtype=bool) if np is not None else None
        else:
            n = min(len(first), len(d))
            if np is not None:
                same = same[:n] & (first[:n] == d[:n])
                first = first[:n]
            else:
                pass
    if np is None:
        arrs = [load(f) for f in files]
        n = min(len(a) for a in arrs)
        same = [all(a[i] == arrs[0][i] for a in arrs[1:]) for i in range(n)]
        first = arrs[0]
    stable[name] = (first, same)

names = list(stable)
n = min(len(stable[k][0]) for k in names)
found = []
if np is not None:
    ok = np.ones(n, dtype=bool)
    for k in names:
        ok &= stable[k][1][:n]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            ok &= stable[names[i]][0][:n] != stable[names[j]][0][:n]
    idx = np.nonzero(ok)[0]
    found = [int(i) for i in idx]
else:
    for i in range(n):
        if all(stable[k][1][i] for k in names):
            vals = [stable[k][0][i] for k in names]
            if len(set(vals)) == len(vals):
                found.append(i)
print("%d places tell the situations apart (showing %d)" % (len(found), min(limit, len(found))))
print("address   " + "  ".join("%-10s" % k for k in names))
for i in found[:limit]:
    print("%08x  " % (i * width) + "  ".join(("%0*x" % (width * 2, int(stable[k][0][i]))).ljust(10) for k in names))
