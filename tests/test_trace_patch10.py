import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_trace_patch10.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "gs.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write("void trace_prim(const State &s, int needed) {\n}\nvoid kick() {\n    if (s.count < needed) return;\n    if (draw) {\n        trace_prim(s, needed);\n    }\n}\n")
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "PS2_SKIP_PRIM" in s and "if (draw && skip_prim(s)) draw = false;" in s and s.index("bool skip_prim") < s.index("void trace_prim")
    assert "already patched" in run(f).stdout
print("ok   trace patch 10 (PS2_SKIP_PRIM) needs patch 6, applies once and is idempotent")
