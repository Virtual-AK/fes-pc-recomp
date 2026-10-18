import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_window_savestate_patch.py")
def run(d):
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    for sub in ("runtime/include/ps2", "runtime/src", "host"):
        os.makedirs(os.path.join(d, sub))
    open(os.path.join(d, "runtime/include/ps2/system.hpp"), "w").write("bool save_state(const std::string &path);\nbool load_state(const std::string &path);\n")
    open(os.path.join(d, "runtime/src/system.cpp"), "w").write("#include <atomic>\n#include <fstream>\nbool g_state_request = false;\nvoid vblank() {\n    if (g_options.save_state_frame && g_frames == g_options.save_state_frame) g_state_request = true;\n}\nbool load_state(const std::uint8_t *data, std::size_t size) {\n}\n")
    open(os.path.join(d, "host/window.cpp"), "w").write("            if (k == SDL_SCANCODE_F12 || k == SDL_SCANCODE_F9 || k == SDL_SCANCODE_F8 || k == SDL_SCANCODE_C) {\n            }\n")
    r = run(d)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    c = open(os.path.join(d, "runtime/src/system.cpp")).read()
    assert "g_live_state_request" in c and "live_" in c and "void request_state_save()" in c
    assert "request_state_save" in open(os.path.join(d, "runtime/include/ps2/system.hpp")).read()
    assert "SDL_SCANCODE_F6" in open(os.path.join(d, "host/window.cpp")).read()
    assert "already patched" in run(d).stdout
    open(os.path.join(d, "host/window.cpp"), "w").write("int x;\n")
    os.remove(os.path.join(d, "host/window.cpp")); 
    r = run(d)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
print("ok   window save-state patch applies once, is idempotent and refuses missing source")
