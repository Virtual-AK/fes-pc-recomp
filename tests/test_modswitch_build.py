# End to end: patch a copy of the translator, translate a tiny MIPS program that has mod switches, compile it and run every on/off combination.
# Needs a copy of the unpatched ps2-web-recomp source (set P3FES_UPSTREAM, or keep one in /tmp/src/ps2-web-recomp) and clang++; skipped otherwise.
import os, shutil, struct, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tools = os.path.join(here, "..", "tools")
up = os.environ.get("P3FES_UPSTREAM") or "/tmp/src/ps2-web-recomp"
cxx = shutil.which("clang++")
if not (os.path.isdir(os.path.join(up, "recomp")) and cxx):
    print("skip modswitch build test: no upstream source copy or no clang++"); sys.exit(0)

def enc(*w): return b"".join(struct.pack("<I", x) for x in w)
def mk(path, text, base=0x100000, size=0x1000):
    body = bytearray(size); body[0:len(text)] = text
    hdr = bytearray(52); hdr[0:4] = b"\x7fELF"; hdr[4] = 1; hdr[5] = 1
    struct.pack_into("<I", hdr, 24, base); struct.pack_into("<I", hdr, 0x1C, 52); struct.pack_into("<HH", hdr, 0x2A, 32, 1)
    open(path, "wb").write(bytes(hdr) + struct.pack("<8I", 1, 84, base, base, size, size, 5, 16) + bytes(body))

def sh(*cmd, **kw):
    r = subprocess.run(list(cmd), capture_output=True, text=True, **kw)
    assert r.returncode == 0, (cmd[:3], r.stdout[-800:], r.stderr[-1500:])
    return r.stdout

with tempfile.TemporaryDirectory() as d:
    p = lambda n: os.path.join(d, n)
    src = p("src"); shutil.copytree(up, src, ignore=shutil.ignore_patterns(".git", "build", "tools", "generated", "games"))
    out = sh(sys.executable, os.path.join(tools, "ps2recomp_modswitch_patch.py"), cwd=src)
    assert "patched" in out
    assert "already patched" in sh(sys.executable, os.path.join(tools, "ps2recomp_modswitch_patch.py"), cwd=src)
    rc = subprocess.run([cxx, "-std=c++23", "-O0", "-o", p("eerecomp")] + [os.path.join(src, "recomp", f) for f in ("main.cpp", "codegen.cpp", "analysis.cpp", "elf.cpp", "r5900.cpp", "snr2.cpp")], capture_output=True, text=True)
    assert rc.returncode == 0, rc.stderr[-1500:]
    # program: v0=1; v1=5 [mod0: 9]; a0=v0+v1; a1=1 [mod1: jump to a cave that sets a1=7]; a1+=a0;
    #          beq v0,zero -> skip a2=3 [mod2: bne; mod3: delay slot a2=4]; a3=9; t0=5
    prog = enc(0x24020001, 0x24030005, 0x00432021, 0x24050001, 0, 0x00A42821,
               0x10400002, 0x24060003, 0x24070009, 0x24080005, 0x03E00008, 0)
    mk(p("van.elf"), prog)
    cave = 0x300000
    open(p("m0.pnach"), "w").write("patch=1,EE,20100004,extended,24030009\n")
    open(p("m1.pnach"), "w").write("patch=1,EE,2010000C,extended,%08X\npatch=1,EE,20100010,extended,00000000\n"
        "patch=1,EE,20300000,extended,24050007\npatch=1,EE,20300004,extended,%08X\npatch=1,EE,20300008,extended,00000000\npatch=0,EE,00000100,word,DEADBEEF\n" % (0x08000000 | cave >> 2, 0x08000000 | 0x100014 >> 2))
    open(p("m2.pnach"), "w").write("patch=1,EE,20100018,extended,14400002\n")
    open(p("m3.pnach"), "w").write("patch=1,EE,2010001C,extended,24060004\n")
    sh(sys.executable, os.path.join(tools, "p3fes_pnach_apply.py"), p("van.elf"), *sum((["--mod", "m%d:%d=%s" % (i, i, p("m%d.pnach" % i))] for i in range(4)), []),
       "-o", p("comb.elf"), "--entries", p("e.txt"), "--variants", p("v.txt"))
    sh(p("eerecomp"), p("comb.elf"), "--entries", p("e.txt"), "--variants", p("v.txt"), "--vanilla", p("van.elf"), "--out", p("gen"))
    assert "ps2_mods" in open(p("gen/unit_0000.cpp")).read()
    open(p("drv.cpp"), "w").write('''#include "units.hpp"
#include <cstdio>
#include <cstdlib>
#include <cstring>
void register_generated_code();
void (*ps2_apply_mods_hook)(std::uint8_t *) = nullptr;
namespace ps2 { void register_units(const UnitInfo*, unsigned) {} void bad_entry(Cpu&, unsigned) {} bool preempt(Cpu&) { return false; } }
int main(int, char **argv) {
  setenv("PS2_MODS", argv[1], 1);
  register_generated_code();                                   // the real runtime calls the hook after loading the program
  static std::uint8_t ram[0x1000] = {};
  if (ps2_apply_mods_hook) ps2_apply_mods_hook(ram);
  static ps2::Cpu c{}; c.budget = 1000; gen::unit_0000(c, 1u, 0u);
  unsigned data; std::memcpy(&data, ram + 0x100, 4);
  std::printf("%u %u %u %u %u", (unsigned)c.r[5].w[0], (unsigned)c.r[6].w[0], (unsigned)c.r[7].w[0], (unsigned)c.r[8].w[0], data);
}
''')
    rt = os.path.join(src, "runtime")
    gens = [os.path.join(p("gen"), f) for f in os.listdir(p("gen")) if f.endswith(".cpp")]
    rc = subprocess.run([cxx, "-std=c++23", "-O0", "-I" + os.path.join(rt, "include"), "-I" + os.path.join(rt, "src"), "-I" + p("gen"), p("drv.cpp")] + gens + ["-o", p("drv")], capture_output=True, text=True)
    assert rc.returncode == 0, rc.stderr[-1500:]
    for mask in range(16):
        v0 = 9 if mask & 1 else 5                      # v1
        a0 = 1 + v0
        a1 = (7 if mask & 2 else 1) + a0
        taken = bool(mask & 4)                         # bne taken: the delay slot still runs, a3 is skipped
        a2 = 4 if mask & 8 else 3
        a3 = 0 if taken else 9
        got = sh(p("drv"), str(mask)).split()
        # the start-up data write belongs to mod 1 (and to nothing else): it is in memory exactly when bit 1 is on
        assert got == [str(a1), str(a2), str(a3), "5", str(0xDEADBEEF if mask & 2 else 0)], (mask, got, (a1, a2, a3, 5))
print("ok   mod switches: translated and run, all 16 on/off combinations of 4 mods give the right result (code swap, jump to new memory, branch, delay slot, start-up data write)")
