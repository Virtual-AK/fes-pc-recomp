import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2gpu_flipfix_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "gs.wgsl")
    open(f, "w").write("fn x() {}\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write("            let t = vertex_tex(p, 0u) * a0 + vertex_tex(p, 1u) * a1 + vertex_tex(p, 2u) * a2;\n")
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    assert "flip_fix" in open(f).read()
    assert "already patched" in run(f).stdout
print("ok   GPU minimap flip-fix patch applies once, is idempotent and refuses unknown source")
