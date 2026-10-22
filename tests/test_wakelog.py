"""Long-wait log patch: applies once, is idempotent, refuses unknown source."""
import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_wakelog_patch.py")

def run(d):
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True)

SRC = ("#include <map>\r\nvoid block_current(Cpu &c, WaitType type, int id) {\r\n    Thread *t = current();\r\n    t->wait_id = id;\r\n    save_context(c, t->context);\r\n}\r\n"
       "void release(Thread &t, std::int64_t result) {\r\n    t.wait = kWaitNone;\r\n}\r\n")
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "runtime/src"))
    p = os.path.join(d, "runtime/src/kernel.cpp")
    open(p, "w", newline="").write(SRC)
    r = run(d)
    assert "patched (4 edits)" in r.stdout, r.stdout + r.stderr
    t = open(p, newline="").read()
    assert "PS2_WAKE_TRACE" in t and "wake_note_release(t, result);" in t and "wake_note_block(t->id" in t
    assert "\n" not in t.replace("\r\n", "")
    assert "already patched" in run(d).stdout
    open(p, "w").write("int main() {}\n")
    r = run(d)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
print("ok   long-wait log patch applies once, is idempotent and refuses unknown source")
