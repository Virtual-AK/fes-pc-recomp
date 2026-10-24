"""Moved-file support: the poke patch applies once, and table_pokes finds the game's file table entry and gives the new size and sector."""
import os, struct, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools"))
import p3fes_modmap as M

SRC = ("#include <cstdlib>\n#include <cstdio>\nbool load_elf(const std::string &path, std::uint32_t &entry) {\n"
       "        std::memcpy(g_ram + vaddr, data.data() + offset, filesz);\n"
       "        std::memset(g_ram + vaddr + filesz, 0, memsz - filesz);\n"
       "    }\n    return true;\n}\n")
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "runtime/src"))
    p = os.path.join(d, "runtime/src/system.cpp")
    open(p, "w", newline="").write(SRC)
    tool = os.path.join(here, "..", "tools", "ps2run_poke_patch.py")
    r = subprocess.run([sys.executable, tool, d], capture_output=True, text=True)
    assert "patched (1 edits)" in r.stdout, r.stdout + r.stderr
    assert "PS2_POKE" in open(p).read()
    assert "already patched" in subprocess.run([sys.executable, tool, d], capture_output=True, text=True).stdout
    open(p, "w").write("int main() {}\n")
    assert "NOT APPLIED" in subprocess.run([sys.executable, tool, d], capture_output=True, text=True).stdout

# the tail of load_elf as the mod-switch patch leaves it (a hook call before the return)
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "runtime/src"))
    open(os.path.join(d, "runtime/src/system.cpp"), "w").write(SRC.replace("    }\n    return true;", "    }\n    if (ps2_apply_mods_hook) ps2_apply_mods_hook(g_ram);\n    return true;"))
    r = subprocess.run([sys.executable, tool, d], capture_output=True, text=True)
    t = open(os.path.join(d, "runtime/src/system.cpp")).read()
    assert "patched (1 edits)" in r.stdout and t.index("PS2_POKE") < t.index("ps2_apply_mods_hook(g_ram)"), r.stdout

prog = bytearray(0x400)
prog[0:4] = b"\x7fELF"
struct.pack_into("<I", prog, 28, 52); struct.pack_into("<H", prog, 42, 32); struct.pack_into("<H", prog, 44, 1)
struct.pack_into("<6I", prog, 52, 1, 0x80, 0x100000, 0, 0x300, 0x300)
struct.pack_into("<III", prog, 0x200, 388416, 0, 629543)
struct.pack_into("<III", prog, 0x230, 388416, 0, 629000)      # same size, another file
mv = {"key": "x", "old_size": 388416, "old_lba": 629543, "new_size": 670912, "new_lba": 123456}
pk, notes = M.table_pokes(bytes(prog), [mv])
assert pk == [(0x100180, 670912), (0x100188, 123456)] and not notes, (pk, notes)
pk, notes = M.table_pokes(bytes(prog), [dict(mv, old_lba=1)])
assert pk == [] and "0 table entries" in notes[0]
print("ok   moved files: poke patch applies once; the game's file table entry is found and gets the new size and sector")
