import os, sys
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools')
sys.path.insert(0, root)
import p3fes_prompt_glyphs as G

# keyboard key names
assert G.key_label('K') == 'K' and G.key_label('Return') == 'ENTER' and G.key_label('Left Shift') == 'SHIFT'
assert G.key_label('Keypad 5') == '5' and G.key_label('Up') == 'UP' and G.key_label('none') == 'NONE'
# controller names: the same physical button is named differently on each controller
assert G.pad_label('xbox', 'a') == 'A' and G.pad_label('switch', 'a') == 'B' and G.pad_label('switch', 'b') == 'A'
assert G.pad_label('xbox', 'leftshoulder') == 'LB' and G.pad_label('switch', 'leftshoulder') == 'L'
assert G.pad_label('xbox', 'start') == 'MENU' and G.pad_label('switch', 'back') == 'MINUS'
# every letter and digit has both sizes, and every glyph row is as wide as its first
for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789':
    assert c in G.G7 and c in G.G5, c
for name, g in list(G.G7.items()) + list(G.G5.items()):
    assert len({len(r) for r in g}) == 1, name
# a label always fits the box it is given
for lab in ('K', 'ENTER', 'LB', 'ZR', 'MENU', 'A', 'NONE', 'UP'):
    for w, h in ((12, 12), (10, 10), (16, 9), (8, 6)):
        b = G.bitmap(lab, w, h)
        assert len(b[0]) <= max(w, 3) and len(b) <= max(h, 5), (lab, w, h, len(b[0]), len(b))
try:
    import numpy, cv2   # noqa: F401
    import p3fes_prompts as P
    k = P.prompt_labels('keyboard', {'cross': 'Z', 'circle': 'Return'})
    assert k['cross'] == 'Z' and k['circle'] == 'ENTER' and k['square'] == 'J' and k['dleft'] == '<'
    x = P.prompt_labels('xbox', None, {'cross': 'b'})
    assert x['cross'] == 'B' and x['circle'] == 'B' and x['L1'] == 'LB' and 'dleft' not in x
    s = P.prompt_labels('switch')
    assert (s['cross'], s['circle'], s['square'], s['triangle'], s['L1'], s['R1']) == ('B', 'A', 'Y', 'X', 'L', 'R')
    # drawing into a plain picture keeps its size and puts pixels inside the box only
    t = P.Tex.__new__(P.Tex)
    t.w, t.h, t.fmt = 40, 30, 0x00
    t.rgba = numpy.zeros((30, 40, 4), numpy.uint8)
    t.dirty = False
    for style in ('keyboard', 'xbox', 'switch'):
        t.rgba[:] = 0
        P.draw_key(t, (8, 5, 24, 21), 'A', style, 'cross')
        ys, xs = numpy.nonzero(t.rgba[..., 3])
        assert len(xs) and xs.min() >= 8 and xs.max() < 24 and ys.min() >= 5 and ys.max() < 21, style
except ImportError:
    print('numpy / opencv not installed: skipped the drawing checks')
print('ok prompts: key and controller names, glyph sizes, labels and drawing')

# 0.54: Start, Select, L2, R2 and the name entry tabs have labels in every style
import p3fes_prompts as _P
_k = _P.prompt_labels('keyboard', {'l1': 'Q', 'start': 'Return'})
assert _k['start'] == 'ENTER' and _k['L1tab'] == '<Q' and _k['R1tab'] == 'E>' and _k['L2'] == '1' and _k['select'] == 'BACK', _k
_x = _P.prompt_labels('xbox')
assert _x['start'] == 'MENU' and _x['L1tab'] == '<LB' and _x['R2'] == 'RT', _x
assert any(k == ('i_nameent01.spr', 0) for k in _P.FIXED)
print('ok prompts: start / select / L2 / R2 labels and the name entry tabs')
