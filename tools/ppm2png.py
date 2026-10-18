"""Turns .ppm frames into .png pictures you can open or send (no extra programs needed).
Usage: python3 ppm2png.py frame.ppm [more.ppm ...]    (writes frame.png next to each)
"""
import struct, sys, zlib
def convert(path):
    d = open(path, 'rb').read()
    parts = d.split(None, 4)
    w, h = int(parts[1]), int(parts[2])
    px = d[len(d) - w * h * 3:]
    raw = b''.join(b'\0' + px[y * w * 3:(y + 1) * w * 3] for y in range(h))
    chunk = lambda t, b: struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b))
    out = path.rsplit('.', 1)[0] + '.png'
    open(out, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
                          chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
    print("wrote", out)
if len(sys.argv) < 2:
    print(__doc__); raise SystemExit(1)
for p in sys.argv[1:]:
    convert(p)
