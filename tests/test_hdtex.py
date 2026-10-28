"""HD textures: the table, the map builder, the launcher switch, and (when g++ exists) the C++ hash and DDS decoder."""
import json, os, shutil, struct, subprocess, sys, tempfile
import numpy as np

here = os.path.dirname(os.path.abspath(__file__))
tools = os.path.join(here, "..", "tools")
sys.path.insert(0, tools)
sys.path.insert(0, os.path.join(tools, "launcher"))
import p3fes_hdtex as H
import p3fes_texhash as T
import p3fes_launcher as L

# ---- the shipped table
table = os.path.join(tools, "hdtex", "hdtex-table-ntscu.tsv")
rows = [l.rstrip("\n").split("\t") for l in open(table) if not l.startswith("#") and l.strip()]
assert len(rows) >= 600, len(rows)
keys = set()
packs = set()
for r in rows:
    assert len(r) == 10, r
    k = int(r[0], 16); assert len(r[0]) == 16 and k not in keys; keys.add(k)
    w, h, psm = int(r[1]), int(r[2]), int(r[3])
    assert w & (w - 1) == 0 and h & (h - 1) == 0 and psm in (19, 20), r
    sx, sy, ox, oy = map(float, r[4:8])
    assert 0.3 < sx < 3 and 0.3 < sy < 3 and -1 < ox < 1 and -1 < oy < 1, r
    assert r[8] in ("0", "1")
    pid, _, rel = r[9].partition(":"); assert rel.endswith(".dds") and "\\" not in rel, r
    packs.add(pid)
assert packs <= {"hq_portraits", "p3hd_enhanced_persona_artwork", "widescreen"}, packs

# ---- the patch file is the one made from the sources (run tools/hdtex/make_patch.py after changing them)
hd = os.path.join(tools, "hdtex")
def rd(n): return open(os.path.join(hd, n), newline="").read().replace("\r\n", "\n")
hpp = rd("hdtex.hpp").replace('#include "bc7_tables.inc"\n', rd("bc7_tables.inc"))
built = rd("patch_template.py").replace("@@HPP@@", repr(hpp)).replace("@@GLUE@@", repr(rd("glue_gpu.inc"))).replace("@@GLUE_V1@@", repr(rd("glue_v1.inc"))).replace("@@GLUE_V2@@", repr(rd("glue_v2.inc"))).replace("@@GLUE_V3@@", repr(rd("glue_v3.inc"))).replace("@@GLUE_V4@@", repr(rd("glue_v4.inc")))
assert built == open(os.path.join(tools, "ps2run_hdtex_patch.py"), newline="").read().replace("\r\n", "\n"), "ps2run_hdtex_patch.py is out of date: run python3 tools/hdtex/make_patch.py"

# ---- the map builder, on a made-up mods folder
d = tempfile.mkdtemp()
mods = os.path.join(d, "hdmods")
want = [r for r in rows][:5]
for r in want[:3]:
    pid, _, rel = r[9].partition(":")
    p = os.path.join(mods, pid + "_abc123", *rel.split("/")); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(b"x")
out = os.path.join(d, "hdtex.map")
n, missing = H.build_map(table, mods, out, "C:\\hd")
assert n == 3, n
assert sum(missing.values()) == len(rows) - 3
lines = [l.rstrip("\n").split("\t") for l in open(out) if not l.startswith("#") and l.strip()]
assert len(lines) == 3 and all(l[9].startswith("C:/hd/") and l[9].endswith(".dds") for l in lines), lines
assert H.main(["--table", table, "--mods", os.path.join(d, "none"), "--out", out]) == 2

# ---- the launcher switch (Settings > Display > HD TEXTURES)
L.DIR = d
L.CFG = os.path.join(d, "cfg.json")
L.saves_dir = lambda: os.path.join(d, "saves")
L.to_win = lambda p: "C:/" + os.path.relpath(p, d).replace(os.sep, "/")
os.makedirs(L.saves_dir(), exist_ok=True)
L.hd_tool().find_table = lambda here=None: table
env, names = {}, []
assert L.hd_env(env, names) == "" and "PS2_HDTEX" not in env           # off: nothing is passed on
r = L.hd_set(True); assert r["ok"] and "3 pictures found" in r["msg"], r
st = L.hd_state_now(); assert st["on"] and st["pictures"] == 3 and st["table"], st
env, names = {}, []
note = L.hd_env(env, names)
assert env["PS2_HDTEX"].endswith("hdtex.map") and names == ["PS2_HDTEX"] and "3 pictures" in note, (env, note)
assert os.path.isfile(L.hd_map_path())
# Play must not convert paths one by one (each is a subprocess in the real launcher) and must not rebuild an unchanged map
calls = []
L.to_win = lambda p: (calls.append(p) or "C:/" + os.path.relpath(p, d).replace(os.sep, "/"))
env, names = {}, []
L.hd_env(env, names); assert len(calls) <= 3, calls            # same sources as the last Play: reuses the map
mtime = os.path.getmtime(L.hd_map_path())
import time; time.sleep(0.05)
env, names = {}, []; L.hd_env(env, names)
assert os.path.getmtime(L.hd_map_path()) == mtime, "an unchanged map must not be rebuilt"
extra = os.path.join(mods, want[3][9].partition(":")[0] + "_abc123", *want[3][9].partition(":")[2].split("/"))
os.makedirs(os.path.dirname(extra), exist_ok=True); open(extra, "wb").write(b"x")
os.utime(os.path.join(mods, want[3][9].partition(":")[0] + "_abc123"), None)
calls.clear(); env, names = {}, []; note = L.hd_env(env, names)
assert "4 pictures" in note and len(calls) <= 3, (note, calls)   # a new picture is picked up, still with a handful of conversions
# the Display page state never waits: first call answers at once (pending or cached) and a side thread fills the cache
t0 = time.time(); L._hd_cache.update(sig=None, state=None, busy=False); st0 = L.hd_state(); assert time.time() - t0 < 0.5
for _ in range(100):
    if L._hd_cache["state"] is not None: break
    time.sleep(0.05)
