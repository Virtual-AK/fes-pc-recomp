import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
patch = os.path.join(here, "..", "tools", "ps2run_vramdump_patch.py")
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "runtime/src/gs"))
p = os.path.join(d, "runtime/src/gs/gs.cpp")
open(p, "w").write("void kick(bool draw) {\n    if (draw) {\n        dump_tex_draw(s);\n        Context &uc = x;\n    }\n}\n")
r = lambda: subprocess.run([sys.executable, patch, d], capture_output=True, text=True).stdout
assert "patched (2 edits)" in r()
assert "already patched" in r()
assert "dump_vram_flag();" in open(p).read()
print("ok vramdump patch")
