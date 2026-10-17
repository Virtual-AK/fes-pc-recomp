#!/usr/bin/env python3
"""
p3fes_pacing.py - how the game keeps time. Phase 1 question 1.4 (frame pacing).

Reads the boot executable (SLUS_216.21) and reports ADDRESSES and COUNTS only (no game code is copied):

  * the system-call wrappers (small functions "load number, syscall, return") with their numbers, standard names
    and how many places call each one
  * the places that touch the time and sync hardware: GS status register (0x12001000, the vertical-sync flag),
    EE timers (0x10000000 .. 0x10001800), interrupt status (0x1000F000), the CPU cycle counter (mfc0 $9)
  * the functions that use those, and for each of them the places that call it, with a note when the call sits
    inside a loop in the calling function (a candidate for the main loop)
  * constants that look like frame times: 1/60, 1/30, 1/50 and 60.0, 30.0, 50.0 as floats
  * strings that mention sync, frame, fps, interlace, NTSC, PAL

Usage:  py p3fes_pacing.py scan extracted3\\SLUS_216.21 -o pacing.txt
Standard library only. It only READS the file.
"""
import argparse
import bisect
import collections
import re
import struct
import sys

import p3fes_vu as V

SYSCALL_WORD = 0x0000000C
NAMES = {
    0x02: "GsSetCrt", 0x04: "Exit", 0x10: "AddIntcHandler", 0x11: "RemoveIntcHandler", 0x12: "AddDmacHandler",
    0x13: "RemoveDmacHandler", 0x14: "EnableIntc", 0x15: "DisableIntc", 0x16: "EnableDmac", 0x17: "DisableDmac",
    0x18: "SetAlarm", 0x19: "ReleaseAlarm", 0x1A: "iEnableIntc", 0x1B: "iDisableIntc", 0x1C: "iEnableDmac",
    0x1D: "iDisableDmac", 0x1E: "iSetAlarm", 0x1F: "iReleaseAlarm", 0x20: "CreateThread", 0x21: "DeleteThread",
    0x22: "StartThread", 0x23: "ExitThread", 0x24: "ExitDeleteThread", 0x25: "TerminateThread",
    0x29: "ChangeThreadPriority", 0x2B: "RotateThreadReadyQueue", 0x2D: "ReleaseWaitThread", 0x2F: "GetThreadId",
    0x32: "SleepThread", 0x33: "WakeupThread", 0x34: "iWakeupThread", 0x37: "SuspendThread", 0x39: "ResumeThread",
    0x40: "CreateSema", 0x41: "DeleteSema", 0x42: "SignalSema", 0x43: "iSignalSema", 0x44: "WaitSema",
    0x45: "PollSema", 0x46: "iPollSema", 0x47: "ReferSemaStatus", 0x64: "FlushCache", 0x70: "GsGetIMR",
    0x71: "GsPutIMR", 0x73: "SetVSyncFlag", 0x74: "SetSyscall", 0x76: "SifDmaStat", 0x77: "SifSetDma",
    0x78: "SifSetDChain", 0x79: "SifSetReg", 0x7A: "SifGetReg", 0x7C: "Deci2Call",
}
WAITERS = {0x44, 0x32, 0x73, 0x14, 0x10, 0x18, 0x42, 0x43, 0x33, 0x34, 0x71}   # wait / signal / vsync related
HW = {                                   # (high half, low value) -> label
    (0x1200, 0x1000): "GS CSR (sync flag)",
    (0x1200, 0x0000): "GS PMODE",
    (0x1000, 0x0000): "EE timer 0 count", (0x1000, 0x0800): "EE timer 1 count",
    (0x1000, 0x1000): "EE timer 2 count", (0x1000, 0x1800): "EE timer 3 count",
    (0x1000, 0xF000): "INTC status",
    (0x1000, 0xF010): "INTC mask",
}
FLOATS = {0x3C888889: "1/60", 0x3D088889: "1/30", 0x3CA3D70A: "1/50", 0x42700000: "60.0", 0x41F00000: "30.0",
          0x42480000: "50.0", 0x3F800000: "1.0"}
STR = re.compile(r"vsync|v-sync|vblank|sync|frame|fps|interlace|ntsc|\bpal\b|60hz|50hz|timer|clock", re.I)


def find_strings(img, base):
    out = {}
    for m in re.finditer(rb"[\x20-\x7e]{4,120}\x00", img):
        s = m.group()[:-1].decode("ascii")
        if STR.search(s):
            out[base + m.start()] = s
    return out


