import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2gs_uploadclamp_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """#include <stdexcept>
bool trace_tex() {
        s.trxdir = value;
        g_transfer = Transfer{};
        g_carried = 0;
        trace_prim(s, needed);
        dump_tex_draw(s);
        if (cpu_raster()) raster::draw(s, s.queue, needed);
#ifdef PS2_GPU
        if (gpu_on()) gpu::draw(s, s.queue, needed);
#endif
"""
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "gs.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "upload_clamp_on" in s and "note_upload(s, value)" in s and "uc.clamp = saved_clamp" in s and "<unordered_map>" in s
    assert "already patched" in run(f).stdout
print("ok   upload-area clamp patch applies once, is idempotent and refuses unknown source")
