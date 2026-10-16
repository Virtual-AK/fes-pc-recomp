#!/usr/bin/env python3
"""Mirrored and scaled frame matrices must survive the split into glTF rotation and scale."""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
import p3fes_gltf as g

def rot_z(a):      # row-vector convention: p' = p * R
    c, s = math.cos(a), math.sin(a)
    return [[c, s, 0], [-s, c, 0], [0, 0, 1]]

def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

def from_quat_scale(q, s):
    """Rebuild the row-vector matrix the way glTF composes it: scale, then rotate (column form T*R*S, transposed)."""
    x, y, z, w = q
    A = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    Ac = [[A[i][j] * s[j] for j in range(3)] for i in range(3)]       # A * diag(s)
    return [[Ac[j][i] for j in range(3)] for i in range(3)]            # transpose back to rows

ok = True
cases = {'plain rotation': rot_z(0.7), 'mirrored x': mul([[-1, 0, 0], [0, 1, 0], [0, 0, 1]], rot_z(0.7)),
         'mirrored and scaled': mul([[-2, 0, 0], [0, 1.5, 0], [0, 0, 1]], rot_z(-1.1))}
for name, R in cases.items():
    q, s = g.decompose_rows(R)
    back = from_quat_scale(q, s)
    err = max(abs(back[i][j] - R[i][j]) for i in range(3) for j in range(3))
    good = err < 1e-9
    ok = ok and good
    print('  %-22s scale %s  round trip error %.1e  %s' % (name, ['%.2f' % v for v in s], err, 'ok' if good else 'FAILED'))
print('ok   mirrored frames export with a negative scale' if ok else 'FAILED mirrored frames')
sys.exit(0 if ok else 1)
