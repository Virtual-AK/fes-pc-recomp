"""p3fes_translate.py: the Spanish files are pulled out of a patched disc (a tiny made-up disc stands in for the 4.6 GB ones)."""
import os, struct, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import p3fes_translate as T

S = 2048


def rec(name, lba, size, isdir):
    nb = name.encode()
    n = 33 + len(nb)
    n += n % 2
    r = bytearray(n)
    r[0] = n
    r[2:6] = struct.pack('<I', lba); r[6:10] = struct.pack('>I', lba)
    r[10:14] = struct.pack('<I', size); r[14:18] = struct.pack('>I', size)
    r[25] = 2 if isdir else 0
    r[32] = len(nb)
    r[33:33 + len(nb)] = nb
    return bytes(r)


def make_iso(tree):
    """tree: {name: bytes | dict}. Returns the bytes of an ISO9660 image (files padded to whole sectors)."""
    out = {}          # sector -> bytes
    nxt = [18]

    def alloc(data):
        n = max(1, (len(data) + S - 1) // S)
        lba = nxt[0]
        nxt[0] += n
        out[lba] = data
        return lba

    def build(d):
        ents = []
        for name in sorted(d):
            v = d[name]
            if isinstance(v, dict):
                lba, size = build(v)
                ents.append(rec(name, lba, size, True))
            else:
                ents.append(rec(name + ';1', alloc(bytes(v)), len(v), False))
        ents = [rec('\x00', 0, 0, True), rec('\x01', 0, 0, True)] + ents
        data = b''.join(ents)
        assert len(data) < S
        data = data.ljust(S, b'\0')
        return alloc(data), S

    rl, rs = build(tree)
    pvd = bytearray(S)
    pvd[0] = 1; pvd[1:6] = b'CD001'; pvd[6] = 1
    pvd[156:190] = rec('\x00', rl, rs, True)[:34].ljust(34, b'\0')
    img = bytearray(nxt[0] * S)
    img[16 * S:17 * S] = pvd
    for lba, data in out.items():
        img[lba * S:lba * S + len(data)] = data
    return bytes(img)


def cvm(tree):
    return b'CVMH'.ljust(T.CVM_HEAD, b'\0') + make_iso(tree)


def disc(data, btl, exe=b'exe'):
    return make_iso({'DATA.CVM': cvm(data), 'BTL.CVM': cvm(btl), 'SLUS_216.21': exe})


# keep(): the rules
assert T.keep('DATA.CVM/FIELD/X.PAK') and T.keep('DATA.CVM/FONT/FONT0.FNT') and T.keep('DATA.CVM/CAMP/CAMP_MAIN.PAK')
assert not T.keep('DATA.CVM/SFD/P3CT001_01.STR') and not T.keep('DATA.CVM/OPED/OP_TITLE.BIN')
assert T.keep('BTL.CVM/SKILL/140.BED') and T.keep('BTL.CVM/BATTLE/SHUFFLE/SFL_BASE.BIN')
for bad in ('BTL.CVM/BATTLE/MSG.TBL', 'BTL.CVM/BATTLE/AICALC.TBL', 'BTL.CVM/BATTLE/PANEL/BS_INIT.BIN', 'BTL.CVM/SND_BENC/PANEL/BP_ALL.BIN',
            'BTL.CVM/BATTLE/RESULT/BR_BASE.BIN', 'BTL.CVM/BATTLE/CUTIN/PER_EFC0_01_00.BIN', 'SLUS_216.21'):
    assert not T.keep(bad), bad
assert len(T.BTL_KEEP) == 22

d = tempfile.mkdtemp()
orig = os.path.join(d, 'game.iso'); esp = os.path.join(d, 'game[T-Esp].iso')
a_data = {'FIELD': {'A.PAK': b'a' * 3000, 'B.PAK': b'b' * 100}, 'FONT': {'FONT0.FNT': b'f' * 500}, 'OPED': {'OP_TITLE.BIN': b'o' * 700}, 'SFD': {'M.STR': b'm' * 50}}
a_btl = {'BATTLE': {'MSG.TBL': b'1' * 300, 'SHUFFLE': {'SFL_BASE.BIN': b's' * 400}}, 'SKILL': {'140.BED': b'k' * 200}}
b_data = {'FIELD': {'A.PAK': b'A' * 3100, 'B.PAK': b'b' * 100}, 'FONT': {'FONT0.FNT': b'F' * 500}, 'OPED': {'OP_TITLE.BIN': b'O' * 900},
          'SFD': {'M.STR': b'M' * 50, 'NEW.STR': b'n' * 60}, 'NEWDIR': {'N.BIN': b'N' * 70}}
b_btl = {'BATTLE': {'MSG.TBL': b'2' * 310, 'SHUFFLE': {'SFL_BASE.BIN': b'S' * 400}}, 'SKILL': {'140.BED': b'k' * 200}}
open(orig, 'wb').write(disc(a_data, a_btl, b'exe-old'))
open(esp, 'wb').write(disc(b_data, b_btl, b'exe-spanish!'))

todo = T.changed(orig, esp)
got = {r: k for r, _, k in todo}
assert got == {'DATA.CVM/FIELD/A.PAK': 'changed', 'DATA.CVM/FONT/FONT0.FNT': 'changed', 'DATA.CVM/NEWDIR/N.BIN': 'new', 'BTL.CVM/BATTLE/SHUFFLE/SFL_BASE.BIN': 'changed'}, got
# same size, same bytes: not listed (FIELD/B.PAK, SKILL/140.BED); not allowed: OPED, SFD, MSG.TBL, the program

out = os.path.join(d, 'out')
n, total = T.extract(orig, esp, out)
assert n == 4 and total == 3100 + 500 + 70 + 400, (n, total)
assert open(os.path.join(out, 'DATA.CVM', 'FIELD', 'A.PAK'), 'rb').read() == b'A' * 3100
assert open(os.path.join(out, 'DATA.CVM', 'NEWDIR', 'N.BIN'), 'rb').read() == b'N' * 70
assert open(os.path.join(out, 'BTL.CVM', 'BATTLE', 'SHUFFLE', 'SFL_BASE.BIN'), 'rb').read() == b'S' * 400
assert not os.path.exists(os.path.join(out, 'DATA.CVM', 'OPED')) and not os.path.exists(os.path.join(out, 'BTL.CVM', 'BATTLE', 'MSG.TBL'))

# a disc that is not a patched copy of yours
other = os.path.join(d, 'other.iso')
open(other, 'wb').write(make_iso({'DATA.CVM': cvm(a_data), 'OTHER.BIN': b'x'}))
try:
    T.changed(orig, other); raise AssertionError('should refuse')
except T.ToolError as e:
    assert 'patched copy' in str(e)
junk = os.path.join(d, 'junk.iso'); open(junk, 'wb').write(b'\0' * 100000)
try:
    T.changed(orig, junk); raise AssertionError('should refuse')
except T.ToolError:
    pass

# finding the patched copy next to the original
assert T.find_patched([d], orig) == esp
assert T.find_patched([d], esp) is None or T.find_patched([d], esp) != esp
e2 = tempfile.mkdtemp(); open(os.path.join(e2, 'x.iso'), 'wb').write(b'1')
assert T.find_patched([e2], None) is None
print('ok   p3fes_translate: keep rules, changed/new files found and copied, wrong discs refused, patched copy found')
