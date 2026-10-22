import os, re, subprocess, shutil
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
js = open(root + '/tools/launcher/ui/music.js').read()
assert 'window.LM' in js and 'setVolume' in js and 'setPaused' in js and 'build' in js
assert not re.search(r"\.(wav|mp3|ogg|flac|adx)\b", js, re.I) and 'fetch(' not in js, 'the music must be made in code, not loaded from files'
if shutil.which('node'):
    r = subprocess.run(['node', '--check', root + '/tools/launcher/ui/music.js'], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
html = open(root + '/tools/launcher/ui/index.html').read()
assert '<script src="music.js">' in html and "['launcher','LAUNCHER']" in html
srv = open(root + '/tools/launcher/p3fes_launcher.py').read()
assert '"launcher"' in srv and 'vol_launcher' in srv
print('ok music: made in code (no audio files), wired to the Audio slider, mute key and server setting')
