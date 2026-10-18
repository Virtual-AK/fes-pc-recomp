import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_primarea_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "gs.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write("    if (f < from || f >= to) return;\n    const std::uint64_t pr = s.prim;\n")
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "PS2_TRACE_PRIMAREA" in s and s.index("PS2_TRACE_PRIMAREA") < s.index("const std::uint64_t pr")
    assert "already patched" in run(f).stdout
print("ok   primarea patch (PS2_TRACE_PRIMAREA) applies once, is idempotent and refuses unknown source")
