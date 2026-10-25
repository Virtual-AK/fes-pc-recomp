import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
import p3fes_launcher as L

# the list of essential mods: unique ids and switch bits, bits inside a 32-bit number
reg = L.packed_registry()
ids = [r['id'] for r in reg]; bits = [r['bit'] for r in reg if r['kind'] == 'code']
assert len(set(ids)) == len(ids) and len(set(bits)) == len(bits) and all(0 <= b < 32 for b in bits), reg
assert {r['kind'] for r in reg} == {'code', 'files', 'cheat'} and all(L.PACKED_ID.match(i) for i in ids)
assert [r['id'] for r in reg if r['kind'] == 'cheat'] == ['classroom', 'sociallink']

d = tempfile.mkdtemp()
L.DIR = d
L.CFG = os.path.join(d, 'cfg.json')
L.saves_dir = lambda: os.path.join(d, 'p3fes', 'saves')
os.makedirs(L.saves_dir())
L.win_exe = lambda: None
L.get_state = lambda: {'state': 'ready'}
def touch(p, text='x'):
    os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w').write(text)
calls = []
L.play_inner = lambda mode, resume=None, mod=False, pcresume=None: (calls.append((mode, resume, mod, pcresume)) or {'ok': True, 'msg': 'started'})

# nothing built, nothing downloaded: normal game, nothing is on except the old Direct Commands default
st = L.packed_state()
assert [r['id'] for r in st['list']] == [r['id'] for r in reg if not r.get('hidden')] and st['mask'] == 0 and st['legacy'] is True
assert not any(r['have'] for r in st['list'] if not r['bundled'])   # only our own cheats (EXP Increase, Run Faster) need no download
r = L.play('browser'); assert calls[-1][2] is False

# an older build (made before there were switches) holds Direct Commands only, always on: the old behaviour
touch(os.path.join(d, 'build', 'web-' + L.MOD_NAME, 'ps2web.html'))
assert L.packed_built() == ({'directcmd': 0}, True) and L.packed_mask() == 0
r = L.play('browser'); assert calls[-1][2] is True and 'Essential mods are on' in r['msg']
L.packed_toggle('directcmd', False); r = L.play('browser'); assert calls[-1][2] is False

# a switchable build: PS2_MODS has one bit per mod that is built in AND on; mods not built in are reported
touch(os.path.join(d, 'games', L.MOD_NAME, 'variants.txt'), 'M directcmd 0\nM modernswitch 1\nM nevertired 4\nC 100 1 0 1\n')
touch(os.path.join(L.packed_dir(), 'partyxp', 'Party.pnach'))
built, legacy = L.packed_built(); assert built == {'directcmd': 0, 'modernswitch': 1, 'nevertired': 4} and not legacy
assert L.packed_mask() == 0 and not L.packed_wanted()           # all off now (Direct Commands was turned off above)
assert 'on' in L.packed_toggle('modernswitch', True)['msg'] and 'on' in L.packed_toggle('nevertired', True)['msg']
assert L.packed_mask() == (1 << 1) | (1 << 4) and L.packed_wanted()
msg = L.packed_toggle('partyxp', True)['msg']; assert 'not in the build' in msg
assert L.packed_mask() == (1 << 1) | (1 << 4), "a mod that is not in the build adds no bit"
st = L.packed_state(); assert st['need_build'] == ['Share Party Experience'] and st['mask'] == 18
r = L.play('browser'); assert calls[-1][2] is True and 'Share Party Experience' in r['msg'], r
L.packed_toggle('modernswitch', False); L.packed_toggle('nevertired', False)
r = L.play('browser'); assert calls[-1][2] is False, "no mod on: the normal game"

# the Windows PC window's mod build older than the newest BUILD is not used (it would not have the new mods)
exe = os.path.join(d, 'winbuild', 'build', 'ps2run.exe'); touch(exe); L.win_exe = lambda: exe
mexe = os.path.join(d, 'winbuild', 'build-mod', 'ps2run.exe'); touch(mexe)
os.utime(mexe, (1, 1))
assert L.win_mod_stale() and not L.direct_available('exe')
os.utime(mexe, None); os.utime(os.path.join(d, 'games', L.MOD_NAME, 'variants.txt'), (1, 1))
assert not L.win_mod_stale() and L.direct_available('exe')

# links: only GameBanana mod pages are accepted
assert L.packed_link('nevertired', 'https://evil.example/mods/5')['ok'] is False
assert L.packed_link('nevertired', 'https://gamebanana.com/mods/123456')['ok'] and L.packed_cfg()['gb']['nevertired'] == 123456
assert [r for r in L.packed_state()['list'] if r['id'] == 'nevertired'][0]['url'] == 'https://gamebanana.com/mods/123456'
assert L.packed_link('nevertired', '')['ok'] and 'nevertired' not in L.packed_cfg()['gb']

# file mods (Fast Start, cheat sheets) are ordinary file mods that start off; toggling goes through the file mod list
assert L.packed_toggle('faststart', True)['ok'] is False        # not downloaded yet
L.lm_save([{'id': 'fs-test', 'kind': 'ZIP', 'name': 'x', 'enabled': False, 'fit': 3, 'total': 3, 'skipped': []}])
c = L.load_cfg(); c['packed']['lm'] = {'faststart': 'fs-test'}; L.save_cfg(c)
row = [r for r in L.packed_state()['list'] if r['id'] == 'faststart'][0]
assert row['have'] and not row['on'] and row['fit'] == 3
print('ok   essential mods list: switch bits, old build still works, mask only holds built-in mods that are on, stale PC window build, links, file mods')


