import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_vif_v2zero_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = ("template <std::uint32_t Bits, std::uint32_t Components, bool Usn>\nvoid unpack_fast(int x) {\n"
       "        } else if constexpr (Components == 2) {\n            value[2] = value[0];\n            value[3] = value[1];\n        }\n}\n"
       "void unpack() {\n                if (components == 1) value[1] = value[2] = value[3] = value[0];\n"
       "                else if (components == 2) { value[2] = value[0]; value[3] = value[1]; }\n"
       "        for (std::uint32_t j = 0; j < 4; ++j) {\n            std::uint32_t m = masked ? 1 : 0;\n            if (fill && m == 0) m = 1;\n            std::uint32_t out;\n            if (m == 3) continue;\n        }\n}\n")
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "vif.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert s.count("v2_zero()") == 3 and "#include <cstdlib>" in s and s.index("bool v2_zero") < s.index("void unpack_fast")
    assert s.count("v2_keep()") == 3 and "PS2_VIF_V2KEEP" in s
    assert 'getenv("PS2_VIF_V2REPEAT") == nullptr' in s and "PS2_VIF_V2ZERO" not in s
    assert "already patched" in run(f).stdout
    # upgrade of a tree that only has the zero switch (first version)
    old = s.replace('getenv("PS2_VIF_V2REPEAT") == nullptr', 'getenv("PS2_VIF_V2ZERO") != nullptr').replace("bool v2_keep() {\n    static const bool k = std::getenv(\"PS2_VIF_V2KEEP\") != nullptr;\n    return k;\n}\n", "")
    old = old.replace("            if (v2_keep()) {\n                std::uint32_t old[4];\n                std::memcpy(old, mem + (addr & mask) * 16, 16);\n                value[2] = old[2];\n                value[3] = old[3];\n            } else if (v2_zero()) {", "            if (v2_zero()) {")
    old = old.replace("            if (!fill && components == 2 && j >= 2 && v2_keep()) continue;\n", "")
    assert "v2_keep" not in old
    open(f, "w").write(old)
    r = run(f)
    assert "now the default" in r.stdout, r.stdout + r.stderr
    assert open(f).read() == s
    # upgrade of a tree that has the zero and keep switches (second version)
    open(f, "w").write(s.replace('getenv("PS2_VIF_V2REPEAT") == nullptr', 'getenv("PS2_VIF_V2ZERO") != nullptr'))
    r = run(f)
    assert "now the default" in r.stdout and open(f).read() == s, r.stdout + r.stderr
    assert "already patched" in run(f).stdout
print("ok   VIF V2-zero test switch applies once, is idempotent and refuses unknown source")
