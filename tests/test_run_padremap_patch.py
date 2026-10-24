import os, re, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_padremap_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
src = open(tool).read()
def const(name):
    m = re.search(name + r' = """(.*?)"""\n', src, re.S)
    return m.group(1)
SRC = ("#include <cstdlib>\n" + const("OLD_TABLE") + "void f() {\n" + const("OLD_READ") +
       "}\nstd::string trim_text(std::string t) {\n  return t;\n}\nvoid g() {\n        const KeyName *entry = nullptr;\n}\n")
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "window.cpp")
    open(f, "w").write("int main() {}\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "ps2-pad-config" in s and "g_pad_buttons" in s and "kPadButtons" not in s and "pad_line(number" in s
    assert "already patched" in run(f).stdout
print("ok   PC runner controller remap patch applies once, is idempotent and refuses unknown source")
