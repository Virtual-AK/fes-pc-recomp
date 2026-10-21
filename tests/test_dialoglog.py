import os, re, shutil, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, '..', 'tools', 'ps2run_dialoglog_patch.py')
d = tempfile.mkdtemp()
os.makedirs(d + '/runtime/src'); os.makedirs(d + '/runtime/include/ps2')
open(d + '/runtime/include/ps2/disc.hpp', 'w').write('a\nstd::uint64_t sector_count();\nb\n')
open(d + '/runtime/src/disc.cpp', 'w').write('std::map<std::string, Entry> g_index;\nbool ready(std::uint32_t sector, std::uint32_t count) {\n    const std::size_t want = static_cast<std::size_t>(count) * kSector;\n    const std::size_t got = g_reader(static_cast<std::uint64_t>(sector) * kSector, out, want);\n')
open(d + '/runtime/src/system.cpp', 'w').write('x\nstd::uint64_t g_iop_synced = 0;\nvoid vblank() {\n    iop::sio2::flush_cards();\n    if (g_options.trace_iop_modules && g_frames % 25 == 0) y;\n}\n')
def run():
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True).stdout.strip()
assert run().startswith('patched (6'), 'first'
assert run() == 'already patched'
assert 'dlog_tick();' in open(d + '/runtime/src/system.cpp').read()
assert 'recent_data_reads' in open(d + '/runtime/src/disc.cpp').read()
open(d + '/runtime/src/system.cpp', 'w').write('nothing')
assert 'PATCH NOT APPLIED' in run()
# compile the logging function against synthetic memory (no game data) when a C++ compiler exists
if shutil.which('g++'):
    src = open(tool).read()
    body = re.search(r"FN_NEW = FN_OLD \+ r'''(.*?)'''\nCALL_OLD", src, re.S).group(1)
    cpp = ('#include <cstdio>\n#include <cstdint>\n#include <cstring>\n#include <cstdlib>\n#include <cctype>\n#include <string>\n#include <vector>\n'
           'constexpr std::uint32_t kRamSize=32u<<20;\nstd::uint8_t g_ram[kRamSize+64];\nstd::uint64_t g_frames=77;\nnamespace disc { std::string recent_data_reads() { return "5:2,9:1,"; } }\n' + body + '''
static void w32(std::uint32_t a, std::uint32_t v){ std::memcpy(g_ram+a,&v,4); }
int main(){
  const std::uint32_t S=0x1069484, B=0x200000, P0=0x200100, P1=0x200140;
  w32(S,0x290); w32(S+4,0xa48); w32(S+0x10,0x360); w32(S+0x14,0xb18); w32(S+0x18,B); w32(S+0x28,0x40001);
  std::memcpy(g_ram+B,"MSG_000",8); w32(B+0x20,P0); w32(B+0x24,P1); w32(B+0x28,0xd8);
  const unsigned char p0[]={0xf2,8,0xff,0xff,0xf1,0x3f,0xf5,0x1f,0x0c,1,0x0b,1,2,1,2,1,0xf2,0x48,2,1,'H','i','\\n',0xf2,0x47,0x0b,1,0xf1,4};
  const unsigned char p1[]={0xf2,8,0xff,0xff,0xf1,0x3f,0xf2,0x48,3,1,'B','y','e',0xf1,4};
  std::memcpy(g_ram+P0,p0,sizeof p0); std::memcpy(g_ram+P1,p1,sizeof p1);
  dlog_tick(); w32(S+0x28,0x40000); dlog_tick(); dlog_tick();
}
''')
    open(d + '/t.cpp', 'w').write(cpp)
    r = subprocess.run(['g++', '-std=c++17', '-o', d + '/t', d + '/t.cpp'], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[:500]
    subprocess.run([d + '/t'], cwd=d, env=dict(os.environ, PS2_DIALOG_LOG='out.tsv'), capture_output=True)
    lines = open(d + '/out.tsv').read().splitlines()
    assert lines == ['77\t12\t3\tMSG_000\t1\tBye\t5:2,9:1,', '77\t12\t2\tMSG_000\t0\tHi\\n\t5:2,9:1,'], lines
print('ok dialoglog patch: patch, idempotent, refusal, logging against synthetic memory')
