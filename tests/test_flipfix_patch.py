import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_flipfix_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "raster.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write("void t() {\n    const float inv = 1.0f / area;\n    const float sg = 1;\n}\n")
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    assert "PS2_TRI_FLIPFIX" in open(f).read()
    assert "already patched" in run(f).stdout
print("ok   minimap flip-fix test patch applies once, is idempotent and refuses unknown source")
