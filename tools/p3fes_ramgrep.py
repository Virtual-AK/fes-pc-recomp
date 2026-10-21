#!/usr/bin/env python3
"""Find a known piece of on-screen text in a memory dump, whatever character encoding the game uses (research tool, docs/log-plan.md).

  python3 p3fes_ramgrep.py ramdump_001_f1234.bin "Dark Hour"
  options: --context N   bytes of hex shown around each hit (default 48)    --limit N   hits per encoding (default 8)

It does not assume ASCII. It looks for letters that are spaced the way your phrase's letters are spaced in the alphabet
(a to b is +1, b to c is +1, and so on), in 1-byte and 2-byte (little and big endian) form, so a shifted or custom table still
matches. Use a phrase of 6 or more letters with a few different letters in it, and keep to ONE case (the tool lowercases both
cases separately, so "Dark Hour" is searched as D-a-r-k and H-o-u-r words, then as a whole). Needs only Python 3.
"""
import re
import sys

args = [a for a in sys.argv[1:] if not a.startswith('--')]
opts = {}
for i, a in enumerate(sys.argv[1:]):
    if a.startswith('--'):
        opts[a[2:]] = sys.argv[1:][i + 1] if i + 1 < len(sys.argv[1:]) else ''
args = [a for a in args if a not in opts.values()]
if len(args) != 2:
    sys.exit(__doc__)
path, phrase = args
ctx = int(opts.get('context', 48))
limit = int(opts.get('limit', 8))
with open(path, 'rb') as f:
    data = f.read()
if len(phrase) < 5:
    sys.exit("use a longer phrase (5 or more characters)")

codes = [ord(c) for c in phrase]
diffs = [b - a for a, b in zip(codes, codes[1:])]


def show(label, hits, width):
    print("\n== %s: %d hit(s)" % (label, len(hits)))
    for pos in hits[:limit]:
        lo, hi = max(0, pos - ctx // 2), min(len(data), pos + ctx)
        chunk = data[lo:hi]
        print("%08x  %s" % (pos, chunk.hex(' ')))


def search(width, byteorder):
    """positions where consecutive characters (stored `width` bytes each) differ by the phrase's diffs"""
    hits = []
    step = 1 if width == 1 else 2
    first = diffs[0]
    n = len(phrase)
    span = n * width
    for pos in range(0, len(data) - span, 1 if width == 1 else 2):
        vals = []
        ok = True
        prev = None
        for k in range(n):
            o = pos + k * width
            v = data[o] if width == 1 else int.from_bytes(data[o:o + 2], byteorder)
            if prev is not None and v - prev != diffs[k - 1]:
                ok = False
                break
            prev = v
        if ok:
            hits.append(pos)
    return hits


# fast prefilter for 1 byte: use a regex on the first two characters' difference to avoid a slow python loop on 32 MB
def search_fast_1():
    hits = []
    # build a regex that matches any byte b0 followed by b0+d1, b0+d2 ... via alternation over all 256 bases
    pats = []
    for base in range(256):
        seq = [base]
        ok = True
        for d in diffs:
            nxt = seq[-1] + d
            if not 0 <= nxt < 256:
                ok = False
                break
            seq.append(nxt)
        if ok:
            pats.append(re.escape(bytes(seq)))
    if not pats:
        return hits
    rx = re.compile(b'(?=(' + b'|'.join(pats) + b'))', re.S)
    return [m.start() for m in rx.finditer(data)]


show("1 byte per character", search_fast_1(), 1)
try:
    import numpy as np
except ImportError:
    np = None
for bo in ('little', 'big'):
    hits = []
    n = len(phrase)
    if np is not None:
        usable = len(data) // 2 * 2
        arr = np.frombuffer(data[:usable], dtype='<u2' if bo == 'little' else '>u2').astype(np.int32)
        ok = np.ones(len(arr) - n + 1, dtype=bool)
        for k in range(n - 1):
            ok &= (arr[k + 1:len(arr) - n + 2 + k] - arr[k:len(arr) - n + 1 + k]) == diffs[k]
        hits = [int(j) * 2 for j in np.nonzero(ok)[0]]
    else:
        for pos in range(0, len(data) - 2 * n, 2):
            prev = int.from_bytes(data[pos:pos + 2], bo)
            ok = True
            for k in range(1, n):
                v = int.from_bytes(data[pos + 2 * k:pos + 2 * k + 2], bo)
                if v - prev != diffs[k - 1]:
                    ok = False
                    break
                prev = v
            if ok:
                hits.append(pos)
    show("2 bytes per character, %s endian" % bo, hits, 2)
