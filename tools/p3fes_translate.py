#!/usr/bin/env python3
"""Spanish text for the launcher: pull the usable files out of a disc the player patched with the TraduSquare / Tio Victor translation.

The translation is a patcher that writes a new copy of the disc (docs/translation-spanish.md). We cannot ship it. The launcher compares that
copy with the player's own disc and keeps the files that change text, menus, pictures and fonts, as an ordinary file mod laid over the
original disc. The battle core files, the results screen and the title screen only work together with the translation's own changed game
program (the game freezes or stays black without it), so they are a second file mod ("core") that the launcher switches on only when the
Spanish program is part of the Essential Mods build. The program itself is turned into a list of word changes (program_pnach) that goes into
that build as one more switchable mod; the translation's own video subtitles are left out of it (this port has its own, docs/subtitles.md).

Usage:  p3fes_translate.py ORIGINAL.iso PATCHED.iso OUT_FOLDER           (OUT_FOLDER gets DATA.CVM/... and BTL.CVM/...)
        p3fes_translate.py --program ORIGINAL.iso PATCHED.iso OUT.pnach   (the game program changes as a patch file)
"""
import os
import re
import struct
import sys

SECTOR = 2048
CVM_HEAD = 0x1800   # a CVM is a 6144-byte header followed by an ISO9660 image

# in DATA.CVM everything that changed is kept except these folders
DATA_SKIP = ("SFD/", "OPED/")
# the files that need the Spanish program ("core"): everything else that changed in BTL.CVM and the title screen (OPED). Still left out: the videos
# (SFD/, this port draws its own subtitles) and the 213 battle cut-in effect files (no text in them, never needed).
CORE_SKIP = ("SFD/", "BATTLE/CUTIN/")
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


def keep(rel, core=False):
    """True when the translation's version of this file is safe to use. rel is like 'DATA.CVM/FIELD/X.PAK'.
    core=True: the files that need the Spanish program instead (see CORE_SKIP); keep(rel) and keep(rel, core=True) never both hold."""
    top, _, rest = rel.partition("/")
    if top not in ("DATA.CVM", "BTL.CVM"):
        return False
    plain = (not rest.startswith(DATA_SKIP)) if top == "DATA.CVM" else rest in BTL_KEEP
    if not core:
        return plain
    return (not plain) and not rest.startswith(CORE_SKIP)


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


def changed(orig, patched, progress=None, core=False):
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
                if not keep(rel, core):
                    continue
                if progress:
                    progress("Comparing %s…" % name)
                if p in FA and FA[p][1] == FB[p][1] and md5_range(ca, *FA[p]) == md5_range(cb, *FB[p]):
                    continue
                out.append((rel, FB[p][1], "changed" if p in FA else "new"))
    return out


def extract(orig, patched, outdir, progress=None, core=False):
    """Write the kept, changed files under outdir/DATA.CVM/... and outdir/BTL.CVM/... Returns (files, bytes)."""
    todo = changed(orig, patched, progress, core)
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


# ------------------------------------------------------------------ the game program (SLUS_216.21)
# The translation changes the game program in three ways (compared with the USA program, 26 Oct 2026, translation v1.1b):
#  1. about 470 instruction words below 0x5B0000: screen layout numbers (positions and sizes of the text boxes, as float or integer constants),
#     and 20 or so hooks that jump into small new routines it put into unused room at 0x685BC0 (more layout adjustments);
#  2. about 85 KB of data (text tables, string pointers, tables moved) between 0x5B0000 and 0x7C0000;
#  3. its own video subtitles: five hooks that jump to new code at 0x7C8DA4, a 12 KB block at 0x9ACC80 (movie list and subtitle tables), and the
#     start of the heap moved up by 12 KB (0x1001D8 and 0x77F494). This port has its own video subtitles, and the movie list in that block
#     points at the sectors of the translation's disc, not yours, so this part is left out.
PROGRAM = "/SLUS_216.21"
PROG_CODE = (0x100000, 0x5B0000)           # instructions; everything above is data in this program
PROG_CAVES = ((0x685BC0, 0x685C80),)       # new routines in unused room (kept as instructions)
PROG_MOVIE_FROM = 0x7C0000                 # changes from here up belong to the video subtitles
PROG_MOVIE_WORDS = frozenset((0x1001D8, 0x10ACC4, 0x10ACC8, 0x10ACFC, 0x10AD00, 0x10BF68, 0x265264, 0x501D8C, 0x50224C, 0x77F494))
PROG_MOVIE_BLOCK = (0x9ACC80, 0x9AFC80)    # the translation's movie list (12 KB of new memory); a table value that points into it belongs to the video subtitles too
PROG_MOVIE_RANGES = ((0x7C0000, 0x7CA000), (0x7CE000, 1 << 32))   # new video subtitle code and the movie list; 0x7CA000-0x7CE000 is real text and layout data
PROG_TABLE_MIN = 1000                      # fewest file-table entries that must be found
PROG_VERSION = 4                           # raise when the words chosen change, so a launcher makes the patch file again
PROG_TACTICS = (0x684F00, 10, 0x10)         # the Tactics menu: a table of 10 pointers; the English strings are 16 bytes apart. Another mod (Direct Commands) moves that table, so the text is put into the strings and the pointers are left alone
PROG_TACTICS_SHORT = {b"Ir a por ca\x81\x90dos": b"Ir por ca\x81\x90dos", b"Asignar objetivo": b"Asig. objetivo"}   # Spanish names that do not fit 16 bytes
PROG_MAX_DIFF = 40000                      # a changed-word count far above this is not the translation this was made for


