#!/usr/bin/env python3
"""
p3fes_models.py - survey of the game's 3D model files (.RMD) for the Persona 3 FES native port.

This is a research survey; to convert models use p3fes_rmd.py. It reads
every .RMD file in the folder that p3fes_unpack.py produced and reports:

  * how many models there are, and their size range
  * the different file headers (first 16 bytes) and how many files share each one
  * whether a RenderWare-style chunk list (type, size, version) can be found inside, and
    if so which chunk types and version stamps occur
  * the text strings that appear near the start of the files (bone, mesh and texture names)
  * the 32-bit numbers at the start, which usually hold counts and offsets

Usage:
    py p3fes_models.py C:\\p3fes\\extracted                  survey every .RMD under the folder
    py p3fes_models.py C:\\p3fes\\extracted --hex PATH      dump one model's first 512 bytes, with strings
    py p3fes_models.py C:\\p3fes\\extracted --ext rmd,pmd   other extensions too

Writes models.report.json and models.summary.txt into the current folder. They hold file
names, sizes and at most 32 bytes of each header, never the game's content.
"""

import argparse
import collections
import json
import os
import re
import struct
import sys

# RenderWare chunk types that contain other chunks.
RW_CONTAINERS = {0x10: "Clump", 0x0E: "FrameList", 0x1A: "GeometryList", 0x0F: "Geometry",
                 0x08: "MaterialList", 0x07: "Material", 0x06: "Texture", 0x14: "Atomic",
                 0x03: "Extension", 0x16: "TexDictionary", 0x15: "TextureNative",
                 0x09: "AtomicSection", 0x0A: "PlaneSection", 0x0B: "World"}
RW_NAMES = dict(RW_CONTAINERS)
RW_NAMES.update({0x01: "Struct", 0x02: "String", 0x1B: "AnimAnimation", 0x1F: "RightToRender",
                 0x116: "Skin", 0x11E: "HAnim", 0x11F: "UserData", 0x120: "MaterialEffects",
                 0x50E: "BinMesh", 0x510: "NativeData", 0x105: "Morph", 0x11D: "Collision",
                 0xF0F000F0: "AtlusPrefix", 0xF0F00003: "Atlus3", 0xF0F00004: "Atlus4",
                 0xF0F00005: "Atlus5", 0xF0F00006: "Atlus6", 0xF0F00080: "Atlus80"})
ATLUS_VERSION = 0x40000000
STRING_RE = re.compile(rb"[A-Za-z0-9_\.\-\[\] ]{4,}")


def plausible_version(v):
    if v == ATLUS_VERSION:
        return True
    """RenderWare version stamps look like 0x0C02FFFF, 0x1C020065 or 0x3F0xxxxx."""
    return (v & 0xFFFF0000) in (0x0C020000, 0x1C020000, 0x1C030000, 0x0C030000, 0x1C0A0000,
                                0x1C0B0000, 0x1C0C0000) or (v >> 16) in (0x0800, 0x0C02, 0x1400, 0x1803, 0x1C02, 0x1C03, 0x1000) or \
        ((v >> 30) in (0, 1) and (v >> 16) & 0x3F < 0x3F and (v & 0xFFFF) < 0x1000 and (v >> 16) >= 0x0800)


def walk_rw(data, pos, end, depth, stats, limit=100000):
    """Walk a RenderWare chunk list. Returns (chunks read, position after the last good chunk).
    Plugin chunks with unknown types are counted but not entered."""
    n = 0
    while pos + 12 <= end and n < limit:
        ctype, size, ver = struct.unpack_from("<III", data, pos)
        if size > end - pos - 12 or ctype == 0 or not plausible_version(ver):
            break
        stats["types"][ctype] += 1
        stats["versions"]["%08X" % ver] += 1
        stats["depth"] = max(stats["depth"], depth)
        n += 1
        if ctype in RW_CONTAINERS:
            sub, _ = walk_rw(data, pos + 12, pos + 12 + size, depth + 1, stats, limit - n)
            n += sub
        pos += 12 + size
    return n, pos