def scan(data):
    segs = V.load_segments(data)
    va, off, fsz = segs[0]
    img = data[off:off + fsz]
    words = struct.unpack_from("<%dI" % (len(img) // 4), img)
    n = len(words)
    starts, jal = [], collections.defaultdict(list)
    wrappers = {}                                # address of the "li v1,N" -> N
    hw, flo, cop9 = [], [], []
    for i, w in enumerate(words):
        pc = va + 4 * i
        op = w >> 26
        if op == 0x09 and (w >> 21) & 31 == 29 and (w >> 16) & 31 == 29 and w & 0x8000:
            starts.append(pc)
        elif op == 3:
            jal[((w & 0x3FFFFFF) << 2) | (pc & 0xF0000000)].append(pc)
        elif op == 0x09 and (w >> 21) & 31 == 0 and (w >> 16) & 31 == 3:        # addiu v1,zero,N
            if i + 1 < n and words[i + 1] == SYSCALL_WORD:
                imm = w & 0xFFFF
                if imm & 0x8000:
                    imm = 0x10000 - imm
                wrappers[pc] = imm
            elif i + 2 < n and words[i + 2] == SYSCALL_WORD:
                imm = w & 0xFFFF
                if imm & 0x8000:
                    imm = 0x10000 - imm
                wrappers[pc] = imm
        elif op == 0x10 and (w >> 21) & 31 == 0 and (w >> 11) & 31 == 9:          # mfc0 rt,$9 (cycle counter)
            cop9.append(pc)
        elif op == 0x0F:
            rt = (w >> 16) & 31
            hi = w & 0xFFFF
            if hi in (0x1000, 0x1200):
                for k in range(1, 5):
                    if i + k >= n:
                        break
                    x = words[i + k]
                    xop = x >> 26
                    if xop in (0x09, 0x0D, 0x23, 0x2B, 0x21, 0x25, 0x28, 0x29, 0x2F, 0x39, 0x3D, 0x35, 0x37) and (x >> 21) & 31 == rt:
                        lo = x & 0xFFFF
                        if (hi, lo) in HW:
                            hw.append((pc, HW[(hi, lo)], xop in (0x2B, 0x29, 0x28, 0x39, 0x3F, 0x3D)))
                        break
            found = False
            for k in range(1, 3):
                if i + k >= n:
                    break
                x = words[i + k]
                if x >> 26 == 0x0D and (x >> 21) & 31 == rt:
                    c = (hi << 16) | (x & 0xFFFF)
                    if c in FLOATS:
                        flo.append((pc, FLOATS[c]))
                        found = True
                    break
            if not found and (hi << 16) in FLOATS and hi in (0x4270, 0x41F0, 0x4248):
                flo.append((pc, FLOATS[hi << 16]))
    # a lui with a bare 0x42700000 etc. (low half zero) is caught above; 1.0 is skipped as noise
    flo = [f for f in flo if f[1] != "1.0"]
    return dict(base=va, words=words, strings=find_strings(img, va), starts=starts, jal=jal, wrappers=wrappers,
                hw=hw, flo=flo, cop9=cop9)


def func_of(starts, pc):
    k = bisect.bisect_right(starts, pc) - 1
    return starts[k] if k >= 0 else None


def func_end(R, f):
    k = bisect.bisect_right(R["starts"], f)
    return R["starts"][k] if k < len(R["starts"]) else f + 0x400


def in_loop(R, f, call_pc):
    """True if a backward branch/jump after call_pc, in the same function, lands at or before call_pc."""
    words, base = R["words"], R["base"]
    end = min(func_end(R, f), f + 0x8000)
    for pc in range(call_pc, end, 4):
        w = words[(pc - base) // 4]
        op = w >> 26
        if op in (4, 5, 6, 7, 1):                       # beq bne blez bgtz regimm
            off = w & 0xFFFF
            if off & 0x8000:
                off -= 0x10000
                tgt = pc + 4 + off * 4
                if f <= tgt <= call_pc:
                    return True
        elif op == 2:                                   # j
            tgt = ((w & 0x3FFFFFF) << 2) | (pc & 0xF0000000)
            if f <= tgt <= call_pc and tgt < pc:
                return True
    return False


def report(R, name):
    starts, jal, W = R["starts"], R["jal"], R["wrappers"]
    L = ["Frame-pacing scan of " + name, ""]
    L.append("Functions (stack-frame starts): %d; system-call wrappers found: %d" % (len(starts), len(W)))
    L.append("")
    L.append("System-call wrappers (address, number, standard name, callers); sync and wait related first:")
    rows = []
    for a, num in W.items():
        f = func_of(starts, a)
        tgt = a if f is None or a - f > 8 else f
        rows.append((0 if num in WAITERS else 1, -len(jal.get(tgt, [])), a, num, tgt))
    for _, _, a, num, tgt in sorted(rows):
        L.append("  0x%08X  %3d (0x%02X)  %-24s %4d callers" % (a, num, num, NAMES.get(num, "?"), len(jal.get(a, [])) or len(jal.get(tgt, []))))
    L.append("")
    L.append("Hardware register touches (code address, register, write?): %d" % len(R["hw"]))
    cnt = collections.Counter((h[1], h[2]) for h in R["hw"])
    for (lab, wr), c in sorted(cnt.items()):
        L.append("  %-20s %s  %d places" % (lab, "write" if wr else "read/other", c))
    byfunc = collections.defaultdict(set)
    for pc, lab, wr in R["hw"]:
        f = func_of(starts, pc)
        if f is not None:
            byfunc[f].add(lab)
    for pc in R["cop9"]:
        f = func_of(starts, pc)
        if f is not None:
            byfunc[f].add("CPU cycle counter (mfc0 $9)")
    L.append("CPU cycle counter reads (mfc0 $9): %d places" % len(R["cop9"]))
    L.append("")
    L.append("Functions that touch time or sync hardware (start, size, callers, what):")
    for f in sorted(byfunc, key=lambda f: -len(jal.get(f, [])))[:40]:
        L.append("  0x%08X %6d bytes %4d callers  %s" % (f, func_end(R, f) - f, len(jal.get(f, [])), ", ".join(sorted(byfunc[f]))))
    L.append("")
    L.append("Wait / signal / vsync wrapper callers: which functions call them (function, wrapper names called):")
    wf = collections.defaultdict(collections.Counter)
    wrapfuncs = {}
    for a, num in W.items():
        f = func_of(starts, a)
        tgt = a if f is None or a - f > 8 else f
        wrapfuncs[tgt] = num
    for tgt, num in wrapfuncs.items():
        if num in WAITERS:
            for pc in jal.get(tgt, []):
                f = func_of(starts, pc)
                if f is not None:
                    wf[f][NAMES.get(num, str(num))] += 1
    for f, c in sorted(wf.items(), key=lambda kv: (-len(kv[1]), -len(jal.get(kv[0], []))))[:40]:
        L.append("  0x%08X %6d bytes %4d callers  %s" % (f, func_end(R, f) - f, len(jal.get(f, [])),
                                                         ", ".join("%s x%d" % kv for kv in sorted(c.items()))))
    L.append("")
    L.append("Call sites of the functions that read the sync flag or set up a vsync interrupt, and whether the call sits in a loop")
    cand = [f for f, labs in byfunc.items() if "GS CSR (sync flag)" in labs]
    cand += [f for f, c in wf.items() if f not in cand and any(k in c for k in ("SetVSyncFlag", "AddIntcHandler", "EnableIntc", "GsPutIMR"))]
    L.append("  (candidates: functions that read the GS status register, or call SetVSyncFlag, AddIntcHandler, EnableIntc or GsPutIMR)")
    L.append("  candidates: %d" % len(cand))
    shown = 0
    for f in sorted(cand, key=lambda f: -len(jal.get(f, [])))[:30]:
        L.append("  function 0x%08X (%d callers)" % (f, len(jal.get(f, []))))
        for pc in jal.get(f, [])[:10]:
            g = func_of(starts, pc)
            loop = in_loop(R, g, pc) if g is not None else False
            L.append("      called at 0x%08X in function 0x%08X (%d bytes, %d callers)%s" % (
                pc, g or 0, (func_end(R, g) - g) if g else 0, len(jal.get(g, [])) if g else 0, "  IN A LOOP" if loop else ""))
            shown += 1
    L.append("")
    L.append("Frame-time constants (1/60, 1/30, 1/50, 60.0, 30.0, 50.0 as floats): %d places" % len(R["flo"]))
    c2 = collections.Counter(lab for _, lab in R["flo"])
    L.append("  " + ", ".join("%s x%d" % kv for kv in sorted(c2.items())))
    ff = collections.defaultdict(set)
    for pc, lab in R["flo"]:
        f = func_of(starts, pc)
        if f is not None:
            ff[f].add(lab)
    for f in sorted(ff, key=lambda f: -len(jal.get(f, [])))[:25]:
        L.append("  0x%08X %6d bytes %4d callers  %s" % (f, func_end(R, f) - f, len(jal.get(f, [])), ", ".join(sorted(ff[f]))))
    L.append("")
    L.append("Strings mentioning sync, frame, fps, interlace, NTSC, PAL, timer, clock: %d" % len(R["strings"]))
    for a in sorted(R["strings"])[:60]:
        L.append("  0x%08X  %s" % (a, R["strings"][a][:100]))
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="How the game keeps time (frame pacing).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="find sync waits, timers, loops and frame-time constants")
    s.add_argument("exe")
    s.add_argument("-o", "--out", default="pacing.txt")
    a = ap.parse_args()
    with open(a.exe, "rb") as fh:
        data = fh.read()
    text = report(scan(data), a.exe)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
