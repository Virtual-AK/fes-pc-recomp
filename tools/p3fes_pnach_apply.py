#!/usr/bin/env python3
"""
p3fes_pnach_apply.py - bake a PCSX2 .pnach code patch into a COPY of the game's boot program (SLUS_216.21).

Our game is recompiled ahead of time, so a patch that rewrites game code while it runs (which is what a .pnach does on
PCSX2) has no effect. This tool writes the patch into a copy of the program file instead; the copy is then recompiled
(see docs/mods.md). It reads only the program file you give it and the .pnach, writes a new file, and never changes the
originals. It prints numbers and addresses only.

Handles lines of the form  patch=1,EE,ADDRESS,word|short|byte,VALUE  (// comments are ignored); when an address appears
twice the later line wins, like on PCSX2. Other line types are counted and skipped.

Also writes a list of extra code entry points (jump targets of the patched code) for the recompiler.

Usage:
    python3 p3fes_pnach_apply.py SLUS_216.21 mod.pnach [more.pnach ...] -o patched.elf [--entries entries_extra.txt]
"""
import argparse
import re
import struct
import sys

LINE = re.compile(r"^\s*patch\s*=\s*(\d+)\s*,\s*EE\s*,\s*(?:0x)?([0-9a-fA-F]+)\s*,\s*(word|short|byte)\s*,\s*(?:0x)?([0-9a-fA-F]+)", re.I)
SIZES = {"word": 4, "short": 2, "byte": 1}


def load_segments(elf):
    if elf[:4] != b"\x7fELF" or elf[4] != 1 or elf[5] != 1:
        sys.exit("not a 32-bit little-endian ELF file")
    phoff = struct.unpack_from("<I", elf, 0x1C)[0]
    phentsize, phnum = struct.unpack_from("<HH", elf, 0x2A)
    segs = []
    for i in range(phnum):
        t, off, vaddr, _p, filesz, memsz, _f, _a = struct.unpack_from("<8I", elf, phoff + i * phentsize)
        if t == 1 and filesz:
            segs.append((vaddr, off, filesz))
    return segs


def to_offset(segs, addr, size):
    for vaddr, off, filesz in segs:
        if vaddr <= addr and addr + size <= vaddr + filesz:
            return off + addr - vaddr
    return None


ORIG = re.compile(r"original\W+(?:instruction\W+)?(?:hex\W+)?(?:0x)?([0-9a-fA-F]{8})\b", re.I)


def parse(paths):
    patches = {}
    expects = []
    skipped = 0
    for path in paths:
        for raw in open(path, encoding="utf-8", errors="replace"):
            text, _sep, comment = raw.partition("//")
            if not text.strip():
                continue
            m = LINE.match(text)
            if not m:
                if text.strip().lower().startswith(("patch", "comment", "gametitle", "author", "description")):
                    skipped += 1 if text.strip().lower().startswith("patch") else 0
                continue
            size = SIZES[m.group(3).lower()]
            addr = int(m.group(2), 16) & 0x0FFFFFFF
            patches[addr] = (size, int(m.group(4), 16) & ((1 << (8 * size)) - 1))
            o = ORIG.search(comment)
            if o and size == 4:
                expects.append((addr, int(o.group(1), 16)))
    return patches, skipped, expects


def entry_points(patches):
    out = set()
    for addr, (size, value) in patches.items():
        if size != 4:
            continue
        op = value >> 26
        if op in (2, 3):
            out.add((((addr + 4) & 0xF0000000) | ((value & 0x3FFFFFF) << 2)) & 0x0FFFFFFF)
    return sorted(out)


def block_starts(patches):
    addrs = sorted(a for a, (s, _v) in patches.items() if s == 4)
    have = set(addrs)
    return [a for a in addrs if a - 4 not in have]


def main():
    ap = argparse.ArgumentParser(description="Bake a .pnach into a copy of the boot program")
    ap.add_argument("elf")
    ap.add_argument("pnach", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--entries", help="write jump targets of the patched code here (one hex address per line)")
    args = ap.parse_args()
    elf = bytearray(open(args.elf, "rb").read())
    segs = load_segments(elf)
    patches, skipped, expects = parse(args.pnach)
    done = changed = outside = 0
    ok = bad = 0
    for addr, want in expects:
        off = to_offset(segs, addr, 4)
        if off is None:
            continue
        if int.from_bytes(elf[off:off + 4], 'little') == want:
            ok += 1
        else:
            bad += 1
            print('MISMATCH at %08X: the program has %08X, the patch notes say the original was %08X' % (addr, int.from_bytes(elf[off:off + 4], 'little'), want))
    print('original-word checks from the patch comments: %d match, %d differ' % (ok, bad))
    for addr in sorted(patches):
        size, value = patches[addr]
        off = to_offset(segs, addr, size)
        if off is None:
            outside += 1
            print("outside the program image: %08X" % addr)
            continue
        old = int.from_bytes(elf[off:off + size], "little")
        elf[off:off + size] = value.to_bytes(size, "little")
        done += 1
        changed += old != value
    open(args.out, "wb").write(elf)
    print("patch lines read: %d distinct addresses, %d unsupported lines skipped" % (len(patches), skipped))
    print("written: %d (%d changed a value), outside the image: %d" % (done, changed, outside))
    print("contiguous patched blocks start at: " + " ".join("%X" % a for a in block_starts(patches)))
    if args.entries:
        eps = entry_points(patches)
        with open(args.entries, "w") as f:
            for a in eps:
                f.write("%x\n" % a)
        print("entry points written to %s: %d" % (args.entries, len(eps)))
    if outside:
        sys.exit(1)


if __name__ == "__main__":
    main()
