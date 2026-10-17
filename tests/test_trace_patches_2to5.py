import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tools = os.path.join(here, "..", "tools")
def run(script, arg):
    return subprocess.run([sys.executable, os.path.join(tools, script), arg], capture_output=True, text=True)
fake = '''#include "ps2/state.hpp"
void load_clut(std::uint64_t tex0) {
    const std::uint32_t cld = 0;
}
void feed_image(const std::uint8_t *data, std::size_t bytes) {
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
    steps = [("ps2run_trace_patch.py", "PS2_TRACE_TEX"), ("ps2run_trace_patch2.py", "g_up_bytes"),
             ("ps2run_trace_patch3.py", "PS2_DUMP_TEX"), ("ps2run_trace_patch4.py", "dump_tex_color")]
    for script, marker in steps:
        r = run(script, p)
        assert "patched" in r.stdout and "NOT" not in r.stdout, script + r.stdout + r.stderr
        assert marker in open(p).read(), script
        assert "already patched" in run(script, p).stdout, script
    # patch 2 to 4 refuse unknown source
    bad = os.path.join(d, "bad.cpp"); open(bad, "w").write("int x;\n")
    for script, _ in steps[1:]:
        r = run(script, bad)
        assert "NOT APPLIED" in r.stdout and r.returncode != 0, script
    # patch 5 works on a folder with vif.cpp and gs/gif.cpp
    os.makedirs(os.path.join(d, "src", "gs"))
    open(os.path.join(d, "src", "vif.cpp"), "w").write("    case 0x06: gif::set_path3_masked((imm >> 15) & 1u); break;\n")
    open(os.path.join(d, "src", "gs", "gif.cpp"), "w").write("void transfer(int path, const std::uint8_t *data, std::uint32_t qwc) {\n}\n")
    r = run("ps2run_trace_patch5.py", os.path.join(d, "src"))
    assert r.stdout.count("patched") == 2 and "NOT" not in r.stdout, r.stdout + r.stderr
    assert "PS2_TRACE_M3" in open(os.path.join(d, "src", "vif.cpp")).read()
    assert run("ps2run_trace_patch5.py", os.path.join(d, "src")).stdout.count("already patched") == 2
print("ok   trace patches 2 to 5 apply in order, are idempotent and refuse unknown source")
