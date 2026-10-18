import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2web_logcapture_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "shell.html")
    open(f, "w").write("<script>var x;</script>\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write('<script>var a=1;var Module={canvas:c,print:e=>console.log(e),printErr:e=>console.error(e),x:1};</script>')
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert 'print: (text) => __out(text)' in s and 'printErr: (text) => __out(text, 1)' in s and s.index('function __out') < s.index('var Module')
    assert "already patched" in run(f).stdout
    open(f, "w").write('var Module = {\n  print: (text) => console.log(text),\n  printErr: (text) => console.log(text),\n  x: 1,\n};')
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert 'console.log(text)' not in s and 'print: (text) => __out(text)' in s and 'printErr: (text) => __out(text, 1)' in s
print("ok   web log capture patch applies once, is idempotent and refuses unknown source")
