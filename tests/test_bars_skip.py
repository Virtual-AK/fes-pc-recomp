"""The launcher gives the shower scene its bars itself, so the two cheat words of that movie are left out of the pokes (p3fes_modmap.letterbox_pokes skip)."""
import os, struct, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import p3fes_modmap as M

elf = bytearray(0x100)
elf[0:4] = b'\x7fELF'
struct.pack_into('<I', elf, 28, 52)
struct.pack_into('<HH', elf, 42, 32, 1)
struct.pack_into('<6I', elf, 52, 1, 0x100, 0x5D4000, 0x5D4000, 0x2000, 0x2000)
prog = bytes(elf) + bytes(0x2000)
pn = ('// Fix ID 10\npatch=1,EE,005D4D00,word,00000006\npatch=1,EE,005D4D10,word,00000046\n'
      'patch=1,EE,005D4D40,word,00000006\npatch=1,EE,205D4D10,extended,00000046 // same word, other spelling\n')
with tempfile.TemporaryDirectory() as d:
    c = os.path.join(d, 'cheats'); os.makedirs(c)
    open(os.path.join(c, '94A82AAA.LetterBoxBe-Gone.pnach'), 'w').write(pn)
    all_ = dict(M.letterbox_pokes(prog, d)[0])
    cut = dict(M.letterbox_pokes(prog, d, [0x5D4D00, 0x5D4D10])[0])
assert set(all_) == {0x5D4D00, 0x5D4D10, 0x5D4D40}, all_
assert set(cut) == {0x5D4D40}, cut
assert M._pnach_addr_in('patch=1,EE,105D4D12,extended,0046', {0x5D4D10}) and not M._pnach_addr_in('// patch=1,EE,005D4D00,word,1', {0x5D4D00})
print('ok bars: the cheat words of a padded movie are left out, the other movies keep theirs')
