import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_trace_patch6.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "gs.cpp")
    open(f, "w").write("void kick(bool draw) {\n    State &s = g_state;\n    if (draw) {\n        if (cpu_raster()) raster::draw(s, s.queue, needed);\n    }\n}\n")
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "PS2_TRACE_PRIM" in s and "trace_prim(s, needed);" in s and s.index("void trace_prim") < s.index("void kick")
    assert "already patched" in run(f).stdout
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
print("ok   trace patch 6 (PS2_TRACE_PRIM) applies once, is idempotent and refuses unknown source")
