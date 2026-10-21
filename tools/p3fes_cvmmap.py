#!/usr/bin/env python3
"""Name the files inside the game's big archives (DATA.CVM, BGM.CVM, BTL.CVM) that a disc log points at (research tool, docs/log-plan.md).

  python3 p3fes_cvmmap.py "Persona3FES.iso" disclog.txt            names every DATA/BGM/BTL read in a disc log
  python3 p3fes_cvmmap.py "Persona3FES.iso" 771825 771840 771849   names single sector numbers
  options: --skip-bgm   leave out the BGM.CVM reads (they are background music, about every 72 frames)

A .cvm file is a small header followed by an ISO9660 volume, so it has its own file names. The sectors in the disc log are
absolute positions on the disc; this tool works out which file inside which archive covers each one. It prints the result for
both ways the archive's own numbering can start (right at the file start, or after a 3-sector header); the right one gives
sensible names. It only reads the disc image, nothing is written next to it. Needs only Python 3.
"""
import re
import struct
import sys

SECTOR = 2048


def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def read_at(f, off, n):
    f.seek(off)
    return f.read(n)


def parse_dir(f, base, lba, size, prefix, out, depth=0):
    """list (path, lba, size) of every file under a directory record; base is the byte offset of the volume start"""
    data = read_at(f, base + lba * SECTOR, size)
    pos = 0
    while pos < len(data):
        ln = data[pos]
        if ln == 0:
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        rec = data[pos:pos + ln]
        pos += ln
        if len(rec) < 34:
            continue
        ext, sz, flags, nlen = u32(rec, 2), u32(rec, 10), rec[25], rec[32]
        name = rec[33:33 + nlen]
        if name in (b'\x00', b'\x01'):
            continue
        name = name.decode('latin-1').split(';')[0]
        if flags & 2:
            if depth < 8 and sz:
                parse_dir(f, base, ext, sz, prefix + name + '/', out, depth + 1)
        else:
            out.append((prefix + name, ext, sz))


def volume_files(f, base):
    pvd = read_at(f, base + 16 * SECTOR, SECTOR)
    if pvd[1:6] != b'CD001':
        return None
    out = []
    root = pvd[156:190]
    parse_dir(f, base, u32(root, 2), u32(root, 10), '', out)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    skip_bgm = '--skip-bgm' in sys.argv
    if len(args) < 2:
        sys.exit(__doc__)
    iso, rest = args[0], args[1:]
    with open(iso, 'rb') as f:
        outer = volume_files(f, 0)
        if outer is None:
            sys.exit("not an ISO9660 disc image: " + iso)
        archives = {}
        for path, lba, size in outer:
            if path.upper().endswith('.CVM'):
                found = {}
                for shift in (0, 3):
                    files = volume_files(f, lba * SECTOR + shift * SECTOR)
                    if files:
                        found[shift] = files
                archives[path.upper()] = (lba, size, found)
        print("archives on the disc: " + ", ".join("%s (starts at sector %d, %d inner files)" % (
            k, v[0], max([len(x) for x in v[2].values()] or [0])) for k, v in archives.items()))

        def name(sector):
            for arch, (lba, size, found) in archives.items():
                if lba <= sector < lba + (size + SECTOR - 1) // SECTOR:
                    parts = []
                    for shift, files in sorted(found.items()):
                        rel = sector - lba - shift
                        hit = [p for p, l, s in files if l <= rel < l + max(1, (s + SECTOR - 1) // SECTOR)]
                        if hit:
                            parts.append("shift %d: %s" % (shift, hit[0]))
                    return arch, ("; ".join(parts) if parts else "(no inner file covers it)")
            return None, None

        jobs = []
        if len(rest) == 1 and not rest[0].isdigit():
            for ln in open(rest[0], errors='replace'):
                m = re.match(r'\[disc\] frame (\d+) sector (\d+) x(\d+)\s+(\S+)', ln)
                if m:
                    jobs.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)))
        else:
            jobs = [(0, int(s), 1, '') for s in rest]
        last = None
        for frame, sector, count, label in jobs:
            arch, nm = name(sector)
            if arch is None:
                continue
            if skip_bgm and arch == 'BGM.CVM':
                continue
            line = "frame %6d  sector %8d x%-4d %-9s %s" % (frame, sector, count, arch, nm)
            if line != last:
                print(line)
            last = line


if __name__ == "__main__":
    main()
