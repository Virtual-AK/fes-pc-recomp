#!/usr/bin/env python3
"""The BF survey reads a folder of synthetic script files and writes a report."""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_bf.py')
with tempfile.TemporaryDirectory() as t:
    os.makedirs(os.path.join(t, 'A', 'B'))
    for n in range(4):
        body = b'FLW0' + struct.pack('<7I', 0x20 + n, 0, 1, 0x40, 8, 0x60, 3) + bytes(32) + b'MSG_SHOW\0' + b'SEL_ON_%d\0' % n
        open(os.path.join(t, 'A', 'B', 's%d.BF' % n), 'wb').write(body.ljust(128, b'\0'))
    open(os.path.join(t, 'A', 'B', 'tiny.BF'), 'wb').write(b'AB')
    rep = os.path.join(t, 'r.txt')
    r = subprocess.run([sys.executable, TOOL, 'survey', t, '-o', rep], capture_output=True, text=True)
    txt = open(rep).read() if os.path.exists(rep) else ''
    h = subprocess.run([sys.executable, TOOL, 'hex', os.path.join(t, 'A', 'B', 's0.BF'), '-n', '32'], capture_output=True, text=True)
    e = tempfile.mkdtemp()
    r2 = subprocess.run([sys.executable, TOOL, 'survey', e, '-o', os.path.join(e, 'x.txt')], capture_output=True, text=True)
# a real-shaped script: header, 3 sections (proc labels, jump labels, instructions)
def lab(name, at): return name.encode().ljust(24, b'\0') + struct.pack('<2I', at, 0)
ins = struct.pack('<5I', 7, 0, 5, 8 | (4 << 16), 9)    # PROC; PUSHI 5; COMM 4; END
tab_at = 0x20 + 48
hdr = struct.pack('<2I4s5I', 0, 0, b'FLW0', 0, 3, 0, 0, 0)[:0x20]
secs = struct.pack('<12I', 0, 32, 1, tab_at, 1, 32, 1, tab_at + 32, 2, 4, 5, tab_at + 64)
flw = bytearray(hdr + secs + lab('start', 0) + lab('lbl', 2) + ins)
struct.pack_into('<I', flw, 4, len(flw) - 8)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
import p3fes_bf as B
pf = B.parse_flw(bytes(flw))
ok0 = pf is not None and set(pf['sections']) == {0, 1, 2}
ins_list = B.instructions(bytes(flw), pf['sections'][2]) if ok0 else []
ok0 = ok0 and [B.OPS[i[1]] for i in ins_list] == ['PROC', 'PUSHI', 'COMM', 'END'] and ins_list[2][2] == 4
with tempfile.TemporaryDirectory() as t3:
    os.makedirs(os.path.join(t3, 'Z'))
    open(os.path.join(t3, 'Z', 'q.bf'), 'wb').write(bytes(flw))
    an = subprocess.run([sys.executable, TOOL, 'analyse', t3, '-o', os.path.join(t3, 'a.txt')], capture_output=True, text=True)
    ds = subprocess.run([sys.executable, TOOL, 'disasm', os.path.join(t3, 'Z', 'q.bf')], capture_output=True, text=True)
    ms = subprocess.run([sys.executable, TOOL, 'messages', t3, '-o', os.path.join(t3, 'm.txt')], capture_output=True, text=True)
    mtxt = open(os.path.join(t3, 'm.txt')).read() if os.path.exists(os.path.join(t3, 'm.txt')) else ''
    ok0 = ok0 and ms.returncode == 0 and 'no message data 1' in mtxt
    atxt = open(os.path.join(t3, 'a.txt')).read() if os.path.exists(os.path.join(t3, 'a.txt')) else ''
    ok0 = ok0 and an.returncode == 0 and '1 files parsed as FLW0' in atxt and 'PROC x1' in atxt and ds.returncode == 0 and 'PUSHI' in ds.stdout
    print(an.stderr, ds.stderr)
# synthetic ELF with a table of 300 code pointers (stride 8: pointer + count)
tab = b''.join(struct.pack('<2I', 0x100100 + 4 * i, i % 5) for i in range(300))
code = bytes(0x1000)
elf = bytearray(0x34 + 32 * 2)
elf[0:4] = b'\x7fELF'; elf[4] = 1; elf[5] = 1
struct.pack_into('<I', elf, 0x1C, 0x34); struct.pack_into('<2H', elf, 0x2A, 32, 2)
off0 = 0x100; off1 = off0 + len(code)
struct.pack_into('<8I', elf, 0x34, 1, off0, 0x100000, 0, len(code), len(code), 5, 0x1000)
struct.pack_into('<8I', elf, 0x34 + 32, 1, off1, 0x200000, 0, len(tab), len(tab), 6, 0x1000)
elf = bytes(elf).ljust(off0, b'\0') + code + tab
tabs = B.pointer_tables(elf)
ok0 = ok0 and tabs and tabs[0][2] == 8 and tabs[0][3] == 300 and tabs[0][0] == off1
with tempfile.TemporaryDirectory() as t4:
    ep = os.path.join(t4, 'x.elf'); open(ep, 'wb').write(elf)
    fr = subprocess.run([sys.executable, TOOL, 'functions', ep, '-o', os.path.join(t4, 'f.txt')], capture_output=True, text=True)
    ok0 = ok0 and fr.returncode == 0 and 'stride 8  length 300' in open(os.path.join(t4, 'f.txt')).read()
    print(fr.stderr)
