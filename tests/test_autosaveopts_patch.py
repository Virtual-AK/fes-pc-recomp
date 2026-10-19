import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2web_autosaveopts_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """const AS_DB = 'ps2-autosave', AS_STORE = 'states', AS_EVERY = 120000, AS_KEEP = 3;
    for (const old of same.slice(AS_KEEP - 1)) await asRun(db, 'readwrite', (store) => store.delete(old.id));
function asSoon() {
  clearTimeout(asSoonTimer);
setInterval(() => asSave('timer'), AS_EVERY);
  card.append(title, help, list, bar);
  document.body.appendChild(box);
  async function fill() {
  help.textContent = 'The whole game is saved every 2 minutes and after each in-game save, in this browser. Resume reloads the page and offers that save on the start screen. The memory card is not part of an autosave.';
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
    assert "AS_EVERY" not in s and "AS_KEEP " not in s and "asOpts.keep - 1" in s and "asSchedule();" in s
    assert "if (!asOpts.afterSave) return;" in s and "ps2-autosave-options" in s and "asPrune" in s
    assert "already patched" in run(f).stdout
print("ok   web autosave settings patch applies once, is idempotent and refuses unknown source")
