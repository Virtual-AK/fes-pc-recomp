"""Script-command trace patch: applies once, is idempotent, refuses unknown source."""
import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_commtrace_patch.py")

def run(d):
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True)

with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "runtime/src"))
    p = os.path.join(d, "runtime/src/dispatch.cpp")
    open(p, "w", newline="").write("#include <cstdio>\r\nvoid record_miss(std::uint32_t pc) {\r\n}\r\nvoid dispatch(Cpu &c) {\r\n    const std::uint32_t pc = c.pc;\r\n    if (pc & kUnwind) return;\r\n}\r\n")
    r = run(d)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    t = open(p, newline="").read()
    assert "PS2_COMM_TRACE" in t and "comm_trace(c, pc)" in t and "\r\n" in t and "\n" not in t.replace("\r\n", "")
    assert "already patched" in run(d).stdout
    open(p, "w").write("int main() {}\n")
    r = run(d)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
print("ok   script-command trace patch applies once, is idempotent and refuses unknown source")
