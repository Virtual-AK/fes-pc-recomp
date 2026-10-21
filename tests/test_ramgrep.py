"""ramgrep finds a phrase stored in a shifted 1-byte table and in a 2-byte table."""
import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "p3fes_ramgrep.py")
with tempfile.TemporaryDirectory() as d:
    b = bytearray(os.urandom(100000))
    t = "Hello there"
    b[1000:1000 + len(t)] = bytes(ord(c) + 0x30 for c in t)
    for i, c in enumerate(t):
        b[5000 + 2 * i:5002 + 2 * i] = (ord(c) + 0x8100).to_bytes(2, "little")
    p = os.path.join(d, "x.bin")
    open(p, "wb").write(b)
    r = subprocess.run([sys.executable, tool, p, t], capture_output=True, text=True)
    out = r.stdout
    assert "000003e8" in out and "00001388" in out, out + r.stderr
print("ok   ramgrep finds shifted 1-byte and 2-byte text")
