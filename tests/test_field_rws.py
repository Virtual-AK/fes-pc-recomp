#!/usr/bin/env python3
"""The .RWS lister finds and decodes the textures of a RenderWare texture dictionary."""
import io, os, random, struct, subprocess, sys, tempfile, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
with contextlib.redirect_stdout(io.StringIO()):
    import test_rmd_textures as T
random.seed(3)
pal = [(random.randrange(256), random.randrange(256), random.randrange(256)) for _ in range(256)]
tex = T.build(64, 64, 8, [random.randrange(256) for _ in range(64 * 64)], pal)
texdict = T.ch(0x16, T.ch(1, struct.pack('<II', 1, 0)) + tex)
with tempfile.TemporaryDirectory() as t:
    d = os.path.join(t, 'DATA.CVM', 'FIELD', 'PACK', 'F000_001.FPC.d')
    os.makedirs(d)
    open(os.path.join(d, 'a.rws'), 'wb').write(texdict)
    out = os.path.join(t, 'r.txt')
    png = os.path.join(t, 'png')
    r = subprocess.run([sys.executable, '-I', TOOL, 'rws', t, '--out', out, '-o', png], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    txt = open(out).read()
    assert '1 .RWS files, 1 textures (1 decoded, 0 not)' in txt and 'tex 64x64' in txt, txt
    r2 = subprocess.run([sys.executable, '-I', TOOL, 'rws', t, '--out', out], capture_output=True, text=True)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert '1 .RWS files, 1 textures (sizes only' in open(out).read() and 'tex 64x64, 8-bit' in open(out).read(), open(out).read()
    r = subprocess.run([sys.executable, '-I', TOOL, 'rws', t, '--out', out, '-o', png], capture_output=True, text=True)
    assert any(f.endswith('tex.png') for _, _, fs in os.walk(png) for f in fs)
print('ok   field rws lister decodes the textures of a texture dictionary')
