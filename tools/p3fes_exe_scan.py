#!/usr/bin/env python3
"""
p3fes_exe_scan.py - Phase 0 executable scan for the Persona 3 FES native port.

Reads the game's main executable (the boot ELF) from your own disc image and
reports what it can learn WITHOUT disassembling or copying any game code:

  * the ELF's sections (names, addresses, sizes)
  * the symbol table, if the executable still has one (function names
    grouped by prefix, which shows which libraries the game was built with)
  * which known middleware libraries the executable contains (Sony PS2 SDK,
    CRI audio/video/file libraries, RenderWare, and so on), with version strings
  * file names and paths the executable mentions (archive names, device names
    such as cdrom0:, format strings that build paths)
  * hints about overlays or runtime module loading

It only READS your image. The reports contain names, addresses and short
identifying strings only. Game text and code are not dumped.

Usage (from a Command Prompt in the folder that holds this script):
    py p3fes_exe_scan.py "C:\\path\\to\\game.iso"
    py p3fes_exe_scan.py "C:\\path\\to\\game.iso" --symbols

You can also point it at an already-extracted executable file instead of an
.iso. --symbols additionally writes a CSV of every symbol name (only useful if
the executable has a symbol table). Reports are written next to this script.
Standard library only, Python 3.8+.
"""

import argparse
import collections
import csv
import json
import os
import re
import struct
import sys
import time

SECTOR = 2048
MIN_STRING = 5
CAT_LIMIT = 300          # entries per category kept in the JSON report
PRINT_LIMIT = 25         # entries per category shown on screen

SECTION_TYPES = {0: "NULL", 1: "PROGBITS", 2: "SYMTAB", 3: "STRTAB", 4: "RELA",
                 5: "HASH", 6: "DYNAMIC", 7: "NOTE", 8: "NOBITS", 9: "REL",
                 0x70000000: "MIPS_REGINFO", 0x70000003: "MIPS_OPTIONS",
                 0x7000000D: "MIPS_DEBUG"}

# (regex applied to symbol names and strings, library it indicates)
LIB_MARKERS = [
    (r"\bsceCd[A-Z]", "Sony libcdvd (disc access)"),
    (r"\bsceSif[A-Z]", "Sony libsif (EE to IOP communication)"),
    (r"\bsceGs[A-Z]", "Sony libgraph (graphics synthesizer setup)"),
    (r"\bsceVu0[A-Z]", "Sony libvu0 (vector math)"),
    (r"\bsceDma[A-Z]", "Sony libdma (DMA transfers)"),
    (r"\bsceMc[A-Z]|\bsceMc[0-9]", "Sony libmc (memory card)"),
    (r"\bscePad[A-Z]", "Sony libpad (controllers)"),
    (r"\bsceSd[A-Z]", "Sony libsd (sound hardware)"),
    (r"\bsceMpeg[A-Z]", "Sony libmpeg (video decoding)"),
    (r"\bsceIpu[A-Z]", "Sony IPU (video decoding hardware)"),
    (r"\bsceDeci[A-Z]", "Sony DECI (debug link)"),
    (r"\bsceDev[A-Z]", "Sony libdev (device access)"),
    (r"\bsceGif[A-Z]", "Sony GIF packet helpers"),
    (r"\bADXT_|\bADXF_|\bADXCRS_|\bADX_[A-Za-z]", "CRI ADX (audio)"),
    (r"\bSFD_[A-Za-z]|\bSFLIB|\bSFTIM|Sofdec", "CRI Sofdec (video)"),
    (r"\bcvFs|\bCVFS|\bCVM[A-Za-z]|\bROFS", "CRI CVM / ROFS (file system)"),
    (r"\bcri[A-Z][A-Za-z]+_|\bCRI[A-Z_]", "CRI middleware (general)"),
    (r"\bAFS_?[A-Za-z]|\.afs\b", "CRI AFS (archive access)"),
    (r"\bRw[A-Z][a-z]|\bRp[A-Z][a-z]|\bRt[A-Z][a-z]|\brwPS2|RenderWare",
     "RenderWare (graphics engine)"),
    (r"\bsdMidi|\bsceMidi|\bsceHSyn|\bsceSESq", "Sony MIDI / sound sequencing"),
    (r"\bmwPly|\bMWSFD|\bMWRNA", "CRI Movie Wing (video player layer)"),
]
LIB_MARKERS = [(re.compile(p), name) for p, name in LIB_MARKERS]

