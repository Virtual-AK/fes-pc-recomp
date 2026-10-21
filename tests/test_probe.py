"""Probe tools: the runner patch applies once, and the memory finder separates situations."""
import os, struct, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tools = os.path.join(here, "..", "tools")

def run(script, *a):
    return subprocess.run([sys.executable, os.path.join(tools, script), *a], capture_output=True, text=True)

with tempfile.TemporaryDirectory() as d:
    for sub in ("runtime/include/ps2", "runtime/src", "host"):
        os.makedirs(os.path.join(d, sub))
    w = lambda rel, t: open(os.path.join(d, rel), "w", newline="").write(t)
    rd = lambda rel: open(os.path.join(d, rel), newline="").read()
    w("runtime/include/ps2/system.hpp", "void request_state_save();\n")
    w("runtime/src/system.cpp", "void time_frames() {\n}\nvoid vblank() {\n    if (g_options.on_vblank) g_options.on_vblank();\n    iop::sio2::flush_cards();\n}\nbool present_frame() { return gs::present(); }\n")
    w("host/window.cpp", "        if (e.type == SDL_KEYDOWN && e.key.keysym.scancode == SDL_SCANCODE_F11 && !e.key.repeat) {\n        }\n")
    r = run("ps2run_probe_patch.py", d)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    assert "PS2_WATCH" in rd("runtime/src/system.cpp") and "probe_tick();" in rd("runtime/src/system.cpp") and rd("runtime/src/system.cpp").count("void request_ramdump()") == 1 and "SDL_SCANCODE_F7" in rd("host/window.cpp")
    assert "already patched" in run("ps2run_probe_patch.py", d).stdout
    w("host/window.cpp", "int x;\n")
    r = run("ps2run_probe_patch.py", d)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0

with tempfile.TemporaryDirectory() as d:
    def mk(n, vals):
        b = bytearray(4096)
        for a, v in vals.items():
            b[a:a + 4] = struct.pack("<I", v)
        p = os.path.join(d, n)
        open(p, "wb").write(b)
        return p
    t1, t2 = mk("t1", {0x100: 5, 0x200: 1, 0x300: 9}), mk("t2", {0x100: 5, 0x200: 1, 0x300: 7})
    c1, c2 = mk("c1", {0x100: 5, 0x200: 2, 0x300: 9}), mk("c2", {0x100: 5, 0x200: 2, 0x300: 3})
    r = run("p3fes_ramfind.py", "talk=%s,%s" % (t1, t2), "choice=%s,%s" % (c1, c2))
    assert "1 places" in r.stdout and "00000200  00000001    00000002" in r.stdout, r.stdout + r.stderr
print("ok   probe patch applies once and refuses unknown source; ramfind separates situations")

import subprocess as sp
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "runtime/src"))
    open(os.path.join(d, "runtime/src/disc.cpp"), "w").write('#include "ps2/disc.hpp"\nbool read(std::uint32_t sector, std::uint32_t count, void *out) {\n    if (!g_reader) return false;\n    x;\n}\n')
    r = run("ps2run_disclog_patch.py", d)
    assert "patched (2 edits)" in r.stdout, r.stdout + r.stderr
    assert "PS2_LOG_DISC" in open(os.path.join(d, "runtime/src/disc.cpp")).read()
    assert "already patched" in run("ps2run_disclog_patch.py", d).stdout
print("ok   disc log patch applies once")
