#!/usr/bin/env python3
"""Spanish text for the launcher: pull the usable files out of a disc the player patched with the TraduSquare / Tio Victor translation.

The translation is a patcher that writes a new copy of the disc (docs/translation-spanish.md). We cannot ship it. The launcher compares that
copy with the player's own disc and keeps the files that change text, menus, pictures and fonts, as an ordinary file mod laid over the
original disc. What it leaves out needs the translation's own changed game program, which this port does not use: the battle core files
(the game freezes or stays black with them), the results screen, the title screen and the subtitled videos.

Usage:  p3fes_translate.py ORIGINAL.iso PATCHED.iso OUT_FOLDER     (OUT_FOLDER gets DATA.CVM/... and BTL.CVM/...)
"""
import os
import struct
import sys

SECTOR = 2048
CVM_HEAD = 0x1800   # a CVM is a 6144-byte header followed by an ISO9660 image

# in DATA.CVM everything that changed is kept except these folders
DATA_SKIP = ("SFD/", "OPED/")
# in BTL.CVM only these (tested in game, 25 Oct 2026): they carry the support lines, Shuffle Time and the enemy files, and boot and finish a battle.
# The rest of BTL.CVM (the battle tables, panels, results screen and 213 effect files) is not safe without the translation's own game program.
BTL_KEEP = frozenset("""BATTLE/PANEL/BP_TUTORIAL.BIN BATTLE/SHUFFLE/AGS_SFL_EFFECT.BIN BATTLE/SHUFFLE/I_CHANGE_PER01.SPR BATTLE/SHUFFLE/SFL_BASE.BIN
BATTLE/SHUFFLE/SFL_EFFECT.BIN BATTLE/SHUFFLE/SFL_GROUND.BIN BATTLE/SHUFFLE/SFL_TUTORIAL.BIN MODEL/PACK/EM0E2.PAC MODEL/PACK/EM0E3.PAC
MODEL/PACK/EM0E4.PAC MODEL/PACK/EM0E5.PAC MODEL/PACK/EM0E6.PAC MODEL/PACK/EM0E7.PAC SKILL/140.BED SKILL/141.BED SKILL/142.BED SKILL/14C.BED
SKILL/14D.BED SKILL/14E.BED SND_BENC/BSV401.BVP SND_BENC/BSV402.BVP SND_BENC/BSV402_AEGIS.BVP""".split())


class ToolError(Exception):
    pass


class Sub:
    """A window of a bigger file that reads like a file of its own."""

    def __init__(self, f, base, size):
        self.f, self.base, self.size, self.p = f, base, size, 0

    def seek(self, o):
        self.p = o

    def read(self, n):
        self.f.seek(self.base + self.p)
        d = self.f.read(n)
        self.p += len(d)
        return d