assert L.hd_state()["pictures"] == 4 and not L.hd_state().get("pending")
shutil.rmtree(mods); os.makedirs(mods)
r = L.hd_set(True); assert "No pictures found" in r["msg"], r
env, names = {}, []
assert "no pictures" in L.hd_env(env, names).lower() and not env
assert L.hd_set(False)["msg"] == "HD textures are off." and not L.hd_state()["on"]
assert L.hd_state().get("pending") or "pictures" in L.hd_state()
assert "hdtex" in L.get_state() and L.LAUNCHER_VERSION >= "0.56"

# ---- the C++ side: the same hash as Python (any chunking) and the DDS decoder
gxx = shutil.which("g++")
if gxx:
    exe = os.path.join(d, "hdcheck")
    r = subprocess.run([gxx, "-std=c++17", "-O1", "-I" + os.path.join(tools, "hdtex"), os.path.join(here, "hdtex_check.cpp"), "-o", exe, "-pthread"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    rng = np.random.default_rng(7)
    for size in (4096, 1000, 77, 1048576 // 4):
        blob = rng.integers(0, 256, size, dtype=np.uint8).tobytes()
        p = os.path.join(d, "blob.bin"); open(p, "wb").write(blob)
        want_h = "%016x" % T.upload_hash(blob)
        for chunk in (1, 7, 8, 13, 4096, 100000):
            got = subprocess.run([exe, "hash", p, str(chunk)], capture_output=True, text=True).stdout.strip()
            assert got == want_h, (size, chunk, got, want_h)

    def dds(w, h, fourcc, blocks):
        hdr = bytearray(128); hdr[0:4] = b"DDS "; struct.pack_into("<I", hdr, 4, 124); struct.pack_into("<I", hdr, 8, 0x1007)
        struct.pack_into("<II", hdr, 12, h, w); struct.pack_into("<I", hdr, 28, 1); struct.pack_into("<I", hdr, 76, 32); struct.pack_into("<I", hdr, 80, 4)
        hdr[84:88] = fourcc; struct.pack_into("<I", hdr, 108, 0x1000)
        return bytes(hdr) + blocks
    # DXT1: every block is solid red (colour 0 = 0xF800, indices 0) -> (255,0,0)
    blk = struct.pack("<HHI", 0xF800, 0x001F, 0)
    p = os.path.join(d, "red.dds"); open(p, "wb").write(dds(8, 8, b"DXT1", blk * 4))
    q = os.path.join(d, "red.raw")
    assert subprocess.run([exe, "dds", p, q]).returncode == 0
    raw = open(q, "rb").read(); w, h = struct.unpack("<II", raw[:8]); a = np.frombuffer(raw[8:], dtype=np.uint8).reshape(h, w, 4)
    assert (w, h) == (8, 8) and (a[..., 0] == 255).all() and (a[..., 1] == 0).all() and (a[..., 2] == 0).all(), a[0, 0]
    # DXT5: colour 0x001F (blue), alpha 0 and 255 endpoints with all indices 1 -> alpha1
    blk = bytes([255, 0]) + b"\x49\x92\x24\x49\x92\x24" + struct.pack("<HHI", 0x001F, 0x001F, 0)   # index 1 in every texel: alpha = alpha1 = 0
    p = os.path.join(d, "a.dds"); open(p, "wb").write(dds(4, 4, b"DXT5", blk))
    assert subprocess.run([exe, "dds", p, q]).returncode == 0
    raw = open(q, "rb").read(); a = np.frombuffer(raw[8:], dtype=np.uint8).reshape(4, 4, 4)
    assert (a[..., 2] == 255).all() and (a[..., 3] == 0).all(), a[0, 0]
    bad = os.path.join(d, "bad.dds"); open(bad, "wb").write(b"nope" * 40)
    assert subprocess.run([exe, "dds", bad, q], capture_output=True).returncode != 0
    # the loader: eight 64x64 pictures, preloads and urgent requests
    blk = struct.pack("<HHI", 0xF800, 0x001F, 0)
    lines = []
    for i in range(8):
        pp = os.path.join(d, "pic%d.dds" % i); open(pp, "wb").write(dds(64, 64, b"DXT1", blk * 256))
        lines.append("%016x\t64\t64\t19\t1\t1\t0\t0\t0\t%s" % (0x1000 + i, pp))
    mp = os.path.join(d, "store.map"); open(mp, "w").write("\n".join(lines) + "\n")
    r = subprocess.run([exe, "store", mp, "8"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "store ok" in r.stdout, (r.returncode, r.stdout, r.stderr)
    cpp = "hash 4 sizes x 6 chunkings, DXT1/DXT5 decode, loader queue"
else:
    cpp = "C++ checks skipped (no g++)"
print("ok hd textures: table (%d pictures), map builder, launcher switch, %s" % (len(rows), cpp))
