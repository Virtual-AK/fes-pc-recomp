"""Browser build: widescreen data patch, speedrun clock patch, and the page parameters the launcher passes."""
import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tools = os.path.join(here, "..", "tools")
sys.path.insert(0, os.path.join(tools, "launcher"))
run = lambda tool, arg: subprocess.run([sys.executable, os.path.join(tools, tool), arg], capture_output=True, text=True)

with tempfile.TemporaryDirectory() as d:
    os.makedirs(d + "/runtime/src")
    sysf = d + "/runtime/src/system.cpp"
    body = "void vblank() {\n    apply_presses();\n#ifndef __EMSCRIPTEN__\n    ws_apply();\n#endif\n    x();\n}\n"
    open(sysf, "w", newline="").write(body.replace("\n", "\r\n"))
    r = run("ps2run_widescreen_web_patch.py", d)
    assert "patched (1 edit)" in r.stdout, r.stdout + r.stderr
    t = open(sysf, newline="").read()
    assert "\r\n" in t and "__EMSCRIPTEN__" not in t and t.count("ws_apply();") == 1
    assert "already patched" in run("ps2run_widescreen_web_patch.py", d).stdout
    open(sysf, "w").write("nothing")
    r = run("ps2run_widescreen_web_patch.py", d)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0

with tempfile.TemporaryDirectory() as d:
    f = d + "/shell.html"
    open(f, "w").write("<style>\n a{}\n</style>\n<div id=\"stage\"><canvas id=\"canvas\" tabindex=\"0\"></canvas></div>\n<script>\nx\n</script>\n{{{ SCRIPT }}}\n</body>\n")
    assert "patched (3 edits)" in run("ps2web_speedrun_patch.py", f).stdout
    t = open(f).read()
    assert "srclock" in t and "speedrun" in t and t.index("ps2-speedrun: real-time") < t.index("{{{ SCRIPT }}}") and t.count("{{{ SCRIPT }}}") == 1
    assert "already patched" in run("ps2web_speedrun_patch.py", f).stdout
    open(f, "w").write("nothing")
    assert "NOT APPLIED" in run("ps2web_speedrun_patch.py", f).stdout
print("ok   browser widescreen and speedrun patches apply once, are idempotent and refuse unknown source")

import p3fes_launcher as L
assert L.web_params({}) == ""
q = L.web_params({"widescreen": True, "vol_music": 40, "speedrun": True, "speedrun_zero_web": True})
assert "PS2_ASPECT=16%3A9" in q and "PS2_PATCH=007cad1c%3D3fe38e38%2F3faaaaab" in q and "PS2_VOL_MUSIC=40" in q and "PS2_VOL_MASTER" not in q
assert "speedrun=1" in q and "srzero=1" in q
assert "srzero" not in L.web_params({"speedrun": True})
print("ok   launcher passes widescreen, volumes and speedrun to the browser game only when set")

_pk = L.lm_pokes_text
L.lm_pokes_text = lambda: "00123456=0000ABCD,00123460=00000001"
assert L.web_pokes_param(None) == "" and L.web_pokes_param("x.ovl") == "&PS2_POKE=00123456%3D0000ABCD%2C00123460%3D00000001"
L.lm_pokes_text = lambda: ""
assert L.web_pokes_param("x.ovl") == ""
L.lm_pokes_text = _pk
print("ok   launcher passes the file-mod table pokes to the browser game only with an overlay")

