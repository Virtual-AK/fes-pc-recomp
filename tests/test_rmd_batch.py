#!/usr/bin/env python3
"""Synthetic test for `p3fes_rmd.py batch`: one good model, one broken file, one non-model."""
import os, struct, subprocess, sys, tempfile, json
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_rmd.py')
V = 0x1C020037

def ch(t, p, ver=V):
    return struct.pack('<III', t, len(p), ver) + p

def model(nverts_tri=True):
    frame = struct.pack('<9f3f', 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0) + struct.pack('<iI', -1, 0)
    flist = ch(0x0E, ch(1, struct.pack('<I', 1) + frame))
    verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    gdata = struct.pack('<IIII', 0x2 | 0x4, 1, 3, 1)                       # positions + textured
    gdata += b''.join(struct.pack('<2f', u, v) for u, v in ((0, 0), (1, 0), (0, 1)))
    gdata += struct.pack('<4H', 1, 0, 0, 2)                                  # v2, v1, mat, v3
    gdata += struct.pack('<4f2I', 0, 0, 0, 1, 1, 0)
    gdata += b''.join(struct.pack('<3f', *v) for v in verts)
    mat = ch(7, ch(1, struct.pack('<IIII', 0, 0xFFFFFFFF, 0, 0)))
    geo = ch(0x0F, ch(1, gdata) + ch(8, ch(1, struct.pack('<Ii', 1, -1)) + mat))
    glist = ch(0x1A, ch(1, struct.pack('<I', 1)) + geo)
    atomic = ch(0x14, ch(1, struct.pack('<4I', 0, 0, 5, 0)))
    clump = ch(0x10, ch(1, struct.pack('<3I', 1, 0, 0)) + flist + glist + atomic)
    return struct.pack('<III', 0xF0F000F0, 2, 0x40000000) + b'\0\0' + clump

with tempfile.TemporaryDirectory() as d:
    src = os.path.join(d, 'MODEL', 'SUB'); os.makedirs(src)
    open(os.path.join(src, 'GOOD.RMD'), 'wb').write(model())
    # a model whose RenderWare data comes after a long game-specific chunk (like FP006.RMD)
    m = model()
    hdr, rw = m[:14], m[14:]
    long_chunk = struct.pack('<III', 0xF0F000E0, 1524, 0x40000000) + bytes(1524)
    open(os.path.join(src, 'LONGHDR.RMD'), 'wb').write(hdr + long_chunk + b'\0\0' + rw)   # 2 padding bytes, as in FP006
    # two game chunks with 2 padding bytes between them (like FP00A)
    open(os.path.join(src, 'TWOCHUNKS.RMD'), 'wb').write(hdr + long_chunk + b'\0\0' + long_chunk + rw)
    open(os.path.join(src, 'BAD.RMD'), 'wb').write(model()[:60])
    open(os.path.join(src, 'JUNK.RMD'), 'wb').write(b'\x00' * 200)
    out = os.path.join(d, 'out')
    r = subprocess.run([sys.executable, TOOL, 'batch', os.path.join(d, 'MODEL'), '-o', out, '--jobs', '2'],
                       capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(os.path.join(out, 'SUB', 'GOOD', 'GOOD.obj'))
    rep = json.load(open(os.path.join(out, 'batch_report.json'))) if ok else []
    st = {os.path.basename(x['file']): x['status'] for x in rep}
    ok = ok and st.get('GOOD.RMD') == 'ok' and st.get('LONGHDR.RMD') == 'ok' and st.get('TWOCHUNKS.RMD') == 'ok' and st.get('BAD.RMD') == 'failed' and st.get('JUNK.RMD') == 'failed'
    if not ok:
        print(r.stdout, r.stderr, st)
    print('ok   batch export handles good, truncated and junk files' if ok else 'FAIL batch export')
    sys.exit(0 if ok else 1)
