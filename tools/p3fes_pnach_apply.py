#!/usr/bin/env python3
"""
p3fes_pnach_apply.py - bake PCSX2 .pnach code patches into a COPY of the game's boot program (SLUS_216.21).

Our game is recompiled ahead of time, so a patch that rewrites game code while it runs (which is what a .pnach does on
PCSX2) has no effect. This tool writes the patches into a copy of the program file instead; the copy is then recompiled
(see docs/mods.md). It reads only the program file you give it and the .pnach files, writes new files, and never
changes the originals. It prints numbers and addresses only.

Line types understood (// comments are ignored; when an address is written twice the later line wins, like on PCSX2):
    patch=N,EE,ADDRESS,word|short|byte,VALUE
    patch=N,EE,TAAAAAAA,extended,VALUE      T = 0 byte write, 1 halfword write, 2 word write (the PCSX2 "raw code" forms)
Other line types are counted and skipped.

Two ways to use it:

  1. One patch, always on (the old way):
        p3fes_pnach_apply.py SLUS_216.21 mod.pnach [more.pnach ...] -o patched.elf [--entries extra.txt]

  2. Several mods with live on/off switches in ONE build (Essential Mods):
        p3fes_pnach_apply.py SLUS_216.21 --mod NAME:BIT=a.pnach[,b.pnach] --mod ... -o combined.elf
                             --entries extra.txt --variants variants.txt
     BIT is the number (0-31) of the switch bit of that mod. The recompiler (eerecomp --variants) then builds both the
     original and the patched version of every changed instruction and picks one at run time from the PS2_MODS number.
     Rules: two mods may not change the same instruction to different values (the tool says which and stops); patch=0
     lines, and changes to data (not code), are written into memory at start-up by the runtime when their mod is on.

  Options for a mod that is large or only for one setting (the Spanish program):  --strict NAME  its start-up writes are applied only when
  that mod itself is on (normally they also apply when any mod with code in new memory is on);  --weak NAME  where it changes a word that
  another mod also changes, the other mod wins and that word is left out of it (instead of refusing to build).

variants.txt lines:   C ADDR MASK ORIG NEW      a code word that differs per mod   (MASK = the mod bits that change it)
                      D ADDR SIZE VALUE MASK    a data write applied at start-up when (PS2_MODS & MASK) != 0
                      M NAME BIT                the mod table, for reference
"""
import argparse
import re
import struct
import sys

LINE = re.compile(r"^\s*patch\s*=\s*(\d+)\s*,\s*EE\s*,\s*(?:0x)?([0-9a-fA-F]+)\s*,\s*(word|short|byte|extended)\s*,\s*(?:0x)?([0-9a-fA-F]+)", re.I)
SIZES = {"word": 4, "short": 2, "byte": 1}
EXT_SIZES = {0: 1, 1: 2, 2: 4}
CAVE_GAP = 0x100      # code-cave words closer than this share one new memory block
CAVE_PAD = 0x40       # zero-filled room kept in front of a block (cave code keeps its flags there)


def load_segments(elf):
    if elf[:4] != b"\x7fELF" or elf[4] != 1 or elf[5] != 1:
        sys.exit("not a 32-bit little-endian ELF file")
    phoff = struct.unpack_from("<I", elf, 0x1C)[0]
    phentsize, phnum = struct.unpack_from("<HH", elf, 0x2A)
    segs = []
    for i in range(phnum):
        t, off, vaddr, _p, filesz, memsz, flags, _a = struct.unpack_from("<8I", elf, phoff + i * phentsize)
        if t == 1 and (filesz or memsz):
            segs.append((vaddr, off, filesz, memsz, flags))
    return segs


def to_offset(segs, addr, size):
    for vaddr, off, filesz, _m, _f in segs:
        if vaddr <= addr and addr + size <= vaddr + filesz:
            return off + addr - vaddr
    return None


ORIG = re.compile(r"original\W+(?:instruction\W+)?(?:hex\W+)?(?:0x)?([0-9a-fA-F]{8})\b", re.I)


