import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_primcount_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "gs.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write("void trace_prim(const State &s, int needed) {\n    static const char *spec = std::getenv(\"PS2_TRACE_PRIM\");\n}\n")
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "PS2_TRACE_PRIMCOUNT" in s and "[primcount] f%llu" in s and s.index("primcount") < s.index("PS2_TRACE_PRIM\"")
    assert "already patched" in run(f).stdout
print("ok   primcount patch (PS2_TRACE_PRIMCOUNT) applies once, is idempotent and refuses unknown source")
