import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2web_vubranch_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """kT, kSign, kExp, kVi0, kI32Locals
    void vi(unsigned i) {
        if (!i) {
            c_.i32c(0);
            return;
        }
        vi_used_ |= 1u << i;
        c_.get(kVi0 + i);
    }
    case 0x28:
    case 0x29:
        vi(is);
        vi(it);
        c_.op((w >> 25) == 0x28 ? kOpEq : kOpNe);
        static const std::uint8_t kCompare[4] = {kOpLtS, kOpGtS, kOpLeS, kOpGeS};
        vi(is);
    upper_pre(u, flags_live);
    if (hi & 0x80000000u) {
        c_.get(kR);
        c_.i32c(lo);
        c_.store(kOffI);
"""
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "vu_jit.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "kBvi, kVi0" in s and s.count("vib(is, pc);") == 2 and "vib(it, pc);" in s and "int bvi_dest" in s and "c_.set(kBvi);" in s
    assert "already patched" in run(f).stdout
print("ok   web vubranch patch (browser VU compiler: branch reads the old integer register) applies once, is idempotent and refuses unknown source")