def parse(paths):
    """-> (ops, skipped, expects); ops = [(when, addr, size, value)] in file order"""
    ops = []
    expects = []
    skipped = 0
    for path in paths:
        for raw in open(path, encoding="utf-8", errors="replace"):
            text, _sep, comment = raw.partition("//")
            if not text.strip():
                continue
            m = LINE.match(text)
            if not m:
                if text.strip().lower().startswith("patch"):
                    skipped += 1
                continue
            when = int(m.group(1))
            kind = m.group(3).lower()
            raw_addr = int(m.group(2), 16)
            if kind == "extended":
                size = EXT_SIZES.get(raw_addr >> 28)
                if size is None:
                    skipped += 1
                    continue
            else:
                size = SIZES[kind]
            addr = raw_addr & 0x0FFFFFFF
            value = int(m.group(4), 16) & ((1 << (8 * size)) - 1)
            ops.append((when, addr, size, value))
            o = ORIG.search(comment)
            if o and size == 4:
                expects.append((addr, int(o.group(1), 16)))
    return ops, skipped, expects


def entry_points(words):
    out = set()
    for addr, value in words.items():
        op = value >> 26
        if op in (2, 3):
            out.add((((addr + 4) & 0xF0000000) | ((value & 0x3FFFFFF) << 2)) & 0x0FFFFFFF)
    return sorted(out)


def block_starts(addrs):
    have = set(addrs)
    return [a for a in sorted(addrs) if a - 4 not in have]


class Image:
    def __init__(self, elf):
        self.elf = elf
        self.segs = load_segments(elf)

    def seg_of(self, addr):
        for s in self.segs:
            if s[0] <= addr < s[0] + s[3]:
                return s
        return None

    def byte(self, addr):
        """vanilla byte, or None when the program image does not hold the address in its file data"""
        off = to_offset(self.segs, addr, 1)
        return None if off is None else self.elf[off]

    def kind(self, addr):
        """'code' | 'data' (inside the file data of a non-executable segment) | 'free' (not in the file data)"""
        s = self.seg_of(addr)
        if s and addr < s[0] + s[2]:
            return "code" if s[4] & 1 else "data"
        return "free"


def byte_writes(ops, forced_data=False):
    """-> {byte address: value}, later lines win"""
    out = {}
    for when, addr, size, value in ops:
        for k in range(size):
            out[addr + k] = (value >> (8 * k)) & 0xFF
    return out


def add_blocks(elf, blocks):
    """append new loadable memory blocks [(start, bytes)] to the program image; returns the new file bytes"""
    out = bytearray(elf)
    phoff = struct.unpack_from("<I", out, 0x1C)[0]
    phentsize, phnum = struct.unpack_from("<HH", out, 0x2A)
    phdrs = [list(struct.unpack_from("<8I", out, phoff + i * phentsize)) for i in range(phnum)]
    extra = []
    for start, data in blocks:
        end = start + len(data)
        for ph in phdrs:
            t, off, vaddr, _p, filesz, memsz, flags, _a = ph
            if t != 1 or not memsz or end <= vaddr or start >= vaddr + memsz:
                continue
            if start < vaddr + filesz:
                sys.exit("a patch needs room at %08X-%08X but the program has data there (%08X-%08X)" % (start, end, vaddr, vaddr + filesz))
            old_end = vaddr + memsz          # the zero-filled tail of the segment: hand the block's part over
            ph[5] = start - vaddr
            if end < old_end:
                extra.append([1, 0, end, end, 0, old_end - end, flags, 16])
        while len(out) % 16:
            out.append(0)
        off = len(out)
        out += data
        extra.append([1, off, start, start, len(data), len(data), 7, 16])
    while len(out) % 16:
        out.append(0)
    new_off = len(out)
    for ph in phdrs + extra:
        out += struct.pack("<8I", *ph)
    struct.pack_into("<I", out, 0x1C, new_off)
    struct.pack_into("<H", out, 0x2C, len(phdrs) + len(extra))
    return bytes(out)


