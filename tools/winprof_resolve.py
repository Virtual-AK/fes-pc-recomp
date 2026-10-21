"""Turns prof_win.txt (written by the Windows PC window with PS2_PROFILE_WIN=1) and ps2run.map into a list of the
busiest functions. Usage: python3 winprof_resolve.py ps2run.map prof_win.txt [how_many]"""
import bisect, re, sys
from collections import Counter

if len(sys.argv) < 3:
    sys.exit(__doc__)
top = int(sys.argv[3]) if len(sys.argv) > 3 else 30
syms, base = [], 0x140000000
for line in open(sys.argv[1], errors="replace"):
    m = re.match(r"\s*Preferred load address is\s+([0-9a-fA-F]+)", line)
    if m:
        base = int(m.group(1), 16)
    m = re.match(r"\s*[0-9a-fA-F]{4}:[0-9a-fA-F]{8}\s+(\S+)\s+([0-9a-fA-F]{16})\s", line)
    if m:
        syms.append((int(m.group(2), 16) - base, m.group(1)))
syms.sort()
addrs = [a for a, _ in syms]


def name(mod, rva):
    if not mod.lower().endswith(".exe"):
        return "[" + mod + "]"
    i = bisect.bisect_right(addrs, rva) - 1
    return syms[i][1] if i >= 0 else "?%x" % rva


sections, cur = {}, None
for line in open(sys.argv[2]):
    p = line.split()
    if len(p) == 1 and p[0] in ("PC", "CALLER"):
        cur = sections.setdefault(p[0], Counter())
    elif len(p) == 3 and cur is not None:
        cur[name(p[1], int(p[2], 16))] += int(p[0])
    elif p and p[0] == "samples":
        print("samples in the last 10 seconds:", p[1])
for title, c in sections.items():
    tot = sum(c.values()) or 1
    print("\n%s  (where the game thread was%s)" % (title, "" if title == "PC" else ", from the top of its stack"))
    for n, k in c.most_common(top):
        print("%5.1f%%  %s" % (100.0 * k / tot, n))
