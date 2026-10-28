import os, struct, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "p3fes_modmap.py")
S = 2048

def rec(name, lba, size, d=False):
    nm = name.encode() + b";1"
    r = bytearray(33 + len(nm) + (len(nm) % 2 == 0))
    r[0] = len(r); struct.pack_into("<I", r, 2, lba); struct.pack_into("<I", r, 10, size)
    r[25] = 2 if d else 0; r[32] = len(nm); r[33:33 + len(nm)] = nm
    return bytes(r)

def pvd(root_lba, vol):
    p = bytearray(S); p[0] = 1; p[1:6] = b"CD001"; p[6] = 1
    struct.pack_into("<I", p, 80, vol)
    root = bytearray(34); root[0] = 34; struct.pack_into("<I", root, 2, root_lba); struct.pack_into("<I", root, 10, S); root[25] = 2; root[32] = 1
    p[156:190] = root
    return bytes(p)

def pak(entries):
    out = b""
    for name, data in entries:
        h = name.encode().ljust(252, b"\0") + struct.pack("<I", len(data))
        out += h + data + b"\0" * ((-len(data)) % 16)
    return out + b"\0" * 256

def build(path, entries=None):
    container = pak(entries or [("a.bmd", b"HELLO-WORLD-0123"), ("b.bin", b"x" * 40)])
    # inner file system: pvd at sector 16, root dir at 20, BTL.BIN at 30
    inner = bytearray(40 * S)
    inner[16 * S:17 * S] = pvd(20, 40)
    inner[20 * S:20 * S + 64] = rec("BTL.BIN", 30, len(container))
    inner[30 * S:30 * S + len(container)] = container
    cvm = bytearray(0x1800) + inner
    cvm += bytes((-len(cvm)) % S)
    outer = bytearray(60 * S)
    outer[16 * S:17 * S] = pvd(20, 60)
    outer[20 * S:20 * S + 64] = rec("TEST.CVM", 30 - 0, len(cvm))
    # place the cvm at sector 30 of the outer image
    outer = outer[:30 * S] + cvm
    open(path, "wb").write(outer)
    return len(container)

