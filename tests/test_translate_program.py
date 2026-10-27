"""p3fes_translate.py program part: the translation's changes to the game program become a switchable mod (made-up ELF files stand in for the real ones),
and p3fes_pnach_apply.py --weak / --strict."""
import json, os, struct, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', 'tools'))
import p3fes_translate as T

SEGS = [(0x100000, 0x2000), (0x600000, 0x1000), (0x7C8000, 0x6000)]
T.PROG_TABLE_MIN = 3
TABLE = 0x600100   # four file-table entries: size, 0, start sector, two bytes, name


def elf(changes=None):
    segs = []
    for base, size in SEGS:
        b = bytearray((bytes(range(1, 255)) * (size // 254 + 1))[:size])
        for k, nm in enumerate((b'A_001.PAK', b'B_002.PAK', b'C_003.BIN', b'D_004.TBL')):
            if base <= TABLE + 48 * k < base + size:
                e = TABLE - base + 48 * k
                b[e:e + 14 + len(nm) + 1] = struct.pack('<III', 1000 + k, 0, 500 + k) + b'\x00\xdf' + nm + b'\x00'
        for a, w in (changes or {}).items():
            if base <= a < base + size:
                struct.pack_into('<I', b, a - base, w)
        segs.append((base, bytes(b)))
    hdr = bytearray(52)
    hdr[0:4] = b'\x7fELF'; hdr[4] = 1; hdr[5] = 1
    struct.pack_into('<I', hdr, 0x1C, 52)
    struct.pack_into('<HH', hdr, 0x2A, 32, len(segs))
    off = 52 + 32 * len(segs)
    ph, body = b'', b''
    for base, data in segs:
        ph += struct.pack('<8I', 1, off + len(body), base, base, len(data), len(data), 7, 16)
        body += data
    return bytes(hdr) + ph + body


orig = elf()

esp = elf({0x100010: 0x03E00008, 0x100014: 0, 0x600020: 0x12345678, 0x600800: 0xCAFEBABE,
           0x1001D8: 0x11111111,           # a word of the translation's video subtitles
           0x600030: 0x009ACC90,            # a pointer to the translation's movie list
           TABLE + 8: 777, TABLE + 48: 1234, TABLE + 48 * 3 + 8: 4321,   # the Spanish disc's file sizes and sectors
           0x7CA010: 0x00700070,            # layout data above the new video code
           0x7C8010: 0x22222222})           # new video subtitle code
code, data, info = T.program_words(orig, esp)
assert sorted(code) == [0x100010, 0x100014], sorted(code)
assert sorted(data) == [0x600020, 0x600800, 0x7CA010] and data[0x600020][1] == 0x12345678
assert info == {'changed': 11, 'movie': 3, 'table': 3, 'code': 2, 'data': 3}, info
text, info2 = T.program_pnach(orig, esp)
lines = [l for l in text.splitlines() if not l.startswith('//')]
assert len([l for l in lines if l.startswith('patch=1')]) == 2 and len([l for l in lines if l.startswith('patch=0')]) == 3
assert 'patch=1,EE,00100010,word,03E00008 // original instruction ' in text and 'patch=0,EE,00600020,word,12345678' in text
assert '001001D8' not in text and '007C8010' not in text and '00600030' not in text and '00600108' not in text and '00600130' not in text and '00600198' not in text, 'the video subtitle parts must stay out'

# without a file table the tool refuses
T.PROG_TABLE_MIN = 99
try:
    T.program_words(orig, esp); raise AssertionError('should refuse')
except T.ToolError as e:
    assert 'file table' in str(e)
T.PROG_TABLE_MIN = 3

# a code word that jumps into the unknown new code is another version of the translation
bad = elf({0x100010: (2 << 26) | (0x7C9000 >> 2)})
try:
    T.program_words(orig, bad); raise AssertionError('should refuse')
except T.ToolError as e:
    assert 'jumps into new code' in str(e)
# nothing changed / not an ELF
for x, y in ((orig, orig), (orig, b'junk' * 100)):
    try:
        T.program_words(x, y); raise AssertionError('should refuse')
    except T.ToolError:
        pass

# which files need the program
assert T.keep('BTL.CVM/BATTLE/PANEL/BP_RESULT.BIN') is False and T.keep('BTL.CVM/BATTLE/PANEL/BP_RESULT.BIN', core=True)
assert T.keep('DATA.CVM/OPED/OP_TITLE.BIN') is False and T.keep('DATA.CVM/OPED/OP_TITLE.BIN', core=True)
assert not T.keep('DATA.CVM/SFD/X.STR', core=True) and not T.keep('BTL.CVM/BATTLE/CUTIN/E1.BIN', core=True)
assert T.keep('BTL.CVM/SKILL/140.BED') and not T.keep('BTL.CVM/SKILL/140.BED', core=True)
assert T.keep('DATA.CVM/FIELD/X.PAK') and not T.keep('DATA.CVM/FIELD/X.PAK', core=True)

# the registry entry
reg = json.load(open(os.path.join(here, '..', 'tools', 'launcher', 'packed_mods.json')))
bits = [r['bit'] for r in reg if r.get('kind') == 'code']
assert len(bits) == len(set(bits)), 'a switch bit is used twice'
sp = next(r for r in reg if r['id'] == 'spanishprog')
assert sp['bit'] == 23 and sp['hidden'] and sp['follows'] == 'spanish' and sp['strict'] and sp['weak']

# p3fes_pnach_apply.py --weak / --strict
tool = os.path.join(here, '..', 'tools', 'p3fes_pnach_apply.py')
with tempfile.TemporaryDirectory() as d:
    p = lambda n: os.path.join(d, n)
    open(p('a.elf'), 'wb').write(orig)
    open(p('a.pnach'), 'w').write('patch=1,EE,00100010,word,0C040040\n')
    open(p('b.pnach'), 'w').write('patch=1,EE,00100010,word,0C040080\npatch=1,EE,00100020,word,03E00008\npatch=0,EE,00600020,word,12345678\n')
    base = [sys.executable, tool, p('a.elf'), '--mod', 'a:0=' + p('a.pnach'), '--mod', 'b:1=' + p('b.pnach'), '-o', p('o.elf'), '--variants', p('v.txt'), '--entries', p('e.txt')]
    r = subprocess.run(base, capture_output=True, text=True)
    assert r.returncode != 0, 'two mods changing one word must still be refused'
    r = subprocess.run(base + ['--weak', 'b', '--strict', 'b'], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'b gives way to another mod at 1 words' in r.stdout, r.stdout
    v = open(p('v.txt')).read().splitlines()
    c = {l.split()[1]: l.split() for l in v if l.startswith('C')}
    assert c['100010'][4] == '0C040040', 'the weak mod must not keep the shared word'
    assert c['100020'][4] == '03E00008' and c['100020'][3] == '24232221', 'its other words stay'
    dl = [l.split() for l in v if l.startswith('D')]
    assert dl == [['D', '600020', '4', '12345678', '2']], dl     # a strict mod: its start-up write applies for its own bit only
print('ok   p3fes_translate program: code/data words split, video parts and unknown hooks refused, core file rules, registry entry; pnach_apply --weak/--strict')


# Tactics menu: the Spanish names are written over the English strings (16 bytes apart); the pointers stay as they are
def words(raw):
    raw = raw + bytes(-len(raw) % 4)
    return struct.unpack('<%dI' % (len(raw) // 4), raw)
T.PROG_TABLE_MIN = 3
T.PROG_TACTICS = (0x600400, 2, 0x10)
ch_o, ch_e = {0x600400: 0x600500, 0x600404: 0x600510}, {0x600400: 0x600600, 0x600404: 0x600610}
for k, w in enumerate(words(b"Act Freely\0\0\0\0\0\0")): ch_o[0x600500 + 4 * k] = ch_e[0x600500 + 4 * k] = w
for k, w in enumerate(words(b"Knock Down\0\0\0\0\0\0")): ch_o[0x600510 + 4 * k] = ch_e[0x600510 + 4 * k] = w
for k, w in enumerate(words(b"Ir por libre\0\0\0\0")): ch_e[0x600600 + 4 * k] = w
for k, w in enumerate(words(b"Derribar\0\0\0\0\0\0\0\0")): ch_e[0x600610 + 4 * k] = w
_c, d2, _i = T.program_words(elf(ch_o), elf(ch_e))
assert 0x600400 not in d2 and 0x600404 not in d2, 'pointers stay'
raw = b"".join(struct.pack('<I', d2[a][1]) for a in sorted(d2) if 0x600500 <= a < 0x600520)
assert b"Ir por libre" in raw and b"Derribar" in raw, raw