def walk(f, base=0):
    """{path: (sector, size)} of every file of the ISO9660 volume in f (paths start with '/', ';1' removed)."""
    f.seek(16 * SECTOR)
    pvd = f.read(SECTOR)
    if pvd[1:6] != b"CD001":
        raise ToolError("not a disc image (no ISO9660 volume)")
    out = {}

    def rd(lba, size, path):
        f.seek(lba * SECTOR)
        data = f.read(size)
        i = 0
        while i < len(data):
            n = data[i]
            if n == 0:
                i = (i // SECTOR + 1) * SECTOR
                continue
            r = data[i:i + n]
            i += n
            lba2, sz = struct.unpack("<I", r[2:6])[0], struct.unpack("<I", r[10:14])[0]
            name = r[33:33 + r[32]]
            if name in (b"\x00", b"\x01"):
                continue
            p = path + "/" + name.decode("latin1").split(";")[0]
            if r[25] & 2:
                rd(lba2, sz, p)
            else:
                out[p] = (lba2, sz)

    root = pvd[156:190]
    rd(struct.unpack("<I", root[2:6])[0], struct.unpack("<I", root[10:14])[0], "")
    return out


def cvm(f, files, name):
    """The files inside DATA.CVM / BTL.CVM: ({path: (sector, size)}, window over the CVM's image)."""
    lba, size = files["/" + name]
    sub = Sub(f, lba * SECTOR + CVM_HEAD, size - CVM_HEAD)
    return walk(sub), sub


def keep(rel):
    """True when the translation's version of this file is safe to use. rel is like 'DATA.CVM/FIELD/X.PAK'."""
    top, _, rest = rel.partition("/")
    if top == "DATA.CVM":
        return not rest.startswith(DATA_SKIP)
    if top == "BTL.CVM":
        return rest in BTL_KEEP
    return False


def md5_range(f, lba, size):
    import hashlib
    f.seek(lba * SECTOR)
    m, left = hashlib.md5(), size
    while left > 0:
        b = f.read(min(left, 1 << 22))
        if not b:
            break
        m.update(b)
        left -= len(b)
    return m.digest()


def same_disc(orig_files, patched_files):
    """The patched copy must be the same game: the same top-level files."""
    return set(orig_files) == set(patched_files) and "/DATA.CVM" in orig_files and "/BTL.CVM" in orig_files


def changed(orig, patched, progress=None):
    """List of (rel, size, kind) for the files the translation changed or added that keep() accepts. Opens both discs itself."""
    with open(orig, "rb") as a, open(patched, "rb") as b:
        A, B = walk(a), walk(b)
        if not same_disc(A, B):
            raise ToolError("that disc is not a patched copy of yours (the files on it do not match)")
        out = []
        for name in ("DATA.CVM", "BTL.CVM"):
            FA, ca = cvm(a, A, name)
            FB, cb = cvm(b, B, name)
            for p in sorted(FB):
                rel = name + p
                if not keep(rel):
                    continue
                if progress:
                    progress("Comparing %s…" % name)
                if p in FA and FA[p][1] == FB[p][1] and md5_range(ca, *FA[p]) == md5_range(cb, *FB[p]):
                    continue
                out.append((rel, FB[p][1], "changed" if p in FA else "new"))
    return out


def extract(orig, patched, outdir, progress=None):
    """Write the kept, changed files under outdir/DATA.CVM/... and outdir/BTL.CVM/... Returns (files, bytes)."""
    todo = changed(orig, patched, progress)
    want = {r for r, _, _ in todo}
    n = total = 0
    with open(patched, "rb") as b:
        B = walk(b)
        for name in ("DATA.CVM", "BTL.CVM"):
            FB, cb = cvm(b, B, name)
            for p in sorted(FB):
                rel = name + p
                if rel not in want:
                    continue
                dst = os.path.join(outdir, *rel.split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                cb.seek(FB[p][0] * SECTOR)
                left = FB[p][1]
                with open(dst, "wb") as o:
                    while left > 0:
                        d = cb.read(min(left, 1 << 22))
                        if not d:
                            raise ToolError("the patched disc ended inside %s" % rel)
                        o.write(d)
                        left -= len(d)
                n += 1
                total += FB[p][1]
                if progress and n % 50 == 0:
                    progress("Copying the Spanish files… %d of %d" % (n, len(want)))
    return n, total


def find_patched(folders, original=None):
    """The disc the TraduSquare patcher wrote: a .iso next to the original whose name has [T-Esp] (its own naming) or 'Esp'. Returns a path or None."""
    import glob
    orig = os.path.realpath(original) if original else None
    cands = []
    for d in folders:
        for pat in ("*[[]T-Esp[]]*.iso", "*T-Esp*.iso", "*Esp*.iso", "*spanish*.iso", "*castellano*.iso"):
            cands += sorted(glob.glob(os.path.join(d, pat)))
    for c in cands:
        if os.path.isfile(c) and os.path.realpath(c) != orig:
            return c
    return None


def main(argv):
    if len(argv) != 4:
        print(__doc__)
        return 2
    n, total = extract(argv[1], argv[2], argv[3], progress=lambda s: print(s, flush=True))
    print("%d files, %.0f MB written to %s" % (n, total / 1e6, argv[3]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except ToolError as e:
        print("error:", e)
        sys.exit(1)
