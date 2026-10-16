#!/usr/bin/env python3
"""The field survey groups files by type and by folder contents."""
import os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')

with tempfile.TemporaryDirectory() as t:
    for n in range(2):
        d = os.path.join(t, 'DATA.CVM', 'FIELD', 'PACK', 'F00%d_001.PAC.d' % n)
        os.makedirs(d)
        open(os.path.join(d, 'a.env'), 'wb').write(b'ABCD' + bytes(8))
        open(os.path.join(d, 'b.hbn'), 'wb').write(bytes(16))
    out = os.path.join(t, 'r.txt')
    r = subprocess.run([sys.executable, '-I', TOOL, 'survey', t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    txt = open(out).read()
    assert '.env: 2 files' in txt and '.hbn: 2 files' in txt, txt
    assert '2 folders: .env x1, .hbn x1' in txt, txt
    r = subprocess.run([sys.executable, '-I', TOOL, 'names', t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert 'a.env | 2 | 2 | 2' in open(out).read(), open(out).read()
    r = subprocess.run([sys.executable, '-I', TOOL, 'words', t, 'env', '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert '2 .env files' in open(out).read(), open(out).read()
    r = subprocess.run([sys.executable, '-I', TOOL, 'check', t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert 'FBN' in open(out).read()
    f = os.path.join(t, 'DATA.CVM', 'FIELD', 'PACK', 'F000_001.PAC.d', 'a.env')
    r = subprocess.run([sys.executable, '-I', TOOL, 'dump', f], capture_output=True, text=True)
    assert r.returncode == 0 and '41424344' in r.stdout.lower() or '44434241' in r.stdout, r.stdout
    import struct as _s
    d = _s.pack('<6I', 0x12345678, 0x10001, 2, 0x70, 0, 0x60) + bytes(0x70 * 2)
    d = bytearray(d)
    for k, (i, x) in enumerate(((0xc03, -101.5), (0xc04, 70.25))):
        _s.pack_into('<If', d, 0x18 + 0x70 * k + 8, i, 60.0)
        _s.pack_into('<3f', d, 0x18 + 0x70 * k + 0x50, x, 3.0, -34.5)
    open(os.path.join(t, 'DATA.CVM', 'FIELD', 'PACK', 'F000_001.PAC.d', 'x_050.FBN'), 'wb').write(bytes(d) + bytes(512 - len(d)))
    r = subprocess.run([sys.executable, '-I', TOOL, 'fbn', t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    txt = open(out).read()
    assert '| 0 | 0xc03 | 3075 | 60 | -101.5 | 3 | -34.5 |' in txt and '| 1 | 0xc04 |' in txt, txt
    r = subprocess.run([sys.executable, '-I', TOOL, 'check', t, '-o', out], capture_output=True, text=True)
    assert 'padded to 512 1' in r.stdout, r.stdout
    import struct as _s
    def entry(name, data): return name.encode().ljust(252, b'\0') + _s.pack('<I', len(data)) + data + bytes(-len(data) % 16)
    open(os.path.join(t, 'DATA.CVM', 'FIELD', 'PACK', 'F000_001.FPC'), 'wb').write(entry('a.RMD', b'RMDX' + bytes(30)) + entry('b.TMX', bytes(48)))
    r = subprocess.run([sys.executable, '-I', TOOL, 'split', t, '-o', out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert os.path.exists(os.path.join(t, 'DATA.CVM', 'FIELD', 'PACK', 'F000_001.FPC.d', 'a.RMD')), open(out).read()
    assert 'Split 1 .FPC files' in open(out).read(), open(out).read()
print('ok   field survey groups file types and folder contents')
