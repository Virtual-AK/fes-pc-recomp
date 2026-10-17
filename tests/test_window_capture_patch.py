import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_window_capture_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "window.cpp")
    open(f, "w").write('#include <vector>\nvoid poll() {\n    while (1) {\n        if (e.type == SDL_WINDOWEVENT && e.window.event == SDL_WINDOWEVENT_SIZE_CHANGED && g_gpu_present) {\n        }\n    }\n}\nvoid show_pixels(const std::uint32_t *rgba, std::uint32_t w, std::uint32_t h) {\n}\n')
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "SDL_SCANCODE_F12" in s and "capture_push(rgba, w, h);" in s and "<filesystem>" in s
    assert "already patched" in run(f).stdout
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
print("ok   window capture patch applies once, is idempotent and refuses unknown source")
