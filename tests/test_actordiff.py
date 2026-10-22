"""p3fes_actordiff.py finds the record that stands still and then moves, and leaves out walkers and props."""
import os, subprocess, sys, tempfile
import numpy as np
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "p3fes_actordiff.py")

def f(*v):
    return np.array(v, dtype="<f4").view("<u4")

n = 0x40000
rng = np.random.default_rng(7)
a = rng.integers(0, 2 ** 32, n, dtype=np.uint32)
a[0x8000:0x8003] = f(100.0, 0.0, 50.0)   # the character: still, still, moved
a[0x9000:0x9003] = f(10.0, 0.0, 5.0)     # a walker: changes every time
a[0xA000:0xA003] = f(7.0, 1.0, 2.0)      # a prop: never changes
a[0xB000:0xB000 + 600] = 0                # a buffer that fills up between dumps (zero -> numbers)
b_fill = rng.uniform(1, 90, 600).astype('<f4').view('<u4')
b = a.copy(); b[0x9000:0x9003] = f(10.5, 0.0, 5.2)
c = b.copy(); c[0xB000:0xB000 + 600] = b_fill; c[0xC000:0xC003] = f(1.0, 0.0, 0.0); c[0x8000:0x8003] = f(103.0, 0.0, 51.5); c[0x9000:0x9003] = f(12.0, 0.0, 6.0)
with tempfile.TemporaryDirectory() as d:
    paths = []
    for name, arr in (("s1", a), ("s2", b), ("m", c)):
        p = os.path.join(d, name + ".bin"); arr.tofile(p); paths.append(p)
    r = subprocess.run([sys.executable, tool] + paths + ["--range", "0x1000-0x100000"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "group at 0x00020000" in r.stdout, r.stdout          # word 0x8000 * 4
    assert "0x00024000" not in r.stdout and "0x00028000" not in r.stdout and "0x0002C000" not in r.stdout and "0x00030000" not in r.stdout, r.stdout
    assert subprocess.run([sys.executable, tool], capture_output=True, text=True).returncode != 0
print("ok   actor diff finds the standing-then-moving record only")

# around mode: shows the words that differ near an address, including a counter that counts down
a2 = a.copy(); b2 = b.copy(); c2 = c.copy()
a2[0x8004] = 150; b2[0x8004] = 52; c2[0x8004] = 0
with tempfile.TemporaryDirectory() as d:
    paths = []
    for name, arr in (("s1", a2), ("s2", b2), ("m", c2)):
        p = os.path.join(d, name + ".bin"); arr.tofile(p); paths.append(p)
    out = os.path.join(d, "o.txt")
    r = subprocess.run([sys.executable, tool] + paths + ["--around", "0x20000", "--span", "0x40", "--out", out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0x00020010" in r.stdout and "150 / 52 / 0" in r.stdout and "the candidate" in r.stdout, r.stdout
    assert os.path.getsize(out) > 0
print("ok   actor diff --around lists the words that change near an address")

# findword mode: the master copy has few hits, a drawing buffer has many
a3 = a.copy(); b3 = b.copy(); c3 = c.copy()
w = f(-25.212)[0]
a3[0xD000] = w; b3[0xD000] = w; c3[0xD000] = f(-18.915)[0]
for k in range(40):
    a3[0xE000 + 16 * k] = w; b3[0xE000 + 16 * k] = w; c3[0xE000 + 16 * k] = f(-18.915)[0]
with tempfile.TemporaryDirectory() as d:
    paths = []
    for name, arr in (("s1", a3), ("s2", b3), ("m", c3)):
        p = os.path.join(d, name + ".bin"); arr.tofile(p); paths.append(p)
    r = subprocess.run([sys.executable, tool] + paths + ["--findword", hex(int(w))], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "at 0x00034000" in r.stdout and "at 0x00038000" not in r.stdout and "in 41 places" in r.stdout, r.stdout
print("ok   actor diff --findword lists the few-hit copy and skips the drawing buffer")