def read_program(path):
    """The game program file of a disc image (bytes)."""
    with open(path, "rb") as f:
        files = walk(f)
        if PROGRAM not in files:
            raise ToolError("the game program (SLUS_216.21) is not on that disc")
        lba, size = files[PROGRAM]
        f.seek(lba * SECTOR)
        return f.read(size)


def _memory(elf):
    """{start: bytes} of the loadable parts of an ELF program, zero-filled up to their memory size."""
    if elf[:4] != b"\x7fELF" or elf[4] != 1 or elf[5] != 1:
        raise ToolError("the game program is not a 32-bit little-endian ELF file")
    phoff = struct.unpack_from("<I", elf, 0x1C)[0]
    phentsize, phnum = struct.unpack_from("<HH", elf, 0x2A)
    out = {}
    for i in range(phnum):
        kind, off, vaddr, _p, filesz, memsz, _fl, _al = struct.unpack_from("<8I", elf, phoff + i * phentsize)
        if kind == 1 and memsz:
            out[vaddr] = bytes(elf[off:off + filesz]) + bytes(memsz - filesz)
    return out


def _flat(mem, lo, hi):
    img = bytearray(hi - lo)
    for start, data in mem.items():
        a, b = max(start, lo), min(start + len(data), hi)
        if a < b:
            img[a - lo:b - lo] = data[a - start:b - start]
    return img


def _jump_target(word, addr):
    op = word >> 26
    return (((addr + 4) & 0xF0000000) | ((word & 0x3FFFFFF) << 2)) if op in (2, 3) else None


def _table_region(img, lo):
    """(start, end) of the game's file table in a flat memory image starting at address lo: the entries are size (4 bytes), 0 (4), start sector (4),
    two bytes, then the name; the entries lie in a few runs close together (with some directory lists between them)."""
    hits = []
    for m in re.finditer(rb"[A-Z0-9_]{1,30}\.[A-Z0-9]{2,4}\x00", bytes(img)):
        p = lo + m.start() - 14
        if p % 4 == 0 and p >= lo and img[p - lo + 4:p - lo + 8] == b"\0\0\0\0":
            hits.append(p)
    runs = []
    for a in hits:
        if runs and a - runs[-1][-1] <= 0x1000:
            runs[-1].append(a)
        else:
            runs.append([a])
    big = max(runs, key=len) if runs else []
    if len(big) < PROG_TABLE_MIN:
        raise ToolError("the file table was not found in the game program (%d entries)" % len(big))
    return big[0] - 0x20, big[-1] + 0x30


