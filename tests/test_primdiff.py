import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "p3fes_primdiff.py")
def shape(f, x):
    return ("[prim] f%d type=4 tme=1 abe=1 tbp=38C0 frame=A0000\n[prim]   v0 x=%d y=2 z=3 rgba=FFFFFFFF s=0 t=0 q=1 u=0 v=0\n"
            "[prim]   v1 x=5 y=6 z=3 rgba=FFFFFFFF s=1 t=0 q=1 u=0 v=0\n") % (f, x)
with tempfile.TemporaryDirectory() as d:
    a, b = os.path.join(d, "a.txt"), os.path.join(d, "b.txt")
    open(a, "w").write("[gpu] hello\n" + shape(10, 1) + shape(10, 2) + shape(11, 3))
    open(b, "w").write(shape(14, 1) + shape(14, 9) + shape(15, 3))
    r = subprocess.run([sys.executable, tool, a, b], capture_output=True, text=True)
    o = r.stdout
    assert "A: 3 shapes   B: 3 shapes" in o and "identical from the start: 1 shapes" in o, o
    assert "first difference at shape 1" in o and "corner 0 differs" in o and "x=2" in o and "x=9" in o, o
    assert "only in A: 1   only in B: 1" in o, o
print("ok   primdiff compares two prim traces ignoring frame numbers and shows the first difference")
