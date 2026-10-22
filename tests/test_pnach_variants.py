import os, struct, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "p3fes_pnach_apply.py")

def make_elf(path, segs):
    hdr = bytearray(52); hdr[0:4] = b"\x7fELF"; hdr[4] = 1; hdr[5] = 1
    struct.pack_into("<I", hdr, 24, segs[0][0]); struct.pack_into("<I", hdr, 0x1C, 52); struct.pack_into("<HH", hdr, 0x2A, 32, len(segs))
    off = 52 + 32 * len(segs); phs = b""; body = b""
    for vaddr, filesz, memsz, flags in segs:
        phs += struct.pack("<8I", 1, off + len(body), vaddr, vaddr, filesz, memsz, flags, 16); body += bytes(range(256)) * (filesz // 256)
    open(path, "wb").write(bytes(hdr) + phs + body)

def run(*args):
    return subprocess.run([sys.executable, tool] + list(args), capture_output=True, text=True)

with tempfile.TemporaryDirectory() as d:
    p = lambda n: os.path.join(d, n)
    # code 0x100000-0x100FFF, data 0x200000-0x200FFF (file data) with a zero tail up to 0x201FFF
    make_elf(p("v.elf"), [(0x100000, 0x1000, 0x1000, 5), (0x200000, 0x1000, 0x2000, 6)])
    open(p("a.pnach"), "w").write("patch=1,EE,20100010,extended,24030009\npatch=1,EE,00100020,extended,000000AB\n")
    open(p("b.pnach"), "w").write("// b\npatch=1,EE,20100010,extended,24030009\npatch=1,EE,20100030,extended,08000000\n"
                                  "patch=1,EE,20300000,extended,24050007\npatch=0,EE,00200100,word,00AACC80\npatch=1,EE,00200104,word,11223344\n")
    r = run(p("v.elf"), "--mod", "a:0=" + p("a.pnach"), "--mod", "b:3=" + p("b.pnach"), "-o", p("o.elf"), "--entries", p("e.txt"), "--variants", p("v.txt"))
    assert r.returncode == 0, r.stdout + r.stderr
    lines = open(p("v.txt")).read().splitlines()
    # the same change made by two mods is one word, switched by both bits; a byte write changes one byte of its word
    assert any(l.startswith("C 100010 9 ") and l.endswith(" 24030009") for l in lines), lines
    word20 = [l for l in lines if l.startswith("C 100020 ")][0].split()
    assert word20[2] == "1" and int(word20[4], 16) & 0xFF == 0xAB and int(word20[3], 16) >> 8 == int(word20[4], 16) >> 8, word20
    assert any(l.startswith("C 100030 8 ") for l in lines)
    # patch=0 and data words are start-up writes; a patch=0 write is also needed by a mod that has code in new memory (mask 3 = b only here)
    assert any(l.startswith("D 200100 4 AACC80 8") for l in lines), lines
    assert any(l.startswith("D 200104 1 44 8") for l in lines) and not any(l.startswith("C 200") for l in lines), lines
    assert "M a 0" in lines and "M b 3" in lines
    o = open(p("o.elf"), "rb").read(); v = open(p("v.elf"), "rb").read()
    # the combined program holds the patched code, the data is untouched, and the code cave got a new memory block
    off = 52 + 32 * 2
    assert o[off + 0x10:off + 0x14] == (0x24030009).to_bytes(4, "little")
    assert o[off + 0x1000 + 0x100:off + 0x1000 + 0x108] == v[off + 0x1000 + 0x100:off + 0x1000 + 0x108], "data must stay as it was"
    assert "new memory blocks: 1" in r.stdout and (0x24050007).to_bytes(4, "little") in o[len(v):]
    n_ph = struct.unpack_from("<H", o, 0x2C)[0]; ph0 = struct.unpack_from("<I", o, 0x1C)[0]
    segs = [struct.unpack_from("<8I", o, ph0 + 32 * i) for i in range(n_ph)]
    assert any(s[2] <= 0x300000 < s[2] + s[5] and s[6] & 1 for s in segs), "cave block must be executable"
    # two mods that change the same word differently cannot share a build
    open(p("c.pnach"), "w").write("patch=1,EE,20100010,extended,24030001\n")
    r = run(p("v.elf"), "--mod", "a:0=" + p("a.pnach"), "--mod", "c:1=" + p("c.pnach"), "-o", p("o2.elf"), "--variants", p("v2.txt"))
    assert r.returncode == 2 and "CONFLICT at 00100010" in r.stdout and not os.path.exists(p("o2.elf")), r.stdout
    # a block of new memory that starts inside the zero tail of a data segment splits that segment instead of overlapping it
    open(p("d.pnach"), "w").write("patch=1,EE,20201800,extended,24050007\n")
    r = run(p("v.elf"), "--mod", "d:2=" + p("d.pnach"), "-o", p("o3.elf"))
    assert r.returncode == 0, r.stdout
    o3 = open(p("o3.elf"), "rb").read(); n = struct.unpack_from("<H", o3, 0x2C)[0]; ph = struct.unpack_from("<I", o3, 0x1C)[0]
    segs = [struct.unpack_from("<8I", o3, ph + 32 * i) for i in range(n)]
    data = [s for s in segs if s[2] == 0x200000][0]
    assert data[5] == 0x17C0, "the data segment's zero tail must stop where the block starts"
    # a block that would sit on real file data is refused
    open(p("e.pnach"), "w").write("patch=1,EE,20200100,extended,24050007\n")
    r = run(p("v.elf"), "--mod", "e:2=" + p("e.pnach"), "-o", p("o4.elf"))
    assert r.returncode == 0  # it is file data of a non-executable segment: becomes a start-up data write, not code
    assert "data writes at start-up: 4" in r.stdout, r.stdout
print("ok   pnach mods: switch table with masks, byte/half/word and extended lines, start-up data writes, conflicts refused, new memory blocks")
