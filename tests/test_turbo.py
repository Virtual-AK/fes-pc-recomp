"""Turbo key: the runner patch applies once and refuses unknown source."""
import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_turbo_patch.py")

def run(d):
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True)

with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "host")); os.makedirs(os.path.join(d, "runtime/include/ps2")); os.makedirs(os.path.join(d, "runtime/src"))
    open(os.path.join(d, "runtime/include/ps2/system.hpp"), "w").write("void post_present();\n")
    open(os.path.join(d, "runtime/src/system.cpp"), "w").write("void post_present() { gs::post_present(); }\n")
    p = os.path.join(d, "host", "window.cpp")
    src = ('void poll() {\n    SDL_Event e;\n            if (log_keys) std::fprintf(stderr, "[key] scancode %d (%s)\\n", static_cast<int>(k), SDL_GetScancodeName(k));\n'
           '}\nconstexpr Uint32 kAudioBytesPerMs = 48 * 4;\n\nvoid pace() {\n    if (g_audio) {\n    }\n}\n'
           '    SDL_SetWindowTitle(g_window, title);\n    poll();\n    present();\n    pace();\n'
           'void queue_audio(const std::int16_t *samples, std::size_t frames) {\n    x;\n}\n')
    open(p, "w", newline="").write(src)
    r = run(d)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    t = open(p).read()
    assert t.index("bool g_turbo") < t.index("void poll()") and "SDL_SCANCODE_TAB" in t and "[TURBO] " in t and t.count("if (g_turbo)") >= 3 and "turbo_n" in t and "set_turbo" in open(os.path.join(d, "runtime/src/system.cpp")).read()
    assert "already patched" in run(d).stdout
    open(p, "w").write("int main() {}\n")
    r = run(d)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
print("ok   turbo patch applies once, is idempotent and refuses unknown source")
