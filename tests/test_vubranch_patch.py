import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_vubranch_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """Vu0Regs g_vu1;
void lower(Unit &u, std::uint32_t w, std::uint32_t pc, std::uint32_t &npc, bool &branch) {
    case 0x28: if (r.vi[is] == r.vi[it]) branch_to(target); break;
    case 0x29: if (r.vi[is] != r.vi[it]) branch_to(target); break;
    case 0x2C: if (static_cast<std::int16_t>(r.vi[is]) < 0) branch_to(target); break;
    case 0x2D: if (static_cast<std::int16_t>(r.vi[is]) > 0) branch_to(target); break;
    case 0x2E: if (static_cast<std::int16_t>(r.vi[is]) <= 0) branch_to(target); break;
    case 0x2F: if (static_cast<std::int16_t>(r.vi[is]) >= 0) branch_to(target); break;
}
for (;;) {
        const std::uint32_t current = pc;
}
for (;;) {
        const std::uint32_t current = pc;
}
"""
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "vu_micro.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert s.count("bvi(r, is)") == 6 and s.count("bvi(r, it)") == 2 and s.count("vb_step(r, steps, lo, hi);") == 2 and "PS2_VU_BRANCHNEW" in s
    assert "r.vi[is] ==" not in s
    assert "already patched" in run(f).stdout
print("ok   vubranch patch (interpreter: branch reads the old integer register) applies once, is idempotent and refuses unknown source")
