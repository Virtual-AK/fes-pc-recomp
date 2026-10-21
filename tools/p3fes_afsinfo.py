#!/usr/bin/env python3
"""Show what a voice archive (SOUND/V*.AFS inside DATA.CVM) contains, to work out the clip format (research tool, docs/log-plan.md).

  python3 p3fes_afsinfo.py "Persona3FES.iso" [SOUND/V129001.AFS]

Prints the archive's own position on the disc, its entry table (offset, size, and the disc sector each entry starts at) and the first
bytes of each entry with a guess at the format (ADX, PS2 ADPCM "VAGp", RIFF/WAV, raw). Only reads the disc image. Needs only Python 3.
"""
import struct
import sys
import p3fes_cvmmap as C

SECTOR = 2048


def guess(b):
    if b[:2] == b'\x80\x00':
        return "ADX"
    if b[:4] == b'VAGp':
        return "VAG (PS2 ADPCM)"
    if b[:4] == b'RIFF':
        return "RIFF/WAV"
    if b[:4] == b'AFS\x00':
        return "nested AFS"
    if b[:4] == b'SShd' or b[:4] == b'SSbd':
        return "SS (PS2 sound header)"
    if len(b) >= 16 and b[0] == 0 and b[1] in (0, 2, 3, 6, 7):
        return "maybe raw PS2 ADPCM blocks"
    return "unknown"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        sys.exit(__doc__)
    iso = args[0]
    want = (args[1] if len(args) > 1 else "SOUND/V129001.AFS").upper()
    with open(iso, 'rb') as f:
        outer = C.volume_files(f, 0)
        dat = [x for x in outer if x[0].upper() == 'DATA.CVM']
        if not dat:
            sys.exit("DATA.CVM not found on the disc image")
        _, base_sec, _ = dat[0]
        base = (base_sec + 3) * SECTOR
        files = C.volume_files(f, base)
        hit = [x for x in files if x[0].upper() == want]
        if not hit:
            sys.exit("not found inside DATA.CVM: " + want)
        path, lba, size = hit[0]
        start = base_sec + 3 + lba
        print("%s: %d bytes, starts at disc sector %d" % (path, size, start))
        head = C.read_at(f, base + lba * SECTOR, min(size, 65536))
        print("first bytes: " + head[:32].hex(' '))
        if head[:4] != b'AFS\x00':
            print("not an AFS archive (no AFS magic); showing the start of the file only")
            return
        n = struct.unpack_from('<I', head, 4)[0]
        print("entries:", n)
        for i in range(min(n, 40)):
            off, sz = struct.unpack_from('<II', head, 8 + i * 8)
            data = C.read_at(f, base + lba * SECTOR + off, min(sz, 48))
            print("  #%-3d offset %8d size %8d  sector %8d  %-28s %s" % (i, off, sz, start + off // SECTOR, guess(data), data[:24].hex(' ')))
        if n > 40:
            print("  ... %d more entries" % (n - 40))


main()
