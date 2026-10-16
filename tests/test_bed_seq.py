#!/usr/bin/env python3
"""Sound sequences: .sq blocks, MIDI-like events and Setb tones parse; a sequence renders to a wav."""
import os, struct, subprocess, sys, tempfile, wave
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
import p3fes_bed as B
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_bed.py')
N = 0xFFFFFFFF

def chunk(name4, body):          # 'SCEI' + 4 letters, both written backwards; size includes the 8-byte name
    return b'IECS' + name4[::-1].encode() + struct.pack('<I', 12 + len(body)) + body

def build_sq(events_by_block):   # one group; blocks given as {block index: event bytes}
    nb = max(events_by_block) + 1
    c0 = 0x30
    top_hdr = struct.pack('<I', 0) + struct.pack('<I', 0x10) + struct.pack('<BBH', 0x7F, 0x40, 1000) + struct.pack('<II', N, N)
    top_table = struct.pack('<I', 0x24)             # group at c+0x24
    g = struct.pack('<I', nb - 1) + struct.pack('<I', 0x0C) + struct.pack('<BBH', 0x7F, 0x40, 1000) + struct.pack('<I', N)
    table_at = 0x24 + 0x10
    blocks_at = table_at + 4 * nb
    table, blob, off = b'', b'', blocks_at
    for i in range(nb):
        ev = events_by_block.get(i)
        if ev is None:
            table += struct.pack('<I', N)
        else:
            table += struct.pack('<I', off)
            blk = struct.pack('<I', 0x10) + struct.pack('<BBH', 0x7F, 0x40, 1000) + struct.pack('<II', len(ev), 0) + ev
            blob += blk; off += len(blk)
    body = top_hdr + top_table + g + table + blob
    sesq = chunk('Sesq', body)
    return chunk('Vers', struct.pack('<I', 0x20000)[:4]) [:16].ljust(16, b'\0') + chunk('Sequ', bytes(20)) + sesq

def tone(sample, vol): return struct.pack('<HBBB', sample, 0, vol, 0x40) + bytes(45)

def build_hd(tones, sample_offsets):
    vagi_body = struct.pack('<II', len(sample_offsets) - 1, 0)
    vagi = b''
    ents = b''
    for k, so in enumerate(sample_offsets):
        vagi_body += struct.pack('<I', 0x10 + 4 * len(sample_offsets) + 8 * k - 0)  # offsets relative to chunk start
        ents += struct.pack('<IHBB', so, 44100, 0, 255)
    vag = chunk('Vagi', vagi_body[0:4] + vagi_body[8:] + b'')
    # simple direct build matching read_vagi: name(8) size(4) top(4) offsets(4*n) entries
    n = len(sample_offsets)
    vag = b'IECSigaV' + struct.pack('<II', 0, n - 1) + b''.join(struct.pack('<I', 16 + 4 * n + 8 * k) for k in range(n)) + ents
    vag = vag[:8] + struct.pack('<I', len(vag)) + vag[12:]
    setb_body = struct.pack('<5I', 0, 0x14, 0, 0x1C, 8) + struct.pack('<HBB', 0x32, len(tones) - 1, 0xFF) + b''.join(tone(s, v) for s, v in tones)
    setb = b'IECSbteS' + struct.pack('<I', 8 + 4 + len(setb_body) - 0)[:4] + setb_body
    setb = setb[:8] + struct.pack('<I', len(setb)) + setb[12:]
    return chunk('Vers', b'\0\0\2\0') + chunk('Head', bytes(52)) + vag + setb

events = bytes([0, 0x90, 0, 0, 0x7F, 0x81, 0x48, 0x90, 0, 1, 0x1E, 0, 0xFF])      # key 0 loud, key 1 quiet 200 ticks later
sq = build_sq({1: events})
hd = build_hd([(0, 127), (0, 30)], [0])
blocks = B.parse_sq(sq)
ok = len(blocks) == 1 and blocks[0]['block'] == 1 and blocks[0]['volume'] == 127 and blocks[0]['resolution'] == 1000
ev = B.parse_events(blocks[0]['data'])
ok = ok and ev == [(0, 0x90, 0, 127, 0, None), (200, 0x90, 1, 30, 0, None), (200, 0xFF, 0, 0, 0, None)]
tones = B.parse_tones(hd)
ok = ok and len(tones) == 1 and [t['volume'] for t in tones[0]] == [127, 30] and [t['sample'] for t in tones[0]] == [0, 0]
print('  parse', 'ok' if ok else 'FAILED')
pcm = [1000] * 100
out = B.render_block(ev, tones, lambda n: (pcm, 44100), 1000, 127)
ok = ok and len(out) == int(0.2 * 44100) + 100 and out[0] == 1000 and abs(out[int(0.2 * 44100) + 5] - int(1000 * (30 / 127.0) ** 2)) <= 1
cev = B.parse_events(bytes([0, 0xB0, 0, 1, 0x0E, 0x87, 0x68, 0xE8, 3, 0x81, 0x48, 0x90, 0, 3, 0x1E, 0, 0xFF]))
ok = ok and cev[0] == (0, 0xB0, 1, 0x0E, 0, (1000, 1000)) and cev[1] == (200, 0x90, 3, 30, 0, None) and cev[2][1] == 0xFF
print('  control event', 'ok' if ok else 'FAILED')
print('  render', 'ok' if ok else 'FAILED', len(out))
try:
    B.parse_events(bytes([0, 0x77, 1, 2]))
    ok = False
except ValueError:
    pass
# several sets (like the big bank): directory u32 highest set, then offsets; each set = u32 8, record header, records
sets = [[(0, 100), (1, 90)], [(2, 80)], [(3, 70), (4, 60), (5, 50)]]
body = struct.pack('<5I', 0, 0x14, len(sets) - 1, 0, 0)[:12]
dirsz = 4 + 4 * len(sets)
offs, blob, pos = [], b'', 0x14 + dirsz
for st in sets:
    offs.append(pos)
    rec = struct.pack('<IHBB', 8, 0x32, len(st) - 1, 0xFF) + b''.join(tone(a, v) for a, v in st)
    blob += rec; pos += len(rec)
chunk_body = struct.pack('<I', 0) + struct.pack('<I', 0x14) + struct.pack('<I', len(sets) - 1) + b''.join(struct.pack('<I', o) for o in offs) + blob
setb = b'IECSbteS' + struct.pack('<I', 12 + len(chunk_body)) + chunk_body
hd2 = chunk('Vers', b'\0\0\2\0') + setb
got = B.parse_tones(hd2)
ok = ok and [[(t['sample'], t['volume']) for t in s] for s in got] == sets
print('  tone sets', 'ok' if ok else 'FAILED')
print('ok   sound sequences parse and render' if ok else 'FAIL sound sequences')
sys.exit(0 if ok else 1)
