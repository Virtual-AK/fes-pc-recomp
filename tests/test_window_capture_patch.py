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
    assert "SDL_SCANCODE_F12" in s and "[capture] requested" in s and "capture_push(rgba, w, h);" in s and "<filesystem>" in s
    assert "PS2_CAPTURE_FRAMES" in s and "> 90" not in s
    assert "already patched" in run(f).stdout
    # upgrade of a tree patched by the first version
    open(f, "w").write(s.replace(s[s.index("    static const std::size_t keep"):s.index("    if (!g_capture_now")], "    if (g_capture_ring.size() > 90) g_capture_ring.pop_front();\n"))
    assert "longer capture window" in run(f).stdout and "PS2_CAPTURE_FRAMES" in open(f).read()
    # upgrade of a tree patched by the version with only F12
    s2 = open(f).read()
    a = s2.index("        if (e.type == SDL_KEYDOWN && !e.key.repeat) {")
    b = s2.index("        if (e.type == SDL_WINDOWEVENT")
    open(f, "w").write(s2[:a] + "        if (e.type == SDL_KEYDOWN && e.key.keysym.scancode == SDL_SCANCODE_F12 && !e.key.repeat) g_capture_now.store(true);\n" + s2[b:])
    assert "more keys and log line" in run(f).stdout and "SDL_SCANCODE_F9" in open(f).read() and "PS2_LOG_KEYS" in open(f).read()
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
print("ok   window capture patch applies once, is idempotent and refuses unknown source")
