"""PC window autosave: the runner patch applies once, and the launcher lists, resumes and configures the PC autosaves."""
import os, subprocess, sys, tempfile, types, time
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_autosave_patch.py")
sys.path.insert(0, os.path.join(here, "..", "tools", "launcher"))

def run(d):
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True)

with tempfile.TemporaryDirectory() as d:
    for sub in ("runtime/include/ps2", "runtime/src", "host"):
        os.makedirs(os.path.join(d, sub))
    w = lambda rel, t: open(os.path.join(d, rel), "w", newline="").write(t)
    rd = lambda rel: open(os.path.join(d, rel), newline="").read()
    w("runtime/include/ps2/system.hpp", "    std::uint64_t save_state_frame = 0;\n};\nvoid request_state_save();\n")
    cpp = ("#include <chrono>\nint g_live_state_n = 0;\nvoid vblank() {\n    if (g_live_state_request.exchange(false)) {\n        std::string name;\n    }\n}\n"
           "void request_state_save() { g_live_state_request.store(true); }\n"
           "int run() {\n        if (g_state_request) {\n            g_state_request = false;\n            save_state(g_options.save_state_path);\n        }\n}\n")
    w("runtime/src/system.cpp", cpp)
    w("host/main.cpp", '"              [--save-state frame:file] [--load-state file]\\n");\n        else if (a == "--load-state" && i + 1 < argc) load_path = argv[++i];\n#ifdef PS2_WINDOW\n    if (window && !open_window(fullscreen)) return 1;\n')
    w("host/window.cpp", "            if (k == SDL_SCANCODE_F12 || k == SDL_SCANCODE_F9 || k == SDL_SCANCODE_F8 || k == SDL_SCANCODE_C) {\n")
    r = run(d)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    c = rd("runtime/src/system.cpp")
    assert "as_tick();" in c and "as_finish();" in c and ".part" in c and "request_autosave_now" in c and "note_card_saved" in c
    assert "autosave_dir" in rd("runtime/include/ps2/system.hpp")
    m = rd("host/main.cpp")
    assert "--autosave-every" in m and "note_card_saved" in m
    assert "SDL_SCANCODE_F5" in rd("host/window.cpp")
    assert "already patched" in run(d).stdout
    # Windows line endings survive
    for f in ("runtime/src/system.cpp", "host/main.cpp"):
        w(f, rd(f).replace("\r\n", "\n").replace("\n", "\r\n"))
    w("host/window.cpp", "            if (k == SDL_SCANCODE_F12 || k == SDL_SCANCODE_F9 || k == SDL_SCANCODE_F8 || k == SDL_SCANCODE_C) {\n")
    # unknown source is refused, and so is a tree without the save-state patch
    w("host/main.cpp", "int main() {}\n")
    r = run(d)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0, r.stdout
    w("runtime/include/ps2/system.hpp", "struct X {};\n")
    r = run(d)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0

import p3fes_launcher as L
with tempfile.TemporaryDirectory() as d:
    b = os.path.join(d, "winbuild", "build"); os.makedirs(b)
    exe = os.path.join(b, "ps2run.exe"); open(exe, "w").write("x" * 10)
    saves = os.path.join(d, "saves"); os.makedirs(saves)
    gdir = os.path.join(d, "games", L.NAME, "disc"); os.makedirs(gdir)
    open(os.path.join(gdir, "SLUS_216.21"), "wb").write(b"ELF")
    old = (L.DIR, L.to_win, L.win_disc, L.saves_dir, subprocess.Popen, L.load_cfg, L.save_cfg)
    got, cfg = {}, {}
    os.environ["P3F_WINEXE"] = exe
    try:
        L.DIR = d
        L.to_win = lambda p: "W:" + p
        L.win_disc = lambda: "W:disc.iso"
        L.saves_dir = lambda: saves
        L.load_cfg = lambda: dict(cfg)
        L.save_cfg = lambda c: cfg.update(c)
        subprocess.Popen = lambda cmd, **kw: got.update(cmd=cmd) or types.SimpleNamespace(args=cmd, poll=lambda: 0)
        cur = L.pc_as_dir(exe)
        os.makedirs(cur)
        other = os.path.join(L.pc_as_root(), "99-1"); os.makedirs(other)
        for n in ("timer_20261020-190000.state", "card_20261020-191500.state", "manual_20261019-080000.state", "timer_20261020-190000.state.part", "junk.state"):
            open(os.path.join(cur, n), "wb").write(b"s" * 2048)
        open(os.path.join(other, "timer_20261001-120000.state"), "wb").write(b"s")
        st = L.pc_as_state()
        assert st["available"] and [a["id"] for a in st["list"]] == ["card_20261020-191500.state", "timer_20261020-190000.state", "manual_20261019-080000.state"], st
        assert st["older"] == 1 and st["list"][0]["reason"] == "game save" and st["list"][0]["when"] == "2026-10-20 19:15"
        assert st["cfg"] == {"every": 2.0, "keep": 3, "card": True}
        cfg.update(pc_as_every="5", pc_as_keep="10", pc_as_card=False)
        assert L.pc_as_cfg() == {"every": 5.0, "keep": 10, "card": False}
        r = L.play_windows(exe)
        c = got["cmd"]
        assert r["ok"] and c[c.index("--autosave") + 1] == "W:" + cur and c[c.index("--autosave-every") + 1] == "5"
        assert c[c.index("--autosave-keep") + 1] == "10" and c[c.index("--autosave-card") + 1] == "0" and "--load-state" not in c
        r = L.play_windows(exe, "card_20261020-191500.state")
        c = got["cmd"]
        assert r["ok"] and c[c.index("--load-state") + 1] == "W:" + os.path.join(cur, "card_20261020-191500.state")
        for bad in ("../x.state", "card_20261020-191500.state.part", "timer_1.state", "card_20990101-000000.state"):
            assert not L.play_windows(exe, bad)["ok"], bad
        r = L.play("browser", pcresume="card_20261020-191500.state")
        assert not r["ok"] or "PC window" in r["msg"]
        # a rebuilt exe (new size) has its own, empty folder; the old files count as older
        open(exe, "w").write("y" * 20)
        st = L.pc_as_state()
        assert st["list"] == [] and st["older"] == 4, st
    finally:
        L.DIR, L.to_win, L.win_disc, L.saves_dir, subprocess.Popen, L.load_cfg, L.save_cfg = old
        os.environ.pop("P3F_WINEXE", None)
print("ok   PC window autosave: runner patch applies once and refuses unknown source; the launcher lists, resumes and configures PC autosaves")
