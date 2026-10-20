import os, re, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2web_autosavesync_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """const CS_URL = 'x';
const asReasons = {
    await asRun(db, 'readwrite', (store) => store.put({ id, key: asKey, reason, time: Date.now(), size: data.length, enc: packed.enc, bytes: packed.bytes }));
    for (const old of same.slice(asOpts.keep - 1)) await asRun(db, 'readwrite', (store) => store.delete(old.id));
      if (seen[e.reason] > asOpts.keep) await asRun(db, 'readwrite', (store) => store.delete(e.id));
          await asRun(db, 'readwrite', (store) => store.delete(entry.id));
    asKey = await asBuildKey();
      const wanted = Number(sessionStorage.getItem('ps2-resume-id'));
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
    assert "asDiskPush(rec)" in s and s.count("asDiskDelete(") >= 4 and "asDiskSync()" in s and "get('resume')" in s
    assert "already patched" in run(f).stdout
print("ok   web autosave sync patch applies once, is idempotent and refuses unknown source")