PATH_EXT = re.compile(
    r"(?i)\.(?:cvm|bin|pac|pak|sfd|adx|irx|img|tmx|rmd|afs|cpk|fpc|tbl|bf|bd|hd|sq|"
    r"elf|ini|dat|bmd|bed|anm|epl|spr|fnt|se|map|seq|pm1|pm2|pm3|bvp|cin|txt|bat)\b")
DEVICE = re.compile(r"(?i)\b(cdrom0?|host0?|mc[01]|rom0|pfs0|hdd0|mass|sc?hd)\s*:")
CONTAINER_EXT = re.compile(r"(?i)\.(?:cvm|afs|irx|img|elf)\b")
API_NAME = re.compile(
    r"\b(?:cvFs[A-Za-z0-9_]*|CVFS_[A-Za-z0-9_]+|ROFS_[A-Za-z0-9_]+|rofs_[a-z0-9_]+|"
    r"ADX[A-Z]*_[A-Za-z0-9_]+|SFD_[A-Za-z0-9_]+|SFLIB_[A-Za-z0-9_]+|MWSFD_[A-Za-z0-9_]+|"
    r"mwPly[A-Za-z0-9_]+|sce(?:Cd|Sif|Gs|Gif|Dma|Mpeg|Ipu|Sd|Pad|Mc2?|Vu0|Dev)[A-Za-z0-9_]*|"
    r"PS2RNA_[A-Za-z0-9_]+|SJ[A-Z]*_[A-Za-z0-9_]+|SVM_[A-Za-z0-9_]+)\b")
SOURCE_PATH = re.compile(r"(?i)[\\/].*\.(?:c|cc|cpp|h|s)$")
LIB_STRING = re.compile(
    r"(?i)\bver(?:sion)?\.?\s*\d|\bbuild\b.*\d{4}|copyright|\(c\)|\bsce\b|\bcri\b|"
    r"sofdec|middleware|library|\bsdk\b")
OVERLAY_HINT = re.compile(r"(?i)overlay|\bovl\b|\.ovl\b|relocat|dll|dynamic link")
STRING_RE = re.compile(rb"[\x20-\x7e]{%d,}" % MIN_STRING)


class ToolError(Exception):
    pass


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0


# ---------------------------------------------------------------- disc access
class Window:
    def __init__(self, f, base, size):
        self.f, self.base, self.size = f, base, size

    def read_at(self, pos, n):
        if pos < 0 or pos >= self.size:
            return b""
        n = min(n, self.size - pos)
        self.f.seek(self.base + pos)
        return self.f.read(n)


def parse_dir(win, lba, size, path, visited, out):
    if (lba, size) in visited or size <= 0 or size > 64 * 1024 * 1024:
        return
    visited.add((lba, size))
    data = win.read_at(lba * SECTOR, size)
    pos = 0
    while pos < len(data):
        n = data[pos]
        if n == 0:
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        if n < 34 or pos + n > len(data):
            break
        rec = data[pos:pos + n]
        extent = struct.unpack_from("<I", rec, 2)[0]
        length = struct.unpack_from("<I", rec, 10)[0]
        flags, name_len = rec[25], rec[32]
        name = rec[33:33 + name_len]
        pos += n
        if name in (b"\x00", b"\x01"):
            continue
        name = name.decode("ascii", "replace").split(";")[0]
        full = path + "/" + name
        if flags & 0x02:
            parse_dir(win, extent, length, full, visited, out)
        else:
            out.append({"path": full, "lba": extent, "size": length})


def list_files(win):
    pvd = win.read_at(16 * SECTOR, SECTOR)
    if len(pvd) < 190 or pvd[1:6] != b"CD001":
        raise ToolError("This does not look like a plain 2048-byte-sector .iso "
                        "(no ISO9660 marker). Run p3fes_inspect.py first to check it.")
    root_extent = struct.unpack_from("<I", pvd, 158)[0]
    root_size = struct.unpack_from("<I", pvd, 166)[0]
    out = []
    parse_dir(win, root_extent, root_size, "", set(), out)
    return out


