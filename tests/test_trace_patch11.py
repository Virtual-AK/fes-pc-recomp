import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_trace_patch11.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "vu_micro.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write("void xgkick(Unit &u, std::uint32_t address) {\n    gif::transfer(1, buffer, count);\n}\n")
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "PS2_TRACE_XGK" in s and "trace_xgk(u, buffer, count, address);" in s and s.index("void trace_xgk") < s.index("void xgkick")
    assert "have_find" in s and "trace_xgk(u, buffer" in s
    assert "already patched" in run(f).stdout
    # upgrade of the first version (no find option)
    old = s.replace("Unit &u, const std::uint8_t *buffer", "const std::uint8_t *buffer").replace("trace_xgk(u, buffer, count, address);", "trace_xgk(buffer, count, address);").replace("have_find", "hf")
    open(f, "w").write(old)
    r = run(f)
    assert "find option added" in r.stdout, r.stdout + r.stderr
    s2 = open(f).read()
    assert s2.count("void trace_xgk") == 1 and s2.count("trace_xgk(u, buffer, count, address);") == 1 and "have_find" in s2
    assert "already patched" in run(f).stdout
print("ok   trace patch 11 (PS2_TRACE_XGK) applies once, is idempotent and refuses unknown source")
