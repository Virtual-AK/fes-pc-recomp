import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2gpu_tricenter_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """            let w2 = 1.0 - w0 - w1;
            let c = vertex_attr(p, 0u) * w0 + vertex_attr(p, 1u) * w1 + vertex_attr(p, 2u) * w2;
            let t = vertex_tex(p, 0u) * w0 + vertex_tex(p, 1u) * w1 + vertex_tex(p, 2u) * w2;
            at = Attr(c.x, c.y, c.z, c.w, t.x, t.y, t.z, t.w, z_at(p, fat(p + 25u) * w1 + fat(p + 26u) * w2));
"""
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "gs.wgsl")
    open(f, "w").write("fn x() {}\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "tri_centre" in s and "f32(SCALE)" in s and "z_at(p, fat(p + 25u) * w1 + fat(p + 26u) * w2)" in s
    assert "already patched" in run(f).stdout
print("ok   GPU triangle pixel-centre patch applies once, is idempotent and refuses unknown source")