with tempfile.TemporaryDirectory() as t5:
    ep = os.path.join(t5, 'x.elf'); open(ep, 'wb').write(elf)
    pr = subprocess.run([sys.executable, TOOL, 'peek', ep, '0x200000', '-s', '8', '-n', '3', '-b', '1'], capture_output=True, text=True)
    ok0 = ok0 and pr.returncode == 0 and '00100100' in pr.stdout and pr.stdout.count('\n') == 4
    print(pr.stderr)
ok0 = ok0 and B.mips(0x27BDFFE0, 0) == 'addiu $sp, $sp, -32' and B.mips(0x03E00008, 0) == 'jr $ra' and B.mips(0, 0) == 'nop'
ok0 = ok0 and B.mips(0x2C4201F6, 0) == 'sltiu $v0, $v0, 502' and B.mips(0x8FBF0010, 0) == 'lw $ra, 16($sp)'
ok0 = ok0 and B.mips(0x10400003, 0x1000) == 'beq $v0, $zero, 0x1010' and B.mips(0x0C040000, 0) == 'jal 0x100000'
with tempfile.TemporaryDirectory() as t6:
    cp = os.path.join(t6, 'c.elf')
    e2 = bytearray(elf); e2[off0:off0 + 4] = struct.pack('<I', 0x2C4201F6)
    open(cp, 'wb').write(bytes(e2))
    lr = subprocess.run([sys.executable, TOOL, 'limit', cp, '502'], capture_output=True, text=True)
    cr = subprocess.run([sys.executable, TOOL, 'code', cp, '0x100000', '-n', '2'], capture_output=True, text=True)
    ok0 = ok0 and lr.returncode == 0 and '1 instructions compare' in lr.stdout and 'sltiu $v0, $v0, 502' in cr.stdout
    print(lr.stderr, cr.stderr)
with tempfile.TemporaryDirectory() as t7:
    cp = os.path.join(t7, 'c.elf')
    e3 = bytearray(elf); e3[off0:off0 + 4] = struct.pack('<I', 0x3C033057)
    open(cp, 'wb').write(bytes(e3))
    lu = subprocess.run([sys.executable, TOOL, 'lui', cp, '0x3057'], capture_output=True, text=True)
    sw = subprocess.run([sys.executable, TOOL, 'switch', cp, '300'], capture_output=True, text=True)
    ok0 = ok0 and lu.returncode == 0 and 'lui $v1, 0x3057' in lu.stdout and sw.returncode == 0 and 'candidates' in sw.stdout
    print(lu.stderr, sw.stderr)
with tempfile.TemporaryDirectory() as t8:
    cp = os.path.join(t8, 'c.elf')
    e4 = bytearray(elf)
    e4[off0:off0 + 8] = struct.pack('<2I', 0x3C040021, 0x24841234)     # lui a0,0x21 ; addiu a0,a0,0x1234 -> 0x211234
    open(cp, 'wb').write(bytes(e4))
    rr = subprocess.run([sys.executable, TOOL, 'ref', cp, '0x211234'], capture_output=True, text=True)
    ok0 = ok0 and rr.returncode == 0 and 'referred to by 1 places' in rr.stdout and 'called (jal or j) from 0 places' in rr.stdout
    print(rr.stderr)
with tempfile.TemporaryDirectory() as t9:
    os.makedirs(os.path.join(t9, 'S'))
    open(os.path.join(t9, 'S', 'q.bf'), 'wb').write(bytes(flw))
    ep = os.path.join(t9, 'x.elf'); open(ep, 'wb').write(elf)
    cr = subprocess.run([sys.executable, TOOL, 'comm', ep, os.path.join(t9, 'S'), '-o', os.path.join(t9, 'c.txt'), '--table', '0x200000', '--count', '300'],
                        capture_output=True, text=True)
    ctxt = open(os.path.join(t9, 'c.txt')).read() if os.path.exists(os.path.join(t9, 'c.txt')) else ''
    ok0 = ok0 and cr.returncode == 0 and 'COMM 4:' in ctxt and '1x in 1 files' in ctxt and 'Functions used by scripts: 1' in ctxt
    print(cr.stderr)
