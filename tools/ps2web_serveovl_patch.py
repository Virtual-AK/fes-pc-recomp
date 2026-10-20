"""Let the browser game's server (scripts/serve.py) lay a mod on top of the disc image while it serves it, so a mod needs
no 4.5 GB copy of the disc and no rebuild of the game. Patches scripts/serve.py only (no C++ change, no rebuild).
Adds:   serve.py <build dir> <disc image> [port] --overlay mods.ovl
The .ovl file comes from  p3fes_modmap.py overlay GAME.iso MOD_FOLDER -o mods.ovl  (a list of "put these bytes at this
position"). Reads that touch a listed position get the mod's bytes; everything else comes from the untouched disc image.
Mods that move a bigger file to the end of the disc make the served disc longer; the server reports the longer size.
Usage (in the ps2-web-recomp folder): python3 ps2web_serveovl_patch.py [scripts/serve.py]
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'scripts/serve.py'
s = open(p).read()
if 'ps2-overlay-reads' in s:
    print("already patched"); raise SystemExit
UPGRADE = 'ps2-overlay' in s

BLOCK = r'''
# ps2-overlay: lay a mod (.ovl from p3fes_modmap.py overlay) over the disc image while serving it (tools/ps2web_serveovl_patch.py)
OVERLAY = None
if '--overlay' in sys.argv:
    at = sys.argv.index('--overlay')
    OVERLAY = os.path.abspath(sys.argv[at + 1])
    del sys.argv[at:at + 2]
'''
BLOCK2 = r'''

import time
OVL_SEEN = set()
READ_LOG = open(OVERLAY + '.reads.log', 'w', buffering=1) if OVERLAY else None   # ps2-overlay-reads
READ_N = [0]
OVL = []   # (offset, length, position of the bytes inside the .ovl file)
OVL_END = 0
if OVERLAY:
    import struct
    with open(OVERLAY, 'rb') as _f:
        if _f.read(8) != b'P3OVL001':
            sys.exit('not a mod overlay file: ' + OVERLAY)
        _n = struct.unpack('<I', _f.read(4))[0]
        for _i in range(_n):
            _off, _len = struct.unpack('<QI', _f.read(12))
            OVL.append((_off, _len, _f.tell()))
            _f.seek(_len, 1)
            OVL_END = max(OVL_END, _off + _len)


def size_of(path):
    size = os.path.getsize(path)
    return max(size, OVL_END) if (OVL and path == DISC) else size


class OverlayFile:
    """The disc image with the mod laid over it; supports seek and read like a file."""

    def __init__(self, path):
        self.f = open(path, 'rb')
        self.real = os.path.getsize(path)
        self.size = max(self.real, OVL_END)
        self.pos = 0
        self.o = open(OVERLAY, 'rb')

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.f.close()
        self.o.close()

    def seek(self, pos):
        self.pos = pos

    def read(self, n):
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b''
        if READ_LOG and READ_N[0] < 40000:      # ps2-overlay-reads: every disc read the game makes (first 40000)
            READ_N[0] += 1
            READ_LOG.write('%s sector %d count %d\n' % (time.strftime('%H:%M:%S'), self.pos // 2048, (n + 2047) // 2048))
        out = bytearray(n)
        if self.pos < self.real:
            self.f.seek(self.pos)
            got = self.f.read(min(n, self.real - self.pos))
            out[:len(got)] = got
        for k, (off, length, at) in enumerate(OVL):
            lo, hi = max(off, self.pos), min(off + length, self.pos + n)
            if lo < hi:
                if k not in OVL_SEEN:      # ps2-overlay-log: the first time the game reads each part of the mod
                    OVL_SEEN.add(k)
                    try:
                        with open(OVERLAY + '.log', 'a') as lg:
                            lg.write('%s hit part %d of %d: disc offset %d, %d bytes\n' % (time.strftime('%H:%M:%S'), k, len(OVL), off, length))
                    except OSError:
                        pass
                self.o.seek(at + lo - off)
                out[lo - self.pos:hi - self.pos] = self.o.read(hi - lo)
        self.pos += n
        return bytes(out)


def open_file(path):
    return OverlayFile(path) if (OVL and path == DISC) else open(path, 'rb')
'''
READLOG = """        if READ_LOG and READ_N[0] < 40000:      # ps2-overlay-reads: every disc read the game makes (first 40000)
            READ_N[0] += 1
            READ_LOG.write('%s sector %d count %d\\n' % (time.strftime('%H:%M:%S'), self.pos // 2048, (n + 2047) // 2048))
        out = bytearray(n)
        if self.pos < self.real:"""
LOGLOOP = """        for k, (off, length, at) in enumerate(OVL):
            lo, hi = max(off, self.pos), min(off + length, self.pos + n)
            if lo < hi:
                if k not in OVL_SEEN:      # ps2-overlay-log: the first time the game reads each part of the mod
                    OVL_SEEN.add(k)
                    try:
                        with open(OVERLAY + '.log', 'a') as lg:
                            lg.write('%s hit part %d of %d: disc offset %d, %d bytes\\n' % (time.strftime('%H:%M:%S'), k, len(OVL), off, length))
                    except OSError:
                        pass
"""
EDITS = [
    ("BUILD = os.path.abspath(sys.argv[1])\n", BLOCK + "BUILD = os.path.abspath(sys.argv[1])\n"),
    ("\n\nclass Handler(", BLOCK2 + "\n\nclass Handler("),
    ("        self.headers_for(path, os.path.getsize(path))\n", "        self.headers_for(path, size_of(path))\n"),
    ("        size = os.path.getsize(path)\n        match =", "        size = size_of(path)\n        match ="),
    ("        with open(path, 'rb') as f:\n            f.seek(start)", "        with open_file(path) as f:\n            f.seek(start)"),
]
if UPGRADE:
    UP = []
    if 'ps2-overlay-log' not in s:        # version 1 -> 2: log the first read of each part of the mod
        UP += [("OVL = []   # (offset", "import time\nOVL_SEEN = set()\nOVL = []   # (offset"),
               ("        for off, length, at in OVL:\n            lo, hi = max(off, self.pos), min(off + length, self.pos + n)\n            if lo < hi:\n",
                LOGLOOP)]
    # version 2 -> 3: log every disc read
    UP += [("OVL_SEEN = set()\n", "OVL_SEEN = set()\nREAD_LOG = open(OVERLAY + '.reads.log', 'w', buffering=1) if OVERLAY else None   # ps2-overlay-reads\nREAD_N = [0]\n"),
           ("        out = bytearray(n)\n        if self.pos < self.real:", READLOG)]
    for old, new in UP:
        if s.count(old) != 1:
            print("PATCH NOT APPLIED: serve.py has an older overlay patch that does not match; use a fresh scripts/serve.py")
            raise SystemExit(1)
        s = s.replace(old, new)
    open(p, 'w').write(s)
    print("patched (upgraded)", p)
    raise SystemExit
for old, new in EDITS:
    if s.count(old) != 1:
        print("PATCH NOT APPLIED: expected text not found exactly once in serve.py: %r" % old[:50])
        raise SystemExit(1)
    s = s.replace(old, new)
open(p, 'w').write(s)
print("patched", p)