def build(image, mods, strict=(), weak=()):
    """mods = [(name, bit, ops)] -> (words C, K, D lists, conflicts)"""
    per_mod = {}
    data_writes = {}      # (addr,size,value) per mod for patch=0 lines
    for name, bit, ops in mods:
        now = [o for o in ops if o[0] != 0]
        boot = [o for o in ops if o[0] == 0]
        per_mod[name] = (bit, byte_writes(now))
        data_writes[name] = (bit, boot)
    dropped = {}
    if weak:   # a weak mod gives way: its changes to words that any other mod changes are left out
        taken = {a & ~3 for n, (_b, w) in per_mod.items() if n not in weak for a in w}
        for n in weak:
            if n in per_mod:
                bit, w = per_mod[n]
                gone = [a for a in w if (a & ~3) in taken]
                for a in gone:
                    del w[a]
                if gone:
                    dropped[n] = len({a & ~3 for a in gone})
    build.dropped = dropped
    owners = {}           # byte -> {value: mask}
    for name, (bit, writes) in per_mod.items():
        for a, v in writes.items():
            owners.setdefault(a, {})
            owners[a][v] = owners[a].get(v, 0) | (1 << bit)
    conflicts = []
    for a in sorted(owners):
        if len(owners[a]) > 1:
            who = sorted(n for n, (bit, w) in per_mod.items() if a in w)
            conflicts.append((a, who))
    words = {}
    for a, vals in owners.items():
        if len(vals) != 1:
            continue
        (v, mask), = vals.items()
        w = a & ~3
        words.setdefault(w, {})[a] = (v, mask)
    code, data, free = [], [], {}
    for w, bytes_ in sorted(words.items()):
        masks = {m for _v, m in bytes_.values()}
        if len(masks) > 1:
            conflicts.append((w, ["different mods change bytes of the same word"]))
            continue
        mask = masks.pop()
        kinds = {image.kind(w + k) for k in range(4)}
        newb = []
        origb = []
        for k in range(4):
            vb = image.byte(w + k)
            origb.append(vb if vb is not None else 0)
            newb.append(bytes_[w + k][0] if (w + k) in bytes_ else origb[k])
        orig = int.from_bytes(bytes(origb), "little")
        new = int.from_bytes(bytes(newb), "little")
        if kinds == {"code"}:
            code.append((w, mask, orig, new))
        elif kinds == {"free"}:
            free[w] = (new, mask)
        else:
            for k in range(4):
                if (w + k) in bytes_:
                    data.append((w + k, 1, bytes_[w + k][0], mask))
    cave_mask = 0
    for _w, (_v, m) in free.items():
        cave_mask |= m
    for name, (bit, boot) in data_writes.items():
        for _when, addr, size, value in boot:
            # start-up writes ("expand executable memory") are needed by every mod that has code in new memory (not for a strict mod)
            data.append((addr, size, value, (1 << bit) | (0 if name in strict else cave_mask)))
    return code, free, data, conflicts


