#!/usr/bin/env python3
"""
p3fes_bmd.py - look inside the game's message (.BMD) files. Step 2 of the text tool.

The survey showed every .BMD file is the "MSG1" kind. The file starts with a 32-byte
header, then a list of messages (8 bytes each: a type number and a position). This
tool shows what is inside one file, so the exact layout of each message can be
confirmed before the real extractor is written. It only READS.

Usage (from a Command Prompt in the folder that holds this script):
    py p3fes_bmd.py "C:\\p3fes\\extracted\\BTL.CVM\\BATTLE\\PANEL\\BP_TUTORIAL.BIN.d\\bp_tutorial1.bmd"
    py p3fes_bmd.py "C:\\p3fes\\extracted\\BTL.CVM\\BATTLE\\RESULT\\BRP_SYSMSG.BMD" --hex

Without --hex it prints the header and the message list. With --hex it also prints the
whole file as a hex dump with the readable characters on the right, which is what is
needed to work out how the text itself is stored. The output contains the game's own
text, so share it only in this chat, never on GitHub.
"""
import argparse, struct, sys


def hexdump(data, base=0):
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        hx = " ".join("%02X" % b for b in chunk)
        tx = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print("%06X  %-47s  %s" % (base + i, hx, tx))


def main():
    ap = argparse.ArgumentParser(description="Show the structure of a .BMD message file.")
    ap.add_argument("file")
    ap.add_argument("--hex", action="store_true", help="also print the whole file as a hex dump")
    args = ap.parse_args()
    with open(args.file, "rb") as fh:
        data = fh.read()
    if len(data) < 32 or data[8:12] != b"MSG1":
        sys.exit("This is not an MSG1 message file.")
    ftype, size = struct.unpack_from("<II", data, 0)
    reloc_off, reloc_size, count = struct.unpack_from("<III", data, 16)
    a, b = struct.unpack_from("<HH", data, 28)
    print("file size %d (header says %d), type %d" % (len(data), size, ftype))
    print("relocation table at 0x%X, %d bytes; message count %d; header word %d/%d" % (reloc_off, reloc_size, count, a, b))
    if count > 100000 or 32 + count * 8 > len(data):
        sys.exit("The message count looks wrong; stopping.")
    print("\nmessages (type, start offset as stored, absolute start = stored + 0x20):")
    starts = []
    for i in range(count):
        t, off = struct.unpack_from("<II", data, 32 + i * 8)
        starts.append(off + 32)
        name = data[off + 32: off + 32 + 24].split(b"\0")[0] if off + 56 <= len(data) else b""
        print("  %3d  type %d  stored 0x%X  absolute 0x%X  name %r" % (i, t, off, off + 32, name.decode("ascii", "replace")))
    if args.hex:
        print()
        hexdump(data)


if __name__ == "__main__":
    main()