def after_game_chunks(data):
    """Offset just after the run of game-specific chunks (F0F0xxxx, version 0x40000000) at the start,
    allowing up to 15 padding bytes between them. Same rule as p3fes_rmd.skip_atlus_chunks."""
    def chunk_at(o):
        if o + 12 > len(data):
            return None
        t, size, ver = struct.unpack_from("<III", data, o)
        return size if (t >> 16) == 0xF0F0 and ver == 0x40000000 and size <= len(data) - o - 12 else None
    off = 0
    while True:
        size = chunk_at(off)
        for pad in range(1, 16):
            if size is not None:
                break
            size = chunk_at(off + pad)
            if size is not None:
                off += pad
        if size is None:
            return off
        off += 12 + size


def find_rw(data):
    """Look for a valid RenderWare chunk list at any byte offset up to 0x40, or within 16 bytes after
    the game-specific chunks. Returns (offset, chunks, stats, top-level types, end position)."""
    best = None
    after = after_game_chunks(data)
    offsets = list(range(0, min(0x40, len(data) - 12) + 1))
    offsets += [o for o in range(after, after + 17) if o not in offsets and o + 12 <= len(data)]
    for off in offsets:
        ctype, size, ver = struct.unpack_from("<III", data, off)
        if ctype in RW_NAMES and size <= len(data) - off - 12 and plausible_version(ver):
            stats = {"types": collections.Counter(), "versions": collections.Counter(), "depth": 0}
            n, end = walk_rw(data, off, len(data), 0, stats)
            if n >= 3 and (best is None or n > best[1]):
                top, p = [], off
                while p + 12 <= end:
                    t, sz, _ = struct.unpack_from("<III", data, p)
                    top.append(t)
                    p += 12 + sz
                best = (off, n, stats, top, end)
    return best


def print_tree(data, pos, end, depth, max_depth, lines, budget):
    """List chunks with offset, name, size and version. Atlus chunks and plugin data show
    their first bytes."""
    while pos + 12 <= end and budget[0] > 0:
        ctype, size, ver = struct.unpack_from("<III", data, pos)
        if size > end - pos - 12 or ctype == 0 or not plausible_version(ver):
            lines.append("%s@%X: stops here (next 16 bytes: %s)" % ("  " * depth, pos, data[pos:pos + 16].hex(" ")))
            return pos
        name = RW_NAMES.get(ctype, "?")
        line = "%s@%X %s (%X) size %d%s" % ("  " * depth, pos, name, ctype, size,
                                           "" if ver in (0x1C020037, ATLUS_VERSION) else " ver %08X" % ver)
        leaf_dump = (ctype >= 0xF0F00000 or ctype in (0x510, 0x50E, 0x11E, 0x11F, 0x1B, 0x116)) and size
        if leaf_dump:
            line += "  data: " + data[pos + 12:pos + 12 + min(size, 24)].hex(" ") + (" ..." if size > 24 else "")
        lines.append(line)
        budget[0] -= 1
        if ctype in RW_CONTAINERS and depth < max_depth:
            print_tree(data, pos + 12, pos + 12 + size, depth + 1, max_depth, lines, budget)
        pos += 12 + size
    return pos


