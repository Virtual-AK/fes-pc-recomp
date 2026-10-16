#!/usr/bin/env python3
"""Synthetic test: the 52-byte effect animation layout (type 0x44A07195) exports; NaN rotations get no rotation channel."""
import json, os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rmd_synth import model
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_rmd.py')
NAN = float('nan')

def kf52(t, q, pos, prev):
    return struct.pack('<f4f3f4fI', t, *q, *pos, 1, 1, 1, 0, prev)

# 3 root keyframes (bone 0 rotates, bones 1 and 2 have NaN rotation), then bone 1 gets one more key
body = b''.join([kf52(0, (0, 0, 0, 1), (1, 2, 3), 0xFFFFFFFF), kf52(0, (NAN,) * 4, (0, 0, 0), 0xFFFFFFFF),
                 kf52(0, (NAN,) * 4, (0, 0, 0), 0xFFFFFFFF), kf52(1.0, (NAN,) * 4, (5, 6, 7), 1 * 52)])
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, 'E.RMD'); open(f, 'wb').write(model(anim1=body, anim1_type=0x44A07195))
    out = os.path.join(d, 'out')
    r = subprocess.run([sys.executable, TOOL, 'gltf', f, '-o', out], capture_output=True, text=True)
    print(r.stdout + r.stderr)
    ok = r.returncode == 0
    g = json.load(open(os.path.join(out, 'E.gltf')))
    a = g['animations'][0]
    paths = {}
    for c in a['channels']:
        paths.setdefault(c['target']['node'], set()).add(c['target']['path'])
    j = g['skins'][0]['joints']
    checks = [('effect animation exported', len(g['animations']) == 2),
              ('bone 0 has rotation and translation', paths.get(j[0]) == {'rotation', 'translation'}),
              ('bone 1 (NaN rotation) has translation only', paths.get(j[1]) == {'translation'})]
    for name, good in checks:
        print('  %-52s %s' % (name, 'ok' if good else 'FAILED'))
        ok = ok and good
sys.exit(0 if ok else 1)
