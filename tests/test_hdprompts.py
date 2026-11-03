"""The battle menu's HD button (p3fes_hdprompts.py): painted into a stand-in pack picture, and the map prefers it."""
import os, sys, tempfile
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools')
sys.path.insert(0, root)
import numpy as np
from PIL import Image
import p3fes_hdprompts as H
import p3fes_hdtex as T

with tempfile.TemporaryDirectory() as d:
    mods, out = os.path.join(d, 'hdmods'), os.path.join(d, 'hd')
    rel = 'Widescreen/BUTTONPROMPT/x.dds'
    pic = os.path.join(mods, 'widescreen_abc', *rel.split('/'))
    os.makedirs(os.path.dirname(pic))
    a = np.zeros((128, 512, 4), np.uint8)
    a[28:92, 32:96] = (50, 68, 78, 127)                  # the round backing
    a[40:80, 40:90] = (148, 214, 236, 128)               # a stand-in for the PlayStation button
    Image.fromarray(a, 'RGBA').save(pic, format='DDS', pixel_format='DXT5')
    table = os.path.join(d, 't.tsv')
    open(table, 'w').write('b614847cee45e44d\t128\t32\t20\t1\t1\t0\t0\t0\twidescreen:' + rel + '\n')
    assert list(H.available(table, mods)) == ['b614847cee45e44d']
    done = H.build(table, mods, out, 'keyboard')
    assert done == [('i_battle04.spr', 0)], done
    new = os.path.join(out, 'widescreen', *rel.split('/'))
    assert os.path.isfile(new)
    b = np.array(Image.open(new).convert('RGBA'))
    assert b.shape == a.shape and (b != a).any()
    assert abs(int(b[60, 64, 0]) - int(a[60, 64, 0])) > 20 or abs(int(b[45, 45, 0]) - int(a[45, 45, 0])) > 20   # the button area changed
    assert (b[:, 200:] == a[:, 200:]).all()                                                                  # nothing outside it
    assert H.build(table, mods, out, 'xbox') and H.build(table, mods, out, 'switch')
    n, _ = T.build_map(table, mods, os.path.join(d, 'm.map'), 'C:/p3fes/hdmods', overlay=out)
    line = [l for l in open(os.path.join(d, 'm.map')) if not l.startswith('#')][0]
    assert n == 1 and '../hd/widescreen/' in line, line
    assert H.build(table, os.path.join(d, 'none'), out) == []
print('ok hd prompts: the button is painted into the HD picture, nothing else changes, and the map uses it first')
