"""Spanish layers (0.54): the battle/title mod and the button prompts on the Spanish pictures are hidden mods that follow the Spanish text,
always sit above everything, and are made again when the prompts or the discs change."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import p3fes_launcher as L

d = tempfile.mkdtemp(); L.DIR = d; L.CFG = os.path.join(d, 'cfg.json')
L.lm_dir = lambda: d
L.pr_dir = lambda: d
mods = []
L.lm_load = lambda: list(mods)
L.lm_save = lambda lst: (mods.clear(), mods.extend(lst))
iso = os.path.join(d, 'o.iso'); es = os.path.join(d, 'o[T-Esp].iso')
open(iso, 'wb').write(b'a'); open(es, 'wb').write(b'b')
L.es_find = lambda: es
L.find_iso = lambda: iso
L.lm_locate = lambda i: ('loc',)
L.read_keys = lambda: {'cross': 'K'}
L.read_pad = lambda: {}
L.pr_modules_ok = lambda say: True

merged_log = []
class FakeMM:
    @staticmethod
    def plan(iso_, folder, loc=None):
        out = []
        for dp, _d, names in os.walk(folder):
            for n in names:
                out.append({'rel': 'DATA.CVM/' + n, 'ok': True, 'key': n, 'who': os.path.basename(os.path.dirname(folder))})
        return out
    @staticmethod
    def write_overlay(items, size, ovl, iso_=None):
        merged_log.append({i['key']: i['who'] for i in items}); open(ovl, 'wb').write(b'x')
L.lm_modmap = lambda: FakeMM
L.lm_write_pokes = lambda *a: None

def mod(i, on=True):
    os.makedirs(os.path.join(d, i, 'files'), exist_ok=True)
    open(os.path.join(d, i, 'files', 'same.bin'), 'wb').write(b'1')
    return {'id': i, 'kind': 'DISC', 'name': i, 'enabled': on, 'fit': 1, 'total': 1, 'skipped': []}

# layers sit above everything whatever the list says, and follow the Spanish mod
mods[:] = [mod('spanish'), mod('prompts'), mod('spanishprompts'), mod('spanishbattle')]
L.lm_rebuild(iso, ('loc',))
assert merged_log[-1]['same.bin'] == 'spanishbattle', merged_log[-1]
mods[0]['enabled'] = False
L.lm_rebuild(iso, ('loc',))
assert merged_log[-1]['same.bin'] == 'prompts', merged_log[-1]       # Spanish off: the layers are off with it
mods[0]['enabled'] = True
mods[:] = [m for m in mods if m['id'] not in L.ES_LAYERS]

# sync: makes both layers from the discs and the prompts, hidden, once
built = []
import p3fes_spanish_battle as B, p3fes_spanish_prompts as SP, p3fes_prompts as P
def fake_battle(i, p, out, prompts=None, report=None):
    built.append(('battle', prompts)); os.makedirs(os.path.join(out, 'files', 'DATA.CVM'), exist_ok=True)
    open(os.path.join(out, 'files', 'DATA.CVM', 'b.bin'), 'wb').write(b'1'); return []
def fake_sp(orig_src, es_src, trans, out, style, keys=None, pad=None, hits=None):
    built.append(('prompts', style)); os.makedirs(os.path.join(out, 'files', 'DATA.CVM'), exist_ok=True)
    open(os.path.join(out, 'files', 'DATA.CVM', 'p.bin'), 'wb').write(b'1'); return {}, [], 1
B.build, SP.build = fake_battle, fake_sp
extracted = []
def fake_extract(i, say, name='src'):
    extracted.append(name); os.makedirs(os.path.join(d, name, 'DATA.CVM', 'CAMP'), exist_ok=True)
    open(os.path.join(d, name, '.done'), 'w').write('ok')
L.pr_extract = fake_extract
L.pr_have_src = lambda: True
L.pr_resolve = lambda setting=None: 'keyboard'
L.pr_built = lambda: {'sig': 'S1'}
os.makedirs(os.path.join(d, 'prompts', 'files'), exist_ok=True)
mods.append(mod('prompts'))
c = L.load_cfg(); c['packed'] = {'lm': {'spanish': 'spanish', 'prompts': 'prompts'}}; L.save_cfg(c)

assert L.es_layers_sync(iso).startswith('Spanish battle'), 'first call builds'
assert [m['id'] for m in mods][:2] == list(L.ES_LAYERS), [m['id'] for m in mods]
assert built == [('battle', os.path.join(d, 'prompts', 'files')), ('prompts', 'keyboard')], built
assert 'src_es' in extracted
assert L.load_cfg()['packed']['lm']['spanishbattle'] == 'spanishbattle', 'hidden like the Spanish mod'
assert 'spanishbattle' not in [m['id'] for m in L.lm_state()['list']], 'hidden from the file mods list'
n = len(built)
assert L.es_layers_sync(iso) == '' and len(built) == n, 'nothing changed: nothing is made again'

# a change of the prompts (new style / keys / controller) makes the layers again
L.pr_built = lambda: {'sig': 'S2'}
L.pr_resolve = lambda setting=None: 'xbox'
assert L.es_layers_sync(iso) and built[-1] == ('prompts', 'xbox')

# PlayStation prompts: no prompts layer, the battle layer is made without a prompts folder
L.pr_resolve = lambda setting=None: 'playstation'
mods[:] = [m for m in mods if m['id'] != 'prompts']
assert L.es_layers_sync(iso) and built[-1] == ('battle', None) and 'spanishprompts' not in [m['id'] for m in mods], (built[-1], [m['id'] for m in mods])

# Spanish switched off (English text): nothing is made, Play is not held up
mods[:] = [dict(m, enabled=False) if m['id'] == 'spanish' else m for m in [mod('spanish'), mod('prompts')]]
n = len(built)
L.pr_built = lambda: {'sig': 'S9'}
assert L.es_layers_sync(iso) == '' and len(built) == n, 'English text must not build the layers'

# without the Spanish mod there is nothing to do
mods[:] = []
assert L.es_layers_sync(iso) == ''
print('ok   Spanish layers: above everything, follow the Spanish text, made again with the prompts')

# Play shows progress text while it makes the pictures, and clears it afterwards
seen = []
L.pr_resolve = lambda setting=None: 'keyboard'
L.pr_signature = lambda style: 'NEW'
L.pr_built = lambda: {'sig': 'OLD'}
L.lm_work['busy'] = False
L.pr_apply = lambda style, say=lambda t: None: (say('Drawing the keyboard buttons…'), seen.append(L.play_progress['msg']), 'ok')[2]
L.es_layers_sync = lambda iso, say=lambda t: None: ''
L.pr_before_play()
assert seen == ['Getting ready: Drawing the keyboard buttons…'] and L.play_progress['msg'] == '', (seen, L.play_progress)
print('ok   Play shows what it is doing while it makes the pictures')
