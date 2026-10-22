"""p3fes_counters.py finds words that tick steadily between two dumps."""
import os, subprocess, sys, tempfile
try:
    import numpy as np
except ImportError:
    print("skip numpy missing"); raise SystemExit
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "p3fes_counters.py")
with tempfile.TemporaryDirectory() as d:
    def dump(name, frame, tick, fl, fixed):
        m = np.zeros(0x2000000 // 4, dtype='<u4')
        m[0x400000 // 4] = tick                 # integer counter, +1 per frame
        m[0x400010 // 4] = np.float32(fl).view('<u4')   # float timer, 1/60 per frame
        m[0x400020 // 4] = fixed                # does not move
        m.tofile(os.path.join(d, "ramdump_001_f%d.bin" % frame))
    dump("a", 1000, 10, 0.5, 7); dump("b", 1200, 210, 0.5 + 200 / 60, 7); dump("c", 1300, 5, 4.0, 7)
    r = subprocess.run([sys.executable, tool] + [os.path.join(d, "ramdump_001_f%d.bin" % f) for f in (1000, 1200, 1300)], capture_output=True, text=True)
    assert "0x00400000" in r.stdout and "reset" in r.stdout and "0x00400010" in r.stdout, r.stdout + r.stderr
    assert "0x00400020" not in r.stdout
print("ok   counters tool finds integer and decimal counters")
