import os, shutil, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, '..', 'tools', 'ps2run_audiosrc_patch.py')
src = '/tmp/src/ps2-web-recomp/runtime/src/disc.cpp'
inc = '/tmp/src/ps2-web-recomp/runtime/include'
d = tempfile.mkdtemp()
os.makedirs(d + '/runtime/src')
run = lambda: subprocess.run(['python3', tool, d], capture_output=True, text=True).stdout.strip()
if not (os.path.exists(src) and shutil.which('g++')):
    open(d + '/runtime/src/disc.cpp', 'w').write('nothing here')
    assert run().startswith('PATCH NOT APPLIED')
    print('ok audiosrc: refuses unknown source (full test needs the reference source and g++)')
    sys.exit()
shutil.copy(src, d + '/runtime/src/disc.cpp')
assert run() == 'patched (4 edits)', run()
assert run() == 'already patched'
# build a fake disc (an outer volume with BGM.CVM and DATA.CVM that each hold a volume of their own) and read it back with the patched reader
shutil.copy(os.path.join(here, 'audiosrc_gen.py'), d + '/gen.py')
subprocess.run([sys.executable, 'gen.py'], cwd=d, check=True, capture_output=True)
open(d + '/h.cpp', 'w').write(r'''
#include "ps2/disc.hpp"
#include <cstdio>
#include <cstdlib>
#include <vector>
int main(int argc, char **argv) {
    if (argc < 4 || !ps2::disc::open(argv[1])) return 2;
    std::vector<unsigned> chunks;
    for (const char *p = argv[3]; *p;) { chunks.push_back(std::atoi(p)); while (*p && *p != ',') ++p; if (*p) ++p; }
    const unsigned total = ps2::disc::sector_count();
    std::FILE *out = std::fopen(argv[2], "wb");
    std::vector<unsigned char> buf(4096 * 2048);
    unsigned s = 0, i = 0;
    while (s < total) {
        unsigned n = chunks[i++ % chunks.size()];
        if (s + n > total) n = total - s;
        ps2::disc::read(s, n, buf.data());
        std::fwrite(buf.data(), 2048, n, out);
        s += n;
    }
    std::fclose(out);
}
''')
r = subprocess.run(['g++', '-std=c++17', '-O1', '-I' + inc, 'h.cpp', 'runtime/src/disc.cpp', '-o', 'h'], cwd=d, capture_output=True, text=True)
assert r.returncode == 0, r.stderr[-800:]
S = 2048
orig = open(d + '/disc.bin', 'rb').read()
regions = [tuple(map(int, l.split())) for l in open(d + '/regions.txt')]
def expect(pm, pv):
    b = bytearray(orig)
    for st, en, data, kind in regions:
        pct = pm if kind == 0 else pv
        if pct == 100:
            continue
        fs = st + data
        while fs + 18 <= en:
            old = (b[fs] << 8) | b[fs + 1]
            if not old & 0x8000:
                new = (old & 0xE000) | (((old & 0x1FFF) * pct + 50) // 100)
                b[fs] = new >> 8
                b[fs + 1] = new & 255
            fs += 18
    return bytes(b)
n = 0
for pm, pv in [(100, 100), (0, 100), (100, 0), (50, 30), (0, 0)]:
    for chunks in ['1', '16', '3,7,1,146,2', '146', '5,5,17']:
        env = dict(os.environ, PS2_VOL_MUSIC=str(pm), PS2_VOL_VOICE=str(pv))
        subprocess.run(['./h', 'disc.bin', 'out.bin', chunks], cwd=d, env=env, stderr=subprocess.DEVNULL, check=True)
        got = open(d + '/out.bin', 'rb').read()
        assert got == expect(pm, pv), ('mismatch', pm, pv, chunks)
        n += 1
shutil.rmtree(d)
print('ok audiosrc: patch applies; %d read patterns give exactly the expected scaled ADX blocks (music, voice archives, other files untouched)' % n)
