"""Bundled cheats (0.39): EXP Increase (Run Faster was cut in 0.44; bit 23 stays reserved). The patch text is in packed_mods.json, the strength travels as a PS2_POKE number."""
import json, os, sys, tempfile, importlib.util
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', 'tools', 'launcher'))
import p3fes_launcher as L
spec = importlib.util.spec_from_file_location('pa', os.path.join(here, '..', 'tools', 'p3fes_pnach_apply.py'))
PA = importlib.util.module_from_spec(spec); spec.loader.exec_module(PA)

reg = {r['id']: r for r in L.packed_registry()}
exp = reg['expmult']
assert 'runfast' not in reg
assert exp['kind'] == 'code' and exp['cheat'] and exp['bundled']
assert exp['bit'] not in [r['bit'] for r in reg.values() if r['id'] != 'expmult' and r['kind'] == 'code'] and 23 not in [r['bit'] for r in reg.values() if r['kind'] == 'code']

# the patch text parses, nothing is skipped, and the two cheats touch different places
d = tempfile.mkdtemp()
ops = {}
for r in (exp,):
    f = os.path.join(d, r['id'] + '.pnach'); open(f, 'w').write(r['pnach'])
    o, skipped, expects = PA.parse([f])
    assert skipped == 0 and len(o) >= 4 and all(op[2] == 4 for op in o), (r['id'], skipped, o)
    assert len(expects) == len(o) - 1, "every code word notes its original word, the strength cell does not"
    ops[r['id']] = {a: v for _w, a, _s, v in o}
# the strength cell sits where the code reads it (lw / lwc1 with the absolute address) and holds the default
assert ops['expmult'][int(exp['level_addr'], 16)] == 3 and ops['expmult'][0x1fbf68] == 0x8c000000 | (1 << 16) | int(exp['level_addr'], 16)

# levels, default, saved choice
c = tempfile.mkdtemp(); L.DIR = c; L.CFG = os.path.join(c, 'cfg.json')
L.saves_dir = lambda: os.path.join(c, 'p3fes', 'saves'); os.makedirs(L.saves_dir())
assert L.packed_level(exp) == '3'
assert L.packed_set_level('expmult', '10')['ok'] and L.packed_level(exp) == '10'
assert not L.packed_set_level('expmult', '7')['ok'] and not L.packed_set_level('nope', '3')['ok']
st = {r['id']: r for r in L.packed_state()['list']}
assert st['expmult']['bundled'] and st['expmult']['have'] and st['expmult']['level'] == '10' and [x['label'] for x in st['expmult']['levels']] == ['x3', 'x5', 'x10']
assert L.packed_remove('expmult')['ok'] is False

# pokes: only for cheats that are built in AND on; empty for an old build
os.makedirs(os.path.join(c, 'games', L.MOD_NAME))
open(os.path.join(c, 'games', L.MOD_NAME, 'variants.txt'), 'w').write('M expmult 22\n')
assert L.packed_cheat_pokes() == ''
L.packed_set_on('expmult', True)
assert L.packed_cheat_pokes() == '00007000=0000000A' and L.packed_mask() == 1 << 22
L.packed_set_on('expmult', False)
assert L.packed_cheat_pokes() == ''
import re
L.packed_set_on('expmult', True)
assert re.match(r'^[0-9A-F]{8}=[0-9A-F]{8}(,[0-9A-F]{8}=[0-9A-F]{8})*$', L.packed_cheat_pokes())

# the builder writes the bundled text to a file of its own
src = open(os.path.join(here, '..', 'tools', 'p3fes_packed_build.py')).read()
assert 'bundled_%s.pnach' in src and 'm.get("pnach")' in src
print('ok   bundled cheats: patch text parses, no clash, strengths saved, pokes only for built-in cheats that are on')
