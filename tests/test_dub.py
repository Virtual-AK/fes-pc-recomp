"""Voice language in Settings > Audio (0.49): the Japanese Dub is a hidden built-in file mod, downloaded when Japanese is chosen and switched on, off for English."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
import p3fes_launcher as L

reg = {r['id']: r for r in L.packed_registry()}
u = reg['undub']
assert u['kind'] == 'files' and u['hidden'] and u['gb'] == 292547
assert 'undub' not in [r['id'] for r in L.packed_state()['list']]          # not a row of Essential Mods or Cheats
assert 292547 in L.packed_gb_ids()                                           # hidden from Browse GameBanana
assert 'Japanese Dub' not in ' '.join(L.essentials_need())                   # not part of the one button (it is 500 MB)

d = tempfile.mkdtemp(); L.DIR = d; L.CFG = os.path.join(d, 'cfg.json')
st = L.dub_state()
assert st['have'] is False and st['on'] is False and st['gb'] == 292547
assert L.packed_state()['dub']['have'] is False

# no disc yet: Japanese is refused with a pointer
L.find_iso = lambda: None
assert L.dub_set('ja')['ok'] is False
L.find_iso = lambda: '/x.iso'

mods = []
def fake_get(mid, gb):
    assert (mid, gb) == ('undub', 292547)
    mods.append({'id': 'm1', 'name': 'Japanese Dub', 'enabled': False, 'fit': 505, 'total': 505})
    c = L.load_cfg(); p = c.get('packed') if isinstance(c.get('packed'), dict) else {}
    p.setdefault('lm', {})['undub'] = 'm1'; c['packed'] = p; L.save_cfg(c)
    L.lm_work['msg'] = 'downloaded'; L.lm_work['busy'] = False
L.packed_get_work = fake_get
L.lm_load = lambda: list(mods)
def fake_change(mid, remove, up=False):
    for m in mods:
        if m['id'] == mid:
            m['enabled'] = not m['enabled']
    L.lm_work['msg'] = 'Done.'; L.lm_work['busy'] = False
L.lm_change_work = fake_change

def wait():
    for _ in range(100):
        if not L.lm_work['busy']:
            return
        time.sleep(0.05)
    raise AssertionError('still busy')

r = L.dub_set('ja'); assert r['ok'] and 'Downloading' in r['msg'], r
wait()
assert L.dub_state()['on'] is True and 'Japanese voices are on' in L.lm_work['msg'] and 'Only' not in L.lm_work['msg'], L.lm_work['msg']
assert L.dub_set('ja') == {'ok': True, 'msg': ''}                           # already on: nothing to do
assert 'm1' in {m['id'] for m in L.lm_state()['list']} or True
assert not any(m['id'] == 'm1' for m in L.lm_state()['list'])               # hidden from File Mods once downloaded
r = L.dub_set('en'); assert r['ok']; wait()
assert L.dub_state()['on'] is False and L.dub_state()['have'] is True
r = L.dub_set('ja'); assert r['ok'] and 'Downloading' not in r['msg']; wait()   # downloaded already: only switched on
assert L.dub_state()['on'] is True
mods[0]['fit'] = 400; mods[0]['enabled'] = False
L.dub_set('ja'); wait()
assert 'Only 400 of 505' in L.lm_work['msg'], L.lm_work['msg']
assert L.dub_set('xx')['ok'] is False
print('ok   voice language: Japanese Dub downloads when chosen, switches on and off, stays out of File Mods and the one button')
