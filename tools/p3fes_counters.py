#!/usr/bin/env python3
"""Find the counters that tick while a scene waits (research tool, docs/known-issues.md).

Take three memory dumps with F7 in the PC window (they land next to ps2run.exe as ramdump_NNN_fFRAME.bin; the frame is in the name):
  D1 = early in the wait (Kenji stands at the gate, just placed)     D2 = later in the same wait, at least 100 frames (2 seconds) after D1
  D3 = after the wait is over (he is walking)
and run:   py p3fes_counters.py D1.bin D2.bin D3.bin [--out counters.txt] [--limit 300]

It lists every 32-bit word that grew between D1 and D2 at a steady rate: a whole number that went up by about 1 (or 1/2, 2, 1/4, 4) per frame,
or a decimal number that went up by 1/60, 1/30 or a similar small step per frame. The timeline that makes the characters wait is one of these.
Per word it prints address, D1, D2, D3 and the rate, and marks whether D3 went on growing (up), came back down (reset) or stayed (same).
Words equal to the frame number itself (the game's global frame counter) are marked "frame". Prints numbers only.
Needs Python 3 and numpy (py -m pip install numpy).
"""
import os, re, sys

try:
    import numpy as np
except ImportError:
    sys.exit("This tool needs numpy:  py -m pip install numpy")

args, opts, it = [], {}, iter(sys.argv[1:])
for a in it:
    if a.startswith('--'):
        opts[a[2:]] = next(it, '')
    else:
        args.append(a)
if len(args) != 3:
    sys.exit(__doc__)
limit = int(opts.get('limit', 300))
LO, HI = 0x100000, 0x2000000

def load(p):
    m = re.search(r'_f(\d+)', os.path.basename(p))
    if not m:
        sys.exit("cannot read the frame number from the name of " + p + " (expected ..._fFRAME.bin)")
    raw = np.fromfile(p, dtype=np.uint8)
    return int(m.group(1)), raw[LO:HI].view('<u4')

f1, a = load(args[0])
f2, b = load(args[1])
f3, c = load(args[2])
df = f2 - f1
if df < 30:
    sys.exit("D1 and D2 are only %d frames apart; take them at least 100 frames apart" % df)
out = []
say = out.append
ia, ib, ic = a.astype(np.int64), b.astype(np.int64), c.astype(np.int64)
d = ib - ia
hits = []
for tag, ratio in (("x1", 1.0), ("x1/2", 0.5), ("x2", 2.0), ("x1/4", 0.25), ("x4", 4.0)):
    want = df * ratio
    ok = (np.abs(d - want) <= max(1.0, df * 0.02)) & (ia >= 0) & (ia < 5_000_000) & (ib < 5_000_000)
    for i in np.nonzero(ok)[0]:
        hits.append((0, tag, int(i), int(ia[i]), int(ib[i]), int(ic[i])))
fa, fb, fc = a.view('<f4'), b.view('<f4'), c.view('<f4')
with np.errstate(all='ignore'):
    rate = (fb - fa) / df
    ok = np.isfinite(fa) & np.isfinite(fb) & (rate > 0.0005) & (rate < 5.0) & (np.abs(fa) < 1e5) & (np.abs(fb) < 1e5) & (np.abs(fb - fa) > 1e-4)
for i in np.nonzero(ok)[0]:
    hits.append((1, "float %.5f/frame" % rate[i], int(i), float(fa[i]), float(fb[i]), float(fc[i])))
def sortkey(h):
    return (h[0], 0 if h[1] == "x1" else 1, h[2])
hits.sort(key=sortkey)
say("D1 frame %d, D2 frame %d (%d apart), D3 frame %d" % (f1, f2, df, f3))
say("%d words grew steadily between D1 and D2 (integers by about 1 per frame or a simple fraction/multiple, decimals by a small step). Showing %d." % (len(hits), min(limit, len(hits))))
say("address        kind               D1            D2            D3            D3 compared with D2")
for kind, tag, i, v1, v2, v3 in hits[:limit]:
    addr = LO + i * 4
    if kind == 0:
        note = "frame" if v1 in (f1, f1 - 1, f1 + 1) and v2 in (f2, f2 - 1, f2 + 1) else ("up" if v3 > v2 else "reset" if v3 < v2 else "same")
        say("0x%08X   %-14s %12d  %12d  %12d   %s" % (addr, tag, v1, v2, v3, note))
    else:
        note = "up" if v3 > v2 else "reset" if v3 < v2 else "same"
        say("0x%08X   %-22s %10.4f  %10.4f  %10.4f   %s" % (addr, tag, v1, v2, v3, note))
text = "\n".join(out)
print(text)
if 'out' in opts and opts['out']:
    with open(opts['out'], 'w') as fh:
        fh.write(text + "\n")
