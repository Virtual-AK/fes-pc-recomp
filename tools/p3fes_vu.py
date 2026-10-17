#!/usr/bin/env python3
"""
p3fes_vu.py - how the game uses the PS2 vector units (VU0 and VU1). Phase 1 question 1.2.

Reads the game's main executable (the boot ELF, SLUS_216.21) and reports NUMBERS AND ADDRESSES ONLY (no code
is copied into the report):

  * VU0 macro mode: how many instructions in the main program talk to VU0 directly (COP2 instructions, LQC2/SQC2)
    and in how many separate places. Many places means VU0 maths is spread through the game's code.
  * VU microcode: blocks of data that look like vector-unit programs. Every VU instruction is 8 bytes; the
    "no operation" lower instruction 0x8000033C is very distinctive, so places where it repeats at 8-byte steps are
    programs. For each block: address, size, number of units, number of program-end markers (the E bit).
  * VIF microcode upload commands (MPG) that sit in the data, with the program size and VU address.
  * Direct access to the vector-unit memory (instructions loading 0x1100xxxx) and to the VIF/GS registers
    (0x1000xxxx, 0x1200xxxx), counted.

Usage:  py p3fes_vu.py scan extracted3\\SLUS_216.21 -o vu_report.txt
Standard library only. It only READS the file.
"""
import argparse
import collections
import hashlib
import struct
import sys

NOP_LOWER = 0x8000033C      # lower VU instruction "NOP"
NOP_UPPER = 0x000002FF      # upper VU instruction "NOP"
E_BIT = 0x40000000          # end-of-program bit in the upper word
MPG = 0x4A                  # VIF command: load microprogram


def load_segments(data):
    if data[:4] != b"\x7fELF":
        raise SystemExit("not an ELF file")
    phoff = struct.unpack_from("<I", data, 0x1C)[0]
    phsz, phn = struct.unpack_from("<HH", data, 0x2A)
    segs = []
    for i in range(phn):
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from("<8I", data, phoff + i * phsz)
        if t == 1 and fsz:
            segs.append((va, off, fsz))
    if not segs:
        raise SystemExit("no loadable segments")
    return segs


def clusters(positions, gap):
    out, cur = [], []
    for p in positions:
        if cur and p - cur[-1] > gap:
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out


