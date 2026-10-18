import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ppm2png.py")
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "a.ppm")
    open(f, "wb").write(b"P6\n2 2\n255\n" + bytes(range(12)))
    r = subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
    assert "wrote" in r.stdout, r.stdout + r.stderr
    assert open(os.path.join(d, "a.png"), "rb").read(8) == b"\x89PNG\r\n\x1a\n"
print("ok   ppm2png turns a frame into a png picture")
