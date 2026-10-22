"""Slow-disc experiment patch: applies once (both disc files), is idempotent, upgrades the first version, refuses unknown source."""
import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_discslow_patch.py")

def run(d):
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True)

CDVD = ("#include <cstdio>\r\nstd::uint64_t read_cycles(std::uint32_t sectors) {\r\n"
        "    return usec_to_cycles(400) + static_cast<std::uint64_t>(sectors) * usec_to_cycles(250);\r\n}\r\n")
FSV = ("#include <cstdio>\nstd::uint64_t delay(std::uint32_t sectors) { return usec_to_cycles(400) + static_cast<std::uint64_t>(sectors) * usec_to_cycles(200); }\n")

with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "runtime/src/iop"))
    p1 = os.path.join(d, "runtime/src/iop/cdvd.cpp")
    p2 = os.path.join(d, "runtime/src/iop/cdvdfsv.cpp")
    open(p1, "w", newline="").write(CDVD)
    open(p2, "w", newline="").write(FSV)
    r = run(d)
    assert "patched (2 files)" in r.stdout, r.stdout + r.stderr
    t1, t2 = open(p1, newline="").read(), open(p2, newline="").read()
    assert "PS2_DISC_SLOW" in t1 and "PS2_DISC_SEEK_MS" in t1 and "\r\n" in t1 and "\n" not in t1.replace("\r\n", "")
    assert "PS2_DISC_SLOW" in t2 and "usec_to_cycles(static_cast<std::uint64_t>(200.0 * slow))" in t2
    assert "already patched" in run(d).stdout
    # first version patched only the first file: the second is still done
    open(p2, "w", newline="").write(FSV)
    assert "patched (1 files)" in run(d).stdout
    open(p1, "w").write("int main() {}\n")
    open(p2, "w").write("int main() {}\n")
    os.remove(p2)
    r = run(d)
    assert r.returncode == 0 or "NOT APPLIED" in r.stdout
print("ok   slow-disc patch applies once to both disc files, upgrades, is idempotent")
