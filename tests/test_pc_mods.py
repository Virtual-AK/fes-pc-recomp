"""File mods in the PC window: the runner patch applies once, and the launcher passes the overlay only to a build that knows it."""
import os, subprocess, sys, tempfile, types
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_overlay_patch.py")
sys.path.insert(0, os.path.join(here, "..", "tools", "launcher"))

def run(d):
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True)

with tempfile.TemporaryDirectory() as d:
    for sub in ("runtime/include/ps2", "runtime/src", "host"):
        os.makedirs(os.path.join(d, sub))
    w = lambda rel, t: open(os.path.join(d, rel), "w", newline="").write(t)
    rd = lambda rel: open(os.path.join(d, rel), newline="").read()
    w("runtime/include/ps2/disc.hpp", "bool open(const std::string &path);\n")
    w("runtime/src/disc.cpp", "std::map<std::string, Entry> g_index;\nbool open(const std::string &path) {\n    std::FILE *file = g_file;\n    return open(path, size, [file](std::uint64_t offset, void *out, std::size_t bytes) {\n    });\n}\n")
    w("runtime/include/ps2/system.hpp", "    std::string save_state_path;\n")
    w("runtime/src/system.cpp", "    if (!g_options.disc_path.empty() && !disc::open(g_options.disc_path))\n        x;\n")
    w("host/main.cpp", '"              [--disc image.iso] [--memcard card.ps2] [--pal | --ntsc] [--trace-io]\\n"\n        else if (a == "--memcard" && i + 1 < argc) ps2::g_options.memcard_path = argv[++i];\n')
    r = run(d)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    c = rd("runtime/src/disc.cpp")
    assert "set_overlay" in c and "P3OVL001" in c and "g_ovl_end" in c and "tell_pos" in c
    assert "set_overlay" in rd("runtime/include/ps2/disc.hpp") and "overlay_path" in rd("runtime/include/ps2/system.hpp")
    assert "set_overlay" in rd("runtime/src/system.cpp") and '"--overlay"' in rd("host/main.cpp") and "[--overlay mods.ovl]" in rd("host/main.cpp")
    assert "already patched" in run(d).stdout
    # a tree patched by the first version of this patch (no usage text) is brought up to date
    w("host/main.cpp", rd("host/main.cpp").replace("[--overlay mods.ovl] ", ""))
    r = run(d)
    assert "patched (1 edits)" in r.stdout and "[--overlay mods.ovl]" in rd("host/main.cpp"), r.stdout
    w("host/main.cpp", "int main() {}\n")
    r = run(d)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0, r.stdout

import p3fes_launcher as L
with tempfile.TemporaryDirectory() as d:
    b = os.path.join(d, "winbuild", "build"); os.makedirs(b)
    exe = os.path.join(b, "ps2run.exe")
    saves = os.path.join(d, "saves"); os.makedirs(saves)
    mods = os.path.join(d, "mods"); os.makedirs(mods)
    gdir = os.path.join(d, "games", L.NAME, "disc"); os.makedirs(gdir)
    open(os.path.join(gdir, "SLUS_216.21"), "wb").write(b"ELF")
    old = (L.DIR, L.to_win, L.win_disc, L.saves_dir, subprocess.Popen, L.load_cfg)
    got = {}
    os.environ["P3F_WINEXE"] = exe
    try:
        L.DIR = d
        L.to_win = lambda p: "W:" + p
        L.win_disc = lambda: "W:disc.iso"
        L.saves_dir = lambda: saves
        L.load_cfg = lambda: {}
        subprocess.Popen = lambda cmd, **kw: got.update(cmd=cmd) or types.SimpleNamespace(args=cmd, poll=lambda: 0)
        # a switch is found even when it straddles two read chunks' boundary is not needed here: plain search
        open(exe, "wb").write(b"MZ" + b"\0" * 100 + b"--overlay\0" + b"\0" * 100)
        assert L.exe_supports(exe, "--overlay") and not L.exe_supports(exe, "--nothing") and not L.exe_supports(exe + "x", "--overlay")
        # the program is asked first: a build that prints the switch in its usage text is accepted even if the bytes do not show it
        open(exe, "w").write("#!/bin/sh\necho 'usage: ps2run [--overlay mods.ovl]' >&2\n"); os.chmod(exe, 0o755)
        L._flag_cache.clear()
        assert L.exe_supports(exe, "--overlay")
        open(exe, "wb").write(b"MZ" + b"\0" * 100 + b"--overlay\0" + b"\0" * 100); L._flag_cache.clear()
        r = L.play_windows(exe)
        assert r["ok"] and "--overlay" not in got["cmd"] and "mods" not in r["msg"].lower()   # no active.ovl: nothing passed
        ovl = os.path.join(mods, "active.ovl"); open(ovl, "wb").write(b"P3OVL001")
        assert L.overlay_file() == ovl
        r = L.play_windows(exe)
        c = got["cmd"]
        assert r["ok"] and c[c.index("--overlay") + 1] == "W:" + ovl and "File mods are on" in r["msg"], r
        open(exe, "wb").write(b"MZ" + b"\0" * 100)      # an older build that does not know the switch
        r = L.play_windows(exe)
        assert r["ok"] and "--overlay" not in got["cmd"] and "not applied" in r["msg"], r
    finally:
        L.DIR, L.to_win, L.win_disc, L.saves_dir, subprocess.Popen, L.load_cfg = old
        os.environ.pop("P3F_WINEXE", None)
print("ok   PC window file mods: runner patch applies once and refuses unknown source; the launcher passes the overlay only to a build that knows it")
