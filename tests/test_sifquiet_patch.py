import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_sifquiet_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """        if (it == g_cmd_handlers.end()) {
            std::fprintf(stderr, "[sif] command 0x%08X has no handler\\n", h->cid);
            break;
        }
"""
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "sif.cpp")
    open(f, "w").write("int main() {}\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "seenCommands" in s and "shown once" in s and "has no handler\\n" not in s
    assert "already patched" in run(f).stdout
print("ok   sif message patch applies once, is idempotent and refuses unknown source")
