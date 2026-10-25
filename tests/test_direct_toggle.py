import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
import p3fes_launcher as L

d = tempfile.mkdtemp()
L.DIR = d
L.CFG = os.path.join(d, 'cfg.json')
def touch(p):
    os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w').write('x')
calls = []
L.play_inner = lambda mode, resume=None, mod=False, pcresume=None: (calls.append((mode, resume, mod, pcresume)) or {'ok': True, 'msg': 'started'})

# nothing built: toggle on by default, nothing changes, no note
L.win_exe = lambda: None
assert L.direct_on() is True
r = L.play('browser'); assert calls[-1] == ('browser', None, False, None) and r['msg'] == 'started', (calls, r)

# browser mod built: on -> modded build, with a note; off -> normal build
touch(os.path.join(d, 'build', 'web-' + L.MOD_NAME, 'ps2web.html'))
r = L.play('browser'); assert calls[-1][2] is True and 'Essential mods are on' in r['msg'], (calls, r)
json.dump({'direct_on': False}, open(L.CFG, 'w'))
r = L.play('browser'); assert calls[-1][2] is False and r['msg'] == 'started'
json.dump({}, open(L.CFG, 'w'))
# a browser resume always uses the normal build
r = L.play('browser', resume=3); assert calls[-1] == ('browser', 3, False, None)

# Windows PC window: mod build missing -> normal build and a note that says where it is built; present -> mod build
exe = os.path.join(d, 'winbuild', 'build', 'ps2run.exe'); touch(exe)
L.win_exe = lambda: exe
r = L.play('exe'); assert calls[-1][2] is False and 'not built for the PC window' in r['msg'], r
assert L.active_win_exe() == exe
touch(os.path.join(d, 'winbuild', 'build-mod', 'ps2run.exe'))
r = L.play('exe'); assert calls[-1][2] is True, calls[-1]
assert L.active_win_exe().endswith(os.path.join('build-mod', 'ps2run.exe'))
r = L.play('exe', pcresume='x'); assert calls[-1][2] is True and calls[-1][3] == 'x'
json.dump({'direct_on': False}, open(L.CFG, 'w'))
assert L.active_win_exe() == exe
assert L.mods_state()['direct_on'] is False and L.mods_state()['direct_win'] is True
print('ok direct commands toggle: default on, falls back with a note, browser resume stays normal, PC window picks the mod build')
