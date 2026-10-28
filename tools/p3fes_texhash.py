"""Same 64-bit upload hash as ps2run_texlog_patch.py, in Python, plus a check of a PS2_TEXLOG log against the disc textures.

  python3 p3fes_texhash.py check texlog.txt tmx.bin index.json   how many logged uploads equal a disc texture's pixels or palette
"""
import json
import sys

import numpy as np

M = (1 << 64) - 1


def mix(z):
    z = (z + 0x9E3779B97F4A7C15) & M
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M
    return z ^ (z >> 31)


def mixv(z):
    z = z + np.uint64(0x9E3779B97F4A7C15)
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return z ^ (z >> np.uint64(31))


def upload_hash(b):
    n = len(b)
    pad = (-n) % 8
    w = np.frombuffer(bytes(b) + b"\0" * pad, dtype="<u8")
    with np.errstate(over="ignore"):
        idx = np.arange(len(w), dtype=np.uint64) * np.uint64(0xD6E8FEB86659FD93)
        s = int(mixv(w ^ idx).sum(dtype=np.uint64))
    return mix((s + n) & M)


def tmx_parts(d):
    """(pixel bytes, palette bytes) of a TMX blob; see p3fes_tmx.py for the layout."""
    if d[8:12] != b"TMX0":
        return None, None
    pal_n, pal_fmt = d[16], d[17]
    w = int.from_bytes(d[18:20], "little")
    h = int.from_bytes(d[20:22], "little")
    pf = d[22]
    pbytes = {0x13: 1024, 0x14: 64}.get(pf, 0) if pal_n else 0
    bpp = {0x13: 8, 0x14: 4, 0: 32}.get(pf)
    if bpp is None:
        return None, None
    return d[64 + pbytes:64 + pbytes + w * h * bpp // 8], d[64:64 + pbytes]


def check(log, binf, idxf):
    blob = open(binf, "rb").read()
    idx = json.load(open(idxf))
    pix, pal = {}, {}
    for name, off, size in idx:
        p, q = tmx_parts(blob[off:off + size])
        if p:
            pix.setdefault(upload_hash(p), name)
        if q:
            pal.setdefault(upload_hash(q), name)
    rows = [l.split() for l in open(log) if l.strip()]
    hit_p = sum(1 for r in rows if int(r[8], 16) in pix)
    hit_q = sum(1 for r in rows if int(r[8], 16) in pal)
    print("uploads %d, distinct %d" % (len(rows), len({r[8] for r in rows})))
    print("equal to a disc texture's pixels: %d, to a palette: %d" % (hit_p, hit_q))
    seen = set()
    for r in rows:
        k = int(r[8], 16)
        if k in pix and k not in seen:
            seen.add(k)
            print("  %s  %sx%s psm %s  %s" % (r[8], r[5], r[6], r[2], pix[k]))


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "check":
        check(*sys.argv[2:])
    else:
        print(__doc__)
