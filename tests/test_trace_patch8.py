import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_trace_patch8.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "vif.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write('// PS2_TRACE_VIF\nvoid run_vu() {\n    vu::run(unit, address);\n}\n')
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "PS2_TRACE_VUMEM" in s and "[vumem]" in s and s.index("[vumem]") < s.index("vu::run(unit, address);")
    assert "already patched" in run(f).stdout
print("ok   trace patch 8 (PS2_TRACE_VUMEM) needs patch 7, applies once and is idempotent")
