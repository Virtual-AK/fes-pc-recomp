#!/usr/bin/env python3
"""Find the position record of a character that stands still and then starts walking (research tool, docs/known-issues.md).

Take three memory dumps with F7 in the PC window (they land next to ps2run.exe as ramdump_NNN_fFRAME.bin):
  STILL1 = the character is standing in place          STILL2 = the same, 1 to 2 seconds later (still standing)
  MOVED  = the same character after he has started walking
and run:   py p3fes_actordiff.py STILL1.bin STILL2.bin MOVED.bin

It lists every place in memory that holds three numbers in a row (x, y, z as decimal numbers) that are the same in STILL1 and STILL2 and
different in MOVED by a small amount (a few steps). Things that move all the time (you, other walkers) differ between STILL1 and STILL2 and are
left out; things that never move are left out too. Nearby hits are grouped into one object. Prints addresses and numbers only.

options:  --min 0.05   smallest move counted (default 0.05)      --max 600   largest move counted (default 600)
          --limit 40   groups shown (default 40)               --maxrec 30   largest group kept (default 30 records)
          --out FILE   also write the result to this text file
          --around 0xADDR[,0xADDR]   instead of searching, print every word near those addresses that differs between the three dumps
          --span 0x300   how far each side of the address (default 0x300 bytes)
          --findword 0xC1C9B2AE   instead of searching, list every place holding exactly this word in the STILL2 dump (blocks with few hits in full),
                                  with the same place in the other two dumps and the numbers around it               --range 0x100000-0x2000000   memory range searched (default whole RAM above the boot code)
Needs Python 3 and numpy (py -m pip install numpy).
"""
import sys

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
lo_move, hi_move = float(opts.get('min', 0.05)), float(opts.get('max', 600))
limit = int(opts.get('limit', 40))
maxrec = int(opts.get('maxrec', 30))
rng = opts.get('range', '0x100000-0x2000000').split('-')
lo_addr, hi_addr = int(rng[0], 0), int(rng[1], 0)


