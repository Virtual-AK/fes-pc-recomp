import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
patch = os.path.join(here, "..", "tools", "ps2run_drawlog_patch.py")
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "runtime/src/gs/gpu"))
p = os.path.join(d, "runtime/src/gs/gpu/gpu.cpp")
open(p, "w").write("#include <deque>\nvoid draw(const State &st, const Vertex *v, int count) {\n    const Context &c = st.ctx[(attr >> 9) & 1u];\n    SetupCache &cache = g_setup_cache;\n}\n")
r = lambda: subprocess.run([sys.executable, patch, d], capture_output=True, text=True).stdout
assert "patched (3 edits)" in r()
assert "already patched" in r()
assert "drawlog(st, attr, prim, c, v, count)" in open(p).read()
print("ok drawlog patch")
