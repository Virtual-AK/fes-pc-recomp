import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_trace_patch6.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = "void kick(bool draw) {\n    State &s = g_state;\n    if (draw) {\n        if (cpu_raster()) raster::draw(s, s.queue, needed);\n    }\n}\n"
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "gs.cpp")
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "PS2_TRACE_PRIM" in s and "trace_prim(s, needed);" in s and s.index("void trace_prim") < s.index("void kick")
    assert "ofx=%u" in s and "xyoffset" in s
    assert "already patched" in run(f).stdout
    assert "pabe=%llX" in s and "s.prmodecont" in s
    # upgrade of a tree patched by the second version (offset, but no global switches)
    v2 = s.replace(" pmc=%llX pm=%llX cc=%llX pabe=%llX fba=%llX scis=%llX", "")
    v2 = v2.replace(",\n                 static_cast<unsigned long long>(s.prmodecont), static_cast<unsigned long long>(s.prmode), static_cast<unsigned long long>(s.colclamp),\n                 static_cast<unsigned long long>(s.pabe), static_cast<unsigned long long>(c.fba), static_cast<unsigned long long>(c.scissor));", ");")
    assert "pabe=%llX" not in v2 and "s.prmodecont" not in v2
    open(f, "w").write(v2)
    r = run(f)
    assert "global" not in r.stdout and "prmodecont" in r.stdout, r.stdout + r.stderr
    assert open(f).read() == s
    # upgrade of a tree patched by the first version (no offset at all)
    v1 = v2.replace(" ofx=%u ofy=%u", "").replace(",\n                 static_cast<unsigned>(c.xyoffset & 0xFFFFu), static_cast<unsigned>((c.xyoffset >> 32) & 0xFFFFu));", ");")
    assert "ofx=%u" not in v1 and "xyoffset" not in v1
    open(f, "w").write(v1)
    r = run(f)
    assert "offset added" in r.stdout and "prmodecont" in r.stdout, r.stdout + r.stderr
    assert open(f).read() == s
    assert "already patched" in run(f).stdout
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
print("ok   trace patch 6 (PS2_TRACE_PRIM) applies once, upgrades the old version, is idempotent and refuses unknown source")
