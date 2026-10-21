"""Audio volume (and an audio probe) for the PC window of PS2 Web Recomp (runtime/src/iop/spu2.cpp).

PS2_VOL_MASTER=<0..200>  percent of the game's own volume for everything (default 100). The launcher sets it from Settings > Audio.
PS2_AUDIO_PROBE=1        research switch: once a second the PC window log gets a line like
    [audio] core0 input 0 voices 4:812 7:3100 | core1 input 9020 voices 2:150
  which says, for each of the two sound chips, how loud the streamed input (music and voice files are streamed) and each of its sound voices
  were during that second. Playing a moment with only music, then only a voice line, then only a sound effect shows which of them carries
  which kind of sound; that is what separate Music / Voices / Effects volumes will be built on.

Run in the ps2-web-recomp folder:  python3 ps2run_audio_patch.py [folder]
(idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
REL = 'runtime/src/iop/spu2.cpp'

TICK_OLD = 'void tick() {\n    std::int16_t out[kBatch * 2];\n'
TICK_NEW = r'''// ---- audio volume and probe (ps2run_audio_patch.py)
int audio_percent(const char *name, int def) {
    const char *e = std::getenv(name);
    if (!e || !*e) return def;
    const int v = std::atoi(e);
    return v < 0 ? 0 : (v > 200 ? 200 : v);
}

struct AudioProbe {
    std::int32_t vpeak[2][24] = {};
    std::int32_t ipeak[2] = {};
    std::uint64_t samples = 0;
};

void tick() {
    static const int vol_master = audio_percent("PS2_VOL_MASTER", 100);
    static const bool probe = std::getenv("PS2_AUDIO_PROBE") != nullptr;
    static AudioProbe pr;
    std::int16_t out[kBatch * 2];
'''
VOICE_OLD = '            render_voice(v, sum[c], i == 1 ? rings[c][2] : i == 3 ? rings[c][3] : nullptr);\n'
VOICE_NEW = r'''            std::int16_t *vr = i == 1 ? rings[c][2] : i == 3 ? rings[c][3] : nullptr;
            std::int16_t vtmp[kBatch];
            if (probe && !vr) {
                std::memset(vtmp, 0, sizeof vtmp);
                vr = vtmp;
            }
            render_voice(v, sum[c], vr);
            if (probe && vr)
                for (unsigned n = 0; n < kBatch; ++n) {
                    const std::int32_t a = vr[n] < 0 ? -vr[n] : vr[n];
                    if (a > pr.vpeak[c][i]) pr.vpeak[c][i] = a;
                }
'''
IN_OLD = '''        for (unsigned n = 0; n < kBatch; ++n)
            render_input(c, sum[c][n][0], sum[c][n][1], c ? unused[0] : rings[0][0][n], c ? unused[1] : rings[0][1][n]);
'''
IN_NEW = '''        for (unsigned n = 0; n < kBatch; ++n) {
            const std::int32_t before = sum[c][n][0];
            render_input(c, sum[c][n][0], sum[c][n][1], c ? unused[0] : rings[0][0][n], c ? unused[1] : rings[0][1][n]);
            if (probe) {
                const std::int32_t d = sum[c][n][0] - before;
                const std::int32_t a = d < 0 ? -d : d;
                if (a > pr.ipeak[c]) pr.ipeak[c] = a;
            }
        }
'''
OUT_OLD = '''        out[n * 2] = clamp16(mix[0]);
        out[n * 2 + 1] = clamp16(mix[1]);
'''
OUT_NEW = '''        out[n * 2] = clamp16(mix[0] * vol_master / 100);
        out[n * 2 + 1] = clamp16(mix[1] * vol_master / 100);
'''
RING_OLD = '    write_rings(0, rings[0]);\n    write_rings(1, rings[1]);\n'
RING_NEW = RING_OLD + r'''    if (probe && (pr.samples += kBatch) >= 48000) {
        std::string line = "[audio]";
        for (int c = 0; c < 2; ++c) {
            line += " core" + std::to_string(c) + " input " + std::to_string(pr.ipeak[c]) + " voices";
            for (int i = 0; i < 24; ++i)
                if (pr.vpeak[c][i] > 100) line += " " + std::to_string(i) + ":" + std::to_string(pr.vpeak[c][i]);
            if (c == 0) line += " |";
        }
        std::fprintf(stderr, "%s\n", line.c_str());
        pr = AudioProbe{};
    }
'''
INC_OLD = '#include <deque>\n'
INC_NEW = INC_OLD + '#include <string>\n'
EDITS = [(INC_OLD, INC_NEW), (TICK_OLD, TICK_NEW), (VOICE_OLD, VOICE_NEW), (IN_OLD, IN_NEW), (OUT_OLD, OUT_NEW), (RING_OLD, RING_NEW)]


def fail(msg):
    print("PATCH NOT APPLIED:", msg)
    raise SystemExit(1)


try:
    with open(root + '/' + REL, newline='') as f:
        t = f.read()
except OSError:
    fail("cannot read " + REL)
crlf = '\r\n' in t
t = t.replace('\r\n', '\n')
orig = t
# the first version wrote a literal backslash-n instead of a line break in the probe line: repair it
t = t.replace('std::fprintf(stderr, "%s\\\\n", line.c_str());', 'std::fprintf(stderr, "%s\\n", line.c_str());')
if all(new in t for _, new in EDITS):
    if t != orig:
        with open(root + '/' + REL, 'w', newline='') as f:
            f.write(t.replace('\n', '\r\n') if crlf else t)
        print("repaired the probe line of an earlier version")
    else:
        print("already patched")
    raise SystemExit
done = 0
for old, new in EDITS:
    if new in t:
        continue
    if t.count(old) != 1:
        fail(REL + " does not look like the expected source (cannot find: " + old.strip().splitlines()[0][:70] + ")")
    t = t.replace(old, new)
    done += 1
with open(root + '/' + REL, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d edits)" % done)
