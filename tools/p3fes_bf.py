#!/usr/bin/env python3
"""Survey of the .BF script files (first look; nothing is decoded yet).

  py p3fes_bf.py survey extracted        write bf_survey.txt: magic and size census, header words, sections, strings
  py p3fes_bf.py analyse extracted       write bf_analysis.txt: check the FLW0 layout and the instruction guess on every file
  py p3fes_bf.py messages extracted      write bf_messages.txt: check that the message data inside the scripts reads with the text tool
  py p3fes_bf.py functions SLUS_216.21   write bf_functions.txt: find the table of game functions the scripts call (COMM)
  py p3fes_bf.py peek SLUS_216.21 ADDR   print table records at an address (words, and text where a word points at text)
  py p3fes_bf.py code SLUS_216.21 ADDR   print the program code (MIPS) at an address
  py p3fes_bf.py limit SLUS_216.21 N...  find comparisons against the given numbers (e.g. a table size) in the program code
  py p3fes_bf.py lui SLUS_216.21 0x3057  find loads of a constant's upper half (e.g. the text FLW0 = 0x3057 4C46) with the code after them
  py p3fes_bf.py switch SLUS_216.21 35   find jump tables with that many entries (the script engine has one entry per instruction type)
  py p3fes_bf.py ref SLUS_216.21 ADDR    find the code and the data that refer to an address (a table, a string, a function)
  py p3fes_bf.py comm SLUS_216.21 extracted   write bf_comm.txt: the table of script functions (COMM n), how scripts use each, text each function mentions
  py p3fes_bf.py msgcheck extracted      write bf_msgcheck.txt: do the message-window functions take message numbers of the script's own text?
  py p3fes_bf.py balance extracted --exe EXE  write bf_balance.txt: do the value counts of the functions keep the scripts' stack in balance?
  py p3fes_bf.py export extracted --exe EXE -o scripts_txt   write a readable listing of every script (with message text as comments; keep private)
  py p3fes_bf.py context extracted --exe EXE N   show sample places where function N is called, with the statements around them
  py p3fes_bf.py listing FILE [--exe EXE] print one script as readable statements (function calls with their values)
  py p3fes_bf.py disasm FILE             print one script's labels and instructions
  py p3fes_bf.py hex FILE [-s START] [-n COUNT]   print part of one file as hex, words and text

Reads only your own files. The report holds counts, numbers and a short list of the most common
text strings (names of at most 40 characters); it holds no script content beyond that.
"""
import argparse, collections, os, re, struct, sys

STR = re.compile(rb"[A-Za-z0-9_./:\-]{4,40}")


def files(root):
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            if fn.lower().endswith(".bf"):
                yield os.path.join(dp, fn)