def scan(data):
    segs = load_segments(data)
    R = {"segments": [(va, fsz) for va, off, fsz in segs]}
    cop2 = collections.Counter()
    cop2_pos, hwreg = [], collections.Counter()
    nop_pos, mpg = [], []
    for va, off, fsz in segs:
        seg = data[off:off + fsz]
        words = struct.unpack_from("<%dI" % (len(seg) // 4), seg)
        for i, w in enumerate(words):
            op = w >> 26
            a = va + 4 * i
            if op == 0x12:
                kind = "macro instructions (VU operations)" if w & (1 << 25) else "moves and branches (QMFC2, QMTC2, CFC2, CTC2, BC2)"
                cop2[kind] += 1
                cop2_pos.append(a)
            elif op == 0x36:
                cop2["LQC2 (load a vector register)"] += 1
                cop2_pos.append(a)
            elif op == 0x3E:
                cop2["SQC2 (store a vector register)"] += 1
                cop2_pos.append(a)
            elif op == 0x0F:
                imm = w & 0xFFFF
                if imm == 0x1100:
                    hwreg["lui 0x1100 (VU memory)"] += 1
                elif imm == 0x1000:
                    hwreg["lui 0x1000 (EE registers: VIF, DMA, timers)"] += 1
                elif imm == 0x1200:
                    hwreg["lui 0x1200 (GS registers)"] += 1
                elif imm == 0x1001:
                    hwreg["lui 0x1001 (DMA registers)"] += 1
            if w == NOP_LOWER and a % 8 == 0:
                nop_pos.append(a)
            if (w >> 24) & 0x7F == MPG:
                num = ((w >> 16) & 0xFF) or 256
                start = 4 * i + 4
                if a % 4 == 0 and start + num * 8 <= len(seg) and (va + start) % 8 == 0:
                    blk = seg[start:start + num * 8]
                    units = struct.unpack_from("<%dI" % (num * 2), blk)
                    nops = sum(1 for k in range(0, num * 2, 2) if units[k] == NOP_LOWER)
                    if nops >= 1 and nops * 20 >= num:
                        mpg.append((a, num, w & 0xFFFF, nops, hashlib.sha1(blk).hexdigest()[:10]))
                        # a VIF command word looks like a COP2 instruction; do not count it as one
                        if op == 0x12:
                            kind = "macro instructions (VU operations)" if w & (1 << 25) else "moves and branches (QMFC2, QMTC2, CFC2, CTC2, BC2)"
                            cop2[kind] -= 1
                            cop2_pos.remove(a)
    R["cop2"] = cop2
    R["cop2_places"] = [[p for p in c] for c in clusters(cop2_pos, 256)]
    R["hwreg"] = hwreg
    R["mpg"] = mpg
    blocks = []
    for c in clusters(nop_pos, 128):
        if len(c) < 8:
            continue
        a0, a1 = c[0], c[-1] + 8
        # the block may start earlier: walk back over units that are not obviously data (no zero words pair)
        seg = next(s for s in segs if s[0] <= a0 < s[0] + s[2])
        base = seg[1] - seg[0]
        units = (a1 - a0) // 8
        ebits = sum(1 for a in range(a0, a1, 8) if struct.unpack_from("<I", data, base + a + 4)[0] & E_BIT)
        blocks.append((a0, a1 - a0, units, ebits, len(c)))
        R.setdefault("blockdata", {})[a0] = data[base + a0: base + a1]
    R["blocks"] = blocks
    return R


def upload_sequences(mpg):
    """Group MPG uploads that follow each other in memory (a short gap) and load consecutive VU addresses."""
    seqs, cur = [], []
    for c in sorted(mpg):
        if cur:
            p = cur[-1]
            if c[0] - (p[0] + 4 + p[1] * 8) <= 32 and c[2] == p[2] + p[1]:
                cur.append(c)
                continue
            seqs.append(cur)
        cur = [c]
    if cur:
        seqs.append(cur)
    return seqs


def block_families(R):
    """Blocks of the same size are often variants of one program: count how many differ and how much."""
    data = R.get("blockdata", {})
    L = ["  Different block contents: %d of %d" % (len(set(hashlib.sha1(v).hexdigest() for v in data.values())), len(data))]
    by_size = collections.defaultdict(list)
    for a, v in data.items():
        by_size[len(v)].append(v)
    L.append("  Blocks of equal size (size, blocks, different contents, average share of 8-byte units equal to the first block):")
    rows = []
    for size, vs in by_size.items():
        if len(vs) < 3:
            continue
        first = vs[0]
        shares = []
        for v in vs[1:]:
            same = sum(1 for k in range(0, size, 8) if v[k:k + 8] == first[k:k + 8])
            shares.append(same / (size // 8))
        rows.append((len(vs), size, len(set(vs)), sum(shares) / len(shares)))
    for n, size, d, sh in sorted(rows, reverse=True)[:20]:
        L.append("    %5d bytes: %3d blocks, %3d different, %3d%% equal" % (size, n, d, round(100 * sh)))
    return L


def report(R, name):
    L = ["VU scan of " + name, ""]
    L.append("Loadable segments (address, bytes): " + ", ".join("0x%X %d" % s for s in R["segments"]))
    L.append("")
    tot = sum(R["cop2"].values())
    L.append("VU0 macro mode (the main program using VU0 directly): %d instructions in %d separate places (places = groups more than 256 bytes apart)"
             % (tot, len(R["cop2_places"])))
    for k, v in R["cop2"].most_common():
        L.append("  %7d  %s" % (v, k))
    big = sorted(R["cop2_places"], key=len, reverse=True)[:15]
    if big:
        L.append("  largest places (first address, last address, instructions):")
        for c in big:
            L.append("    0x%X - 0x%X  %d" % (c[0], c[-1], len(c)))
    L.append("  note: words in data can look like instructions, so small counts are noise; the clusters are the real use.")
    L.append("")
    L.append("Direct access to hardware registers (instructions that load an address high half):")
    for k, v in R["hwreg"].most_common():
        L.append("  %7d  %s" % (v, k))
    L.append("")
    tb = sum(b[1] for b in R["blocks"])
    L.append("VU microcode blocks (repeats of the VU no-operation instruction at 8-byte steps): %d blocks, %d bytes, %d program-end markers"
             % (len(R["blocks"]), tb, sum(b[3] for b in R["blocks"])))
    L.append("  address      bytes   units  end-markers  nop-count")
    for a, n, u, e, c in sorted(R["blocks"], key=lambda b: -b[1])[:80]:
        L.append("  0x%08X %7d %6d %12d %10d" % (a, n, u, e, c))
    if len(R["blocks"]) > 80:
        L.append("  ... %d smaller blocks not shown" % (len(R["blocks"]) - 80))
    L.extend(block_families(R))
    L.append("  note: a block is a lower bound (it starts at the first and ends at the last no-operation); one block can hold several programs.")
    L.append("")
    L.append("VIF microprogram-load commands (MPG) found in data with plausible program bytes behind them: %d" % len(R["mpg"]))
    seqs = upload_sequences(R["mpg"])
    distinct = collections.Counter(tuple(c[4] for c in s) for s in seqs)
    uniq_chunks = {c[4]: c[1] for c in R["mpg"]}
    L.append("  Chunks that follow each other in memory and load consecutive VU addresses are one program loaded in pieces.")
    L.append("  Programs (upload sequences): %d, of which %d different; different chunks: %d (%d bytes in all)"
             % (len(seqs), len(distinct), len(uniq_chunks), 8 * sum(uniq_chunks.values())))
    sizes = collections.Counter()
    for key in distinct:
        sizes[sum(uniq_chunks[h] for h in key)] += 1
    L.append("  different programs by size in units (units: how many programs): " + ", ".join(
        "%d: %d" % kv for kv in sorted(sizes.items())[:40]))
    L.append("  most repeated programs (copies, pieces, units):")
    for key, n in distinct.most_common(12):
        L.append("    %4d copies, %d pieces, %d units" % (n, len(key), sum(uniq_chunks[h] for h in key)))
    L.append("  first 60 uploads:")
    for a, num, imm, nops, h in R["mpg"][:60]:
        L.append("  at 0x%08X: %d units (%d bytes) to VU address 0x%04X, %d no-operations, content %s" % (a, num, num * 8, imm, nops, h))
    if len(R["mpg"]) > 60:
        L.append("  ... %d more not shown" % (len(R["mpg"]) - 60))
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="How the game uses the PS2 vector units.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="count VU0 macro-mode use and find VU microcode in the executable")
    s.add_argument("exe")
    s.add_argument("-o", "--out", default="vu_report.txt")
    a = ap.parse_args()
    with open(a.exe, "rb") as fh:
        data = fh.read()
    text = report(scan(data), a.exe)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text[:3000])
    print("Report: " + a.out)


if __name__ == "__main__":
    main()