st = B.statements(bytes(flw), B.parse_flw(bytes(flw)), {4: 1})
texts = [x[1] for x in st]
ok0 = ok0 and 'fn_4(5)' in texts and 'end' in texts and not any(x[2] for x in st)
st2 = B.statements(bytes(flw), B.parse_flw(bytes(flw)), {4: 3})
ok0 = ok0 and any(x[2] for x in st2)          # too few values on the stack is flagged
with tempfile.TemporaryDirectory() as t10:
    os.makedirs(os.path.join(t10, 'S'))
    fp = os.path.join(t10, 'S', 'q.bf'); open(fp, 'wb').write(bytes(flw))
    lr = subprocess.run([sys.executable, TOOL, 'listing', fp], capture_output=True, text=True)
    mr = subprocess.run([sys.executable, TOOL, 'msgcheck', t10, '-o', os.path.join(t10, 'm.txt')], capture_output=True, text=True)
    ok0 = ok0 and lr.returncode == 0 and 'fn_4(...)' in lr.stdout and mr.returncode == 0 and 'over 0 scripts' in open(os.path.join(t10, 'm.txt')).read()
    print(lr.stderr, mr.stderr)
with tempfile.TemporaryDirectory() as t11:
    os.makedirs(os.path.join(t11, 'S'))
    open(os.path.join(t11, 'S', 'q.bf'), 'wb').write(bytes(flw))
    ep = os.path.join(t11, 'x.elf'); open(ep, 'wb').write(elf)
    bl = subprocess.run([sys.executable, TOOL, 'balance', os.path.join(t11, 'S'), '--exe', ep, '--table', '0x200000', '-o', os.path.join(t11, 'b.txt')], capture_output=True, text=True)
    btxt = open(os.path.join(t11, 'b.txt')).read() if os.path.exists(os.path.join(t11, 'b.txt')) else ''
    print(bl.stderr)
# constant folding: PUSHIS 2, PUSHIS 3, ADD, POP -> ivar? (check through statements)
ins_f = struct.pack('<6I', 7, 29 | (16 << 16), 29 | (1024 << 16), 14, 8 | (7 << 16), 9)
fl = bytearray(hdr + secs + lab('p', 0) + lab('l', 5) + ins_f)
struct.pack_into('<I', fl, 4, len(fl) - 8); struct.pack_into('<I', fl, 0x20 + 40, 6)
fl = bytes(fl)
B.NAMES[9] = 'renamed'
ok0 = ok0 and B.func_name(9) == 'renamed' and B.func_name(10) == 'common_10'
B.NAMES.clear()
# inlining: PUSHIS 5, COMM 7, PUSHREG 0, EQ, IF  ->  if (5 == common_7()):  (function 7 taking 0 values here)
ins_i = struct.pack('<9I', 7, 29 | (5 << 16), 8 | (7 << 16), 4, 22, 28, 9, 0, 0)[:28]
fi = bytearray(hdr + secs + lab('p', 0) + lab('l', 6) + ins_i)
struct.pack_into('<I', fi, 4, len(fi) - 8); struct.pack_into('<I', fi, 0x20 + 40, 7)
fi = bytes(fi)
texts_i = [x[1] for x in B.statements(fi, B.parse_flw(fi), {7: 0})]
ok0 = ok0 and 'if (common_7() == 5):' in texts_i and 'common_7()' not in texts_i

ok0 = ok0 and 'common_7(1040)' in [x[1] for x in B.statements(fl, B.parse_flw(fl), {7: 1})]
ok0 = ok0 and 'Procedures that end with an empty stack' in btxt
with tempfile.TemporaryDirectory() as t12:
    os.makedirs(os.path.join(t12, 'in', 'S'))
    open(os.path.join(t12, 'in', 'S', 'q.bf'), 'wb').write(bytes(flw))
    ep = os.path.join(t12, 'x.elf'); open(ep, 'wb').write(elf)
    xr = subprocess.run([sys.executable, TOOL, 'export', os.path.join(t12, 'in'), '--exe', ep, '--table', '0x200000', '-o', os.path.join(t12, 'out')], capture_output=True, text=True)
    print(xr.stderr)
    lst = os.path.join(t12, 'out', 'S', 'q.bf.script.txt')
    ok0 = ok0 and xr.returncode == 0 and os.path.exists(lst) and 'proc start:' not in 'x' and 'fn_4(' in open(lst).read()
with tempfile.TemporaryDirectory() as t13:
    os.makedirs(os.path.join(t13, 'S'))
    open(os.path.join(t13, 'S', 'q.bf'), 'wb').write(bytes(fl))
    ep = os.path.join(t13, 'x.elf'); open(ep, 'wb').write(elf)
    cx = subprocess.run([sys.executable, TOOL, 'context', os.path.join(t13, 'S'), '--exe', ep, '--table', '0x200000', '7'], capture_output=True, text=True)
    ok0 = ok0 and cx.returncode == 0 and '1 samples of' in cx.stdout and '>>' in cx.stdout
    print(cx.stderr)
ok = ok0 and (r.returncode == 0 and '5 .BF files' in txt and 'FLW0 x4' in txt and 'MSG_SHOW' in txt and '4 files' in txt
      and h.returncode == 0 and 'FLW0' in h.stdout and r2.returncode == 0 and 'No .BF files' in r2.stdout)
print(r.stderr, h.stderr, r2.stderr)
print('ok   BF survey writes a report' if ok else 'FAIL BF survey')
sys.exit(0 if ok else 1)
