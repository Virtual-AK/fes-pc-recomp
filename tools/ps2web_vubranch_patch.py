"""Fix for the half-drawn cut-in portraits (part 2 of 2: the browser's VU compiler, runtime/src/vu_jit.cpp).
Same rule as ps2run_vubranch_patch.py: a conditional branch right after an integer instruction that changed one of its registers sees the OLD value.
The compiler saves the old value in a spare local when the next instruction is such a branch, and the branch uses it.
Usage (in the ps2-web-recomp folder): python3 ps2web_vubranch_patch.py [runtime/src/vu_jit.cpp]
Safe to run twice. Rebuild afterwards (web: scripts/build_web.sh p3fes)
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/vu_jit.cpp'
s = open(p).read()
if 'bvi_dest' in s:
    print("already patched"); raise SystemExit
E_OLD = 'kT, kSign, kExp, kVi0,'
E_NEW = 'kT, kSign, kExp, kBvi, kVi0,'
V_OLD = '    void vi(unsigned i) {\n        if (!i) {\n            c_.i32c(0);\n            return;\n        }\n        vi_used_ |= 1u << i;\n        c_.get(kVi0 + i);\n    }\n'
V_NEW = V_OLD + '''
    // Register written by the integer instruction at pc when the next instruction is a conditional branch that reads it (-1 if none).
    // The branch must see the value from before that write, so the old value is kept in kBvi.
    int bvi_dest(std::uint32_t pc) const {
        const std::uint32_t lo = word(pc), hi = word(pc + 4);
        if (hi & 0x80000000u) return -1;
        unsigned d = 0;
        const std::uint32_t op = lo >> 25;
        if (op == 0x08 || op == 0x09) {
            d = (lo >> 16) & 15u;
        } else if (op == 0x40) {
            const std::uint32_t f = lo & 63u;
            if (f == 0x30 || f == 0x31 || f == 0x34 || f == 0x35) d = (lo >> 6) & 15u;
            else if (f == 0x32) d = (lo >> 16) & 15u;
            else return -1;
        } else {
            return -1;
        }
        if (!d) return -1;
        const std::uint32_t next = (pc + 8u) & kMask;
        if (!in_.count(next)) return -1;
        const std::uint32_t nlo = word(next), nhi = word(next + 4);
        if (nhi & 0x80000000u) return -1;
        const std::uint32_t nop = nlo >> 25;
        const unsigned is = (nlo >> 11) & 15u, it = (nlo >> 16) & 15u;
        const bool reads = (nop == 0x28 || nop == 0x29) ? (is == d || it == d) : (nop >= 0x2C && nop <= 0x2F && is == d);
        if (!reads) return -1;
        const auto at = lowers_.find(next);
        if (at == lowers_.end() || !at->second.supported) return -1;
        for (const auto &e : lowers_)
            if (e.second.branch && e.second.target == next) return -1;
        return static_cast<int>(d);
    }

    // Read a register for a branch compare at pc
    void vib(unsigned reg, std::uint32_t pc) {
        const std::uint32_t prev = (pc - 8u) & kMask;
        if (reg && in_.count(prev) && bvi_dest(prev) == static_cast<int>(reg)) {
            c_.get(kBvi);
            return;
        }
        vi(reg);
    }
'''
B1_OLD = '''    case 0x28:
    case 0x29:
        vi(is);
        vi(it);
        c_.op((w >> 25) == 0x28 ? kOpEq : kOpNe);'''
B1_NEW = '''    case 0x28:
    case 0x29:
        vib(is, pc);
        vib(it, pc);
        c_.op((w >> 25) == 0x28 ? kOpEq : kOpNe);'''
B2_OLD = '''        static const std::uint8_t kCompare[4] = {kOpLtS, kOpGtS, kOpLeS, kOpGeS};
        vi(is);'''
B2_NEW = '''        static const std::uint8_t kCompare[4] = {kOpLtS, kOpGtS, kOpLeS, kOpGeS};
        vib(is, pc);'''
I_OLD = '    upper_pre(u, flags_live);\n    if (hi & 0x80000000u) {\n        c_.get(kR);\n        c_.i32c(lo);\n        c_.store(kOffI);'
I_NEW = '''    upper_pre(u, flags_live);
    if (!(hi & 0x80000000u) && li.supported) {
        const int bd = bvi_dest(pc);
        if (bd >= 0) {
            vi(static_cast<unsigned>(bd));
            c_.set(kBvi);
        }
    }
    if (hi & 0x80000000u) {
        c_.get(kR);
        c_.i32c(lo);
        c_.store(kOffI);'''
for o in [E_OLD, V_OLD, B1_OLD, B2_OLD, I_OLD]:
    if s.count(o) != 1:
        print("PATCH NOT APPLIED: vu_jit.cpp does not look like the expected source"); raise SystemExit(1)
s = s.replace(E_OLD, E_NEW, 1).replace(V_OLD, V_NEW, 1).replace(B1_OLD, B1_NEW, 1).replace(B2_OLD, B2_NEW, 1).replace(I_OLD, I_NEW, 1)
open(p, 'w').write(s)
print("patched (browser VU compiler: branch reads the old integer register value)")
