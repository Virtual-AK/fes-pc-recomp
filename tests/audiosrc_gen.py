import struct, random, sys
S = 2048
random.seed(7)
def rec(name, lba, size, dirflag=False):
    nm = name.encode()
    ln = 33 + len(nm)
    if ln % 2: ln += 1
    r = bytearray(ln)
    r[0] = ln
    struct.pack_into('<I', r, 2, lba); struct.pack_into('>I', r, 6, lba)
    struct.pack_into('<I', r, 10, size); struct.pack_into('>I', r, 14, size)
    r[25] = 2 if dirflag else 0
    r[32] = len(nm); r[33:33+len(nm)] = nm
    return bytes(r)
def dirsec(entries, self_lba):
    d = rec('\x00', self_lba, S, True) + rec('\x01', self_lba, S, True)
    for e in entries: d += rec(*e)
    return d.ljust(S, b'\0')
def pvd(root_lba, vol_size):
    p = bytearray(S)
    p[0] = 1; p[1:6] = b'CD001'; p[6] = 1
    struct.pack_into('<I', p, 80, vol_size)
    p[156:156+34] = rec('\x00', root_lba, S, True)[:34].ljust(34, b'\0')
    p[156] = 34
    return bytes(p)
def adx(nframes, ch, seed):
    r = random.Random(seed)
    hdr = bytearray(0x24)
    hdr[0:2] = b'\x80\x00'; hdr[2:4] = struct.pack('>H', 0x20); hdr[4] = 3; hdr[5] = 18; hdr[6] = 4; hdr[7] = ch
    hdr[8:12] = struct.pack('>I', 24000); hdr[12:16] = struct.pack('>I', nframes * 32)
    body = bytearray()
    for i in range(nframes * ch):
        fr = bytearray(r.randrange(256) for _ in range(18))
        sc = (50 + r.randrange(0x1000)) | (0x2000 if i % 5 == 0 else 0)
        fr[0:2] = struct.pack('>H', sc)
        body += fr
    end = bytearray(18); end[0:2] = b'\x80\x01'; end[2:4] = struct.pack('>H', 18)
    return bytes(hdr) + bytes(body) + bytes(end)
img = bytearray()
def put(sector, data):
    global img
    off = sector * S
    if len(img) < off + len(data): img += bytes(off + len(data) - len(img))
    img[off:off+len(data)] = data
# music: BGM.CVM at abs 100, inner base 103
one = adx(700, 2, 1)
put(100, b'CVMH' + bytes(2044)); 
put(103 + 16, pvd(20, 0)); put(103 + 20, dirsec([('ONE.ADX;1', 30, len(one)), ('TWO.BIN;1', 60, 4096)], 20))
put(103 + 30, one); put(103 + 60, bytes(random.randrange(256) for _ in range(4096)))
bgm_size = (60 + 3 + 4) * S
# voices: DATA.CVM at abs 400, inner base 403
a1, a2 = adx(300, 1, 2), adx(450, 1, 3)
off1 = 0x800; off2 = off1 + (len(a1) + 0x7ff) // 0x800 * 0x800
afs = bytearray(b'AFS\0' + struct.pack('<I', 2) + struct.pack('<II', off1, len(a1)) + struct.pack('<II', off2, len(a2)))
afs = afs.ljust(off1, b'\0') + a1; afs = afs.ljust(off2, b'\0') + a2
other = bytes(random.randrange(256) for _ in range(5000))
put(403 + 16, pvd(20, 0))
put(403 + 20, dirsec([('SOUND', 21, S, True), ('OTHER.BIN;1', 100, len(other))], 20))
put(403 + 21, dirsec([('V001001.AFS;1', 40, len(afs)), ('BGM.AFS;1', 200, 4096)], 21))
put(403 + 40, bytes(afs)); put(403 + 100, other)
# outer
put(16, pvd(20, 0))
put(20, dirsec([('BGM.CVM;1', 100, bgm_size), ('DATA.CVM;1', 400, 200 * S)], 20))
img = img.ljust(700 * S, b'\0')
open('disc.bin', 'wb').write(img)
# regions: (abs byte start, end, data off, kind)
regions = [((103 + 30) * S, (103 + 30) * S + len(one), 0x24, 0),
           ((403 + 40) * S + off1, (403 + 40) * S + off1 + len(a1), 0x24, 1),
           ((403 + 40) * S + off2, (403 + 40) * S + off2 + len(a2), 0x24, 1)]
open('regions.txt', 'w').write('\n'.join('%d %d %d %d' % r for r in regions))
print(len(img) // S, 'sectors')
