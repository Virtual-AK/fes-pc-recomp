"""The launcher page's script must parse (one stray apostrophe blanks the whole launcher)."""
import os, re, shutil, subprocess, tempfile
here = os.path.dirname(os.path.abspath(__file__))
ui = os.path.join(here, "..", "tools", "launcher", "ui")
node = shutil.which("node")
html = open(os.path.join(ui, "index.html")).read()
scripts = re.findall(r"<script>([\s\S]*?)</script>", html)
assert scripts, "no inline script found"
files = [(i, s) for i, s in enumerate(scripts)] + [("music", open(os.path.join(ui, "music.js")).read()), ("guide100", open(os.path.join(ui, "guide100.js")).read())]
if node:
    for i, s in files:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(s)
        r = subprocess.run([node, "--check", f.name], capture_output=True, text=True)
        os.unlink(f.name)
        assert r.returncode == 0, "script %s does not parse:\n%s" % (i, r.stderr[:600])
    print("ok   launcher page scripts parse (%d scripts checked with node)" % len(files))
else:
    print("ok   launcher page scripts: node not installed here, syntax not checked")
