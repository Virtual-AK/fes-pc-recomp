import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_tricenter_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """#include <cstring>
    const float inv = 1.0f / area;
    const float sg = area > 0.0f ? 1.0f : -1.0f;
    const auto edge_in = x;
            const float w0 = e0 * inv;
            const float w1 = e1 * inv;
            const float w2 = 1.0f - w0 - w1;
            plot(s, x, y, lerp3(a0, a1, a2, w0, w1, w2));
"""
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "raster.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "PS2_TRI_CENTER" in s and "px + 0.5f" in s and "<cstdlib>" in s
    assert "already patched" in run(f).stdout
print("ok   triangle pixel-centre test patch applies once, is idempotent and refuses unknown source")
