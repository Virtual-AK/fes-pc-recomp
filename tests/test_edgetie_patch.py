import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2gpu_edgetie_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "gs.wgsl")
    open(f, "w").write("fn x() {}\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write("fn edge_in(w: f32, inclusive: u32) -> bool {\n    return w > 0.0 || (w == 0.0 && inclusive != 0u);\n}\n")
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "edge_tie" in s and "abs(w) <= tie" in s and "w == 0.0" not in s
    assert "already patched" in run(f).stdout
print("ok   edge-tie (diagonal line) patch applies once, is idempotent and refuses unknown source")
