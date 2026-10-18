import os, subprocess, sys, tempfile, zlib
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "p3fes_ppm2png.py")
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "t.ppm")
    open(f, "wb").write(b"P6\n2 2\n255\n" + bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 9, 9, 9]))
    r = subprocess.run([sys.executable, tool, d], capture_output=True, text=True)
    assert r.returncode == 0 and "wrote" in r.stdout, r.stdout + r.stderr
    png = open(os.path.join(d, "t.png"), "rb").read()
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and b"IHDR" in png and b"IEND" in png
    # decode the IDAT back and compare with the source pixels
    i = png.index(b"IDAT")
    n = int.from_bytes(png[i - 4:i], "big")
    raw = zlib.decompress(png[i + 4:i + 4 + n])
    assert raw == b"\x00" + bytes([255, 0, 0, 0, 255, 0]) + b"\x00" + bytes([0, 0, 255, 9, 9, 9])
    r = subprocess.run([sys.executable, tool], capture_output=True, text=True)
    assert r.returncode == 1
print("ok   ppm2png writes a valid PNG with the same pixels")
