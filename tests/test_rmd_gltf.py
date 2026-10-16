#!/usr/bin/env python3
"""Synthetic test for `p3fes_rmd.py gltf`: node tree, skin, animation channels and keyframe decoding."""
import json, os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rmd_synth import model
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_rmd.py')

def kf(t, rot, tr, prev):
    return struct.pack('<f4H3HI', t, *rot, *tr, prev)

W, HALF, QUART = 0x7800, 0x7000, 0x7400      # 1.0, 0.5, 0.75 in the animation number format
ident = (0, 0, 0, W)
frames = [kf(0, ident, (W, W, W), 0xFF463FC0)] * 3
frames.append(kf(1.0, (0, HALF, 0, 0x7350), (W, W, W), 1 * 24))   # bone 1 at t=1: y 0.5, w 0.707
frames.append(kf(2.0, ident, (QUART, W, W), 3 * 24))                                   # bone 1 at t=2: x 0.75 of scale
block = struct.pack('<6f', 1, 2, 3, 10, 10, 10)
anim = b''.join(frames) + block

def kf36(t, q, pos, prev):
    return struct.pack('<f4f3fI', t, *q, *pos, prev)

anim1 = b''.join([kf36(0, (0, 0, 0, 1), (1, 2, 3), 0)] * 3 + [kf36(0.5, (0, 0.7071068, 0, 0.7071068), (4, 5, 6), 0 * 36)])

with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, 'M.RMD'); open(f, 'wb').write(model(anim2=anim, anim1=anim1))
    out = os.path.join(d, 'out')
    r = subprocess.run([sys.executable, TOOL, 'gltf', f, '-o', out], capture_output=True, text=True)
    ok = r.returncode == 0
    print(r.stdout + r.stderr)
    g = json.load(open(os.path.join(out, 'M.gltf')))
    blob = open(os.path.join(out, 'M.bin'), 'rb').read()
    def acc(i):
        a = g['accessors'][i]; v = g['bufferViews'][a['bufferView']]
        n = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[a['type']]
        return struct.unpack_from('<%df' % (a['count'] * n), blob, v['byteOffset']), n
    checks = []
    checks.append(('3 nodes with parent links', len(g['nodes']) >= 3 and 1 in g['nodes'][0].get('children', [])))
    checks.append(('one skin with 3 joints', len(g['skins']) == 1 and len(g['skins'][0]['joints']) == 3))
    checks.append(('mesh has joints and weights', 'JOINTS_0' in g['meshes'][0]['primitives'][0]['attributes']))
    anims = g['animations']
    checks.append(('both animation types exported', len(anims) == 2))
    a = anims[1]
    a1 = anims[0]
    c0 = [c for c in a1['channels'] if c['target']['node'] == g['skins'][0]['joints'][0]]
    p0 = {c['target']['path']: a1['samplers'][c['sampler']] for c in c0}
    t1, _ = acc(p0['rotation']['input']); r1, _ = acc(p0['rotation']['output']); x1, _ = acc(p0['translation']['output'])
    checks.append(('type 1: bone 0 has keys at 0 and 0.5 s', [round(t, 3) for t in t1] == [0.0, 0.5]))
    checks.append(('type 1: quaternion and position read as floats', abs(r1[5] - 0.7071) < 1e-3 and abs(x1[3] - 4) < 1e-5))
    ch1 = [c for c in a['channels'] if c['target']['node'] == g['skins'][0]['joints'][1]]
    paths = {c['target']['path']: a['samplers'][c['sampler']] for c in ch1}
    times, _ = acc(paths['rotation']['input'])
    rots, _ = acc(paths['rotation']['output'])
    trans, _ = acc(paths['translation']['output'])
    checks.append(('bone 1 has keyframes at 0, 1, 2 s', [round(t, 3) for t in times] == [0.0, 1.0, 2.0]))
    checks.append(('rotation at t=1 is the decoded unit quaternion', abs(rots[5] - 0.5774) < 3e-3 and abs(rots[7] - 0.8165) < 3e-3))
    checks.append(('translation = offset + scale * value', abs(trans[0] - 11) < 1e-3 and abs(trans[6] - 8.5) < 1e-2))
    for name, good in checks:
        print('  %-52s %s' % (name, 'ok' if good else 'FAILED'))
        ok = ok and good
print('ok   glTF export writes nodes, skin and decoded animation' if ok else 'FAILED glTF export')
sys.exit(0 if ok else 1)
