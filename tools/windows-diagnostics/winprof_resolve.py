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


import os, struct

DLL_DIRS = ["/mnt/c/Windows/System32", os.path.dirname(os.path.abspath(sys.argv[1]))]
_exports = {}


def exports(mod):
    """Sorted (rva, name) of a DLL's exported functions, read from the file itself (system DLLs and the ones next to the map)."""
    if mod in _exports:
        return _exports[mod]
    out = []
    for d in DLL_DIRS:
        path = next((os.path.join(d, f) for f in (os.listdir(d) if os.path.isdir(d) else []) if f.lower() == mod.lower()), None)
        if not path:
            continue
        try:
            b = open(path, "rb").read()
            pe = struct.unpack_from("<I", b, 0x3C)[0]
            nsec = struct.unpack_from("<H", b, pe + 6)[0]
            optsz = struct.unpack_from("<H", b, pe + 20)[0]
            opt = pe + 24
            exp_rva, exp_size = struct.unpack_from("<II", b, opt + (112 if struct.unpack_from("<H", b, opt)[0] == 0x20B else 96))
            secs = [struct.unpack_from("<IIII", b, opt + optsz + 40 * i + 8) for i in range(nsec)]

            def off(rva):
                for vsize, va, rsize, raw in secs:
                    if va <= rva < va + max(vsize, rsize):
                        return raw + rva - va
                return None

            e = off(exp_rva)
            nfun, nnames, afun, anames, aords = struct.unpack_from("<IIIII", b, e + 20)
            fun = off(afun)
            for i in range(nnames):
                nm = off(struct.unpack_from("<I", b, off(anames) + 4 * i)[0])
                ordinal = struct.unpack_from("<H", b, off(aords) + 2 * i)[0]
                frva = struct.unpack_from("<I", b, fun + 4 * ordinal)[0]
                if exp_rva <= frva < exp_rva + exp_size:
                    continue
                out.append((frva, b[nm:b.index(b"\0", nm)].decode("ascii", "replace")))
            break
        except Exception:
            out = []
    out.sort()
    _exports[mod] = out
    return out


def name(mod, rva):
    if not mod.lower().endswith(".exe"):
        ex = exports(mod)
        if ex:
            i = bisect.bisect_right([a for a, _ in ex], rva) - 1
            if i >= 0:
                return "[%s] %s%s" % (mod, ex[i][1], " (nearest export, +0x%x)" % (rva - ex[i][0]) if rva - ex[i][0] > 0x300 else "")
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
    elif p and p[0] == "#":
        print(line.strip())
    elif p and p[0] == "samples":
        print("samples in the last 10 seconds:", p[1])
for title, c in sections.items():
    tot = sum(c.values()) or 1
    print("\n%s  (where the game thread was%s)" % (title, "" if title == "PC" else ", from the top of its stack"))
    for n, k in c.most_common(top):
        print("%5.1f%%  %s" % (100.0 * k / tot, n))