# Always Cut-In and Always Critical share one download but are two switches: the file name decides which file belongs to which
touch(os.path.join(L.packed_dir(), 'alwayscutin', 'Always Cutins.pnach'))
touch(os.path.join(L.packed_dir(), 'alwayscutin', 'Always Critical.pnach'))
assert [os.path.basename(x) for x in L.packed_pnach('alwayscutin')] == ['Always Cutins.pnach']
assert [os.path.basename(x) for x in L.packed_pnach('alwayscrit')] == ['Always Critical.pnach']
assert L.packed_src('alwayscrit') == 'alwayscutin' and L.packed_src('alwayscutin') == 'alwayscutin'
rows = {r['id']: r for r in L.packed_state()['list']}
assert rows['alwayscrit']['cheat'] is True and rows['alwayscutin']['cheat'] is False and rows['alwayscrit']['have'] and rows['alwayscutin']['have']
L.packed_remove('alwayscrit')
assert [os.path.basename(x) for x in L.packed_pnach('alwayscutin')] == ['Always Cutins.pnach'] and not L.packed_pnach('alwayscrit')
print('ok   Always Critical is its own switch and shares the Always Cut-In download')


# a mod page with several zips: the registry words choose the right one (Manual Skill Inheritance: FES, not Portable)
sk = [r for r in L.packed_registry() if r['id'] == 'skillinherit'][0]
assert sk['kind'] == 'code' and sk.get('with_files')
pg = [{'_sFile': 'manual_inheritance_portable.zip'}, {'_sFile': 'manual_inheritance_fes_version.zip'}]
assert L.packed_pick_archive(sk, pg)['_sFile'] == 'manual_inheritance_fes_version.zip'
assert L.packed_pick_archive({}, pg)['_sFile'] == 'manual_inheritance_portable.zip'
print('ok   archive choice by name words')

# widescreen menus: a hidden code mod (switch 7) that follows Settings > Widescreen, never listed
ws = next(r for r in reg if r['id'] == 'widescreen')
assert ws['hidden'] and ws['follows'] == 'widescreen' and ws['bit'] == 7 and ws['kind'] == 'code'
os.makedirs(os.path.join(d, 'games', L.MOD_NAME), exist_ok=True)
open(os.path.join(d, 'games', L.MOD_NAME, 'variants.txt'), 'w').write('M directcmd 0\nM widescreen 7\n')
c = L.load_cfg(); c['widescreen'] = False; L.save_cfg(c)
assert L.packed_mask() & 128 == 0 and 'widescreen' not in [r['id'] for r in L.packed_state()['list']]
assert L.ws_menus_status() == 'built'
c['widescreen'] = True; L.save_cfg(c)
assert L.packed_mask() & 128 == 128
open(os.path.join(d, 'games', L.MOD_NAME, 'variants.txt'), 'w').write('M directcmd 0\n')
assert L.ws_menus_status() == 'nofile'
touch(os.path.join(L.packed_dir(), 'widescreen', 'ws1_core.pnach'))
assert L.ws_menus_status() == 'needbuild' and L.packed_mask() & 128 == 0
# the eleven parts: bits 7..17, each owns the files whose name holds its tag; a P3F_WS_OFF line leaves parts off
parts = [r for r in reg if r.get('follows') == 'widescreen']
assert sorted(r['bit'] for r in parts) == list(range(7, 22)) and all(r['hidden'] and r['source'] == 'widescreen' for r in parts)
touch(os.path.join(L.packed_dir(), 'widescreen', 'ws5_slink.pnach'))
touch(os.path.join(L.packed_dir(), 'widescreen', 'ws10_480p.pnach'))   # ws1 must not take ws10 (the tags end with _)
assert [os.path.basename(f) for f in L.packed_pnach('ws5')] == ['ws5_slink.pnach'] and [os.path.basename(f) for f in L.packed_pnach('widescreen')] == ['ws1_core.pnach'] and [os.path.basename(f) for f in L.packed_pnach('ws10')] == ['ws10_480p.pnach']
open(os.path.join(d, 'games', L.MOD_NAME, 'variants.txt'), 'w').write(''.join('M %s %d\n' % (r['id'], r['bit']) for r in parts))
c['widescreen'] = True; L.save_cfg(c)
assert L.packed_mask() == 0x3FFF80 & ~(1 << 13) & ~(1 << 14) & ~(1 << 9) & ~(1 << 19)   # ws7, ws8, ws3a, ws3c are off by default
home = os.environ.get('HOME'); os.environ['HOME'] = d
open(os.path.join(d, '.p3fes-window-env'), 'w').write('P3F_WS_OFF=ws2, ws5\n')
assert L.ws_parts_off() == {'ws2', 'ws5'} and L.packed_mask() == 0x3FFF80 & ~(1 << 13) & ~(1 << 14) & ~(1 << 9) & ~(1 << 19) & ~(1 << 8) & ~(1 << 11)
open(os.path.join(d, '.p3fes-window-env'), 'w').write('P3F_WS_ON=ws7\n')
assert L.ws_parts_on() == {'ws7'} and L.packed_mask() == 0x3FFF80 & ~(1 << 14) & ~(1 << 9) & ~(1 << 19)
os.environ['HOME'] = home
print('ok   widescreen menus mod follows the setting')
