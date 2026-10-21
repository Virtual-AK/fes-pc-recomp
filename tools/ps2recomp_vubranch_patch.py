"""Fix for the half-drawn cut-in portraits (part 3 of 3: the program compiler vurecomp, which makes the ahead-of-time VU1 code).
Same rule as part 1 (ps2run_vubranch_patch.py): a conditional branch (IBEQ, IBNE, IBLTZ, IBGTZ, IBLEZ, IBGEZ) that comes right
after an integer ALU instruction (IADDIU, ISUBIU, IADD, ISUB, IADDI, IAND, IOR) sees the OLD value of the registers. The generated code
now saves the two registers the branch compares before such an instruction and the branch reads the saved copies.
Usage (in the ps2-web-recomp folder): python3 ps2recomp_vubranch_patch.py [recomp/vurecomp.cpp]   Safe to run twice.
Rebuild vurecomp afterwards (ninja -C build/tools vurecomp) and compile the programs again (tools/p3fes_vu_compile.sh).
"""
import sys

p = sys.argv[1] if len(sys.argv) > 1 else "recomp/vurecomp.cpp"
s = open(p, newline="").read()
if "ovi[16]" in s:
    print("already patched")
    raise SystemExit
crlf = "\r\n" in s
s = s.replace("\r\n", "\n")

HELPER_AT = "std::string generate(const Program &p, std::string &name) {\n"
HELPER = '''// VU integer ALU instructions whose result a directly following conditional branch does not see yet
bool int_alu(std::uint32_t lo, std::uint32_t hi) {
    if (hi & 0x80000000u) return false;
    const std::uint32_t op = lo >> 25;
    if (op == 0x08 || op == 0x09) return true;
    if (op != 0x40) return false;
    const std::uint32_t f = lo & 63u;
    return f == 0x30 || f == 0x31 || f == 0x32 || f == 0x34 || f == 0x35;
}

'''
PRO_OLD = "    std::uint32_t jpc = 0;\\n    (void)pend;\\n    (void)pendj;\\n"
PRO_NEW = "    std::uint32_t jpc = 0;\\n    std::uint16_t ovi[16] = {{}};\\n    (void)ovi;\\n    (void)pend;\\n    (void)pendj;\\n"
BODY_OLD = "        std::string body = u.pre;\n        if (hi & 0x80000000u) body += std::format(\"r.i = {}u; \", lo);\n        else if (!l.supported) body += std::format(\"vu::interpret(1, {}u); return; \", pc);\n        else body += l.code;\n"
BODY_NEW = '''        // a conditional branch right after an integer ALU instruction reads the registers as they were before it
        const auto old_branch = [&](std::uint32_t at) {
            const std::uint32_t before = (at - 8u) & kMask;
            const std::uint32_t blo = word(p.code, at), bhi = word(p.code, at + 4);
            const std::uint32_t bop = blo >> 25;
            if (!in.count(at) || !in.count(before) || (bhi & 0x80000000u) || !(bop == 0x28 || bop == 0x29 || (bop >= 0x2C && bop <= 0x2F))) return false;
            if (at == (p.entry & kMask)) return false;
            for (std::uint32_t q : pcs)
                if (lowers[q].branch && (lowers[q].target & kMask) == at) return false;
            return int_alu(word(p.code, before), word(p.code, before + 4));
        };
        std::string code = l.code;
        if (old_branch(pc)) replace_all(code, "r.vi[", "ovi[");
        std::string body = u.pre;
        if (old_branch((pc + 8u) & kMask)) {
            const std::uint32_t bw = word(p.code, (pc + 8u) & kMask);
            body += std::format("ovi[{0}] = r.vi[{0}]; ovi[{1}] = r.vi[{1}]; ", (bw >> 11) & 15u, (bw >> 16) & 15u);
        }
        if (hi & 0x80000000u) body += std::format("r.i = {}u; ", lo);
        else if (!l.supported) body += std::format("vu::interpret(1, {}u); return; ", pc);
        else body += code;
'''
bad = [x for x in (HELPER_AT, PRO_OLD, BODY_OLD) if s.count(x) != 1]
if bad:
    print("PATCH NOT APPLIED: vurecomp.cpp does not look like the expected source")
    raise SystemExit(1)
s = s.replace(HELPER_AT, HELPER + HELPER_AT, 1).replace(PRO_OLD, PRO_NEW, 1).replace(BODY_OLD, BODY_NEW, 1)
if crlf:
    s = s.replace("\n", "\r\n")
open(p, "w", newline="").write(s)
print("patched (vurecomp: branch reads the old integer register value)")
