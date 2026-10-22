import os, struct, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "p3fes_pnach_apply.py")
def make_elf(path, base=0x100000, size=0x1000):
    body = bytes(range(256)) * (size // 256)
    hdr = bytearray(52)
    hdr[0:4] = b"\x7fELF"; hdr[4] = 1; hdr[5] = 1
    struct.pack_into("<I", hdr, 0x1C, 52)
    struct.pack_into("<HH", hdr, 0x2A, 32, 1)
    ph = struct.pack("<8I", 1, 84, base, base, size, size, 7, 16)
    open(path, "wb").write(bytes(hdr) + ph + body)
PN = """// test
patch=1,EE,00100010,word,0C040800 // jal 0x102000
patch=1,EE,00100014,word,00000000 // original instruction hex 17161514 / test
patch=1,EE,00100018,word,00000000 // original 00000000
patch=1,EE,00100010,word,0C040040 // later line wins: jal 0x100100
patch=1,EE,00100100,short,ABCD
patch=0,EE,0x00100200,byte,7F
patch=1,EE,00100300,extended,12345678
patch=1,EE,30100304,extended,12345678
patch=1,EE,20100308,extended,A1B2C3D4
"""
with tempfile.TemporaryDirectory() as d:
    elf, pn, out, ent = (os.path.join(d, n) for n in ("a.elf", "m.pnach", "o.elf", "e.txt"))
    make_elf(elf)
    open(pn, "w").write(PN)
    r = subprocess.run([sys.executable, tool, elf, pn, "-o", out, "--entries", ent], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    o = open(out, "rb").read(); a = open(elf, "rb").read()
    off = 84 + 0x10
    assert o[off:off + 4] == (0x0C040040).to_bytes(4, "little"), "later line must win"
    assert o[84 + 0x100:84 + 0x102] == bytes([0xCD, 0xAB]) and o[84 + 0x200] == 0x7F
    assert o[84 + 0x300] == 0x78 and o[84 + 0x301:84 + 0x304] == a[84 + 0x301:84 + 0x304], "extended 0xxxxxxx writes one byte"
    assert o[84 + 0x304:84 + 0x308] == a[84 + 0x304:84 + 0x308], "unsupported extended type must not change anything"
    assert o[84 + 0x308:84 + 0x30C] == bytes.fromhex("D4C3B2A1"), "extended 2xxxxxxx writes a word"
    assert len(o) == len(a) and a[:84] == o[:84]
    assert open(ent).read().split() == ["100100"], open(ent).read()
    assert "checks from the patch comments: 1 match, 1 differ" in r.stdout and "MISMATCH at 00100018" in r.stdout, r.stdout
    open(pn, "w").write("patch=1,EE,00900000,word,0C040040\n")
    r = subprocess.run([sys.executable, tool, elf, pn, "-o", out], capture_output=True, text=True)
    assert r.returncode == 0 and "new memory blocks: 1" in r.stdout, r.stdout + r.stderr
    o = open(out, "rb").read()
    assert b"\x40\x00\x04\x0c" in o[len(a):], "a word outside the image goes into a new memory block"
print("ok   pnach apply writes words, shorts and bytes into the program image, last line wins, finds jump targets, puts words outside the image into a new memory block, understands extended lines")
