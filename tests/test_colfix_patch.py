import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
patch = os.path.join(here, "..", "tools", "ps2run_colfix_patch.py")
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "runtime/src/gs/gpu"))
p = os.path.join(d, "runtime/src/gs/gpu/gs.wgsl")
open(p, "w").write("    var r = i32(at.r);\n    var g = i32(at.g);\n    var b = i32(at.b);\n    var a = i32(at.a);\n")
r = lambda: subprocess.run([sys.executable, patch, d], capture_output=True, text=True).stdout
assert r().startswith("patched")
assert "already patched" in r()
assert "i32(at.a + 0.002)" in open(p).read()
print("ok colfix patch")