def u32s(data, count=16):
    count = min(count, len(data) // 4)
    return struct.unpack_from("<%dI" % count, data, 0) if count else ()


def strings_in(data, limit=4096, minlen=4, maxn=12):
    out = []
    for m in STRING_RE.finditer(data[:limit]):
        s = m.group(0).decode("ascii", "replace").strip()
        if len(s) >= minlen and s not in out:
            out.append(s)
        if len(out) >= maxn:
            break
    return out


def hex_dump(data, n=512):
    lines = []
    for i in range(0, min(n, len(data)), 16):
        chunk = data[i:i + 16]
        lines.append("%06X  %-47s  %s" % (i, " ".join("%02X" % b for b in chunk),
                                          "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)))
    return "\n".join(lines)


def find_models(root, exts):
    found = []
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if os.path.splitext(fn)[1].lower().lstrip(".") in exts:
                found.append(os.path.join(dp, fn))
    return sorted(found)


def survey(root, exts, out_dir):
    files = find_models(root, exts)
    if not files:
        sys.exit("No model files (%s) found under %s. Run p3fes_unpack.py first." % (",".join(sorted(exts)), root))
    headers = collections.Counter()
    sizes = []
    rw_found = 0
    rw_types, rw_versions = collections.Counter(), collections.Counter()
    rw_offsets = collections.Counter()
    str_counts = collections.Counter()
    first_words = collections.defaultdict(collections.Counter)   # position -> value -> count
    layouts, tails, tail_example = collections.Counter(), collections.Counter(), {}
    prefix_sizes = collections.Counter()
    no_stream = []
    examples = {}
    empty = 0
    groups = collections.defaultdict(lambda: [0, 0, 0])      # folder -> [files, with RenderWare data, bytes]
    for i, path in enumerate(files, 1):
        if i % 500 == 0:
            print("  ... %d of %d" % (i, len(files)), flush=True)
        with open(path, "rb") as fh:
            data = fh.read()
        if not data:
            empty += 1
            continue
        sizes.append(len(data))
        grp = "\\".join(os.path.relpath(path, root).split(os.sep)[:-1][:3]) or "."
        groups[grp][0] += 1
        groups[grp][2] += len(data)
        h = data[:16].hex(" ")
        headers[h] += 1
        examples.setdefault(h, os.path.relpath(path, root))
        for k, v in enumerate(u32s(data, 8)):
            first_words[k][v] += 1
        r = find_rw(data)
        if not r and len(no_stream) < 6:
            no_stream.append((os.path.relpath(path, root), len(data), data[:48].hex(" ")))
        if r:
            rw_found += 1
            groups[grp][1] += 1
            off, n, st, top, end = r
            rw_offsets[off] += 1
            layouts[" ".join("%02X" % t if t < 0x100 else "%X" % t for t in top[:8]) + (" ..." if len(top) > 8 else "")] += 1
            tail = len(data) - end
            tkey = "none" if tail == 0 else "under 16 bytes" if tail < 16 else "16 to 4095 bytes" if tail < 4096 else "4 KB or more"
            tails[tkey] += 1
            tail_example.setdefault(tkey, os.path.relpath(path, root))
            if off:
                prefix_sizes[off] += 1
            rw_types.update(st["types"])
            rw_versions.update(st["versions"])
        for s in strings_in(data):
            str_counts[s] += 1
    sizes.sort()
    report = {
        "files": len(files), "empty": empty,
        "size_min": sizes[0] if sizes else 0, "size_median": sizes[len(sizes) // 2] if sizes else 0,
        "size_max": sizes[-1] if sizes else 0, "total_bytes": sum(sizes),
        "distinct_headers": len(headers),
        "top_headers": [{"header": h, "files": c, "example": examples[h]} for h, c in headers.most_common(25)],
        "renderware_chunk_lists_found": rw_found,
        "renderware_start_offsets": dict(rw_offsets),
        "renderware_types": {"%02X %s" % (t, RW_NAMES.get(t, "?")): c for t, c in rw_types.most_common()},
        "renderware_versions": dict(rw_versions.most_common(10)),
        "no_stream_examples": no_stream,
        "top_level_layouts": layouts.most_common(15),
        "bytes_after_stream": dict(tails), "bytes_after_stream_examples": tail_example,
        "folders": {k: {"files": v[0], "with_renderware_data": v[1], "bytes": v[2]} for k, v in sorted(groups.items())},
        "common_strings": str_counts.most_common(40),
        "first_words": {str(k): [("%08X" % v, c) for v, c in cnt.most_common(6)] + [("distinct", len(cnt))]
                        for k, cnt in sorted(first_words.items())},
    }
    with open(os.path.join(out_dir, "models.report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    lines = ["Model files: %d (%d empty), %.1f MB in total" % (len(files), empty, report["total_bytes"] / 1048576),
             "Sizes: smallest %d, median %d, largest %d bytes" % (report["size_min"], report["size_median"], report["size_max"]),
             "Distinct 16-byte headers: %d" % len(headers)]
    for h, c in headers.most_common(8):
        lines.append("   %5d files  %s   e.g. %s" % (c, h, examples[h]))
    lines.append("RenderWare-style chunk lists found in %d of %d files" % (rw_found, len(files) - empty))
    if rw_found:
        lines.append("   start offsets: " + ", ".join("0x%X x%d" % kv for kv in sorted(rw_offsets.items())))
        lines.append("   chunk types: " + ", ".join("%s x%d" % kv for kv in list(report["renderware_types"].items())[:12]))
        lines.append("   versions: " + ", ".join("%s x%d" % kv for kv in rw_versions.most_common(4)))
    if rw_found:
        lines.append("   top-level chunk order: " + "; ".join("%s x%d" % kv for kv in layouts.most_common(6)))
        lines.append("   bytes left after the RenderWare stream: " + ", ".join("%s x%d" % kv for kv in tails.most_common()))
        for k, ex in tail_example.items():
            if k != "none":
                lines.append("      e.g. %s: %s" % (k, ex))
    lines.append("Files per folder (files / with RenderWare data / MB):")
    for k, v in sorted(groups.items()):
        lines.append("   %-40s %5d / %5d / %7.1f" % (k, v[0], v[1], v[2] / 1048576))
    for rel, sz, hx in no_stream[:4]:
        lines.append("   no chunk list: %s (%d bytes) starts %s" % (rel, sz, hx))
    lines.append("Words at the start of each file (32-bit, little endian), most common values:")
    for k, v in report["first_words"].items():
        lines.append("   word %s: %s" % (k, ", ".join("%s x%s" % kv for kv in v[:-1][:5]) + "  (%s distinct)" % v[-1][1]))
    lines.append("Strings near the start (most common): " + ", ".join("%s x%d" % kv for kv in str_counts.most_common(12)))
    text = "\n".join(lines)
    with open(os.path.join(out_dir, "models.summary.txt"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(text)
    print("Details written to models.summary.txt and models.report.json")


def main():
    ap = argparse.ArgumentParser(description="Survey the game's 3D model files.")
    ap.add_argument("folder", help="the folder p3fes_unpack.py wrote (for example C:\\p3fes\\extracted)")
    ap.add_argument("--hex", metavar="PATH", help="dump the start of one model file and exit")
    ap.add_argument("--tree", metavar="PATH", help="print the chunk tree of one model file and exit")
    ap.add_argument("--depth", type=int, default=3, help="how deep --tree goes (default 3)")
    ap.add_argument("--ext", default="rmd", help="file extensions to treat as models, comma separated (default rmd)")
    a = ap.parse_args()
    root = os.path.abspath(a.folder)
    if a.tree:
        path = a.tree if os.path.isabs(a.tree) else os.path.join(root, a.tree)
        with open(path, "rb") as fh:
            data = fh.read()
        r = find_rw(data)
        print("%s: %d bytes" % (path, len(data)))
        if not r:
            print("No chunk list found. First 64 bytes: " + data[:64].hex(" "))
            return
        lines = []
        if r[0]:
            lines.append("@0 prefix, %d bytes: %s" % (r[0], data[:r[0]].hex(" ")))
        end = print_tree(data, r[0], len(data), 0, a.depth, lines, [400])
        print("\n".join(lines))
        print("Stream ends at 0x%X; file is 0x%X bytes (%d left over)" % (end, len(data), len(data) - end))
        return
    if a.hex:
        path = a.hex if os.path.isabs(a.hex) else os.path.join(root, a.hex)
        with open(path, "rb") as fh:
            data = fh.read()
        print("%s: %d bytes" % (path, len(data)))
        print(hex_dump(data))
        print("32-bit words: " + " ".join("%08X" % w for w in u32s(data, 32)))
        print("Strings: " + ", ".join(strings_in(data, 8192, 4, 30)))
        r = find_rw(data)
        print("RenderWare chunk list: " + ("none found" if not r else "at 0x%X, %d chunks, types %s" % (
            r[0], r[1], ", ".join("%02X x%d" % kv for kv in r[2]["types"].most_common(8)))
            + ("" if not r else "; stream ends at 0x%X of 0x%X; top-level types %s" % (
                r[4], len(data), " ".join("%X" % t for t in r[3][:12])))))
        return
    survey(root, set(e.strip().lower().lstrip(".") for e in a.ext.split(",")), os.getcwd())


if __name__ == "__main__":
    main()
