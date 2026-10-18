import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2web_controls_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """title="Fullscreen (F or double click)"
const keyMap = { ArrowUp: 4, ArrowRight: 5, ArrowDown: 6, ArrowLeft: 7, KeyZ: 14, KeyX: 13, KeyA: 15, KeyS: 12,
                 KeyQ: 10, KeyW: 11, Digit1: 8, Digit2: 9, Enter: 3, Backspace: 0 };
const stickKeys = new Set(['KeyI', 'KeyJ', 'KeyK', 'KeyL']);
  if (e.code !== 'KeyF' || e.repeat || e.target.tagName === 'SELECT') return;
    if (keys.has('KeyJ')) lx = 0;
    if (keys.has('KeyL')) lx = 255;
    if (keys.has('KeyI')) ly = 0;
    if (keys.has('KeyK')) ly = 255;
"""
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "shell.html")
    open(f, "w").write("<html></html>\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "KeyE: 11" in s and "mouseLook()" in s and "'Backquote'" in s and "requestPointerLock" in s and "KeyT" in s
    assert "already patched" in run(f).stdout
print("ok   web controls patch (PCSX2-style keys, mouse look) applies once, is idempotent and refuses unknown source")
