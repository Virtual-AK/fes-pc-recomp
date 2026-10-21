"""Effects and streamed-sound volumes for the PC window (runtime/src/iop/spu2.cpp). Apply after ps2run_audio_patch.py.

What the first audio probe showed: the music (and the game's other streamed sound) arrives through the first sound chip's streamed input;
sound effects (footsteps, menu clicks) are ordinary sound voices on both chips.
  PS2_VOL_FX=<0..200>      percent for the sound effects (the sound voices of both chips), default 100
  PS2_VOL_STREAM=<0..200>  percent for the streamed input (music, and voice lines if they travel the same way), default 100
  PS2_AUDIO_PROBE=1        now also logs, about once a second, a line [adma] with the memory areas the streamed sound is read from and how loud each
                           is. If music and voice lines come from different areas that line shows it, and they can get separate volumes.

Run in the ps2-web-recomp folder:  python3 ps2run_audio2_patch.py [folder]
(idempotent; refuses unknown source; needs ps2run_audio_patch.py applied first)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
REL = 'runtime/src/iop/spu2.cpp'

FX_OLD = '        std::int16_t unused[2];\n'
FX_NEW = ('        if (vol_fx != 100)   // ps2run_audio2_patch.py: the sound voices are the effects\n'
          '            for (unsigned n = 0; n < kBatch; ++n) {\n'
          '                sum[c][n][0] = sum[c][n][0] * vol_fx / 100;\n'
          '                sum[c][n][1] = sum[c][n][1] * vol_fx / 100;\n'
          '            }\n') + FX_OLD
IN_OLD = ('    left += k.input[slot][0] * static_cast<std::int16_t>(k.bvol[0]) >> 15;\n'
          '    right += k.input[slot][1] * static_cast<std::int16_t>(k.bvol[1]) >> 15;\n')
IN_NEW = ('    left += (k.input[slot][0] * static_cast<std::int16_t>(k.bvol[0]) >> 15) * vol_stream / 100;   // ps2run_audio2_patch.py\n'
          '    right += (k.input[slot][1] * static_cast<std::int16_t>(k.bvol[1]) >> 15) * vol_stream / 100;\n')
FEED_OLD = 'void feed_input(int core) {\n'
FEED_NEW = r'''// ---- effects and stream volume, streamed sound probe (ps2run_audio2_patch.py)
int a2_percent(const char *name) {
    const char *e = std::getenv(name);
    if (!e || !*e) return 100;
    const int v = std::atoi(e);
    return v < 0 ? 0 : (v > 200 ? 200 : v);
}
const int vol_fx = a2_percent("PS2_VOL_FX");
const int vol_stream = a2_percent("PS2_VOL_STREAM");

void adma_note(int core, std::uint32_t madr, const std::uint8_t *src, std::uint32_t frames) {
    struct Area { std::uint32_t area; std::int32_t peak; unsigned chunks; };
    static std::vector<Area> areas[2];
    static unsigned total = 0;
    const std::uint32_t area = madr & ~0x3FFFu;
    Area *a = nullptr;
    for (Area &x : areas[core]) if (x.area == area) a = &x;
    if (!a) { areas[core].push_back({area, 0, 0}); a = &areas[core].back(); }
    for (std::uint32_t i = 0; i < frames; ++i) {
        std::int16_t l;
        std::memcpy(&l, src + i * 2, 2);
        const std::int32_t v = l < 0 ? -l : l;
        if (v > a->peak) a->peak = v;
    }
    ++a->chunks;
    if (++total < 188) return;
    total = 0;
    std::string line = "[adma]";
    for (int c = 0; c < 2; ++c) {
        for (const Area &x : areas[c]) {
            char buf[64];
            std::snprintf(buf, sizeof buf, " core%d@%06X:%d:%u", c, x.area, x.peak, x.chunks);
            line += buf;
        }
        areas[c].clear();
    }
    std::fprintf(stderr, "%s\n", line.c_str());
}

''' + FEED_OLD
SRC_OLD = '        const std::uint8_t *src = ram_ptr(t.madr);\n'
SRC_NEW = SRC_OLD + '        static const bool adma_probe = std::getenv("PS2_AUDIO_PROBE") != nullptr;\n        if (adma_probe) adma_note(core, t.madr, src, frames);\n'
EDITS = [(FX_OLD, FX_NEW), (IN_OLD, IN_NEW), (FEED_OLD, FEED_NEW), (SRC_OLD, SRC_NEW)]


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
if 'PS2_VOL_MASTER' not in t:
    fail("apply ps2run_audio_patch.py first")
if all(new in t for _, new in EDITS):
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
