import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2recomp_vubranch_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """std::string generate(const Program &p, std::string &name) {
    std::string o = std::format("void {}(Vu0Regs &r, std::uint8_t *mem) {{\\n    FlagPipe fl;\\n    std::uint32_t jpc = 0;\\n    (void)pend;\\n    (void)pendj;\\n    (void)ending;\\n", name);
        const Lower &l = lowers[pc];
        std::string body = u.pre;
        if (hi & 0x80000000u) body += std::format("r.i = {}u; ", lo);
        else if (!l.supported) body += std::format("vu::interpret(1, {}u); return; ", pc);
        else body += l.code;
        body += u.post;
}
"""
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "vurecomp.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w", newline="").write(SRC.replace("\n", "\r\n"))
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f, newline="").read()
    assert "\r\n" in s and s.count("ovi[16] = {{}}") == 1 and "old_branch" in s and "bool int_alu" in s and 'replace_all(code, "r.vi["' in s
    assert "already patched" in run(f).stdout
print("ok   vurecomp vubranch patch (ahead-of-time VU1 code: branch reads the old integer register) applies once, keeps line endings, is idempotent and refuses unknown source")
