import os, struct, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools"))
import p3fes_sfd as F
import p3fes_modmap as M

S = 2048
def pack(k): return F.pack_header(k)
def pes(sid, hdr, payload): return b"\0\0\1" + bytes([sid]) + struct.pack(">H", len(hdr) + len(payload)) + hdr + payload

def make_original():
    secs = []
    def add(body): secs.append(pack(len(secs)) + body.ljust(S - 12, b"\xff"))
    add(b"\0\0\1\xbb\0\x09\x80\x8f\x5d\x06\x20\xff\xc0\xc0\x04")
    add(b"\0\0\1\xbf" + struct.pack(">H", 2030) + b"\0" * 16 + b"SofdecStream" + b"\0" * 20 + b"X.M2V" + b"\0" * 20 + b"\x28\x01\xc0\x04")
    add(b"\0\0\1\xbf" + struct.pack(">H", 32) + b"\0" * 32)
    add(b"\0\0\1\xbf" + struct.pack(">H", 32) + b"\0" * 32)
    seq = b"\0\0\1\xb3\x28\x01\xc0\x24"
    for n in range(3):
        add(pes(0xC0, b"\x40\x04" + F.put_ts(2, n * 3360), b"\x80\0" + bytes(range(100))))
    add(pes(0xE0, b"\xff" * 9 + b"\x60\x2e\x0f", seq + b"\0" * 100))
    secs.append(b"\0\0\1\xb9" + b"\xff" * (S - 4))
    return b"".join(secs)

def make_m2v(n=5):
    out = b"\0\0\1\xb3\x50\x03\x80\x24"
    for i in range(n):
        out += b"\0\0\1\0" + bytes([i, 0x0a, 0x39]) + b"\x55" * (1500 if i == 0 else 700)
    return out

d = tempfile.mkdtemp()
orig, m2v, out = [os.path.join(d, x) for x in ("o.sfd", "v.m2v", "n.sfd")]
open(orig, "wb").write(make_original())
open(m2v, "wb").write(make_m2v())
F.remux(orig, m2v, out, "1280x896")
data = open(out, "rb").read()
assert len(data) % S == 0 and data[-S:-S + 4] == b"\0\0\1\xb9"
header, audio, n = F.parse(data)
assert len(header) == 4 and len(audio) == 3, (len(header), len(audio))
assert [a[0] for a in audio] == [0, 3360, 6720], [a[0] for a in audio]
# the new size is in the header: 1280x896 packed as 50 03 80, the old one is gone
assert b"X.M2V" in header[1] and b"\x50\x03\x80" in header[1] and b"\x28\x01\xc0" not in header[1]
# every pack clock goes up 201 ticks a sector, and the pictures carry 3003-tick time stamps
for k in range(n):
    sec = data[k * S:(k + 1) * S]
    if sec[:4] == b"\0\0\1\xba":
        assert F.read_pts(sec[4:9]) == k * 201 + 1
pts = []
for k in range(n):
    sec = data[k * S:(k + 1) * S]
    for sid, pos, ln in F.pes_list(sec):
        if sid == 0xE0 and sec[pos + 6 + 2] >> 4 == 3:
            pts.append(F.read_pts(sec[pos + 6 + 2:pos + 6 + 7]))
assert pts and pts[0] == 0 and all(p % 3003 == 0 for p in pts) and pts == sorted(pts), pts   # a sector holding several small pictures stamps only the first
# the video bytes read back unchanged
es = b""
for k in range(n):
    sec = data[k * S:(k + 1) * S]
    for sid, pos, ln in F.pes_list(sec):
        if sid == 0xE0:
            h = sec[pos + 6:pos + 6 + ln]
            i = 0
            while h[i] == 0xFF: i += 1
            i += 2
            i += 10 if h[i] >> 4 == 3 else 1
            es += h[i:]
assert es.startswith(make_m2v()), "video not kept"

# data pokes of a .pnach: byte, short, word and extended, merged into whole words from the program image
prog = bytearray(0x1000)
prog[:4] = b"\x7fELF"
struct.pack_into("<I", prog, 28, 52); struct.pack_into("<H", prog, 42, 32); struct.pack_into("<H", prog, 44, 1)
struct.pack_into("<6I", prog, 52, 1, 0x100, 0x00100000, 0x00100000, 0x800, 0x800)
prog[0x100 + 0x20:0x100 + 0x24] = b"\x05\x00\x00\x00"
prog[0x100 + 0x30:0x100 + 0x34] = b"\xc0\x01\x00\x00"
pk, notes = M.pnach_data_pokes(bytes(prog), "patch=1,EE,00100020,extended,06 //flag\npatch=1,EE,00100030,extended,70\npatch=1,EE,00100040,word,11223344\npatch=1,EE,00100050,short,BEEF\npatch=1,EE,00300000,word,1\n")
assert dict(pk) == {0x00100020: 6, 0x00100030: 0x170, 0x00100040: 0x11223344, 0x00100050: 0xBEEF}, pk
assert len(notes) == 1 and "not inside" in notes[0], notes
print("ok sfd: remux keeps the sound, the video and the clock rules; pnach data pokes merge into words")
