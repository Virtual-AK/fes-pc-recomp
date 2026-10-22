"""p3fes_showcode.py finds the unit holding an address and prints the code around it."""
import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "p3fes_showcode.py")
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "sub"))
    open(os.path.join(d, "sub", "unit_0001.cpp"), "w").write("x\nL_00329360:\n    a();\nL_003293C0:\n    b();\n}\n")
    open(os.path.join(d, "unit_0002.cpp"), "w").write("L_00500000:\n    z();\n")
    r = subprocess.run([sys.executable, tool, d, "0x003293B8", "0x00900000"], capture_output=True, text=True)
    assert "unit_0001.cpp" in r.stdout and "2> L_00329360:" in r.stdout and "a();" in r.stdout, r.stdout + r.stderr
    assert "(not found in any unit)" in r.stdout
print("ok   showcode finds the unit around an address")
