"""One-button setup of the essential mods (0.41): downloads mods that have a link, builds the mods game, builds the PC window through vcvars."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
import p3fes_launcher as L

d = tempfile.mkdtemp()
L.DIR = d; L.CFG = os.path.join(d, 'cfg.json')
L.saves_dir = lambda: os.path.join(d, 'p3fes', 'saves'); os.makedirs(L.saves_dir())
L.auto['log'] = os.path.join(d, 'ess.log')
L.get_state = lambda: {'state': 'ready'}
exe = os.path.join(d, 'winbuild', 'build', 'ps2run.exe'); os.makedirs(os.path.dirname(exe)); open(exe, 'w').write('x')
L.win_exe = lambda: exe
L.WINCWD = d
calls = []

def fake_get(mid, gb):
    calls.append(('get', mid, gb))
    p = os.path.join(L.packed_dir(), mid); os.makedirs(p, exist_ok=True); open(os.path.join(p, mid + '.pnach'), 'w').write('x')
    L.lm_work['busy'] = False; L.lm_work['msg'] = 'got ' + mid
L.packed_get_work = fake_get

def fake_run(cmd, logf, cwd=None):
    calls.append(('run', os.path.basename(cmd[1]) if cmd[0] != 'cmd.exe' else 'cmd', cmd))
    if cmd[0] != 'cmd.exe':   # the mods build writes the switch table the launcher reads
        g = os.path.join(d, 'games', L.MOD_NAME); os.makedirs(g, exist_ok=True)
        names = [r for r in L.packed_registry() if r.get('kind') == 'code' and L.packed_pnach(r['id'])]
        open(os.path.join(g, 'variants.txt'), 'w').write(''.join('M %s %d\n' % (r['id'], r['bit']) for r in names))
    else:
        m = os.path.join(d, 'winbuild', 'build-mod'); os.makedirs(m, exist_ok=True); open(os.path.join(m, 'ps2run.exe'), 'w').write('x')
    return 0
L.auto_run = fake_run
L.vcvars_win = lambda: 'C:\\VS\\VC\\Auxiliary\\Build\\vcvars64.bat'
L.to_win = lambda p: 'C:\\' + os.path.basename(p)

# the mods ship with their GameBanana numbers, so every non-cheat mod is a download, then the two builds
need = L.essentials_need()
assert set(n for n in need if n.startswith('download')) == {'download ' + n for n in ('Direct Commands', 'Modern Persona Switch', 'Always Cut-In', 'Share Party Experience', 'Never Tired', 'Manual Skill Inheritance', 'Fast Start', 'Classroom Cheat Sheet', 'Social Link Cheat Sheet')}, need
assert 'build the essential mods game' in need and 'build the PC window' in need
assert L.packed_gb('alwayscrit') == L.packed_gb('alwayscutin') == 704069 and L.packed_gb('nevertired') == 474418
# a player's own link wins over the built-in one
L.packed_link('nevertired', 'https://gamebanana.com/mods/123456')
assert L.packed_gb('nevertired') == 123456

L.essentials_work()
assert L.auto['state'] == 'done', L.auto
kinds = [c[:2] for c in calls]
gets = [c for c in kinds if c[0] == 'get']
assert len(gets) == 9 and ('get', 'nevertired') in gets and ('get', 'faststart') in gets, kinds
assert kinds[-2] == ('run', 'p3fes_packed_build.py') and kinds[-1] == ('run', 'cmd'), kinds
assert 'No GameBanana link yet' not in L.auto['msg'], L.auto['msg']   # every essential mod and cheat now has its number
wrap = open(os.path.join(d, 'p3fes', '_essentials_win.bat'), newline='').read()
assert 'vcvars64.bat' in wrap and 'p3fes_win_mod.bat' in wrap and wrap.count('\r\n') == wrap.count('\n') > 3, wrap

# a second run with nothing to do says so and runs nothing
calls.clear()
L.packed_lm = lambda mid: {'id': 'x'}      # pretend the file mod (Fast Start) is there too
assert L.essentials_need() == [], L.essentials_need()
L.essentials_work()
assert calls == [] and L.auto['state'] == 'done', calls

# the state the page shows
st = L.packed_state()
assert 'auto' in st and st['auto']['busy'] is False and isinstance(st['auto']['need'], list)
# start refuses while running
L.auto['busy'] = True
assert L.essentials_start()['ok'] is False

# file mods owned by Essential Mods / Cheats are hidden from FILE MODS, and their GameBanana pages from BROWSE GAMEBANANA
L.packed_lm = L.__dict__['packed_lm']
L.lm_save([{'id': 'fs-x', 'kind': 'ZIP', 'name': 'Fast Start', 'enabled': True, 'fit': 1, 'total': 1, 'skipped': []},
           {'id': 'mine', 'kind': 'ZIP', 'name': 'My own', 'enabled': True, 'fit': 1, 'total': 1, 'skipped': []}])
c = L.load_cfg(); c.setdefault('packed', {}).setdefault('lm', {})['faststart'] = 'fs-x'; L.save_cfg(c)
assert [m['id'] for m in L.lm_state()['list']] == ['mine'] and L.lm_state()['on'] == 1
assert 390790 in L.packed_gb_ids() and 704069 in L.packed_gb_ids() and 123456 in L.packed_gb_ids()
L.gb_cache.update(mods=[{'id': 390790, 'name': 'Fast Start', 'by': 'x', 'cat': 'c', 'likes': 1, 'views': 1, 'date': 1}, {'id': 5, 'name': 'Other', 'by': 'y', 'cat': 'c', 'likes': 1, 'views': 1, 'date': 2}], t=time.time(), err='')
assert [m['id'] for m in L.gb_view()['mods']] == [5]
L.lm_work['busy'] = True; L.gb_install_work(390790); assert 'Essential Mods' in L.lm_work['msg'] and L.lm_work['busy'] is False
print('ok   one-button essential mods setup: downloads with links, mods build, PC window build through vcvars, missing links reported')
