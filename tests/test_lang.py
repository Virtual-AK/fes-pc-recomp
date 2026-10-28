"""Text language in Settings > Audio (0.50): Spanish is a hidden file mod built from the player's own Spanish copy of the disc."""
import json, os, shutil, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import p3fes_launcher as L
import p3fes_translate as T

assert L.LAUNCHER_VERSION == '0.56'
reg = {r['id']: r for r in L.packed_registry()}
assert reg['spanish']['hidden'] and reg['spanish']['kind'] == 'files'
assert 'spanish' not in [r['id'] for r in L.packed_state()['list']]
assert 'Spanish' not in ' '.join(L.essentials_need())

d = tempfile.mkdtemp(); L.DIR = d; L.CFG = os.path.join(d, 'cfg.json')
assert L.es_state()['have'] is False and L.packed_state()['lang']['on'] is False

# the Spanish copy is never taken for the original disc
iso_dir = tempfile.mkdtemp()
open(os.path.join(iso_dir, 'P3 (USA)[T-Esp].iso'), 'wb').write(b'x')
real_glob = L.glob.glob
L.glob.glob = lambda pat: sorted(real_glob(os.path.join(iso_dir, '*.iso'))) if pat == '/mnt/c/p3fes/*.iso' else []
assert L.find_iso() is None
open(os.path.join(iso_dir, 'P3 (USA).iso'), 'wb').write(b'y')
assert os.path.basename(L.find_iso()) == 'P3 (USA).iso'
L.glob.glob = real_glob

# no disc: refused; disc but no Spanish copy: told how to make it
L.find_iso = lambda: None
assert L.es_set('es')['ok'] is False
L.find_iso = lambda: '/x/orig.iso'
L.es_find = lambda: None
r = L.es_set('es'); assert r['ok'] is False and 'T-Esp' in r['msg'] and 'patcher' in r['msg'], r

# with the copy: built, added hidden, switched on
mods = []
calls = []
def fake_extract(iso, patched, out, progress=None, core=False):
    assert not core, 'the extra title and battle files are not made any more'
    calls.append((iso, patched)); os.makedirs(os.path.join(out, 'DATA.CVM')); open(os.path.join(out, 'DATA.CVM', 'a.bin'), 'wb').write(b'1')
    progress('Copying the Spanish files… 50 of 99'); return 99, 12345
T.extract = fake_extract
T.read_program = lambda path: b'prog'
T.program_pnach = lambda a, b: ('// version %d\npatch=1,EE,00100010,word,03E00008\n' % T.PROG_VERSION, {})
L.packed_dir = lambda: d
class FakeMM:
    @staticmethod
    def plan(iso, folder, loc=None):
        return [{'rel': 'DATA.CVM/a.bin', 'ok': True, 'key': 1}] * 98 + [{'rel': 'DATA.CVM/b.bin', 'ok': False, 'why': 'no such file in the image', 'key': 2}]
L.lm_modmap = lambda: FakeMM
L.lm_locate = lambda iso: ('loc',)
L.lm_rebuild = lambda iso, loc: 98
L.lm_load = lambda: list(mods)
L.lm_save = lambda lst: (mods.clear(), mods.extend(lst))
L.lm_dir = lambda: d
L.es_find = lambda: '/x/orig[T-Esp].iso'

def wait():
    for _ in range(100):
        if not L.lm_work['busy']:
            return
        time.sleep(0.05)
    raise AssertionError('still busy')

