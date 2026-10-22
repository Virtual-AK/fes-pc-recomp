"""Store watch patch: applies once, is idempotent, refuses unknown source."""
import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_storewatch_patch.py")

def run(d):
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True)

HPP = ("extern std::uint8_t g_ram[];\r\ninline void st32(std::uint32_t a, std::uint32_t v) {\r\n}\r\n"
       "inline void st64(std::uint32_t a, std::uint64_t v) {\r\n}\r\ninline void st128(std::uint32_t a, const Reg128 &v) {\r\n}\r\n")
CPP = "Cpu g_cpu;\r\nOptions g_options;\r\n"
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "runtime/include/ps2")); os.makedirs(os.path.join(d, "runtime/src"))
    h = os.path.join(d, "runtime/include/ps2/memory.hpp"); c = os.path.join(d, "runtime/src/system.cpp")
    open(h, "w", newline="").write(HPP); open(c, "w", newline="").write(CPP)
    r = run(d)
    assert "patched (5 edits)" in r.stdout, r.stdout + r.stderr
    t = open(h, newline="").read(); u = open(c, newline="").read()
    assert t.count("store_watch_hit(a,") == 3 and "PS2_STORE_WATCH" in u
    assert "\n" not in t.replace("\r\n", "") and "\n" not in u.replace("\r\n", "")
    assert "already patched" in run(d).stdout
    open(c, "w").write("int main() {}\n")
    open(h, "w", newline="").write(HPP)
    r = run(d)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    assert "store_watch_hit" not in open(h, newline="").read()   # nothing half-applied
print("ok   store watch patch applies once, is idempotent and refuses unknown source")
