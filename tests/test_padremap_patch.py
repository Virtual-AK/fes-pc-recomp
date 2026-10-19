import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2web_padremap_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """const padButtons = [[0, 14], [1, 13], [2, 15], [3, 12], [4, 10], [5, 11], [6, 8], [7, 9], [8, 0], [9, 3], [10, 1], [11, 2],
                    [12, 4], [13, 6], [14, 7], [15, 5]];
  if (gamepad) {
    for (const [index, bit] of padButtons) {
function keyShow() {
document.getElementById('keys').addEventListener('click', (e) => { e.target.blur(); keyShow(); });
  bar.append(reset, shut);
  card.append(title, help, list, bar);
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
    assert "padEntries(gamepad)" in s and "padCapturing" in s and "xbox:" in s and "nintendo:" in s
    assert "function keyShowKeyboard()" in s and "padShow(); });" in s and "of padButtons" not in s
    assert "already patched" in run(f).stdout
print("ok   web controller panel patch applies once, is idempotent and refuses unknown source")
