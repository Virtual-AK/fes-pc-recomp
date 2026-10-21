"""Click-to-play voice: ADX decoding, voice archive lookup on a synthetic disc, mapping from disc reads to an archive. No game data."""
import io, math, os, struct, sys, tempfile, wave
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
import p3fes_launcher as L


def rec(name, ext, size, is_dir):
    nm = name.encode()
    r = bytearray(33 + len(nm) + (len(nm) % 2 == 0))
    r[0] = len(r)
    struct.pack_into('<I', r, 2, ext); struct.pack_into('<I', r, 10, size)
    r[25] = 2 if is_dir else 0
    r[32] = len(nm); r[33:33 + len(nm)] = nm
    return bytes(r)


def make_volume(files, first_dir_sector=20):
    """ISO9660 volume (as bytes) holding {path: bytes}; paths are 'A.BIN' or 'DIR/B.BIN'."""
    dirs = sorted({p.split('/')[0] for p in files if '/' in p})
    nsec = first_dir_sector
    root_sec = nsec; nsec += 1
    dir_sec = {}
    for d in dirs:
        dir_sec[d] = nsec; nsec += 1
    data_sec = {}
    for p in sorted(files):
        data_sec[p] = nsec; nsec += (len(files[p]) + 2047) // 2048
    vol = bytearray(nsec * 2048)
    root = bytearray()
    for d in dirs:
        root += rec(d, dir_sec[d], 2048, True)
    for p in sorted(files):
        if '/' not in p:
            root += rec(p + ';1', data_sec[p], len(files[p]), False)
    vol[root_sec * 2048:root_sec * 2048 + len(root)] = root
    for d in dirs:
        body = bytearray()
        for p in sorted(files):
            if p.startswith(d + '/'):
                body += rec(p.split('/')[1] + ';1', data_sec[p], len(files[p]), False)
        vol[dir_sec[d] * 2048:dir_sec[d] * 2048 + len(body)] = body
    for p, b in files.items():
        vol[data_sec[p] * 2048:data_sec[p] * 2048 + len(b)] = b
    pvd = bytearray(2048); pvd[0] = 1; pvd[1:6] = b'CD001'; pvd[6] = 1
    pvd[156:190] = rec('\x00', root_sec, 2048, True)[:34].ljust(34, b'\x00')
    pvd[156] = 34
    vol[16 * 2048:17 * 2048] = pvd
    return bytes(vol)


def adx_encode(pcm, rate=24000, cutoff=500):
    """Tiny ADX encoder (mono, standard): used to check the decoder reproduces a tone."""
    a = math.sqrt(2) - math.cos(2 * math.pi * cutoff / rate); b = math.sqrt(2) - 1
    c = (a - math.sqrt((a + b) * (a - b))) / b
    c0, c1 = int(math.floor(c * 2 * 4096 + .5)), int(math.floor(-(c * c) * 4096 + .5))
    out = bytearray(b'\x80\x00\x00\x24\x03\x12\x04\x01') + struct.pack('>II', rate, len(pcm)) + struct.pack('>H', cutoff) + b'\x04\x00'
    out += bytes(0x28 - len(out) - 6) + b'(c)CRI'
    s1 = s2 = 0
    for i in range(0, len(pcm), 32):
        chunk = pcm[i:i + 32] + [0] * (32 - len(pcm[i:i + 32]))
        res = []
        t1, t2 = s1, s2
        for x in chunk:
            pred = (t1 * c0 + t2 * c1) >> 12
            res.append(x - pred)
            t2, t1 = t1, x
        scale = max(1, max(abs(r) for r in res) // 7 + 1)
        blk = bytearray(struct.pack('>H', scale))
        nibs = []
        for x in chunk:
            pred = (s1 * c0 + s2 * c1) >> 12
            d = max(-8, min(7, round((x - pred) / scale)))
            nibs.append(d & 15)
            s = max(-32768, min(32767, (((d * 4096) * scale) + s1 * c0 + s2 * c1) >> 12))
            s2, s1 = s1, s
        for j in range(0, 32, 2):
            blk.append((nibs[j] << 4) | nibs[j + 1])
        out += blk
    return bytes(out)


tone = [int(8000 * math.sin(2 * math.pi * 440 * i / 24000)) for i in range(2400)]
adx = adx_encode(tone)
wav = L.adx_to_wav(adx)
w = wave.open(io.BytesIO(wav))
assert (w.getnchannels(), w.getframerate(), w.getnframes()) == (1, 24000, 2400)
dec = struct.unpack('<%dh' % 2400, w.readframes(2400))
err = sum(abs(a - b) for a, b in zip(tone[200:], dec[200:])) / 2200
assert err < 400, err       # 4-bit coding: close to the tone, not identical

# a synthetic disc: DATA.CVM = 3 header sectors + a volume holding SOUND/V129001.AFS with two clips
clip1, clip2 = adx_encode(tone[:640]), adx_encode(tone[:960])
afs = bytearray(b'AFS\x00' + struct.pack('<I', 2))
off1 = 2048
off2 = off1 + (len(clip1) + 2047) // 2048 * 2048
afs += struct.pack('<II', off1, len(clip1)) + struct.pack('<II', off2, len(clip2))
afs = bytes(afs).ljust(off1, b'\x00') + clip1.ljust(off2 - off1, b'\x00') + clip2
inner = make_volume({'SOUND/V129001.AFS': afs, 'OTHER.BIN': b'x' * 10})
cvm = b'\x00' * (3 * 2048) + inner
outer = make_volume({'DATA.CVM': cvm})
iso = os.path.join(tempfile.mkdtemp(), 'd.iso')
open(iso, 'wb').write(outer)
idx = L.afs_index(iso)
assert list(idx['files']) == ['V129001'], idx['files']
start = idx['files']['V129001'][0]
assert L.afs_for_reads('5:1,%d:9,70:2' % (start + 1), idx) == 'V129001'     # the last read inside an archive wins
assert L.afs_for_reads('5:1,70:2', idx) is None
L.voice_iso = lambda: iso
w1 = wave.open(io.BytesIO(L.voice_wav('V129001', 1))); w2 = wave.open(io.BytesIO(L.voice_wav('V129001', 2)))
assert (w1.getnframes(), w2.getnframes()) == (640, 960)
try:
    L.voice_wav('V129001', 3); raise SystemExit('clip 3 should not exist')
except ValueError:
    pass
print('ok voice: ADX decode, voice archive lookup, read-to-archive mapping, clip extraction')