def read_boot_elf(f, size):
    win = Window(f, 0, size)
    files = list_files(win)
    cnf = next((e for e in files if e["path"].upper() == "/SYSTEM.CNF"), None)
    if not cnf:
        raise ToolError("SYSTEM.CNF not found on the disc.")
    text = win.read_at(cnf["lba"] * SECTOR, cnf["size"]).decode("ascii", "replace")
    boot = None
    for line in text.replace("\r", "\n").split("\n"):
        if "=" in line and line.split("=", 1)[0].strip().upper() == "BOOT2":
            boot = line.split("=", 1)[1].strip()
    if not boot:
        raise ToolError("No BOOT2 line in SYSTEM.CNF.")
    exe = boot.replace("/", "\\").split("\\")[-1].split(";")[0].strip()
    e = next((x for x in files if x["path"].upper().split("/")[-1] == exe.upper()), None)
    if not e:
        raise ToolError(f"Boot file {exe} not found on the disc.")
    return exe, win.read_at(e["lba"] * SECTOR, e["size"])


# ------------------------------------------------------------------ ELF parse
def cstr(data, off, limit=200):
    if off < 0 or off >= len(data):
        return ""
    end = data.find(b"\x00", off, off + limit)
    if end < 0:
        end = min(len(data), off + limit)
    return data[off:end].decode("ascii", "replace")


def parse_elf(data):
    if data[:4] != b"\x7fELF":
        raise ToolError("The executable is not an ELF file (bad magic).")
    if data[4] != 1 or data[5] != 1:
        raise ToolError("Expected a 32-bit little-endian ELF (PS2 EE executable).")
    (e_type, e_machine, _v, e_entry, e_phoff, e_shoff, e_flags, _eh,
     e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx) = struct.unpack_from(
        "<HHIIIIIHHHHHH", data, 16)
    segs = []
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        if o + 32 > len(data):
            break
        p_type, p_off, p_vaddr, _pa, p_filesz, p_memsz, p_flags, _al = \
            struct.unpack_from("<8I", data, o)
        segs.append({"type": p_type, "offset": p_off, "vaddr": p_vaddr,
                     "filesz": p_filesz, "memsz": p_memsz, "flags": p_flags})
    secs = []
    if e_shoff and e_shnum and e_shentsize >= 40:
        for i in range(e_shnum):
            o = e_shoff + i * e_shentsize
            if o + 40 > len(data):
                break
            (n, t, fl, addr, off, sz, link, info, _al, ent) = struct.unpack_from("<10I", data, o)
            secs.append({"name_off": n, "type": t, "flags": fl, "addr": addr,
                         "offset": off, "size": sz, "link": link, "entsize": ent})
        if 0 <= e_shstrndx < len(secs):
            base = secs[e_shstrndx]["offset"]
            for s in secs:
                s["name"] = cstr(data, base + s["name_off"], 64)
        for s in secs:
            s.setdefault("name", "")
    return {"entry": e_entry, "machine": e_machine, "segments": segs, "sections": secs}


def vaddr_of(segs, off):
    for s in segs:
        if s["type"] == 1 and s["offset"] <= off < s["offset"] + s["filesz"]:
            return s["vaddr"] + (off - s["offset"])
    return None