with tempfile.TemporaryDirectory() as d:
    iso = os.path.join(d, "g.iso"); build(iso)
    mod = os.path.join(d, "mod"); os.makedirs(os.path.join(mod, "TEST.CVM", "BTL.BIN.d"))
    open(os.path.join(mod, "TEST.CVM", "BTL.BIN.d", "a.bmd"), "wb").write(b"HELLO-MODDED-012")
    open(os.path.join(mod, "TEST.CVM", "BTL.BIN.d", "b.bin"), "wb").write(b"y" * 41)   # too big
    open(os.path.join(mod, "nothing.txt"), "wb").write(b"z")
    r = subprocess.run([sys.executable, tool, "check", iso, mod], capture_output=True, text=True)
    assert "OK   TEST.CVM/BTL.BIN.d/a.bmd" in r.stdout and "same size" in r.stdout, r.stdout + r.stderr
    assert "grows" in r.stdout and "no such file" in r.stdout and "2 of 3" in r.stdout, r.stdout
    out = os.path.join(d, "copy.iso")
    r = subprocess.run([sys.executable, tool, "apply", iso, mod, "-o", out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    a, b = open(iso, "rb").read(), open(out, "rb").read()
    assert a != b and b"HELLO-MODDED-012" in b and b"HELLO-WORLD-0123" in a   # the rebuilt container is a few bytes bigger but still inside its own sector, so it can stay where it was
    # the rebuilt container: both entries readable at the new place, b.bin has its new size
    sys.path.insert(0, os.path.join(here, "..", "tools"))
    import p3fes_unpack as U
    with open(out, "rb") as f:
        e = [x for x in U.list_files(U.Window(f, 0, os.fstat(f.fileno()).st_size)) if x["path"].endswith(".CVM")][0]
        inner, fl = U.open_cvm(f, e)
        f.seek(inner.base + fl[0]["lba"] * S)
        cont = f.read(fl[0]["size"])
        info = U.analyse_pak(type("V", (), {"size": len(cont), "read_at": lambda self, p, n: cont[p:p + n]})())
        assert info["ok"] and [(n, l) for n, l in info["entries"]] == [("a.bmd", 16), ("b.bin", 41)], info
        assert b"HELLO-MODDED-012" in cont and b"y" * 41 in cont
    ov = os.path.join(d, "m.ovl")
    r = subprocess.run([sys.executable, tool, "overlay", iso, mod, "-o", ov], capture_output=True, text=True)
    assert open(ov, "rb").read(8) == b"P3OVL001"
    r = subprocess.run([sys.executable, tool, "apply", iso, mod, "-o", iso], capture_output=True, text=True)
    assert r.returncode != 0
    # relocation: a whole file bigger than the original moves to the end and its directory entry follows
    mod2 = os.path.join(d, "mod2"); os.makedirs(os.path.join(mod2, "TEST.CVM"))
    big = b"BIGFILE!" * 1000
    open(os.path.join(mod2, "TEST.CVM", "BTL.BIN"), "wb").write(big)
    out2 = os.path.join(d, "moved.iso")
    r = subprocess.run([sys.executable, tool, "apply", iso, mod2, "-o", out2], capture_output=True, text=True)
    assert r.returncode == 0 and "moved to the end" in r.stdout, r.stdout + r.stderr
    sys.path.insert(0, os.path.join(here, "..", "tools"))
    import p3fes_unpack as U
    with open(out2, "rb") as f:
        outer = U.Window(f, 0, os.fstat(f.fileno()).st_size)
        e = [x for x in U.list_files(outer) if x["path"].endswith(".CVM")][0]
        inner, fl = U.open_cvm(f, e)
        x = fl[0]
        f.seek(inner.base + x["lba"] * S)
        assert x["size"] == len(big) and f.read(len(big)) == big
        assert (inner.base + x["lba"] * S) % S == 0 and inner.base + x["lba"] * S >= os.path.getsize(iso)
print("ok   modmap finds files inside CVM containers, flags too-big and unknown files, writes copy and overlay")
with tempfile.TemporaryDirectory() as d:
    iso = os.path.join(d, "g.iso"); build(iso); out = os.path.join(d, "mt.iso")
    r = subprocess.run([sys.executable, tool, "movetest", iso, "-o", out], capture_output=True, text=True)
    assert r.returncode == 0 and "moved 1 files" in r.stdout, r.stdout + r.stderr
    sys.path.insert(0, os.path.join(here, "..", "tools"))
    import p3fes_unpack as U
    with open(out, "rb") as f:
        e = [x for x in U.list_files(U.Window(f, 0, os.fstat(f.fileno()).st_size)) if x["path"].endswith(".CVM")][0]
        inner, fl = U.open_cvm(f, e)
        assert fl[0]["lba"] != 30 and len(open(out, "rb").read()) > len(open(iso, "rb").read())
print("ok   movetest")

# mod-manager layout: extension-less container folder, DATA entry, textures inside a .SPR named ...a.tmx / ...b.tmx
def tmx(n, fill):
    return struct.pack("<HHI", 2, 0, n) + b"TMX0" + fill * (n - 12)
def spr(n):
    body = b"\x01\0\0\0\0\0\0\0SPR0" + b"\0" * 20
    t1, t2 = tmx(n, b"1"), tmx(n, b"2")
    return body + t1 + t2
with tempfile.TemporaryDirectory() as d:
    iso = os.path.join(d, "g.iso"); build(iso, [("DATA/FACE03.SPR", spr(64)), ("BP_X.BMD", b"q" * 20)])
    mod = os.path.join(d, "mod", "test", "BTL_ALL", "data", "FACE03"); os.makedirs(mod)
    os.rename(os.path.join(d, "mod", "test", "BTL_ALL"), os.path.join(d, "mod", "test", "BTL"))
    mod = os.path.join(d, "mod", "test", "BTL", "data", "FACE03")
    open(os.path.join(mod, "AGS_face03a.tmx"), "wb").write(tmx(64, b"A"))
    open(os.path.join(mod, "AGS_face03b.tmx"), "wb").write(tmx(64, b"B"))
    open(os.path.join(mod, "AGS_face03c.tmx"), "wb").write(tmx(64, b"C"))   # only two textures: skipped
    out = os.path.join(d, "o.iso")
    r = subprocess.run([sys.executable, tool, "apply", iso, os.path.join(d, "mod"), "-o", out], capture_output=True, text=True)
    assert "2 of 3" in r.stdout and "cannot tell" in r.stdout, r.stdout + r.stderr
    b = open(out, "rb").read()
    assert b.count(tmx(64, b"A")) == 1 and b.count(tmx(64, b"B")) == 1 and tmx(64, b"1") not in b and tmx(64, b"2") not in b
print("ok   modmap .SPR textures inside containers (mod-manager layout)")

# growing textures inside a .SPR: the sprite header's offsets follow, the container is rebuilt and moved
def spr2(n):
    t1, t2 = tmx(n, b"1"), tmx(n, b"2")
    h = bytearray(b"\x01\0\0\0\0\0\0\0SPR0" + b"\0" * 52)           # 64 bytes
    struct.pack_into("<I", h, 0x10, 64 + 2 * n - 4)                   # size - 4
    struct.pack_into("<I", h, 0x24, 64); struct.pack_into("<I", h, 0x2C, 64 + n)
    return bytes(h) + t1 + t2
with tempfile.TemporaryDirectory() as d:
    iso = os.path.join(d, "g.iso"); build(iso, [("DATA/FACE03.SPR", spr2(64)), ("BP_X.BMD", b"q" * 20)])
    mod = os.path.join(d, "mod", "test", "BTL", "data", "FACE03"); os.makedirs(mod)
    open(os.path.join(mod, "x_face03a.tmx"), "wb").write(tmx(160, b"A"))
    open(os.path.join(mod, "x_face03b.tmx"), "wb").write(tmx(160, b"B"))
    out = os.path.join(d, "o.iso")
    r = subprocess.run([sys.executable, tool, "apply", iso, os.path.join(d, "mod"), "-o", out], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.count("grows") == 2, r.stdout + r.stderr
    b = open(out, "rb").read()
    at = b.rfind(b"SPR0") - 8      # the new copy of the sprite file (small, so it may stay inside its old sector, or sit after the old image end)
    assert at > 0
    new = b[at:at + 64 + 320]
    assert struct.unpack_from("<I", new, 0x24)[0] == 64 and struct.unpack_from("<I", new, 0x2C)[0] == 64 + 160
    assert struct.unpack_from("<I", new, 0x10)[0] == 64 + 320 - 4
    assert new[64:64 + 160] == tmx(160, b"A") and new[64 + 160:64 + 320] == tmx(160, b"B")
print("ok   modmap grows textures inside a .SPR (header offsets follow, container rebuilt)")

# tint: a red test mod made from the disc itself, then applied (in place and with --move)
def tmx_pal(fill):
    return struct.pack("<HHI", 2, 0, 17472) + b"TMX0" + b"\0" * 52 + bytes([10, 20, 30, 128]) * 256 + fill * (17472 - 64 - 1024)
with tempfile.TemporaryDirectory() as d:
    sp = b"\x01\0\0\0\0\0\0\0SPR0" + b"\0" * 20
    iso = os.path.join(d, "g.iso"); build(iso, [("DATA/I_B_FACE02.SPR", sp + tmx_pal(b"\x01") + tmx_pal(b"\x02"))])
    for extra in ([], ["--move"]):
        out = os.path.join(d, "tint" + str(len(extra)))
        r = subprocess.run([sys.executable, tool, "tint", iso, "BTL.BIN", "-o", out] + extra, capture_output=True, text=True)
        assert "wrote 2 red" in r.stdout, r.stdout + r.stderr
        got = os.path.join(out, "TEST.CVM", "BTL", "DATA", "I_B_FACE02", "ta.tmx")
        assert os.path.isfile(got) and open(got, "rb").read()[64:68] == bytes([255, 5, 7, 128]), got
        r = subprocess.run([sys.executable, tool, "check", iso, out], capture_output=True, text=True)
        assert "2 of 2" in r.stdout, r.stdout
print("ok   modmap tint test mod")

# a 32-bit texture bigger than the original 8-bit one is reduced to 256 colours and put in place (palette order read off the original)
import importlib.util
spec = importlib.util.spec_from_file_location("mm", tool); mm = importlib.util.module_from_spec(spec); spec.loader.exec_module(mm)
def orig8(swapped):
    hdr = struct.pack("<HHI", 2, 0, 17472) + b"TMX0" + b"\0" * 52
    pal = bytearray(1024)
    for k in range(256):
        pos = mm.swz(k) if swapped else k
        pal[4 * pos:4 * pos + 4] = bytes([k, k, k, 128])
    idx = bytes((x * 2) & 255 for y in range(128) for x in range(128))     # smooth left-to-right ramp
    return hdr + bytes(pal) + idx
def mod32():
    hdr = struct.pack("<HHI", 2, 0, 65600) + b"TMX0" + b"\0" * 52
    px = b"".join(bytes([255, 0, 0, 128]) if (x < 64) == (y < 64) else bytes([0, 0, 255, 128]) for y in range(128) for x in range(128))
    return hdr + px
for swapped in (False, True):
    new = mm.tmx_to_8bit(orig8(swapped), mod32())
    assert len(new) == 17472 and new[:64] == orig8(swapped)[:64]
    for (x, y, want) in ((10, 10, (255, 0, 0, 128)), (100, 10, (0, 0, 255, 128)), (10, 100, (0, 0, 255, 128)), (100, 100, (255, 0, 0, 128))):
        k = new[64 + 1024 + y * 128 + x]
        pos = mm.swz(k) if swapped else k
        assert tuple(new[64 + 4 * pos:68 + 4 * pos]) == want, (swapped, x, y)
assert mm.tmx_convertible(17472, 65600) and not mm.tmx_convertible(17472, 17488)
# end to end: a mod with a 65600-byte texture where the disc has 17472 bytes goes in place (no rebuild)
with tempfile.TemporaryDirectory() as d:
    sp = b"\x01\0\0\0\0\0\0\0SPR0" + b"\0" * 20
    iso = os.path.join(d, "g.iso"); build(iso, [("DATA/FACE.SPR", sp + orig8(False) + orig8(False))])
    mod = os.path.join(d, "mod", "test", "BTL", "data", "FACE"); os.makedirs(mod)
    open(os.path.join(mod, "x_facea.tmx"), "wb").write(mod32())
    out = os.path.join(d, "o.iso")
    r = subprocess.run([sys.executable, tool, "apply", iso, os.path.join(d, "mod"), "-o", out], capture_output=True, text=True)
    assert r.returncode == 0 and "reduced to 256 colours" in r.stdout and "rebuilt" not in r.stdout, r.stdout + r.stderr
    assert len(open(out, "rb").read()) == len(open(iso, "rb").read())      # nothing appended
print("ok   modmap reduces 32-bit textures to the original's 8-bit form")

# colour reduction keeps fully transparent pixels invisible (their own palette entry with alpha 0)
import random as _r
_r.seed(1)
_px = [(_r.randrange(256), _r.randrange(256), _r.randrange(256), 0) for _ in range(5000)] + [(_r.randrange(256), 100, 50, _r.choice((16, 24, 64, 128))) for _ in range(5000)]
_pal, _idx = mm.quantize(_px)
assert len(_pal) == 256 and all(_pal[i][3] == 0 for p, i in zip(_px, _idx) if p[3] == 0)
assert all(_pal[i][3] > 0 for p, i in zip(_px, _idx) if p[3] > 0)
print("ok   quantize keeps transparent pixels transparent and edge pixels visible")

# entries with Japanese names match by their ASCII part, whichever way the name was decoded
_c = {"/X.PAK": [("ΓùÆi_f_face03b_pt.tmx", 100, 50), ("OTHER.TMX", 200, 50)]}
_f = {"/X.PAK": (0, 300)}
for _n in ("◆i_f_face03b_pt.tmx", "◆i_f_face03b_pt.tmx".encode("utf-8").decode("cp437"), "i_f_face03b_pt.tmx"):
    _r2 = mm.resolve("X/" + _n, _f, _c)
    assert _r2[0] == 100, (_n, _r2)
print("ok   modmap matches entries with Japanese names")

# mod-manager layout with entries named ...SPR.SPR and textures named with a Japanese tail
_c = {"/X.PAK": [("I_F_FACE01SPR.SPR", 100, 90), ("AGS_I_F_FACE03SPR.SPR", 300, 90)],
      "/X.PAK :: I_F_FACE01SPR.SPR": [("#0", 110, 40), ("#1", 160, 20)],
      "/X.PAK :: AGS_I_F_FACE03SPR.SPR": [("#0", 310, 40), ("#1", 360, 20)]}
for _rel, _want in (("X/i_f_face01/i_f_face01a.tmx", 110), ("X/i_f_face01/i_f_face01b.tmx", 160),
                    ("X/AGS_i_f_face03/◆i_f_face03b_アmk2.tmx", 360), ("X/AGS_i_f_face03/◆i_f_face03a_アmk2.tmx", 310)):
    _r2 = mm.resolve(_rel, {"/X.PAK": (0, 400)}, _c)
    assert _r2[0] == _want, (_rel, _r2)
print("ok   modmap matches SPR entries named with SPR suffix")