with tempfile.TemporaryDirectory() as d:
    for sub in ("host", "web", "runtime/include/ps2"):
        os.makedirs(os.path.join(d, sub))
    w = lambda rel, t: open(os.path.join(d, rel), "w", newline="").write(t)
    rd = lambda rel: open(os.path.join(d, rel), newline="").read()
    w("host/web.cpp", "namespace {\nvoid push_audio(const std::int16_t *samples, std::size_t frames) {\n    x();\n}\ndouble g_next_frame = 0.0;\nvoid pace() {\n    ps2::post_present();\n    if (a) {}\n}\n}\n"
      'extern "C" EMSCRIPTEN_KEEPALIVE int ps2web_rumble(int pad) { return ps2::pad_rumble(pad); }\n')
    w("web/shell.html", "<script>\nx\n</script>\n{{{ SCRIPT }}}\n</body>\n")
    w("runtime/include/ps2/system.hpp", "void post_present();\n")
    r = run("ps2web_turbo_patch.py", d)
    assert "NOT APPLIED" in r.stdout and "ps2run_turbo_patch" in r.stdout, r.stdout   # needs the PC turbo patch first
    w("runtime/include/ps2/system.hpp", "void post_present();\nvoid set_turbo(bool on);\n")
    r = run("ps2web_turbo_patch.py", d)
    assert "patched (4 edits)" in r.stdout, r.stdout + r.stderr
    c, h = rd("host/web.cpp"), rd("web/shell.html")
    assert c.index("g_turbo{false}") < c.index("void push_audio") and "ps2web_set_turbo" in c and c.count("g_turbo.load()") == 2
    assert "ps2-turbo" in h and h.index("ps2-turbo") < h.index("{{{ SCRIPT }}}") and "u25B6" in h
    assert "already patched" in run("ps2web_turbo_patch.py", d).stdout
    w("host/web.cpp", "nothing")
    assert "NOT APPLIED" in run("ps2web_turbo_patch.py", d).stdout
print("ok   browser turbo patch needs the PC turbo patch, applies once, is idempotent and refuses unknown source")

# the PC widescreen patch must still accept a tree where the browser patch already ran
with tempfile.TemporaryDirectory() as d:
    for sub in ("runtime/src/gs/gpu", "runtime/src"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    w = lambda rel, t: open(os.path.join(d, rel), "w", newline="").write(t)
    w("runtime/src/gs/gpu/gpu.cpp",
      "std::uint32_t g_scale = 1, g_copy_words = 1u << 20, g_field_words = 1u << 19;\n"
      "        const float vw = std::min(w, h * 4.0f / 3.0f), vh = vw * 3.0f / 4.0f;\n"
      "    const float vw = std::min(sw, sh * 4.0f / 3.0f), vh = vw * 3.0f / 4.0f;\n"
      '    if (const char *scale = std::getenv("PS2_SCALE")) g_scale = 1;\n')
    w("runtime/src/system.cpp", "#include <algorithm>\nvoid vblank() {\n    gif::flush_path3();\n    apply_presses();\n    if (g_options.on_vblank) g_options.on_vblank();\n}\n")
    assert "patched" in run("ps2run_widescreen_patch.py", d).stdout
    assert "patched (1 edit)" in run("ps2run_widescreen_web_patch.py", d).stdout
    r = run("ps2run_widescreen_patch.py", d)
    assert "already patched" in r.stdout, r.stdout
print("ok   PC widescreen patch still reports 'already patched' after the browser widescreen patch")

with tempfile.TemporaryDirectory() as d:
    f = d + "/shell.html"
    open(f, "w", newline="").write("<script>\nx\n</script>\n{{{ SCRIPT }}}\n</body>\n")
    assert "patched (1 edit)" in run("ps2web_gamebeat_patch.py", f).stdout
    t = open(f).read()
    assert "gamebeat?s=" in t and "pagehide" in t and t.index("ps2-gamebeat") < t.index("{{{ SCRIPT }}}")
    assert "already patched" in run("ps2web_gamebeat_patch.py", f).stdout
    open(f, "w").write("nothing")
    assert "NOT APPLIED" in run("ps2web_gamebeat_patch.py", f).stdout
# the launcher: a beat holds the music, a goodbye frees it at once, a silent page stops holding after 30 s
import time
L.port_open = lambda p: True
L.children.clear()
L.game_seen[0] = 0.0
assert not L.music_hold()
L.game_seen[0] = time.time()
assert L.music_hold()
L.game_seen[0] = 0.0
assert not L.music_hold()
L.game_seen[0] = time.time() - 40
assert not L.music_hold()
print("ok   browser game beat patch applies once; launcher music hold follows beats and goodbyes")
