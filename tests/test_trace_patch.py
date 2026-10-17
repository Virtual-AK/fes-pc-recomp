import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_trace_patch.py")
fake = '''#include "ps2/state.hpp"
void load_clut(std::uint64_t tex0) {
    const std::uint32_t cld = 0;
}
void f() {
    case 0x06: case 0x07:
        s.ctx[reg - 6].tex0 = value;
        load_clut(value);
        break;
    case 0x16: case 0x17: {
        c.tex0 = (c.tex0 & ~mask) | (value & mask);
        load_clut(c.tex0);
    }
    case 0x53:
        s.trxdir = value;
        g_transfer = Transfer{};
}
'''
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "gs.cpp")
    open(p, "w").write(fake)
    r = subprocess.run([sys.executable, tool, p], capture_output=True, text=True)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    t = open(p).read()
    assert "PS2_TRACE_TEX" in t and 'print_tex0("TEX0"' in t and "[trx]" in t and '"ps2/system.hpp"' in t
    r2 = subprocess.run([sys.executable, tool, p], capture_output=True, text=True)
    assert "already patched" in r2.stdout
    bad = os.path.join(d, "bad.cpp")
    open(bad, "w").write("int x;\n")
    r3 = subprocess.run([sys.executable, tool, bad], capture_output=True, text=True)
    assert "NOT APPLIED" in r3.stdout and r3.returncode != 0
print("ok   trace patch applies once, is idempotent and refuses unknown source")