def main():
    ap = argparse.ArgumentParser(description="Bake .pnach files into a copy of the boot program")
    ap.add_argument("elf")
    ap.add_argument("pnach", nargs="*")
    ap.add_argument("--mod", action="append", default=[], help="NAME:BIT=file.pnach[,file2.pnach] (live switch)")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--entries", help="write jump targets of the patched code here (one hex address per line)")
    ap.add_argument("--variants", help="write the live-switch table here (needed with --mod)")
    ap.add_argument("--strict", action="append", default=[], help="mod NAME whose start-up writes apply only when it is on")
    ap.add_argument("--weak", action="append", default=[], help="mod NAME that gives way where another mod changes the same word")
    args = ap.parse_args()
    elf = bytes(open(args.elf, "rb").read())
    image = Image(elf)

    mods = []
    expects = []
    skipped = 0
    if args.pnach:
        ops, sk, ex = parse(args.pnach)
        skipped += sk
        expects += ex
        mods.append(("baked", 0, ops, True))
    for spec in args.mod:
        head, _eq, files = spec.partition("=")
        name, _c, bit = head.partition(":")
        if not name or not bit.isdigit() or int(bit) > 31 or not files:
            sys.exit("--mod wants NAME:BIT=file.pnach[,file.pnach]  (BIT 0-31), not %r" % spec)
        ops, sk, ex = parse([f for f in files.split(",") if f])
        skipped += sk
        expects += ex
        mods.append((name, int(bit), ops, False))
    if not mods:
        sys.exit("nothing to do: give a .pnach file or --mod")

    ok = bad = 0
    for addr, want in expects:
        off = to_offset(image.segs, addr, 4)
        if off is None:
            continue
        if int.from_bytes(elf[off:off + 4], "little") == want:
            ok += 1
        else:
            bad += 1
            print("MISMATCH at %08X: the program has %08X, the patch notes say the original was %08X" % (addr, int.from_bytes(elf[off:off + 4], "little"), want))
    print("original-word checks from the patch comments: %d match, %d differ" % (ok, bad))

    code, free, data, conflicts = build(image, [(n, b, o) for n, b, o, _x in mods], set(args.strict), set(args.weak))
    for n, k in sorted(getattr(build, "dropped", {}).items()):
        print("%s gives way to another mod at %d words (left out of it)" % (n, k))
    if conflicts:
        for a, who in conflicts:
            print("CONFLICT at %08X: %s" % (a, ", ".join(who)))
        print("These mods change the same place in different ways, so they cannot share one build. Nothing was written.")
        sys.exit(2)

    # baked mode: every change goes straight in, nothing is switchable
    baked = len(mods) == 1 and mods[0][3]
    out = bytearray(elf)
    changed = outside = 0
    for addr, mask, orig, new in code:
        off = to_offset(image.segs, addr, 4)
        out[off:off + 4] = new.to_bytes(4, "little")
        changed += orig != new
    for addr, size, value, mask in data:
        off = to_offset(image.segs, addr, size)
        if off is None:
            if baked:
                outside += 1
                print("outside the program image: %08X" % addr)
            continue
        if baked:
            out[off:off + size] = value.to_bytes(size, "little")
            changed += 1
    # words outside the file's data: new memory blocks (code caves)
    blocks = []
    if free:
        groups = []
        for a in sorted(free):
            if groups and a - groups[-1][-1] <= CAVE_GAP:
                groups[-1].append(a)
            else:
                groups.append([a])
        for g in groups:
            start = (g[0] - CAVE_PAD) & ~0xF
            end = (g[-1] + 4 + 0xF) & ~0xF
            data_ = bytearray(end - start)
            for a in g:
                data_[a - start:a - start + 4] = free[a][0].to_bytes(4, "little")
            blocks.append((start, bytes(data_)))
    if baked and outside:
        sys.exit(1)
    if blocks:
        result = add_blocks(bytes(out), blocks)
    else:
        result = bytes(out)
    open(args.out, "wb").write(result)

    all_words = {a: n for a, _m, _o, n in code}
    all_words.update({a: v for a, (v, _m) in free.items()})
    print("patch lines read: %d mods, %d unsupported lines skipped" % (len(mods), skipped))
    print("code words changed: %d, new memory blocks: %d (%d words), data writes at start-up: %d" % (len(code), len(blocks), len(free), len(data)))
    print("contiguous patched blocks start at: " + " ".join("%X" % a for a in block_starts(all_words)))
    if args.entries:
        eps = entry_points(all_words)
        with open(args.entries, "w") as f:
            for a in eps:
                f.write("%x\n" % a)
        print("entry points written to %s: %d" % (args.entries, len(eps)))
    if args.variants:
        with open(args.variants, "w") as f:
            for name, bit, _o, _x in mods:
                f.write("M %s %d\n" % (name, bit))
            for addr, mask, orig, new in code:
                if not baked and orig != new:
                    f.write("C %X %X %08X %08X\n" % (addr, mask, orig, new))
            for addr, size, value, mask in data:
                if not baked:
                    f.write("D %X %d %X %X\n" % (addr, size, value, mask))
        print("switch table written to %s" % args.variants)


if __name__ == "__main__":
    main()