def read_symbols(data, secs):
    sym = next((s for s in secs if s["type"] == 2), None)
    if not sym or sym["link"] >= len(secs):
        return None
    strtab = secs[sym["link"]]
    out = []
    n = min(sym["size"] // 16, 500000)
    for i in range(n):
        o = sym["offset"] + i * 16
        if o + 16 > len(data):
            break
        st_name, st_value, st_size, st_info, _other, _shndx = struct.unpack_from("<IIIBBH", data, o)
        name = cstr(data, strtab["offset"] + st_name, 160)
        if name:
            out.append({"name": name, "value": st_value, "size": st_size,
                        "type": {0: "NOTYPE", 1: "OBJECT", 2: "FUNC", 3: "SECTION",
                                 4: "FILE"}.get(st_info & 0xF, str(st_info & 0xF))})
    return out


def symbol_prefix(name):
    if "_" in name.strip("_"):
        p = name.strip("_").split("_")[0]
        if 1 < len(p) <= 16:
            return p
    m = re.match(r"^[a-z]+[A-Z][a-z0-9]+", name)
    if m:
        return m.group(0)
    m = re.match(r"^[A-Za-z]+", name)
    return m.group(0)[:16] if m else "(other)"


# ----------------------------------------------------------------- the report
def scan(data):
    elf = parse_elf(data)
    segs = elf["segments"]
    report = {"size": len(data), "entry": f"0x{elf['entry']:08X}"}

    report["sections"] = [
        {"name": s["name"], "type": SECTION_TYPES.get(s["type"], f"0x{s['type']:X}"),
         "address": f"0x{s['addr']:08X}", "file_offset": f"0x{s['offset']:X}",
         "size": s["size"]} for s in elf["sections"] if s["type"] != 0]

    syms = read_symbols(data, elf["sections"])
    texts = []   # (text, offset or None) for library detection
    if syms is None:
        report["symbols"] = {"present": False}
    else:
        pref = collections.defaultdict(list)
        for s in syms:
            pref[symbol_prefix(s["name"])].append(s["name"])
        top = sorted(pref.items(), key=lambda kv: -len(kv[1]))[:80]
        report["symbols"] = {
            "present": True, "count": len(syms),
            "functions": sum(1 for s in syms if s["type"] == "FUNC"),
            "top_prefixes": [{"prefix": p, "count": len(v), "examples": v[:3]} for p, v in top]}
        texts.extend((s["name"], None) for s in syms)

    cats = {"device_paths": [], "container_names": [], "path_formats": [],
            "source_paths": [], "library_strings": [], "overlay_hints": []}
    patterns = {}
    api_names = collections.Counter()
    seen = set()
    total = 0
    for m in STRING_RE.finditer(data):
        total += 1
        s = m.group(0).decode("ascii")[:200]
        if s in seen:
            continue
        seen.add(s)
        texts.append((s, m.start()))
        for a in API_NAME.findall(s):
            api_names[a] += 1
        cat = None
        if " " not in s:
            if SOURCE_PATH.search(s) and len(s) <= 160:
                cat = "source_paths"
            elif "%" in s and ("/" in s or "\\" in s or PATH_EXT.search(s)):
                cat = "path_formats"
            elif DEVICE.search(s):
                cat = "device_paths"
            elif CONTAINER_EXT.search(s):
                cat = "container_names"
            elif PATH_EXT.search(s):
                key = re.sub(r"[0-9]+", "#", s)
                d = patterns.setdefault(key, {"count": 0, "examples": []})
                d["count"] += 1
                if len(d["examples"]) < 3:
                    d["examples"].append(s)
        if cat is None and len(s) <= 140 and LIB_STRING.search(s):
            cat = "library_strings"
        if cat is None and len(s) <= 100 and OVERLAY_HINT.search(s):
            cat = "overlay_hints"
        if cat:
            va = vaddr_of(segs, m.start())
            cats[cat].append({"text": s, "file_offset": f"0x{m.start():X}",
                              "address": f"0x{va:08X}" if va is not None else None})
    report["string_count"] = total
    report["strings"] = {k: v[:CAT_LIMIT] for k, v in cats.items()}
    report["string_totals"] = {k: len(v) for k, v in cats.items()}
    report["file_name_total"] = sum(v["count"] for v in patterns.values())
    report["file_name_patterns"] = [
        {"pattern": k, "count": v["count"], "examples": v["examples"]}
        for k, v in sorted(patterns.items(), key=lambda kv: -kv[1]["count"])[:150]]
    report["api_names"] = [{"name": n, "mentions": c} for n, c in sorted(api_names.items())[:600]]

    libs = {}
    for text, off in texts:
        for rx, name in LIB_MARKERS:
            if rx.search(text):
                d = libs.setdefault(name, {"hits": 0, "examples": []})
                d["hits"] += 1
                if len(d["examples"]) < 5 and text not in d["examples"]:
                    d["examples"].append(text[:80])
    report["libraries_detected"] = dict(sorted(libs.items(), key=lambda kv: -kv[1]["hits"]))
    return report, syms


def print_report(r, name):
    print("=" * 70)
    print(f"Executable: {name}  ({human(r['size'])}), entry point {r['entry']}")
    print("Sections:")
    if not r["sections"]:
        print("  (none)")
    for s in r["sections"]:
        print(f"  {s['name'] or '(unnamed)':<14} {s['type']:<14} addr {s['address']}  "
              f"size {s['size']:>9}")
    sy = r["symbols"]
    print("-" * 70)
    if sy["present"]:
        print(f"Symbol table: {sy['count']} symbols ({sy['functions']} functions). "
              "Most common name prefixes:")
        for p in sy["top_prefixes"][:25]:
            print(f"  {p['prefix']:<18} {p['count']:>6}   e.g. {', '.join(p['examples'])}")
    else:
        print("Symbol table: none (the executable is stripped).")
    print("-" * 70)
    print("Libraries detected (from symbol names and strings):")
    if not r["libraries_detected"]:
        print("  none matched")
    for name_, d in r["libraries_detected"].items():
        print(f"  {name_:<44} {d['hits']:>5} hits   e.g. {d['examples'][0]}")
    for cat, label in (("library_strings", "Version and copyright strings"),
                       ("device_paths", "Device paths (cdrom0:, host:, mc0: ...)"),
                       ("container_names", "Archive and module names (.CVM, .AFS, .IRX ...)"),
                       ("path_formats", "Path-building format strings"),
                       ("source_paths", "Library source paths"),
                       ("overlay_hints", "Overlay and module-loading hints")):
        items = r["strings"][cat]
        print("-" * 70)
        print(f"{label}: {r['string_totals'][cat]} found" +
              (f" (showing {min(PRINT_LIMIT, len(items))})" if items else ""))
        for it in items[:PRINT_LIMIT]:
            print(f"  {it['address'] or it['file_offset']:<12} {it['text'][:90]}")
    print("-" * 70)
    pats = r["file_name_patterns"]
    print(f"Other file names: {r['file_name_total']} names in {len(pats)} patterns "
          "(numbers shown as #)")
    for p in pats[:PRINT_LIMIT]:
        print(f"  {p['count']:>6}  {p['pattern'][:44]:<44} e.g. {p['examples'][0][:30]}")
    print("-" * 70)
    names = [a["name"] for a in r["api_names"]]
    print(f"Library function names mentioned in strings: {len(names)}")
    for i in range(0, min(len(names), 48), 3):
        print("  " + ", ".join(names[i:i + 3]))
    print("=" * 70)


def main():
    ap = argparse.ArgumentParser(description="Scan the main executable of a PS2 disc image you own.")
    ap.add_argument("source", help="path to your .iso dump, or to an extracted executable")
    ap.add_argument("--symbols", action="store_true",
                    help="also write a CSV of every symbol name (if the executable has any)")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    stem = os.path.splitext(os.path.basename(args.source))[0]
    t0 = time.time()
    try:
        with open(args.source, "rb") as f:
            magic = f.read(4)
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(0)
            if magic == b"\x7fELF":
                name, data = os.path.basename(args.source), f.read()
            else:
                name, data = read_boot_elf(f, size)
        report, syms = scan(data)
    except ToolError as e:
        sys.exit(f"Error: {e}")
    except FileNotFoundError as e:
        sys.exit(f"Error: file not found: {e.filename}")

    print_report(report, name)
    report["image"] = os.path.basename(args.source)
    report["executable"] = name
    out = os.path.join(here, stem + ".exe.report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    if args.symbols and syms:
        cp = os.path.join(here, stem + ".exe.symbols.csv")
        with open(cp, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["name", "address", "size", "type"])
            for s in sorted(syms, key=lambda s: s["value"]):
                w.writerow([s["name"], f"0x{s['value']:08X}", s["size"], s["type"]])
        print(f"Symbols written to: {cp}")
    elif args.symbols:
        print("No symbol table in this executable, so no symbols file was written.")
    print(f"Report written to: {out}  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
