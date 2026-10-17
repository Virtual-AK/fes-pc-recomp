import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_fix_path3_mask.py")
def run(d):
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True)
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "gs"))
    open(os.path.join(d, "gs", "gif.cpp"), "w").write('#include <cstring>\nvoid transfer(int path, const std::uint8_t *data, std::uint32_t qwc) {\n}\nvoid set_path3_masked(bool masked) { g_stat = (g_stat & ~2u) | (masked ? 2u : 0u); }\n')
    open(os.path.join(d, "gs", "gif.hpp"), "w").write("void set_path3_masked(bool masked);\n")
    open(os.path.join(d, "gs", "queue.hpp"), "w").write("enum Type { a, kDownloadAsync };\n")
    open(os.path.join(d, "system.cpp"), "w").write('#include "gs/gif.hpp"\nvoid vblank() {\n}\nvoid run() {\n            case gs::queue::kVuFence:\n}\n')
    open(os.path.join(d, "dmac.cpp"), "w").write("void finish(int ch) {\n    c.chcr &= ~0x100u;\n    hw::dmac_raise(static_cast<unsigned>(ch));\n}\n")
    r = run(d)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    g = open(os.path.join(d, "gs", "gif.cpp")).read()
    assert "transfer_direct" in g and "g_pend3" in g and "#include <vector>" in g
    assert "flush_path3" in open(os.path.join(d, "gs", "gif.hpp")).read()
    assert "gif::flush_path3();" in open(os.path.join(d, "system.cpp")).read()
    assert "[p3] queued" in g and "chain_end" in g and "vu_path3" in g
    assert "kPath3Flush" in open(os.path.join(d, "gs", "queue.hpp")).read()
    assert "gif::vu_path3(payload" in open(os.path.join(d, "system.cpp")).read()
    assert "gif::chain_end();" in open(os.path.join(d, "dmac.cpp")).read()
    assert "g_vmask" in g and "mask_up()" in g and "role() != gs::queue::Role::Vu) {\n            g_stat" in g
    assert "already patched" in run(d).stdout
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "gs"))
    for f in ("gs/gif.cpp", "gs/gif.hpp", "gs/queue.hpp", "system.cpp", "dmac.cpp"):
        open(os.path.join(d, f), "w").write("int x;\n")
    r = run(d)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
print("ok   PATH3 mask fix applies once, is idempotent and refuses unknown source")
