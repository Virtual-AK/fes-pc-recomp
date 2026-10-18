"""Fix for the half-drawn cut-in portraits (part 1 of 3: the VU interpreter, used by PS2_VU_EXACT=1 and PS2_VU_INTERPRET=1).
On the real PS2 vector unit a conditional branch (IBEQ, IBNE, IBLTZ, IBGTZ, IBLEZ, IBGEZ) that comes right after an integer
instruction (IADDIU, ISUBIU, IADD, ISUB, IADDI, IAND, IOR) which changed one of its registers still sees the OLD value of that register.
The game's polygon program counts down with "ISUBIU vi5,vi5,3" followed at once by "IBEQ vi5,vi2": with the old value the loop writes all four
corners of a portrait, with the new value it stops one corner early and the quad loses a corner.
PS2_VU_BRANCHNEW=1 switches the fix off (old behaviour) for comparing.
Usage (in the ps2-web-recomp folder): python3 ps2run_vubranch_patch.py [runtime/src/vu_micro.cpp]
Safe to run twice. Rebuild afterwards (native: ninja -C build/native-p3fes ps2run)
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/vu_micro.cpp'
s = open(p).read()
if 'g_branch_old' in s:
    print("already patched"); raise SystemExit
G = 'Vu0Regs g_vu1;\n'
L = 'void lower(Unit &u, std::uint32_t w, std::uint32_t pc, std::uint32_t &npc, bool &branch) {\n'
STEP = '        const std::uint32_t current = pc;\n'
CASES = [
    ('    case 0x28: if (r.vi[is] == r.vi[it]) branch_to(target); break;', '    case 0x28: if (bvi(r, is) == bvi(r, it)) branch_to(target); break;'),
    ('    case 0x29: if (r.vi[is] != r.vi[it]) branch_to(target); break;', '    case 0x29: if (bvi(r, is) != bvi(r, it)) branch_to(target); break;'),
    ('    case 0x2C: if (static_cast<std::int16_t>(r.vi[is]) < 0) branch_to(target); break;', '    case 0x2C: if (static_cast<std::int16_t>(bvi(r, is)) < 0) branch_to(target); break;'),
    ('    case 0x2D: if (static_cast<std::int16_t>(r.vi[is]) > 0) branch_to(target); break;', '    case 0x2D: if (static_cast<std::int16_t>(bvi(r, is)) > 0) branch_to(target); break;'),
    ('    case 0x2E: if (static_cast<std::int16_t>(r.vi[is]) <= 0) branch_to(target); break;', '    case 0x2E: if (static_cast<std::int16_t>(bvi(r, is)) <= 0) branch_to(target); break;'),
    ('    case 0x2F: if (static_cast<std::int16_t>(r.vi[is]) >= 0) branch_to(target); break;', '    case 0x2F: if (static_cast<std::int16_t>(bvi(r, is)) >= 0) branch_to(target); break;'),
]
bad = [x for x in [G, L] if s.count(x) != 1] + [o for o, n in CASES if s.count(o) != 1] + ([STEP] if s.count(STEP) != 2 else [])
if bad:
    print("PATCH NOT APPLIED: vu_micro.cpp does not look like the expected source"); raise SystemExit(1)
for o, n in CASES:
    s = s.replace(o, n, 1)
s = s.replace(G, G + '''// VI registers as they were before the previous instruction, and whether that instruction was an integer ALU op
std::uint16_t g_vb_prev[16], g_vb_cur[16];
bool g_vb_prev_alu = false, g_vb_cur_alu = false;
const bool g_branch_old = std::getenv("PS2_VU_BRANCHNEW") == nullptr;

bool int_alu(std::uint32_t lo, std::uint32_t hi) {
    if (hi & 0x80000000u) return false;
    const std::uint32_t op = lo >> 25;
    if (op == 0x08 || op == 0x09) return true;
    if (op != 0x40) return false;
    const std::uint32_t f = lo & 63u;
    return f == 0x30 || f == 0x31 || f == 0x32 || f == 0x34 || f == 0x35;
}

void vb_step(const Vu0Regs &r, std::uint32_t steps, std::uint32_t lo, std::uint32_t hi) {
    if (steps == 0) {
        std::memcpy(g_vb_cur, r.vi, sizeof g_vb_cur);
        g_vb_cur_alu = false;
    }
    std::memcpy(g_vb_prev, g_vb_cur, sizeof g_vb_prev);
    g_vb_prev_alu = g_vb_cur_alu;
    std::memcpy(g_vb_cur, r.vi, sizeof g_vb_cur);
    g_vb_cur_alu = int_alu(lo, hi);
}

std::uint16_t bvi(const Vu0Regs &r, unsigned k) {
    if (g_branch_old && g_vb_prev_alu) return g_vb_prev[k];
    return r.vi[k];
}
''', 1)
s = s.replace(STEP, STEP + '        vb_step(r, steps, lo, hi);\n')
open(p, 'w').write(s)
print("patched (VU branch reads the old integer register value)")
