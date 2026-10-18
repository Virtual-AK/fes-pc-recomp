import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_trace_patch7.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = '#include "ps2/state.hpp"\n\n#include <cstdio>\n\nnamespace {\n\nstd::uint32_t unpack_words(int x) {\n}\nvoid run_vu() {\n    vu::run(unit, address);\n}\nvoid unpack() {\n    const std::uint32_t components = vn + 1;\n    const std::uint32_t bits = element_bits(vl);\n    std::size_t bit_pos = 0;\n}\n}\n'
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "vif.cpp")
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "PS2_TRACE_VIF" in s and "[vifu]" in s and '"ps2/system.hpp"' in s and "<cstdlib>" in s
    assert s.index("bool trace_vif") < s.index("std::uint32_t unpack_words")
    assert "already patched" in run(f).stdout
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
print("ok   trace patch 7 (PS2_TRACE_VIF) applies once, is idempotent and refuses unknown source")