def words(d, start, count):
    n = max(0, min(count, (len(d) - start) // 4))
    return struct.unpack_from("<%dI" % n, d, start)


def fmt(w):
    return "%X" % w if w > 0xFFFF else str(w)


def sections(d):
    """Guess a table of (kind, size, count, offset) records after the first 0x10 bytes: report words that look like offsets
    inside the file in the first 0x80 bytes, in order."""
    ws = words(d, 0, 0x20)
    return [(i * 4, w) for i, w in enumerate(ws) if 0x20 <= w < len(d) and w % 4 == 0]


def survey(root, report_path):
    paths = list(files(root))
    L = []
    if not paths:
        L.append("No .BF files found under " + root)
        open(report_path, "w").write("\n".join(L) + "\n")
        print(L[0])
        return
    magic = collections.Counter()
    sizes = []
    heads = collections.defaultdict(list)
    strings = collections.Counter()
    files_with = collections.Counter()
    align = collections.Counter()
    tails = collections.Counter()
    offs = collections.Counter()
    folders = collections.Counter()
    small = []
    for p in paths:
        d = open(p, "rb").read()
        sizes.append(len(d))
        folders[os.path.relpath(os.path.dirname(p), root).split(os.sep)[0]] += 1
        magic[d[:4]] += 1
        if len(d) < 64:
            small.append(os.path.basename(p))
        heads[d[:4]].append((os.path.basename(p), (words(d, 0, 16) + (0,) * 16)[:16]))
        align[len(d) % 16] += 1
        tails[d[-4:].hex()] += 1
        for i, w in sections(d):
            offs[i] += 1
        seen = set()
        for m in STR.finditer(d):
            s = m.group().decode("ascii")
            strings[s] += 1
            seen.add(s)
        for s in seen:
            files_with[s] += 1
    sizes.sort()
    n = len(sizes)
    L.append("Survey of %d .BF files (%d bytes in total)" % (n, sum(sizes)))
    L.append("Sizes: smallest %d, median %d, largest %d; under 64 bytes: %d%s" % (sizes[0], sizes[n // 2], sizes[-1], len(small), (" (e.g. " + ", ".join(small[:3]) + ")") if small else ""))
    L.append("Folders: " + ", ".join("%s %d" % kv for kv in folders.most_common(10)))
    L.append("File size modulo 16: " + ", ".join("%d x%d" % kv for kv in sorted(align.items())))
    L.append("Last four bytes: " + ", ".join("%s x%d" % kv for kv in tails.most_common(6)))
    L.append("")
    L.append("First four bytes (as text or hex): " + ", ".join(
        "%s x%d" % (k.decode("ascii") if k.isalnum() else k.hex(), c) for k, c in magic.most_common(8)))
    L.append("")
    L.append("Header words (first 16 little-endian words), a few distinct examples per magic:")
    for k, lst in heads.items():
        L.append(" magic %s: %d files" % (k.decode("ascii") if k.isalnum() else k.hex(), len(lst)))
        seen = set()
        for name, ws in sorted(lst, key=lambda x: len(x[0]))[:200]:
            key = ws[:6]
            if key in seen:
                continue
            seen.add(key)
            if len(seen) > 8:
                break
            L.append("   %-14s %s" % (name[:14], " ".join(fmt(w) for w in ws)))
        for col in range(1, 8):
            c = collections.Counter(ws[col] for _, ws in lst)
            L.append("   word %d: %d distinct; most common %s" % (col, len(c), ", ".join("%s x%d" % (fmt(v), m) for v, m in c.most_common(4))))
    L.append("")
    L.append("Positions in the first 0x80 bytes that hold a plausible offset into the file (word position: files):")
    L.append("  " + ", ".join("+0x%02X x%d" % (k, v) for k, v in sorted(offs.items())))
    L.append("")
    L.append("Most common text strings (4 to 40 characters), with the number of files that contain them:")
    for s, c in strings.most_common(60):
        L.append("  %-42s %6d times in %d files" % (s, c, files_with[s]))
    L.append("")
    L.append("Strings found in only one file: %d of %d distinct" % (sum(1 for s in files_with if files_with[s] == 1), len(files_with)))
    open(report_path, "w").write("\n".join(L) + "\n")
    print("Wrote %s (%d files)" % (report_path, n))


# --- FLW0 layout (read from the survey; the instruction names below are a hypothesis that "analyse" tests) ---
# +0x00 u32 0, +0x04 u32 size, +0x08 'FLW0', +0x10 u32 section count, +0x14 u32 variable count, section headers from +0x20:
# four words each: type, element size, element count, start offset.  Types: 0 procedure labels, 1 jump labels (32-byte
# records: 24-byte name, u32 instruction index, u32 reserved), 2 instructions (4 bytes), 3 message data, 4 string data.
OPS = ["PUSHI", "PUSHF", "PUSHIX", "PUSHIF", "PUSHREG", "POPIX", "POPFX", "PROC", "COMM", "END", "JUMP", "CALL", "RUN",
       "GOTO", "ADD", "SUB", "MUL", "DIV", "MINUS", "NOT", "OR", "AND", "EQ", "NEQ", "S", "L", "SE", "LE", "IF",
       "PUSHIS", "PUSHLIX", "PUSHLFX", "POPLIX", "POPLFX", "PUSHSTR"]
WIDE = {0, 1}   # PUSHI, PUSHF: the value is in the next word


def parse_flw(d):
    if len(d) < 0x20 or d[8:12] != b"FLW0":
        return None
    n = struct.unpack_from("<I", d, 0x10)[0]
    if n > 16 or 0x20 + 16 * n > len(d):
        return None
    secs = {}
    for i in range(n):
        t, es, cnt, st = struct.unpack_from("<4I", d, 0x20 + 16 * i)
        if st + es * cnt > len(d):
            return None
        secs[t] = (es, cnt, st)
    return {"size": struct.unpack_from("<I", d, 4)[0], "vars": struct.unpack_from("<I", d, 0x14)[0], "n": n, "sections": secs}


def labels(d, sec):
    es, cnt, st = sec
    out = []
    for i in range(cnt):
        o = st + es * i
        name = d[o:o + 24].split(b"\0")[0].decode("latin-1")
        out.append((name, struct.unpack_from("<I", d, o + 24)[0]))
    return out


def instructions(d, sec):
    es, cnt, st = sec
    ws = struct.unpack_from("<%dI" % cnt, d, st)
    out, i = [], 0
    while i < cnt:
        w = ws[i]
        op, arg = w & 0xFFFF, w >> 16
        if op in WIDE and i + 1 < cnt:
            out.append((i, op, arg, ws[i + 1]))
            i += 2
        else:
            out.append((i, op, arg, None))
            i += 1
    return out


def analyse(root, report_path):
    paths = list(files(root))
    L = []
    c_ok = c_bad = 0
    secsets = collections.Counter()
    ess = collections.Counter()
    contig = collections.Counter()
    ops = collections.Counter()
    unknown_ops = collections.Counter()
    proc_first = collections.Counter()
    proc_end = collections.Counter()
    jump_ok = collections.Counter()
    comm = collections.Counter()
    pushstr_ok = collections.Counter()
    msg_magic = collections.Counter()
    size_rule = collections.Counter()
    varcounts = collections.Counter()
    diffs = collections.Counter()
    endrel = collections.Counter()
    msgw = collections.defaultdict(collections.Counter)
    bad_ex = []
    for p in paths:
        d = open(p, "rb").read()
        f = parse_flw(d)
        if not f:
            c_bad += 1
            if len(bad_ex) < 5:
                bad_ex.append(os.path.basename(p))
            continue
        c_ok += 1
        secs = f["sections"]
        secsets[tuple(sorted(secs))] += 1
        diffs[len(d) - f["size"]] += 1
        ends = [st + es * cnt for t, (es, cnt, st) in secs.items()]
        endrel["size field = end of last section" if f["size"] == max(ends) else "size field = end of last section - 8" if f["size"] == max(ends) - 8 else "other"] += 1
        size_rule["size field = file size - 8" if f["size"] == len(d) - 8 else "size field = file size" if f["size"] == len(d)
                  else "other"] += 1
        for t, (es, cnt, st) in secs.items():
            ess[(t, es)] += 1
        order = sorted((st, es * cnt, t) for t, (es, cnt, st) in secs.items())
        contig["sections contiguous in type order" if all(a[0] + a[1] <= b[0] for a, b in zip(order, order[1:])) else "overlap"] += 1
        if 3 in secs:
            es, cnt, st = secs[3]
            for k, w in enumerate(struct.unpack_from("<%dI" % min(8, cnt // 4), d, st)):
                msgw[k][w] += 1
            msg_magic[d[st:st + 4].hex() + " " + "".join(chr(b) if 32 <= b < 127 else "." for b in d[st:st + 4])] += 1
        if 2 in secs and secs[2][0] == 4:
            ins = instructions(d, secs[2])
            index = {i: (op, arg, val) for i, op, arg, val in ins}
            for i, op, arg, val in ins:
                if op < len(OPS):
                    ops[OPS[op]] += 1
                else:
                    unknown_ops[op] += 1
                if op == 8:
                    comm[arg] += 1
            if 0 in secs:
                for name, at in labels(d, secs[0]):
                    proc_first["PROC" if at in index and index[at][0] == 7 else "not PROC"] += 1
                    prev = index.get(max([i for i in index if i < at], default=-1))
                    proc_end["follows END" if at == 0 or (prev and prev[0] == 9) else "follows something else"] += 1
            if 1 in secs:
                for name, at in labels(d, secs[1]):
                    jump_ok["inside" if at < secs[2][1] else "outside"] += 1
            if 4 in secs:
                for i, op, arg, val in ins:
                    if op == 34:
                        pushstr_ok["inside string section" if arg < secs[4][1] * secs[4][0] else "outside"] += 1
    L.append("%d files parsed as FLW0, %d not (%s)" % (c_ok, c_bad, ", ".join(bad_ex)))
    L.append("Section type sets: " + ", ".join("%s x%d" % (k, v) for k, v in secsets.most_common(6)))
    L.append("(type, element size): " + ", ".join("%s x%d" % (k, v) for k, v in sorted(ess.items())))
    L.append("Size word: " + ", ".join("%s x%d" % kv for kv in size_rule.most_common()))
    L.append("File size minus size word: " + ", ".join("%d x%d" % kv for kv in diffs.most_common(6)))
    L.append("Size word against the last section's end: " + ", ".join("%s x%d" % kv for kv in endrel.most_common()))
    L.append("First words of the message data section: " + "; ".join(
        "word %d: %s" % (k, ", ".join("%X x%d" % kv for kv in c.most_common(3))) for k, c in sorted(msgw.items())))
    L.append("Layout: " + ", ".join("%s x%d" % kv for kv in contig.most_common()))
    L.append("Start of the type-3 section (message data): " + ", ".join("%s x%d" % kv for kv in msg_magic.most_common(5)))
    L.append("")
    L.append("Instruction guess (low 16 bits opcode, high 16 bits operand; PUSHI and PUSHF take the next word too)")
    L.append("  opcodes: " + ", ".join("%s %d" % kv for kv in ops.most_common()))
    L.append("  opcodes outside the guessed list: " + (", ".join("%d x%d" % kv for kv in unknown_ops.most_common(10)) or "none"))
    L.append("  procedure labels pointing at a PROC instruction: " + ", ".join("%s x%d" % kv for kv in proc_first.most_common()))
    L.append("  procedure start preceded by END: " + ", ".join("%s x%d" % kv for kv in proc_end.most_common()))
    L.append("  jump labels: " + ", ".join("%s x%d" % kv for kv in jump_ok.most_common()))
    L.append("  PUSHSTR operands: " + ", ".join("%s x%d" % kv for kv in pushstr_ok.most_common()))
    L.append("  COMM operands (function numbers), most used: " + ", ".join("%d x%d" % kv for kv in comm.most_common(40)))
    L.append("  distinct COMM numbers: %d, highest %s" % (len(comm), max(comm) if comm else "-"))
    open(report_path, "w").write("\n".join(L) + "\n")
    print("Wrote %s (%d files)" % (report_path, c_ok))


def embedded_bmd(d, f):
    """The message data section holds a complete message (.BMD style) file; return its bytes or None."""
    if 3 not in f["sections"]:
        return None
    es, cnt, st = f["sections"][3]
    if cnt < 48 or d[st + 8:st + 12] != b"MSG1":
        return None
    size = struct.unpack_from("<I", d, st + 4)[0]
    return d[st:st + size] if size <= cnt else None


def messages(root, report_path):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import p3fes_text as T
    paths = list(files(root))
    c = collections.Counter()
    kinds = collections.Counter()
    types = collections.Counter()
    fails = collections.Counter()
    nmsgs = []
    pad = collections.Counter()
    ex = []
    diag = []
    seen_diag = set()
    seen_diff = set()
    for p in paths:
        d = open(p, "rb").read()
        f = parse_flw(d)
        if not f:
            c["not a script"] += 1
            continue
        b = embedded_bmd(d, f)
        if b is None:
            c["no message data"] += 1
            continue
        es, cnt, st = f["sections"][3]
        pad[cnt - len(b)] += 1
        try:
            bmd = T.parse_bmd(b)
        except Exception as e:
            c["message data did not parse"] += 1
            fails[str(e)[:60]] += 1
            if len(ex) < 5:
                ex.append(os.path.basename(p))
            key = (os.path.basename(p), len(b))
            if key not in seen_diag and len(seen_diag) < 6 and len(b) >= 48:
                seen_diag.add(key)
                count = struct.unpack_from("<I", b, 24)[0]
                reloc_off = struct.unpack_from("<I", b, 16)[0]
                ents = [struct.unpack_from("<II", b, 32 + 8 * i) for i in range(count) if 32 + 8 * i + 8 <= len(b)]
                offs = [o + 32 for _, o in ents]
                bad = [i for i in range(1, len(offs)) if offs[i] < offs[i - 1]]
                dup = sum(1 for i in range(1, len(offs)) if offs[i] == offs[i - 1])
                diag.append("%s: %d bytes, %d entries, relocation table at %d; first start %d, last start %d; entries out of order at %s "
                            "(%d equal to the one before); types %s; around the first break: %s" % (
                    os.path.basename(p), len(b), count, reloc_off, offs[0], offs[-1], bad[:8], dup,
                    dict(collections.Counter(t for t, _ in ents)),
                    [(i, ents[i - 1], ents[i]) for i in bad[:2]]))
            continue
        c["parsed"] += 1
        nmsgs.append(len(bmd["msgs"]))
        for m in bmd["msgs"]:
            kinds[m["kind"]] += 1
            types[m["type"]] += 1
        if not bmd["ordered"]:
            c["read only (messages out of file order)"] += 1
            continue
        try:
            same = T.build_bmd(bmd)[0] == b
        except Exception:
            same = False
        c["rebuilds identically" if same else "does not rebuild identically"] += 1
        dkey = (os.path.basename(p), len(b))
        if not same and dkey not in seen_diff and len(seen_diff) < 6:
            seen_diff.add(dkey)
            try:
                nb, nstarts = T.build_bmd(bmd)
                ostarts = bmd["starts"]
                which = next((i for i in range(len(ostarts) - 1) if nstarts[i + 1] - nstarts[i] != ostarts[i + 1] - ostarts[i]), None)
                if which is not None:
                    m = bmd["msgs"][which]
                    olen = ostarts[which + 1] - ostarts[which]
                    diag.append("%s message %d (type %d, %s): original %d bytes, rebuilt %d; original ends with %s" % (
                        os.path.basename(p), which, m["type"], m["kind"], olen, nstarts[which + 1] - nstarts[which],
                        b[ostarts[which] + olen - 12:ostarts[which] + olen].hex()))
                first = next((i for i in range(min(len(nb), len(b))) if nb[i] != b[i]), min(len(nb), len(b)))
                nreloc = struct.unpack_from("<2I", nb, 16)
                diag.append("%s rebuild differs: original %d bytes, rebuilt %d, first difference at byte %d; table at %d (rebuilt %d), "
                            "table size %d (rebuilt %d); last message %d bytes (rebuilt %d), kinds %s, gap word %s" % (
                    os.path.basename(p), len(b), len(nb), first, bmd["reloc_off"], nreloc[0], len(bmd["reloc"]), nreloc[1],
                    bmd["reloc_off"] - bmd["starts"][-1], nreloc[0] - nstarts[-1],
                    dict(collections.Counter(m["kind"] for m in bmd["msgs"])), bmd["gap"].hex()))
            except Exception as e:
                diag.append("%s rebuild failed: %s" % (os.path.basename(p), e))
    L = ["Message data inside %d .BF files" % len(paths)]
    L.append("Results: " + ", ".join("%s %d" % kv for kv in c.most_common()))
    L.append("Failure reasons: " + (", ".join("%s x%d" % kv for kv in fails.most_common()) or "none") + (" e.g. " + ", ".join(ex) if ex else ""))
    L.append("Message kinds: " + ", ".join("%s %d" % kv for kv in kinds.most_common()))
    L.append("Message types: " + ", ".join("%s %d" % kv for kv in types.most_common()))
    if nmsgs:
        nmsgs.sort()
        L.append("Messages per file: smallest %d, median %d, largest %d, total %d" % (nmsgs[0], nmsgs[len(nmsgs) // 2], nmsgs[-1], sum(nmsgs)))
    L.append("Bytes between the end of the message file and the end of its section: " + ", ".join("%d x%d" % kv for kv in pad.most_common(6)))
    if diag:
        L.append("")
        L.append("Details of the first problem files:")
        L.extend("  " + x for x in diag)
    open(report_path, "w").write("\n".join(L) + "\n")
    print("Wrote %s" % report_path)


def elf_segments(d):
    """Loadable segments of a 32-bit little-endian ELF: list of (file offset, vaddr, file size, flags)."""
    if d[:4] != b"\x7fELF" or d[4] != 1 or d[5] != 1:
        return None
    phoff = struct.unpack_from("<I", d, 0x1C)[0]
    phsz, phn = struct.unpack_from("<2H", d, 0x2A)
    segs = []
    for i in range(phn):
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from("<8I", d, phoff + phsz * i)
        if t == 1 and fsz and off + fsz <= len(d):
            segs.append((off, va, fsz, fl))
    return segs


def pointer_tables(d, min_len=200):
    """Find runs of consecutive code pointers (the command table of a script engine looks like this): returns
    (file offset, vaddr, stride in bytes, length, distinct count, first entries) sorted by length."""
    segs = elf_segments(d)
    if not segs:
        return None
    code = [(va, va + fsz) for off, va, fsz, fl in segs if fl & 1]
    lo, hi = min(a for a, _ in code), max(b for _, b in code)
    out = []
    for off, va, fsz, fl in segs:
        n = fsz // 4
        ws = struct.unpack_from("<%dI" % n, d, off)
        for sw in (1, 2, 3, 4, 5, 6):
            for lane in range(sw):
                run_start, run_len = None, 0
                seq = ws[lane::sw]
                for k, w in enumerate(seq + (0,)):
                    if k < len(seq) and lo <= w < hi and w % 4 == 0:
                        if run_start is None:
                            run_start = k
                        run_len += 1
                    else:
                        if run_len >= min_len:
                            idx = lane + sw * run_start
                            ents = seq[run_start:run_start + run_len]
                            out.append((off + 4 * idx, va + 4 * idx, 4 * sw, run_len, len(set(ents)), ents[:6]))
                        run_start, run_len = None, 0
    out.sort(key=lambda r: -r[3])
    return out


def functions(path, report_path):
    d = open(path, "rb").read()
    tabs = pointer_tables(d)
    L = ["Pointer-table search in %s (%d bytes)" % (os.path.basename(path), len(d))]
    if tabs is None:
        L.append("Not a 32-bit little-endian ELF file; give the boot executable (SLUS_216.21).")
    else:
        L.append("Runs of at least 200 consecutive code addresses, longest first (a table of the ~500 script functions should be one of them).")
        L.append("File offset, address, stride in bytes (4 = bare pointers, larger = pointer plus other words), length, distinct values, first entries:")
        for off, va, stride, ln, dist, ents in tabs[:25]:
            L.append("  0x%X  0x%X  stride %d  length %d  distinct %d  %s" % (off, va, stride, ln, dist, " ".join("%X" % e for e in ents)))
        if not tabs:
            L.append("  none found")
    open(report_path, "w").write("\n".join(L) + "\n")
    print("Wrote %s" % report_path)


def addr_to_off(segs, a):
    for off, va, fsz, fl in segs:
        if va <= a < va + fsz:
            return off + (a - va)
    return None


def c_string(d, segs, a):
    o = addr_to_off(segs, a)
    if o is None or a < 0x100000:
        return None
    end = d.find(b"\0", o, o + 48)
    if end - o < 3 if end != -1 else True:
        return None
    t = d[o:end]
    return t.decode("ascii") if all(32 <= b < 127 for b in t) else None


def peek(path, addr, stride, count, before):
    d = open(path, "rb").read()
    segs = elf_segments(d)
    if not segs:
        sys.exit("Not a 32-bit little-endian ELF file")
    start = addr - before * stride
    for k in range(count + before):
        a = start + k * stride
        o = addr_to_off(segs, a)
        if o is None or o + stride > len(d):
            print("0x%X  (outside the file)" % a)
            continue
        ws = struct.unpack_from("<%dI" % (stride // 4), d, o)
        note = []
        for w in ws:
            t = c_string(d, segs, w)
            if t:
                note.append('"%s"' % t)
        print("%2d  0x%X  %s  %s" % (k - before, a, " ".join("%08X" % w for w in ws), " ".join(note)))


REGS = ["zero", "at", "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "s0", "s1", "s2", "s3",
        "s4", "s5", "s6", "s7", "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra"]
RFUN = {0: "sll", 2: "srl", 3: "sra", 4: "sllv", 6: "srlv", 7: "srav", 10: "movz", 11: "movn", 12: "syscall", 13: "break",
        15: "sync", 24: "mult", 25: "multu", 26: "div", 27: "divu", 32: "add", 33: "addu", 34: "sub", 35: "subu", 36: "and",
        37: "or", 38: "xor", 39: "nor", 42: "slt", 43: "sltu", 44: "dadd", 45: "daddu", 46: "dsub", 47: "dsubu", 56: "dsll",
        58: "dsrl", 59: "dsra", 60: "dsll32", 62: "dsrl32", 63: "dsra32"}
IOP = {8: "addi", 9: "addiu", 10: "slti", 11: "sltiu", 12: "andi", 13: "ori", 14: "xori", 24: "daddi", 25: "daddiu"}
MEM = {26: "ldl", 27: "ldr", 30: "lq", 31: "sq", 32: "lb", 33: "lh", 34: "lwl", 35: "lw", 36: "lbu", 37: "lhu", 38: "lwr", 39: "lwu",
       40: "sb", 41: "sh", 42: "swl", 43: "sw", 44: "sdl", 45: "sdr", 46: "swr", 49: "lwc1", 55: "ld", 57: "swc1", 63: "sd"}
BR = {4: "beq", 5: "bne", 20: "beql", 21: "bnel"}
BR1 = {6: "blez", 7: "bgtz", 22: "blezl", 23: "bgtzl"}


def mips(w, pc):
    op, rs, rt, rd, sh, fn = w >> 26, (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31, (w >> 6) & 31, w & 63
    imm = w & 0xFFFF
    simm = imm - 0x10000 if imm & 0x8000 else imm
    r = lambda i: "$" + REGS[i]
    if w == 0:
        return "nop"
    if op == 0:
        if fn == 8:
            return "jr " + r(rs)
        if fn == 9:
            return "jalr %s, %s" % (r(rd), r(rs))
        if fn in (16, 18):
            return "%s %s" % ("mfhi" if fn == 16 else "mflo", r(rd))
        if fn in (0, 2, 3, 56, 58, 59, 60, 62, 63):
            return "%s %s, %s, %d" % (RFUN[fn], r(rd), r(rt), sh)
        if fn in (24, 25, 26, 27):
            return "%s %s, %s" % (RFUN[fn], r(rs), r(rt))
        if fn in RFUN:
            return "%s %s, %s, %s" % (RFUN[fn], r(rd), r(rs), r(rt))
    elif op == 1:
        n = {0: "bltz", 1: "bgez", 2: "bltzl", 3: "bgezl"}.get(rt)
        if n:
            return "%s %s, 0x%X" % (n, r(rs), pc + 4 + (simm << 2))
    elif op in (2, 3):
        return "%s 0x%X" % ("j" if op == 2 else "jal", ((pc + 4) & 0xF0000000) | ((w & 0x3FFFFFF) << 2))
    elif op in BR:
        return "%s %s, %s, 0x%X" % (BR[op], r(rs), r(rt), pc + 4 + (simm << 2))
    elif op in BR1:
        return "%s %s, 0x%X" % (BR1[op], r(rs), pc + 4 + (simm << 2))
    elif op == 15:
        return "lui %s, 0x%X" % (r(rt), imm)
    elif op in IOP:
        return "%s %s, %s, %s" % (IOP[op], r(rt), r(rs), ("0x%X" % imm) if op in (12, 13, 14) else str(simm))
    elif op in MEM:
        return "%s %s, %d(%s)" % (MEM[op], r(rt), simm, r(rs))
    return ".word 0x%08X" % w


def code_dump(d, segs, addr, count):
    for k in range(count):
        a = addr + 4 * k
        o = addr_to_off(segs, a)
        if o is None or o + 4 > len(d):
            print("0x%X  (outside the file)" % a)
            continue
        w = struct.unpack_from("<I", d, o)[0]
        print("0x%X  %08X  %s" % (a, w, mips(w, a)))


def find_limit(path, values, context=6, maxhits=12):
    d = open(path, "rb").read()
    segs = elf_segments(d)
    if not segs:
        sys.exit("Not a 32-bit little-endian ELF file")
    want = set()
    for v in values:
        want.update((v, v - 1, v + 1))
    hits = []
    for off, va, fsz, fl in segs:
        if not fl & 1:
            continue
        n = fsz // 4
        ws = struct.unpack_from("<%dI" % n, d, off)
        for i, w in enumerate(ws):
            if (w >> 26) in (9, 10, 11) and (w & 0xFFFF) in want:
                hits.append(va + 4 * i)
    print("%d instructions compare or add one of %s (+-1): showing the first %d with the code after them" % (
        len(hits), ", ".join(str(v) for v in values), min(len(hits), maxhits)))
    for a in hits[:maxhits]:
        print("--- 0x%X" % a)
        code_dump(d, segs, a - 4 * 2, context + 2)


def find_lui(path, imm, maxhits=10, context=14):
    d = open(path, "rb").read()
    segs = elf_segments(d)
    hits = []
    for off, va, fsz, fl in segs:
        if not fl & 1:
            continue
        ws = struct.unpack_from("<%dI" % (fsz // 4), d, off)
        for i, w in enumerate(ws):
            if (w >> 26) == 15 and (w & 0xFFFF) == imm:
                hits.append(va + 4 * i)
    print("%d instructions load 0x%X into the upper half of a register; first %d:" % (len(hits), imm, min(len(hits), maxhits)))
    for a in hits[:maxhits]:
        print("--- 0x%X" % a)
        code_dump(d, segs, a - 4 * 2, context)


def find_switch(path, length, slack=2):
    d = open(path, "rb").read()
    segs = elf_segments(d)
    code = [(va, va + fsz) for off, va, fsz, fl in segs if fl & 1]
    lo, hi = min(a for a, _ in code), max(b for _, b in code)
    found = []
    for off, va, fsz, fl in segs:
        ws = struct.unpack_from("<%dI" % (fsz // 4), d, off)
        i = 0
        while i < len(ws):
            if lo <= ws[i] < hi and ws[i] % 4 == 0:
                j = i
                while j < len(ws) and lo <= ws[j] < hi and ws[j] % 4 == 0:
                    j += 1
                n = j - i
                ents = ws[i:j]
                if length - slack <= n <= length + slack and max(ents) - min(ents) < 0x8000:
                    found.append((va + 4 * i, n, len(set(ents)), min(ents), max(ents), ents[:5]))
                i = j
            else:
                i += 1
    print("%d jump-table candidates with %d (+-%d) entries whose targets lie within 0x8000 bytes of each other:" % (len(found), length, slack))
    for a, n, dist, mn, mx, ents in found[:40]:
        print("  table at 0x%X: %d entries, %d distinct, targets 0x%X..0x%X, first %s" % (a, n, dist, mn, mx, " ".join("%X" % e for e in ents)))


def find_refs(path, addr, maxhits=8, context=24):
    d = open(path, "rb").read()
    segs = elf_segments(d)
    hi, lo = ((addr + 0x8000) >> 16) & 0xFFFF, addr & 0xFFFF
    code_hits, data_hits, calls = [], [], []
    for off, va, fsz, fl in segs:
        ws = struct.unpack_from("<%dI" % (fsz // 4), d, off)
        for i, w in enumerate(ws):
            if w == addr:
                data_hits.append(va + 4 * i)
        if not fl & 1:
            continue
        for i, w in enumerate(ws):
            if (w >> 26) in (2, 3) and ((va + 4 * i + 4) & 0xF0000000 | (w & 0x3FFFFFF) << 2) == addr:
                calls.append(va + 4 * i)
            if (w >> 26) == 15 and (w & 0xFFFF) == hi:
                reg = (w >> 16) & 31
                for j in range(i + 1, min(i + 9, len(ws))):
                    x = ws[j]
                    if (x >> 26) in (9, 13, 32, 33, 35, 36, 37, 40, 41, 43, 55, 63, 49, 57, 30, 31, 15) and ((x >> 21) & 31) == reg and (x & 0xFFFF) == lo:
                        code_hits.append(va + 4 * i)
                        break
    print("0x%X is referred to by %d places in the code (lui + low half) and %d words of data %s" % (
        addr, len(code_hits), len(data_hits), ", ".join("0x%X" % a for a in data_hits[:8])))
    print("It is called (jal or j) from %d places: %s" % (len(calls), ", ".join("0x%X" % a for a in calls[:40])))
    for a in code_hits[:maxhits]:
        print("--- 0x%X" % a)
        code_dump(d, segs, a - 4 * 6, context)


PUSHES = {0, 1, 2, 3, 4, 29, 30, 31, 34}      # PUSHI PUSHF PUSHIX PUSHIF PUSHREG PUSHIS PUSHLIX PUSHLFX PUSHSTR
COMM_TABLE, COMM_COUNT = 0x7B92B0, 502        # found in the executable: records of (function address, second word)


def function_strings(d, segs, start, limit=500, want=3):
    """Text a function mentions (debug and file-name strings), found by following lui + addiu address loads."""
    found = []
    o = addr_to_off(segs, start)
    if o is None:
        return found
    n = min(limit, (len(d) - o) // 4)
    ws = struct.unpack_from("<%dI" % n, d, o)
    ret_at = None
    for i, w in enumerate(ws):
        if ret_at is not None and i > ret_at + 1:
            break
        if w == 0x03E00008 and ret_at is None:
            ret_at = i
        if (w >> 26) == 15:
            reg, hi = (w >> 16) & 31, w & 0xFFFF
            for j in range(i + 1, min(i + 4, n)):
                x = ws[j]
                if (x >> 26) == 9 and ((x >> 21) & 31) == reg:
                    lo = x & 0xFFFF
                    a = (hi << 16) + (lo - 0x10000 if lo & 0x8000 else lo)
                    t = c_string(d, segs, a)
                    if t and t not in found:
                        found.append(t)
                    break
        if len(found) >= want:
            break
    return found


def comm(exe, root, report_path, table=COMM_TABLE, count=COMM_COUNT):
    d = open(exe, "rb").read()
    segs = elf_segments(d)
    if not segs:
        sys.exit("Not a 32-bit little-endian ELF file")
    o = addr_to_off(segs, table)
    recs = [struct.unpack_from("<2I", d, o + 8 * n) for n in range(count)]
    uses = collections.Counter()
    in_files = collections.defaultdict(set)
    before = collections.defaultdict(collections.Counter)
    for p in files(root):
        data = open(p, "rb").read()
        f = parse_flw(data)
        if not f or 2 not in f["sections"] or f["sections"][2][0] != 4:
            continue
        ins = instructions(data, f["sections"][2])
        for k, (i, op, arg, val) in enumerate(ins):
            if op == 8:
                uses[arg] += 1
                in_files[arg].add(p)
                c = 0
                while k - 1 - c >= 0 and ins[k - 1 - c][1] in PUSHES:
                    c += 1
                before[arg][c] += 1
    L = ["Script function table at 0x%X: %d records (function address, second word)" % (table, count)]
    used = [n for n in range(count) if uses[n]]
    null_used = [n for n in used if recs[n][0] == 0]
    L.append("Functions used by scripts: %d; of those with no function in the table: %d %s" % (len(used), len(null_used), null_used[:10]))
    beyond = [n for n in uses if n >= count]
    L.append("Numbers used beyond the table: %s" % (beyond or "none"))
    match = tot = 0
    for n in used:
        m = before[n].most_common(1)[0][0]
        tot += 1
        match += (m == recs[n][1])
    L.append("Second word equals the usual number of values pushed just before the call: %d of %d used functions" % (match, tot))
    L.append("")
    L.append("n, address, second word | uses in files | values pushed just before the call (count x times) | text the function mentions")
    for n in sorted(used, key=lambda x: -uses[x]):
        ptr, extra = recs[n]
        strs = function_strings(d, segs, ptr) if ptr else []
        L.append("COMM %d: 0x%X, %d | %dx in %d files | %s | %s" % (
            n, ptr, extra, uses[n], len(in_files[n]), ", ".join("%d x%d" % kv for kv in before[n].most_common(4)),
            "; ".join('"%s"' % t[:40] for t in strs)))
    L.append("")
    L.append("Table entries never used by any script: %d" % sum(1 for n in range(count) if not uses[n] and recs[n][0]))
    open(report_path, "w").write("\n".join(L) + "\n")
    print("Wrote %s" % report_path)


# Source-file group of the script functions (from the strings the executable holds; see docs/script-functions.md)
MODULE_OF = {133: 'gdata', 134: 'gdata', 209: 'gdata', 210: 'gdata', 211: 'gdata', 212: 'gdata', 213: 'gdata', 13: 'field', 14: 'field', 33: 'field', 118: 'field', 120: 'field', 121: 'field', 122: 'field', 126: 'field', 127: 'field', 128: 'field', 129: 'field', 130: 'field', 131: 'field', 132: 'field', 135: 'field', 136: 'field', 137: 'field', 138: 'field', 192: 'field', 193: 'field', 194: 'field', 197: 'field', 201: 'field', 202: 'field', 204: 'field', 214: 'field', 215: 'field', 216: 'field', 217: 'field', 226: 'field', 229: 'field', 230: 'field', 231: 'field', 232: 'field', 233: 'field', 276: 'field', 277: 'field', 278: 'field', 279: 'field', 281: 'field', 282: 'field', 283: 'field', 284: 'field', 287: 'field', 288: 'field', 296: 'field', 304: 'field', 305: 'field', 311: 'field', 312: 'field', 313: 'field', 314: 'field', 315: 'field', 316: 'field', 339: 'field', 340: 'field', 341: 'field', 342: 'field', 357: 'field', 358: 'field', 359: 'field', 360: 'field', 361: 'field', 371: 'field', 372: 'field', 376: 'field', 377: 'field', 387: 'field', 389: 'field', 390: 'field', 395: 'field', 398: 'field', 401: 'field', 416: 'field', 428: 'field', 464: 'field', 465: 'field', 467: 'field', 469: 'field', 470: 'field', 473: 'field', 477: 'field', 482: 'field', 483: 'field', 484: 'field', 487: 'field', 488: 'field', 489: 'field', 490: 'field', 498: 'field', 501: 'field', 369: 'friend', 7: 'common', 8: 'common', 9: 'common', 10: 'common', 11: 'common', 12: 'common', 18: 'common', 23: 'common', 24: 'common', 25: 'common', 123: 'comu', 124: 'comu', 186: 'comu', 207: 'comu', 208: 'comu', 218: 'comu', 219: 'comu', 220: 'comu', 221: 'comu', 222: 'comu', 223: 'comu', 224: 'comu', 225: 'comu', 234: 'comu', 285: 'comu', 290: 'comu', 292: 'comu', 293: 'comu', 294: 'comu', 297: 'comu', 298: 'comu', 331: 'comu', 332: 'comu', 333: 'comu', 370: 'comu', 381: 'comu', 414: 'comu', 424: 'comu', 425: 'comu', 495: 'comu', 496: 'comu', 497: 'comu', 184: 'evt', 182: 'cutin', 183: 'cutin', 0: 'mes', 1: 'mes', 2: 'mes', 3: 'mes', 6: 'mes', 28: 'mes', 38: 'mes', 40: 'mes'}
BINOP = {14: "+", 15: "-", 16: "*", 17: "/", 20: "||", 21: "&&", 22: "==", 23: "!=", 24: "<", 25: ">", 26: "<=", 27: ">="}
VARS = {2: "ivar", 30: "lvar", 31: "lfvar"}
POPS = {5: "ivar", 6: "fvar", 32: "lvar", 33: "lfvar"}


NAMES = {}
NAMES_FILE = []


def load_names(path):
    """Read a names file: one 'number name' per line, '#' starts a comment. Names replace the default group_number names."""
    try:
        for line in open(path, encoding="utf-8"):
            line = line.split("#")[0].split()
            if len(line) >= 2 and line[0].isdigit():
                NAMES[int(line[0])] = line[1]
        NAMES_FILE.append(path)
    except OSError:
        pass


def names_report():
    if NAMES_FILE:
        return "Function names: %d from %s" % (len(NAMES), NAMES_FILE[-1])
    return "WARNING: script_names.txt was not found next to p3fes_bf.py, so functions keep their number names (copy it into the same folder as this tool)"


load_names(os.path.join(os.path.dirname(os.path.abspath(__file__)), "script_names.txt"))


def func_name(n):
    return NAMES.get(n) or "%s_%d" % (MODULE_OF.get(n, "fn"), n)


def sgn16(v):
    return v - 0x10000 if v & 0x8000 else v


def arg_counts(exe, table=COMM_TABLE):
    if not exe:
        return {}
    d = open(exe, "rb").read()
    segs = elf_segments(d)
    o = addr_to_off(segs, table) if segs else None
    if o is None:
        sys.exit("This executable has nothing at 0x%X, where the script function table is on the NTSC-U disc (SLUS_216.21)." % table)
    return {n: struct.unpack_from("<2I", d, o + 8 * n)[1] for n in range(COMM_COUNT) if o + 8 * n + 8 <= len(d)}


def statements(d, f, counts):
    """Rebuild readable statements from the stack code. Returns list of (instruction index, text, problem flag)."""
    secs = f["sections"]
    ins = instructions(d, secs[2])
    procs = {at: nm for nm, at in labels(d, secs[0])} if 0 in secs else {}
    jumps = labels(d, secs[1]) if 1 in secs else []
    jname = {i: nm for i, (nm, at) in enumerate(jumps)}
    jat = collections.defaultdict(list)
    for nm, at in jumps:
        jat[at].append(nm)
    out, stack = [], []
    recs, last = [], None          # calls, and the latest one (PUSHREG 0 reads its result)
    for i, op, arg, val in ins:
        bad = [False]

        def pop():
            if stack:
                return stack.pop()
            bad[0] = True
            return "?"
        for nm in jat.get(i, []):
            out.append((i, nm + ":", False))
        if op == 0:
            stack.append(str(val - (1 << 32) if val >= 0x80000000 else val))
        elif op == 1:
            stack.append("%g" % struct.unpack("<f", struct.pack("<I", val))[0])
        elif op == 29:
            stack.append(str(sgn16(arg)))
        elif op == 4:
            if arg == 0 and last is not None:
                last["used"] += 1
                stack.append("\x01%d\x02" % last["id"])
            else:
                stack.append("reg%d" % arg)
        elif op in VARS:
            stack.append("%s%d" % (VARS[op], arg))
        elif op == 3:
            stack.append("fvar%d" % arg)
        elif op == 34:
            stack.append("str@%d" % arg)
        elif op in BINOP:
            a = pop()          # the top of the stack is the LEFT operand (scripts push right to left; see docs)
            b = pop()
            if op in (14, 15, 16) and re.fullmatch(r"-?\d+", a) and re.fullmatch(r"-?\d+", b):
                stack.append(str({14: int(a) + int(b), 15: int(a) - int(b), 16: int(a) * int(b)}[op]))   # constant folding
            else:
                stack.append("(%s %s %s)" % (a, BINOP[op], b))
        elif op == 18:
            stack.append("-" + pop())
        elif op == 19:
            stack.append("!" + pop())
        elif op in POPS:
            out.append((i, "%s%d = %s" % (POPS[op], arg, pop()), bad[0]))
        elif op == 8:
            k = counts.get(arg)
            if k is None:
                text = "%s(...)" % func_name(arg)
            else:
                args = [pop() for _ in range(k)]      # the first value is the one on top (pushed last)
                text = "%s(%s)" % (func_name(arg), ", ".join(args))
            last = {"id": len(recs), "text": text, "bad": bad[0], "used": 0}
            recs.append(last)
            out.append((i, last, False))
        elif op == 28:
            out.append((i, "if %s:" % pop(), bad[0]))
        elif op == 13:
            out.append((i, "goto " + jname.get(arg, "label%d" % arg), False))
        elif op == 7:
            out.append((i, "", False))
            out.append((i, "proc %s:" % procs.get(i, "?"), False))
            stack = []
            last = None
        elif op == 9:
            out.append((i, "end" + ("   ; stack not empty: " + " ".join(stack) if stack else ""), bool(stack)))
            stack = []
        else:
            out.append((i, "%s %d" % (OPS[op] if op < len(OPS) else "op%d" % op, arg), False))
    return finish(out, recs)


def finish(out, recs):
    """Put a call that is used once (through PUSHREG 0) inline where its result is used."""
    def res(t):
        bad = False
        while True:
            m = re.search("\x01(\\d+)\x02", t)
            if not m:
                return t, bad
            rec = recs[int(m.group(1))]
            if rec["used"] == 1:
                sub, b = res(rec["text"])
                bad = bad or b or rec["bad"]
            else:
                sub = "reg0"
            t = t[:m.start()] + sub + t[m.end():]
    final = []
    for i, t, flag in out:
        if isinstance(t, dict):
            if t["used"] == 1:
                continue
            text, b = res(t["text"])
            final.append((i, text, flag or t["bad"] or b))
        else:
            text, b = res(t)
            final.append((i, text, flag or b))
    return final


def listing(path, exe, limit):
    d = open(path, "rb").read()
    f = parse_flw(d)
    if not f or 2 not in f["sections"]:
        sys.exit("Not an FLW0 script")
    counts = arg_counts(exe)
    for k, (i, text, bad) in enumerate(statements(d, f, counts)):
        if k >= limit:
            print("... (stopped after %d statements; use -n for more)" % limit)
            break
        head = text.endswith(":") and not text.startswith("if")
        print(("      " if head or not text else "%5d   " % i) + text + ("   ; ? stack ran short" if bad else ""))


def export(root, exe, out, table=COMM_TABLE):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import p3fes_text as T
    if os.path.commonpath([root, out]) == root:
        sys.exit("Error: the output folder must not be inside the input folder.")
    counts = arg_counts(exe, table)
    msg_names = {func_name(k) for k in (0, 3, 38)}
    n = skipped = 0
    for p in files(root):
        d = open(p, "rb").read()
        f = parse_flw(d)
        if not f or 2 not in f["sections"] or f["sections"][2][0] != 4:
            skipped += 1
            continue
        texts = {}
        try:
            bmd = T.parse_bmd(T.message_bytes("x.bf", d))
            for k, m in enumerate(bmd["msgs"]):
                if m["kind"] == "dialog" and m["lines"]:
                    plain = re.sub(r"\{[^}]*\}", "", T.line_to_text(m["lines"][0], m["type"])).replace("\n", " ").strip()
                    texts[k] = plain[:80] or "(codes only)"
        except Exception:
            pass
        lines = []
        for i, text, flag in statements(d, f, counts):
            m = re.match(r"(\w+)\((\d+)", text)
            note = ""
            if m and m.group(1) in msg_names and int(m.group(2)) in texts:
                note = "   ; " + texts[int(m.group(2))]
            lines.append(("%5d   " % i if text and not (text.endswith(":") and not text.startswith("if")) else "      ") + text + note + ("   ; ? stack ran short" if flag else ""))
        rel = os.path.relpath(p, root)
        dest = os.path.join(out, rel + ".script.txt")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        n += 1
    print("Wrote %d listings to %s (%d files skipped)" % (n, out, skipped))
    print(names_report())
    print("Reminder: the comments hold the game's own text. Keep these files on your computer; never upload them.")


def context(root, exe, number, samples, around, table=COMM_TABLE):
    counts = arg_counts(exe, table)
    name = func_name(number)
    shown = 0
    seen = collections.Counter()
    for p in files(root):
        if shown >= samples:
            break
        d = open(p, "rb").read()
        f = parse_flw(d)
        if not f or 2 not in f["sections"] or f["sections"][2][0] != 4:
            continue
        st = statements(d, f, counts)
        hits = [k for k, (i, t, fl) in enumerate(st) if name + "(" in t]
        for k in hits[:1]:
            shape = re.sub(r"\d+", "#", st[k][1])
            if seen[shape] >= 2:      # prefer a variety of call shapes
                continue
            seen[shape] += 1
            print("=== %s (%d calls in this script)" % (os.path.basename(p), len(hits)))
            for j in range(max(0, k - around), min(len(st), k + around + 1)):
                t = st[j][1]
                print("%s %s" % (">>" if j == k else "  ", t))
            shown += 1
            if shown >= samples:
                break
    print("%d samples of %s" % (shown, name))


def balance(root, exe, report_path, table=COMM_TABLE):
    counts = arg_counts(exe, table)
    tot = bad = procs = clean = 0
    bad_by = collections.Counter()
    calls_by = collections.Counter()
    nonempty = collections.Counter()
    for p in files(root):
        d = open(p, "rb").read()
        f = parse_flw(d)
        if not f or 2 not in f["sections"] or f["sections"][2][0] != 4:
            continue
        for i, text, flag in statements(d, f, counts):
            tot += 1
            m = re.match(r"\w+_(\d+)\(", text)
            if m:
                calls_by[int(m.group(1))] += 1
            if text.startswith("end"):
                procs += 1
                if "stack not empty" in text:
                    nonempty[os.path.basename(p)] += 1
                else:
                    clean += 1
            if flag:
                bad += 1
                if m:
                    bad_by[int(m.group(1))] += 1
    L = ["Stack balance of %d statements with the value counts from the executable's table" % tot,
         "Statements that needed more values than were on the stack: %d" % bad,
         "Procedures that end with an empty stack: %d of %d" % (clean, procs),
         "Functions with the most short-stack calls (n: bad calls of all calls, table count):"]
    for n, c in bad_by.most_common(25):
        L.append("  %d: %d of %d, table says %s" % (n, c, calls_by[n], counts.get(n)))
    L.append("Scripts with procedures that end with something left on the stack: %d" % len(nonempty))
    open(report_path, "w").write("\n".join(L) + "\n")
    print("Wrote %s" % report_path)


def msgcheck(root, report_path):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import p3fes_text as T
    watch = [0, 1, 2, 3, 6, 28, 38, 40]
    seen = {n: collections.Counter() for n in watch}
    inside = {n: [0, 0] for n in watch}
    pre = {n: collections.Counter() for n in watch}
    nfiles = 0
    for p in files(root):
        d = open(p, "rb").read()
        f = parse_flw(d)
        if not f or 2 not in f["sections"] or f["sections"][2][0] != 4:
            continue
        try:
            n_msgs = len(T.parse_bmd(T.message_bytes("x.bf", d))["msgs"])
        except Exception:
            continue
        nfiles += 1
        ins = instructions(d, f["sections"][2])
        for k, (i, op, arg, val) in enumerate(ins):
            if op == 8 and arg in seen:
                prev = ins[k - 1] if k else None
                if prev and prev[1] == 29:
                    v = sgn16(prev[2])
                    seen[arg][v] += 1
                    inside[arg][0 if 0 <= v < n_msgs else 1] += 1
                    pre[arg]["PUSHIS directly before"] += 1
                else:
                    pre[arg]["something else before"] += 1
    L = ["Message-window functions against the script's own message count, over %d scripts with messages" % nfiles,
         "(value = the constant pushed just before the call; inside = 0 <= value < number of messages in that script)"]
    for n in watch:
        tot = sum(seen[n].values())
        L.append("COMM %d: %s; %d with a constant value; inside the message range %d, outside %d; most common values: %s" % (
            n, ", ".join("%s %d" % kv for kv in pre[n].most_common()), tot, inside[n][0], inside[n][1],
            ", ".join("%d x%d" % kv for kv in seen[n].most_common(8))))
    open(report_path, "w").write("\n".join(L) + "\n")
    print("Wrote %s" % report_path)


def disasm(path, limit=400):
    d = open(path, "rb").read()
    f = parse_flw(d)
    if not f:
        sys.exit("Not an FLW0 script")
    secs = f["sections"]
    print("%s: %d bytes, sections %s, variable count %d" % (os.path.basename(path), len(d),
          ", ".join("type %d: %d x %d at 0x%X" % (t, v[0], v[1], v[2]) for t, v in sorted(secs.items())), f["vars"]))
    names = {}
    for kind in (0, 1):
        if kind in secs:
            for name, at in labels(d, secs[kind]):
                names.setdefault(at, []).append(("proc " if kind == 0 else "label ") + name)
    if 2 not in secs:
        return
    for n, (i, op, arg, val) in enumerate(instructions(d, secs[2])):
        if n >= limit:
            print("... (stopped after %d instructions; use a smaller file or edit the limit)" % limit)
            break
        for lab in names.get(i, []):
            print(lab + ":")
        nm = OPS[op] if op < len(OPS) else "OP%d" % op
        extra = "" if val is None else (" %d (%g)" % (val, struct.unpack("<f", struct.pack("<I", val))[0]) if op == 1 else " %d" % val)
        print("  %5d  %-8s %d%s" % (i, nm, arg, extra))


def hexdump(path, start, count):
    d = open(path, "rb").read()
    print("%s: %d bytes" % (os.path.basename(path), len(d)))
    for o in range(start, min(len(d), start + count), 16):
        row = d[o:o + 16]
        ws = struct.unpack_from("<%dI" % (len(row) // 4), row, 0)
        print("%06X  %-47s  %-35s  %s" % (o, " ".join("%02X" % b for b in row), " ".join(fmt(w) for w in ws),
                                         "".join(chr(b) if 32 <= b < 127 else "." for b in row)))


def main():
    ap = argparse.ArgumentParser(description="Survey the .BF script files.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("survey")
    s.add_argument("folder")
    s.add_argument("-o", "--output", default="bf_survey.txt")
    an = sub.add_parser("analyse")
    an.add_argument("folder")
    an.add_argument("-o", "--output", default="bf_analysis.txt")
    ms = sub.add_parser("messages")
    ms.add_argument("folder")
    ms.add_argument("-o", "--output", default="bf_messages.txt")
    fn = sub.add_parser("functions")
    fn.add_argument("exe")
    fn.add_argument("-o", "--output", default="bf_functions.txt")
    pk = sub.add_parser("peek")
    pk.add_argument("exe")
    pk.add_argument("addr", help="address, e.g. 0x7B6A10")
    pk.add_argument("-s", "--stride", type=int, default=16, help="bytes per record (default 16)")
    pk.add_argument("-n", "--count", type=int, default=24)
    pk.add_argument("-b", "--before", type=int, default=2, help="records to show before the address")
    cd = sub.add_parser("code")
    cd.add_argument("exe")
    cd.add_argument("addr")
    cd.add_argument("-n", "--count", type=int, default=40)
    lm = sub.add_parser("limit")
    lm.add_argument("exe")
    lm.add_argument("values", nargs="+", type=int)
    lm.add_argument("--hits", type=int, default=12)
    lu = sub.add_parser("lui")
    lu.add_argument("exe")
    lu.add_argument("imm")
    sw = sub.add_parser("switch")
    sw.add_argument("exe")
    sw.add_argument("length", type=int)
    rf = sub.add_parser("ref")
    rf.add_argument("exe")
    rf.add_argument("addr")
    rf.add_argument("--hits", type=int, default=8)
    cm = sub.add_parser("comm")
    cm.add_argument("exe")
    cm.add_argument("folder")
    cm.add_argument("-o", "--output", default="bf_comm.txt")
    cm.add_argument("--table", default=hex(COMM_TABLE))
    cm.add_argument("--count", type=int, default=COMM_COUNT)
    ex = sub.add_parser("export")
    ex.add_argument("folder")
    ex.add_argument("--exe", required=True)
    ex.add_argument("-o", "--out", default="scripts_txt")
    ex.add_argument("--table", default=hex(COMM_TABLE))
    ex.add_argument("--names", help="a names file (default: script_names.txt next to this tool)")
    cx = sub.add_parser("context")
    cx.add_argument("folder")
    cx.add_argument("--exe", required=True)
    cx.add_argument("number", type=int)
    cx.add_argument("-n", "--samples", type=int, default=8)
    cx.add_argument("-c", "--around", type=int, default=4, help="statements to show before and after")
    cx.add_argument("--table", default=hex(COMM_TABLE))
    bl = sub.add_parser("balance")
    bl.add_argument("folder")
    bl.add_argument("--exe", required=True)
    bl.add_argument("-o", "--output", default="bf_balance.txt")
    bl.add_argument("--table", default=hex(COMM_TABLE))
    mc = sub.add_parser("msgcheck")
    mc.add_argument("folder")
    mc.add_argument("-o", "--output", default="bf_msgcheck.txt")
    ls = sub.add_parser("listing")
    ls.add_argument("file")
    ls.add_argument("--exe", help="the boot executable (SLUS_216.21), to know how many values each function takes")
    ls.add_argument("-n", "--count", type=int, default=300)
    ls.add_argument("--names", help="a names file (default: script_names.txt next to this tool)")
    ds = sub.add_parser("disasm")
    ds.add_argument("file")
    ds.add_argument("-n", "--count", type=int, default=400)
    h = sub.add_parser("hex")
    h.add_argument("file")
    h.add_argument("-s", "--start", type=int, default=0)
    h.add_argument("-n", "--count", type=int, default=256)
    a = ap.parse_args()
    if a.cmd == "survey":
        survey(os.path.abspath(a.folder), a.output)
    elif a.cmd == "analyse":
        analyse(os.path.abspath(a.folder), a.output)
    elif a.cmd == "messages":
        messages(os.path.abspath(a.folder), a.output)
    elif a.cmd == "functions":
        functions(a.exe, a.output)
    elif a.cmd == "peek":
        peek(a.exe, int(a.addr, 0), a.stride, a.count, a.before)
    elif a.cmd == "code":
        d = open(a.exe, "rb").read()
        code_dump(d, elf_segments(d), int(a.addr, 0), a.count)
    elif a.cmd == "limit":
        find_limit(a.exe, a.values, maxhits=a.hits)
    elif a.cmd == "lui":
        find_lui(a.exe, int(a.imm, 0))
    elif a.cmd == "switch":
        find_switch(a.exe, a.length)
    elif a.cmd == "ref":
        find_refs(a.exe, int(a.addr, 0), maxhits=a.hits)
    elif a.cmd == "comm":
        comm(a.exe, os.path.abspath(a.folder), a.output, int(a.table, 0), a.count)
    elif a.cmd == "export":
        if a.names:
            load_names(a.names)
        export(os.path.abspath(a.folder), a.exe, os.path.abspath(a.out), int(a.table, 0))
    elif a.cmd == "context":
        context(os.path.abspath(a.folder), a.exe, a.number, a.samples, a.around, int(a.table, 0))
    elif a.cmd == "balance":
        balance(os.path.abspath(a.folder), a.exe, a.output, int(a.table, 0))
    elif a.cmd == "msgcheck":
        msgcheck(os.path.abspath(a.folder), a.output)
    elif a.cmd == "listing":
        if a.names:
            load_names(a.names)
        listing(a.file, a.exe, a.count)
    elif a.cmd == "disasm":
        disasm(a.file, a.count)
    else:
        hexdump(a.file, a.start, a.count)


if __name__ == "__main__":
    main()
