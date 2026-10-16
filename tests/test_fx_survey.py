#!/usr/bin/env python3
"""The BED survey parses the fixed header layout and writes a report."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_fx.py')

def row(t, off, fl): return struct.pack('<6I', t, off, fl, 0, 0, 0)
def bed(blobs):
    d = bytearray(0x630)
    d[0:4] = b'BED4'; struct.pack_into('<I', d, 4, 0x3030)
    struct.pack_into('<5I', d, 8, 150, 0, len(blobs), 150, 0)
    for r in range(32): d[0x1C + 24 * r:0x1C + 24 * r + 24] = row(0xFE, 0, 0)
    struct.pack_into('<5I', d, 0x31C, 150, 0, 0, 150, 0)
    for r in range(32): d[0x330 + 24 * r:0x330 + 24 * r + 24] = row(0xFE, 0, 0)
    body = b''
    for i, b in enumerate(blobs):
        d[0x1C + 24 * i:0x1C + 24 * i + 24] = row(7, 0x630 + len(body), 0x400)
        body += b
    return bytes(d) + body

with tempfile.TemporaryDirectory() as t:
    os.makedirs(os.path.join(t, 'A', 'B', 'C'))
    for n in range(3):
        blob = b''.join(struct.pack('<4f', 0, 5.0 + n, 0, 1.0) for _ in range(40))
        open(os.path.join(t, 'A', 'B', 'C', 'f%d.BED' % n), 'wb').write(bed([blob, blob[:256]]))
    rep = os.path.join(t, 'r.txt')
    r = subprocess.run([sys.executable, TOOL, 'survey', t, '-o', rep], capture_output=True, text=True)
    txt = open(rep).read() if os.path.exists(rep) else ''
    ok = r.returncode == 0 and '3 BED4 files' in txt and 'Blobs per file: 2 x3' in txt and 'first data at 0x630 x3' in txt and '40.0' not in 'x'
    ok = ok and 'Word tables' in txt
    d = subprocess.run([sys.executable, TOOL, 'dump', os.path.join(t, 'A', 'B', 'C', 'f0.BED'), '-n', '32'], capture_output=True, text=True)
    ok = ok and d.returncode == 0 and '5' in d.stdout
    print(r.stderr, d.stderr)
# element tree: root + 2 elements + parameter blocks
def vec(*a): return struct.pack('<4f', *a)
def element(name, off, pos):
    nm = name.encode().ljust(0x24, b'\0')
    return (vec(0, 0, 0, 1) * 2 + vec(1, 1, 1, 1) + vec(0, 0, 0, 0) + vec(*pos) + vec(0, 0, 0, 1)
            + struct.pack('<fIII', 1.0, 0xFFFFFFFF, 0x80, 0) + vec(0, 1, 0, 0) + struct.pack('<4I', 0, 1, 8, 0)
            + struct.pack('<III', off, 0, 0) + nm)
root = (vec(0, 0, 0, 1) * 2 + vec(1, 1, 1, 1) + vec(0, 0, 0, 0) + vec(0, 5, 0, 1) + vec(0, 0, 0, 1)
        + struct.pack('<fIII', 1.0, 0xFFFFFFFF, 0x80, 0) + vec(0, 1, 0, 0) + struct.pack('<4I', 2, 0, 0x90, 0))
tab = 0x90 + 2 * 0xC0
tree = root + element('R-CRCLE', tab, (0, 1, 2, 1)) + element('D-POINT', tab + 64, (3, 4, 5, 1)) + bytes(64) + bytes(32)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
import p3fes_fx as F
tr = F.parse_nodes(tree, 0, len(tree))
ok = ok and tr is not None and tr['count'] == 2 and [n['name'] for n in tr['nodes']] == ['R-CRCLE', 'D-POINT']
ok = ok and [n['size'] for n in tr['nodes']] == [64, 32] and tr['nodes'][1]['rows'][16:19] == (3.0, 4.0, 5.0)
print('  element tree', 'ok' if ok else 'FAILED')
with tempfile.TemporaryDirectory() as t2:
    os.makedirs(os.path.join(t2, 'X', 'Y', 'Z'))
    fp = os.path.join(t2, 'X', 'Y', 'Z', 'e.BED')
    open(fp, 'wb').write(bed([tree]))
    sh = subprocess.run([sys.executable, TOOL, 'show', fp], capture_output=True, text=True)
    nd = subprocess.run([sys.executable, TOOL, 'nodes', t2, '-o', os.path.join(t2, 'n.txt')], capture_output=True, text=True)
    ok = ok and sh.returncode == 0 and 'R-CRCLE' in sh.stdout and nd.returncode == 0 and 'D-POINT' in open(os.path.join(t2, 'n.txt')).read()
    print(sh.stderr, nd.stderr)
    fd = subprocess.run([sys.executable, TOOL, 'fields', t2, '-o', os.path.join(t2, 'f.txt')], capture_output=True, text=True)
    ok = ok and fd.returncode == 0 and 'R-CRCLE, 64 bytes' in open(os.path.join(t2, 'f.txt')).read()
    print(fd.stderr)
pp = F.parse_params(tree, 0, tr, tr['nodes'][0])
ok = ok and pp is not None and pp['size'] == 64 and len(pp['colours']) >= 2
print('ok   BED survey parses the header layout' if ok else 'FAIL BED survey')
sys.exit(0 if ok else 1)
