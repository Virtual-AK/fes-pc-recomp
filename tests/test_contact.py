#!/usr/bin/env python3
"""p3fes_contact: makes a valid PNG contact sheet of the right size from synthetic PPM frames."""
import os, struct, subprocess, sys, tempfile, zlib
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'tools')
with tempfile.TemporaryDirectory() as t:
    for n in (300, 600, 900, 1200, 1500):
        w, h = 64, 48
        open(os.path.join(t, 'frame_%05d.ppm' % n), 'wb').write(b'P6\n%d %d\n255\n' % (w, h) + bytes([n // 10 % 256, 80, 160]) * (w * h))
    out = os.path.join(t, 'sheet')
    r = subprocess.run([sys.executable, os.path.join(TOOLS, 'p3fes_contact.py'), t, '-o', out, '--cols', '3', '--shrink', '2', '--per-sheet', '4'], capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(out + '_1.png') and os.path.exists(out + '_2.png')
    if ok:
        d = open(out + '_1.png', 'rb').read()
        ok = d[:8] == b'\x89PNG\r\n\x1a\n'
        w, h = struct.unpack('>II', d[16:24])
        ok = ok and w == 3 * (32 + 4) and h == 2 * (24 + 4)          # 4 tiles on 3 columns -> 2 rows
        i = d.index(b'IDAT'); n = struct.unpack('>I', d[i - 4:i])[0]
        ok = ok and len(zlib.decompress(d[i + 4:i + 4 + n])) == h * (1 + w * 3)
    if not ok:
        print(r.stdout[-400:], r.stderr[-400:])
if ok:
    with tempfile.TemporaryDirectory() as t2:
        for n in (300, 600, 900, 1200, 1500, 1800):
            open(os.path.join(t2, 'frame_%05d.ppm' % n), 'wb').write(b'P6\n8 8\n255\n' + bytes(8 * 8 * 3))
        r = subprocess.run([sys.executable, os.path.join(TOOLS, 'p3fes_contact.py'), t2, '-o', os.path.join(t2, 's'), '--from-frame', '600', '--step', '2', '--cols', '2', '--shrink', '1'], capture_output=True, text=True)
        d = open(os.path.join(t2, 's_1.png'), 'rb').read()
        ok = r.returncode == 0 and struct.unpack('>II', d[16:24]) == (24, 24)      # frames 600, 1200, 1800 -> 3 tiles, 2 columns
print('ok   contact sheets are valid PNG files of the right size' if ok else 'FAIL contact')
sys.exit(0 if ok else 1)
