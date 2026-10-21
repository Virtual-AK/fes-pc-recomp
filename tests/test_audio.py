import os, subprocess, tempfile, shutil
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, '..', 'tools', 'ps2run_audio_patch.py')
src = '/tmp/src/ps2-web-recomp/runtime/src/iop/spu2.cpp'
d = tempfile.mkdtemp()
os.makedirs(d + '/runtime/src/iop')
def run():
    return subprocess.run(['python3', tool, d], capture_output=True, text=True).stdout.strip()
if os.path.exists(src):
    shutil.copy(src, d + '/runtime/src/iop/spu2.cpp')
    assert run() == 'patched (6 edits)', run()
    t = open(d + '/runtime/src/iop/spu2.cpp').read()
    assert 'PS2_VOL_MASTER' in t and 'vol_master / 100' in t
    assert run() == 'already patched'
    tool2 = os.path.join(here, '..', 'tools', 'ps2run_audio2_patch.py')
    r2 = lambda: subprocess.run(['python3', tool2, d], capture_output=True, text=True).stdout.strip()
    assert r2() == 'patched (4 edits)', r2()
    assert run() == 'already patched' and r2() == 'already patched'
    t2 = open(d + '/runtime/src/iop/spu2.cpp').read()
    assert 'PS2_VOL_FX' in t2 and 'PS2_VOL_STREAM' in t2 and 'adma_note' in t2 and '"%s\\\\n"' not in t2
open(d + '/runtime/src/iop/spu2.cpp', 'w').write('nothing here')
assert run().startswith('PATCH NOT APPLIED')
h = open(os.path.join(here, '..', 'tools', 'launcher', 'ui', 'index.html')).read()
assert 'vl-${w}' in h and "['fx','EFFECTS']" in h and "['music','MUSIC']" in h and "['voice','VOICES']" in h and "'AUDIO'" in h
py = open(os.path.join(here, '..', 'tools', 'launcher', 'p3fes_launcher.py')).read()
assert 'PS2_VOL_MASTER' in py and 'PS2_VOL_FX' in py and 'PS2_VOL_MUSIC' in py and 'PS2_VOL_VOICE' in py and '/api/volume' in py
assert 'ps2run_audio_patch.py' in open(os.path.join(here, '..', 'tools', 'p3fes_install.sh')).read()
shutil.rmtree(d)
print('ok audio: patch applies, repeats cleanly, refuses unknown source; launcher volume setting and installer wired')
