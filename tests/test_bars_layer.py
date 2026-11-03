"""lm_bars_layer: pads the shower scene once per movie file, skips it when it cannot, and returns the cheat words to leave out."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
import p3fes_launcher as L
import p3fes_movie_bars as B

d = tempfile.mkdtemp()
L.saves_dir = lambda: os.path.join(d, 'p3fes', 'saves'); os.makedirs(L.saves_dir())
mod = os.path.join(L.lm_dir(), 'sbfmv-eng', 'files', 'DATA', 'SFD'); os.makedirs(mod)
open(os.path.join(mod, 'P3CT008.SFD'), 'wb').write(b'x' * 100)
open(os.path.join(mod, 'P3CT019_01.SFD'), 'wb').write(b'y' * 100)
runs = []
def fake_pad(src, out, *a, **k):
    runs.append(os.path.basename(src)); open(out, 'wb').write(b'padded')
B.pad_movie = fake_pad
L.lm_bars_ffmpeg_ok = lambda: True
folders = [os.path.join(L.lm_dir(), 'sbfmv-eng', 'files')]
layer, made = L.lm_bars_layer(folders)
out = os.path.join(layer, 'files', 'DATA', 'SFD', 'P3CT008.SFD')
assert layer and open(out, 'rb').read() == b'padded' and list(made) == ['P3CT008'] and made['P3CT008'] == (0x5D4D00, 0x5D4D10), (layer, made)
assert runs == ['P3CT008.SFD']
L.lm_bars_layer(folders)
assert runs == ['P3CT008.SFD'], 'a second call must reuse the copy'
open(os.path.join(mod, 'P3CT008.SFD'), 'wb').write(b'z' * 120)
L.lm_bars_layer(folders)
assert len(runs) == 2, 'a changed movie is padded again'
def bad(src, out, *a, **k): raise ValueError('the picture is already 448 high')
B.pad_movie = bad
open(os.path.join(mod, 'P3CT008.SFD'), 'wb').write(b'q' * 130)
layer, made = L.lm_bars_layer(folders)
assert not made and 'already 448' in L.lm_work.get('bars', ''), (made, L.lm_work.get('bars'))
assert L.lm_bars_layer([]) == (None, {})
print('ok bars layer: padded once per movie file, redone when it changes, left alone when it cannot be padded')
