import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_trace_patch12.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = ("#include <unordered_set>\n"
       "void xgkick(Unit &u, std::uint32_t address) {\n    gif::transfer(1, buffer, count);\n}\n"
       "void lower(Unit &u, std::uint32_t w, std::uint32_t pc, std::uint32_t &npc, bool &branch) {\n"
       "    case 0x00: {\n        const std::uint8_t *q = qword(u, r.vi[is] + static_cast<std::uint32_t>(imm11));\n        break;\n    }\n"
       "    case 0x01: {\n        std::uint8_t *q = qword(u, r.vi[it] + static_cast<std::uint32_t>(imm11));\n        break;\n    }\n}\n")
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "vu_micro.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert s.count("trace_vulq(u,") == 2 and s.index("void trace_vulq") < s.index("void lower")
    assert s.index("void vulq_kick") < s.index("void xgkick") and "vulq_kick(buffer, count, address);" in s
    assert "#include <vector>" in s and "#include <string>" in s
    assert "already patched" in run(f).stdout
    # upgrade of the first version (unique-case printing)
    OLDV = SRC.replace("void lower(", "void trace_vulq(const Unit &u, const char *kind, std::uint32_t pc) {\n}\n\nvoid lower(", 1)
    OLDV = OLDV.replace("imm11));\n        break;\n    }\n    case 0x01", "imm11));\n        trace_vulq(u, \"LQ\", pc, is, r.vi[is], imm11, w);\n        break;\n    }\n    case 0x01", 1)
    OLDV = OLDV.replace("imm11));\n        break;\n    }\n}", "imm11));\n        trace_vulq(u, \"SQ\", pc, it, r.vi[it], imm11, w);\n        break;\n    }\n}", 1)
    OLDV = OLDV.replace("void xgkick", "// PS2_TRACE_VULQ first version\nvoid xgkick", 1)
    open(f, "w").write(OLDV)
    r = run(f)
    assert "packet-linked" in r.stdout, r.stdout + r.stderr
    s2 = open(f).read()
    assert s2.count("void trace_vulq") == 1 and s2.count("trace_vulq(u,") == 2 and "vulq_kick" in s2
    assert "already patched" in run(f).stdout
print("ok   trace patch 12 (PS2_TRACE_VULQ) applies once, upgrades the first version, is idempotent and refuses unknown source")