def load(path):
    with open(path, 'rb') as f:
        data = f.read()
    data = data[:len(data) // 4 * 4]
    return np.frombuffer(data, dtype='<u4')


w1, w2, w3 = (load(p) for p in args)
n = min(len(w1), len(w2), len(w3))
w1, w2, w3 = w1[:n], w2[:n], w3[:n]
f1, f2, f3 = (w.view('<f4') for w in (w1, w2, w3))

_lines = []


def say(text=""):
    print(text)
    _lines.append(text)


def finish():
    if opts.get("out"):
        with open(opts["out"], "w") as fh:
            fh.write("\n".join(_lines) + "\n")
        print("written to " + opts["out"])


if opts.get("findword"):
    target = int(opts["findword"], 0) & 0xFFFFFFFF
    hits = np.nonzero(w2 == np.uint32(target))[0]
    say("word 0x%08X (%.6g as a decimal number) is in %d places of the STILL2 dump" % (target, float(np.array([target], dtype='<u4').view('<f4')[0]), len(hits)))
    blocks = {}
    for i in hits:
        blocks.setdefault(int(i) * 4 // 0x1000, []).append(int(i))
    say("%d blocks of 4 KB hold it; blocks with at most 6 hits are listed in full (a single character record is a few hits, drawing buffers are many)" % len(blocks))
    shown = 0
    for blk in sorted(blocks, key=lambda b: (len(blocks[b]), b)):
        if len(blocks[blk]) > 6 or shown >= limit:
            continue
        shown += 1
        for i in blocks[blk]:
            say("at 0x%08X   STILL1 %08X  STILL2 %08X  MOVED %08X" % (i * 4, w1[i], w2[i], w3[i]))
            lo2, hi2 = max(0, i - 6), min(n, i + 7)
            line = []
            for k in range(lo2, hi2):
                v = float(f2[k]); u = float(f3[k])
                line.append("%s%.3f>%.3f" % ("*" if k == i else "", v, u) if np.isfinite(v) and np.isfinite(u) and abs(v) < 1e7 and abs(u) < 1e7 else "%s%08X>%08X" % ("*" if k == i else "", w2[k], w3[k]))
            say("      nearby (STILL2 > MOVED): " + "  ".join(line))
    finish()
    sys.exit(0)

if opts.get("around"):
    span = int(opts.get("span", '0x300'), 0)
    for a in opts["around"].split(","):
        base = int(a, 0)
        lo, hi = max(0, base - span) // 4, min(n, (base + span) // 4)
        say("around 0x%08X (words that differ between the dumps; S1 = standing, S2 = standing later, M = moving)" % base)
        say("   address      S1 hex   S2 hex   M hex      S1 / S2 / M as whole numbers          as decimals")
        same_count = 0
        for i in range(lo, hi):
            if w1[i] == w2[i] == w3[i]:
                same_count += 1
                continue
            def sg(x):
                return int(x) - (1 << 32) if int(x) >= (1 << 31) else int(x)
            fl = []
            for ff in (f1, f2, f3):
                v = float(ff[i])
                fl.append("%.3f" % v if np.isfinite(v) and abs(v) < 1e6 else "-")
            say("   0x%08X  %08X %08X %08X   %d / %d / %d    %s / %s / %s%s" % (i * 4, w1[i], w2[i], w3[i], sg(w1[i]), sg(w2[i]), sg(w3[i]), fl[0], fl[1], fl[2],
                                                                                "   <-- the candidate" if i * 4 == base else ""))
        say("   (%d words in the range are identical in all three)" % same_count)
        say("")
    finish()
    sys.exit(0)

with np.errstate(all='ignore'):
    ok1 = np.isfinite(f1) & (np.abs(f1) < 1e5)
    ok2 = np.isfinite(f2) & (np.abs(f2) < 1e5)
    ok3 = np.isfinite(f3) & (np.abs(f3) < 1e5)
    same = (w1 == w2)
    delta = np.abs(f3 - f2)
    sizable = np.abs(f2) >= 0.5                      # a coordinate that is not zero or a tiny number
    # a coordinate that moved like a walking step: a changed value that stays close to the old one (zero -> number or a jump to
    # another kind of data is a buffer filling up, not a position)
    moved = (w3 != w2) & ok2 & ok3 & sizable & (delta >= lo_move) & (delta <= hi_move) & (delta <= 0.6 * np.abs(f2) + 30.0)

# a record = three consecutive words i, i+1, i+2: unchanged between 1 and 2, valid numbers, at least two of them sizable, at least one moved
m = n - 2
trip_same = same[:m] & same[1:m + 1] & same[2:m + 2]
trip_valid = ok2[:m] & ok2[1:m + 1] & ok2[2:m + 2] & ok3[:m] & ok3[1:m + 1] & ok3[2:m + 2]
trip_sizable = (sizable[:m].astype(np.int8) + sizable[1:m + 1] + sizable[2:m + 2]) >= 2
trip_moved = moved[:m] | moved[1:m + 1] | moved[2:m + 2]
hit = trip_same & trip_valid & trip_sizable & trip_moved
idx = np.nonzero(hit)[0]
idx = idx[(idx * 4 >= lo_addr) & (idx * 4 < hi_addr)]
say("%d candidate records (words in %s to %s)" % (len(idx), hex(lo_addr), hex(hi_addr)))
if not len(idx):
    finish()
    sys.exit(0)

groups, cur = [], [int(idx[0])]
for i in idx[1:]:
    if int(i) - cur[-1] <= 64:    # within 256 bytes: same object
        cur.append(int(i))
    else:
        groups.append(cur)
        cur = [int(i)]
groups.append(cur)
groups = [g for g in groups if len(g) <= maxrec]
groups.sort(key=lambda g: (len(g), g[0]))
say("%d groups of at most %d records (a character is a small record, big blocks are graphics buffers); showing %d, smallest first. Columns: address, x y z while standing, x y z after moving" % (len(groups), maxrec, min(limit, len(groups))))
for g in groups[:limit]:
    say("group at 0x%08X, %d record(s), spans 0x%X bytes" % (g[0] * 4, len(g), (g[-1] - g[0]) * 4 + 12))
    for i in g[:6]:
        a = [float(f2[i + k]) for k in range(3)]
        b = [float(f3[i + k]) for k in range(3)]
        say("   0x%08X  %10.3f %10.3f %10.3f   ->  %10.3f %10.3f %10.3f" % (i * 4, a[0], a[1], a[2], b[0], b[1], b[2]))
    if len(g) > 6:
        say("   ... %d more" % (len(g) - 6))
say("\nNext: put the addresses you want to follow in PS2_WATCH=0xADDR,0xADDR (see ps2run_probe_patch.py).")
finish()
