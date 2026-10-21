"""Widescreen: the runner patch applies once and refuses unknown source; the launcher sets the switches only when asked."""
import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_widescreen_patch.py")
sys.path.insert(0, os.path.join(here, "..", "tools", "launcher"))

def run(d):
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True)

with tempfile.TemporaryDirectory() as d:
    for sub in ("runtime/src/gs/gpu", "runtime/src"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    w = lambda rel, t: open(os.path.join(d, rel), "w", newline="").write(t)
    rd = lambda rel: open(os.path.join(d, rel), newline="").read()
    w("runtime/src/gs/gpu/gpu.cpp",
      "std::uint32_t g_scale = 1, g_copy_words = 1u << 20, g_field_words = 1u << 19;\n"
      "        const float vw = std::min(w, h * 4.0f / 3.0f), vh = vw * 3.0f / 4.0f;\n"
      "    const float vw = std::min(sw, sh * 4.0f / 3.0f), vh = vw * 3.0f / 4.0f;\n"
      '    if (const char *scale = std::getenv("PS2_SCALE")) g_scale = 1;\n')
    w("runtime/src/system.cpp", "#include <algorithm>\nvoid vblank() {\n    gif::flush_path3();\n    apply_presses();\n    if (g_options.on_vblank) g_options.on_vblank();\n}\n")
    r = run(d)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    g, s = rd("runtime/src/gs/gpu/gpu.cpp"), rd("runtime/src/system.cpp")
    assert "g_aspect" in g and "4.0f / 3.0f, vh" not in g and "PS2_ASPECT" in g and "PS2_PATCH" in s and s.count("ws_apply();") == 1
    assert "already patched" in run(d).stdout
    w("runtime/src/system.cpp", "int x;\n")
    r = run(d)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0

import p3fes_launcher as L
old = L.load_cfg
try:
    L.load_cfg = lambda: {}
    e = {}
    assert not L.widescreen_env(e) and not e
    L.load_cfg = lambda: {"widescreen": True}
    assert L.widescreen_env(e) and e["PS2_ASPECT"] == "16:9" and e["PS2_PATCH"] == "007cad1c=3fe38e38/3faaaaab"
finally:
    L.load_cfg = old
print("ok   widescreen patch applies once, is idempotent and refuses unknown source; launcher sets it only when on")
