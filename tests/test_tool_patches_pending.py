"""A launcher update that adds a tool patch (0.46): the essential-mods button applies it, then rebuilds the mods game and the PC window."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
import p3fes_launcher as L

d = tempfile.mkdtemp(); L.DIR = d
inst = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'p3fes_install.sh')).read()
assert '--new-patches' in inst and 'ps2run_logkey_patch.py' in inst
assert L.tool_patches_pending() == []                       # no project folder yet: nothing to apply
os.makedirs(os.path.join(d, 'runtime', 'src'))
names = [x for x in inst[inst.index('PATCHES="') + 9:].split('"')[0].split() if x.endswith('.py')]
open(os.path.join(d, '.p3fes_applied'), 'w').write('\n'.join(n for n in names if n != 'ps2run_logkey_patch.py') + '\n')
assert L.tool_patches_pending() == ['ps2run_logkey_patch.py']
open(os.path.join(d, '.p3fes_applied'), 'a').write('ps2run_logkey_patch.py\n')
assert L.tool_patches_pending() == []
# a file made before the newest patch is stale, one made after is not
f = os.path.join(d, 'built'); open(f, 'w').write('x')
t = os.path.getmtime(os.path.join(d, '.p3fes_applied'))
os.utime(f, (t - 100, t - 100)); assert L.tools_newer_than(f)
os.utime(f, (t + 100, t + 100)); assert not L.tools_newer_than(f)
assert not L.tools_newer_than(os.path.join(d, 'missing'))
# an older install has no list: the source itself says whether the Log key patch is in
os.makedirs(os.path.join(d, 'host')); sysf = os.path.join(d, 'host', 'window.cpp'); open(sysf, 'w').write('void poll(){}\n')
assert L.tool_patches_pending() == []   # (list present here)
os.remove(os.path.join(d, '.p3fes_applied'))
assert L.tool_patches_pending() == ['ps2run_logkey_patch.py']
open(sysf, 'w').write('SDL_WINDOWEVENT_CLOSE && g_window\n')
assert L.tool_patches_pending() == []
# an older install has no list: the patched runner source still dates the patch
w = os.path.join(d, 'host', 'window.cpp'); open(w, 'w').write('x')
os.utime(w, (t, t)); os.utime(f, (t - 100, t - 100)); assert L.tools_newer_than(f)
os.utime(f, (t + 100, t + 100)); assert not L.tools_newer_than(f)
print('ok   tool patches added by an update are found, and builds older than them count as stale')
