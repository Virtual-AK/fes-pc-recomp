import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_keyremap_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """#include <cstdlib>
struct PadBinding {
    int x;
};
        for (const KeyBinding &b : kKeys)
            if (keys[b.key]) pressed |= b.button;
        if (keys[SDL_SCANCODE_A]) lx = 0x00;
        if (keys[SDL_SCANCODE_D]) lx = 0xFF;
        if (keys[SDL_SCANCODE_W]) ly = 0x00;
        if (keys[SDL_SCANCODE_S]) ly = 0xFF;
        if (keys[SDL_SCANCODE_F]) rx = 0x00;
        if (keys[SDL_SCANCODE_H]) rx = 0xFF;
        if (keys[SDL_SCANCODE_T]) ry = 0x00;
        if (keys[SDL_SCANCODE_G]) ry = 0xFF;
"""
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "window.cpp")
    open(f, "w").write("int main() {}\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "load_key_file" in s and "PS2_KEYS" in s and "g_sticks" in s and "kKeys)" not in s.split("keysLoaded")[1]
    assert "keys[SDL_SCANCODE_A]" not in s
    assert "already patched" in run(f).stdout
print("ok   PC runner key remap patch applies once, is idempotent and refuses unknown source")
