import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2web_cardbackup_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """  <button id="import-card" type="button" title="Put a .ps2 memory card file in slot 1">Import card</button>
        if (err) console.warn('memory card: could not write browser storage', err);
  onRuntimeInitialized: () => {
  if (!confirm('Replace the memory card in slot 1 with ' + file.name + '? The page reloads to use it.')) return;
  try {
    FS.writeFile(CARD_FILE, data);
const statsEl = document.getElementById('stats');
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
    assert 'id="backups"' in s and "backupCard('game save')" in s and "backupCard('page start')" in s and "backupCard('before import')" in s
    assert "already patched" in run(f).stdout
print("ok   card backup patch applies once, is idempotent and refuses unknown source")
