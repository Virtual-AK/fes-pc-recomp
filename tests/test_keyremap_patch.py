import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2web_keyremap_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """  <button id="backups" type="button" title="Earlier versions of the memory card kept in this browser">Backups</button>
const keyMap = { ArrowUp: 4, ArrowRight: 5, ArrowDown: 6, ArrowLeft: 7, KeyI: 12, KeyL: 13, KeyK: 14, KeyJ: 15,
                 KeyQ: 10, KeyE: 11, Digit1: 8, Digit3: 9, Digit2: 1, Digit4: 2, Enter: 3, Backspace: 0 };
const stickKeys = new Set(['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyT', 'KeyF', 'KeyG', 'KeyH']);
window.addEventListener('keydown', (e) => { if (e.code in keyMap || stickKeys.has(e.code)) { keys.add(e.code); e.preventDefault(); } });
    if (keys.has('KeyA')) lx = 0;
    if (keys.has('KeyD')) lx = 255;
    if (keys.has('KeyW')) ly = 0;
    if (keys.has('KeyS')) ly = 255;
    if (keys.has('KeyF')) rx = 0;
    if (keys.has('KeyH')) rx = 255;
    if (keys.has('KeyT')) ry = 0;
    if (keys.has('KeyG')) ry = 255;
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
    assert 'id="keys"' in s and "ps2-keymap" in s and "stickMap" in s and "stickKeys" not in s and "keys.has('KeyA')" not in s
    assert "already patched" in run(f).stdout
print("ok   web key remap patch applies once, is idempotent and refuses unknown source")
