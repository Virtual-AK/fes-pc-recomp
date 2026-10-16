#!/usr/bin/env python3
"""`p3fes_field.py fields` writes every model and texture of the field .RWS files and a report without game content."""
import io, os, random, struct, subprocess, sys, tempfile, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_field.py')
with contextlib.redirect_stdout(io.StringIO()):
    import test_rmd_textures as T
from rmd_synth import model
random.seed(4)
pal = [(random.randrange(256), random.randrange(256), random.randrange(256)) for _ in range(16)]
tex = T.build(64, 64, 4, [random.randrange(16) for _ in range(64 * 64)], pal, up16=True)
texdict = T.ch(0x16, T.ch(1, struct.pack('<II', 1, 0)) + tex)
d = model()
size = struct.unpack_from('<I', d, 14 + 4)[0]
clump = d[14:14 + 12 + size]
two = d[:14] + clump + clump + d[14 + 12 + size:]
with tempfile.TemporaryDirectory() as t:
    for name, blob in (('F000_001', two), ('F000_002', texdict)):
        p = os.path.join(t, 'FIELD', 'PACK', name + '.FPC.d')
        os.makedirs(p)
        open(os.path.join(p, name.lower() + '.rws'), 'wb').write(blob)
    out = os.path.join(t, 'out')
    r = subprocess.run([sys.executable, '-I', TOOL, 'fields', t, '-o', out, '--jobs', '1'], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    rep = open(os.path.join(out, 'fields_report.txt')).read()
    assert 'Field files: 2' in rep and 'Models (clumps): 2' in rep, rep
    assert '4-bit, 16-bit upload' in rep, rep
    assert os.path.exists(os.path.join(out, 'F000_001', 'f000_001', 'f000_001_clump1.obj')), os.listdir(out)
    r = subprocess.run([sys.executable, '-I', TOOL, 'fields', t, '-o', out + '2', '--jobs', '2', '--match', 'f000_002'], capture_output=True, text=True)
    assert r.returncode == 0 and 'Field files: 1' in open(os.path.join(out + '2', 'fields_report.txt')).read(), r.stdout + r.stderr
print('ok   field batch exporter writes models, textures and a report')
