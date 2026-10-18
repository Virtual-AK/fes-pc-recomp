import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_vudump_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "vu_micro.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write("void trace_xgk(Unit &u, const std::uint8_t *buffer, std::uint32_t count, std::uint32_t address) {\n}\nvoid run(int n, std::uint32_t address) {\n}\n    trace_xgk(u, buffer, count, address);\n")
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "PS2_DUMP_VU1" in s and "dump_enter(address)" in s and "dump_kick(u, address);\n    trace_xgk(u" in s
    assert "already patched" in run(f).stdout
print("ok   vudump patch (PS2_DUMP_VU1) applies once, is idempotent and refuses unknown source")