def program_words(orig_elf, esp_elf):
    """-> (code, data, info): the words the translation changed, as {address: (original, new)}.
    code = instructions to switch with the mod; data = values to write at start-up. The video subtitle parts are left out."""
    mo, me = _memory(orig_elf), _memory(esp_elf)
    lo = min(mo)
    hi = max(s + len(d) for s, d in list(mo.items()) + list(me.items()))
    hi = (hi + 3) & ~3
    A, B = _flat(mo, lo, hi), _flat(me, lo, hi)
    diff = []
    if A != B:
        for k in range(0, len(A), 4096):     # find the differing blocks first, then the words
            if A[k:k + 4096] != B[k:k + 4096]:
                for j in range(k, min(k + 4096, len(A)), 4):
                    if A[j:j + 4] != B[j:j + 4]:
                        diff.append(lo + j)
    movie = [a for a in diff if a in PROG_MOVIE_WORDS or any(r0 <= a < r1 for r0, r1 in PROG_MOVIE_RANGES)]
    # the game's file table (size, 0, start sector, name) holds the numbers of the translation's disc; your own disc has other ones, so none of it is taken
    table = _table_region(A, lo)
    rest = [a for a in diff if a not in set(movie) and not (table[0] <= a < table[1])]
    ntable = sum(1 for a in diff if table[0] <= a < table[1])
    if len(rest) > PROG_MAX_DIFF or not rest:
        raise ToolError("the changes in the game program are not the ones this tool knows (%d words)" % len(diff))
    word = lambda img, a: struct.unpack_from("<I", img, a - lo)[0]
    code, data = {}, {}
    for a in rest:
        pair = (word(A, a), word(B, a))
        if PROG_MOVIE_BLOCK[0] <= pair[1] < PROG_MOVIE_BLOCK[1] and not PROG_MOVIE_BLOCK[0] <= pair[0] < PROG_MOVIE_BLOCK[1]:
            movie.append(a)      # a pointer to the movie list: without that list in memory the game would read garbage
            continue
        if PROG_CODE[0] <= a < PROG_CODE[1] or any(c0 <= a < c1 for c0, c1 in PROG_CAVES):
            code[a] = pair
        else:
            data[a] = pair
    # Tactics names: write the Spanish text over the English strings instead of changing the pointers (works with or without a mod that moves the table)
    t0, tn, tstep = PROG_TACTICS
    for i in range(tn):
        pa = t0 + 4 * i
        if pa not in data:
            continue
        p = data[pa][1]
        if not lo <= p < hi:
            continue
        end = B.find(b"\0", p - lo)
        text = bytes(B[p - lo:end])
        text = PROG_TACTICS_SHORT.get(text, text)
        slot = data[pa][0]
        if len(text) + 1 > tstep or not lo <= slot < hi:
            continue
        raw = (text + bytes(tstep))[:tstep]
        for k in range(0, tstep, 4):
            a = slot + k
            w = struct.unpack_from("<I", raw, k)[0]
            if w != word(A, a):
                data[a] = (word(A, a), w)
        del data[pa]
    # every hook into the video subtitle code must be one we know, otherwise this is another version of the translation
    hooks = [a for a, (_o, n) in code.items() if (_jump_target(n, a) or 0) >= PROG_MOVIE_FROM]
    if hooks:
        raise ToolError("the game program jumps into new code this tool does not know (%s)" % ", ".join("%X" % a for a in sorted(hooks)[:4]))
    return code, data, {"changed": len(diff), "movie": len(movie), "table": ntable, "code": len(code), "data": len(data)}


def program_pnach(orig_elf, esp_elf):
    """-> (pnach text, info). Code words are patch=1 lines (switched with the mod), data words patch=0 lines (written at start-up when it is on)."""
    code, data, info = program_words(orig_elf, esp_elf)
    out = ["// version %d" % PROG_VERSION,
           "// Spanish program: the changes of the translation's game program (layout and text tables), made on this computer from your two discs.",
           "// Not shipped and not for sharing. The translation's own video subtitles are left out (docs/translation-spanish.md)."]
    for a in sorted(code):
        out.append("patch=1,EE,%08X,word,%08X // original instruction %08X" % (a, code[a][1], code[a][0]))
    for a in sorted(data):
        out.append("patch=0,EE,%08X,word,%08X" % (a, data[a][1]))
    return "\n".join(out) + "\n", info


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
    if len(argv) == 5 and argv[1] == "--program":
        text, info = program_pnach(read_program(argv[2]), read_program(argv[3]))
        with open(argv[4], "w", newline="\n") as f:
            f.write(text)
        print("%d words changed in the program: %d instructions, %d data words kept, %d video subtitle words left out -> %s"
              % (info["changed"], info["code"], info["data"], info["movie"], argv[4]))
        return 0
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