r = L.es_set('es'); assert r['ok'] and 'orig[T-Esp].iso' in r['msg'], r
wait()
assert calls == [('/x/orig.iso', '/x/orig[T-Esp].iso')], calls
st = L.es_state()
assert st['have'] and st['on'] and st['fit'] == 98 and st['total'] == 99, st
assert 'Spanish is on (98 files)' in L.lm_work['msg'] and 'SET UP ESSENTIAL MODS' in L.lm_work['msg'], L.lm_work['msg']
assert os.path.exists(os.path.join(d, 'spanishprog', 'esp_program.pnach')) and not os.path.exists(os.path.join(d, 'spanishprog', 'esp_program.pnach.tmp'))
assert [m['id'] for m in mods] == ['spanish'] and not os.path.exists(os.path.join(d, 'spanishcore'))
sp = next(r for r in L.packed_registry() if r['id'] == 'spanishprog')
assert L.packed_active(sp) is True                  # Spanish on and its patch file there
assert L.es_core_missing() is False
assert mods[0]['id'] == 'spanish' and not any(m['id'] == 'spanish' for m in L.lm_state()['list'])   # hidden from File Mods
assert json.load(open(L.CFG))['packed']['lm']['spanish'] == 'spanish'
assert os.path.exists(os.path.join(d, 'spanish', 'files', 'DATA.CVM', 'a.bin'))
assert L.es_set('es') == {'ok': True, 'msg': ''}                                    # already on

# English switches it off; Spanish again switches it on without building again
def fake_change(mid, remove, up=False):
    for m in mods:
        if m['id'] == mid:
            m['enabled'] = not m['enabled']
    L.lm_work['msg'] = 'Done.'; L.lm_work['busy'] = False
L.lm_change_work = fake_change
r = L.es_set('en'); assert r['ok']; wait()
assert L.es_state()['on'] is False and L.es_state()['have'] is True
r = L.es_set('es'); assert r['ok']; wait()
assert L.es_state()['on'] is True and len(calls) == 1
assert L.es_set('xx')['ok'] is False

# a patched disc whose game program is not the one this tool knows: the Spanish text still works, without the game program part
mods.clear(); c = L.load_cfg(); c['packed']['lm'] = {}; L.save_cfg(c)
shutil.rmtree(os.path.join(d, 'spanishprog'))
def odd_pnach(a, b):
    raise T.ToolError('the changes in the game program are not the ones this tool knows (5 words)')
T.program_pnach = odd_pnach
r = L.es_set('es'); wait()
assert 'could not be made' in L.lm_work['msg'] and 'not the ones this tool knows' in L.lm_work['msg'], L.lm_work['msg']
assert [m['id'] for m in mods] == ['spanish'] and not os.path.exists(os.path.join(d, 'spanishprog', 'esp_program.pnach'))
sp = next(r for r in L.packed_registry() if r['id'] == 'spanishprog')
assert L.packed_active(sp) is False
assert L.es_core_missing() is True                  # an upgrade is offered the next time SET UP ESSENTIAL MODS is pressed

# a disc that is not the patched copy: a plain message, nothing added
mods.clear(); L.es_state = L.es_state
def bad_extract(iso, patched, out, progress=None):
    raise T.ToolError('that disc is not a patched copy of yours (the files on it do not match)')
T.extract = bad_extract
c = L.load_cfg(); c['packed']['lm'] = {}; L.save_cfg(c)
r = L.es_set('es'); wait()
assert 'cannot be used' in L.lm_work['msg'] and not mods and not os.path.exists(os.path.join(d, 'spanish'))
print('ok   text language: Spanish builds from the patched disc, stays hidden, switches on and off, refuses a wrong disc')

# launcher language (Settings > Language): page wiring and server endpoint
html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher', 'ui', 'index.html'), encoding='utf-8').read()
for need in ("function langPanel()", "function applyLang()", "'ul:'", "/api/uilang", "'LANGUAGE'", "msel===9", "msel===10", "'ul:es'"):
    assert need in html, need
assert "'VOICE LANGUAGE'" in html and html.count("lang:es") >= 1
assert '"ui_lang"' in open(L.__file__, encoding='utf-8').read() and '/api/uilang' in open(L.__file__, encoding='utf-8').read()
assert "const ORD={help:[0,1,2,4,3],log:[2,3,0,1],about:[0,2,3,1],mods:[0,1,2,3,5,4,6],settings:[9,3,8,1,0,2,7,5,4,6,10]}" in html
