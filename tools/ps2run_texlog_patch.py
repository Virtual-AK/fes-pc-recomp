"""Texture upload log for the PC window of PS2 Web Recomp (probe for the HD texture work).

When the environment variable PS2_TEXLOG is set to a file name, the runner writes one line for every complete image the game
uploads to the graphics chip (textures, palettes, screen copies):

    dbp dbw psm sax say width height bytes key

key is a 64-bit hash of the uploaded bytes (see p3fes_texhash.py for the same hash in Python). Nothing is written, and nothing
changes, when the variable is not set. The log contains only hashes and sizes, no game data.

Run in the ps2-web-recomp folder:  python3 ps2run_texlog_patch.py [folder]
(patches runtime/src/gs/gpu/gpu.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
REL = 'runtime/src/gs/gpu/gpu.cpp'
TAG = '// ps2run_texlog_patch.py'

HELP = TAG + ''': hash of every uploaded image, written to the file named by PS2_TEXLOG
struct TexLog {
    std::FILE *f = nullptr;
    bool init = false;
    std::uint64_t sum = 0, words = 0, seen = 0, need = 0, acc = 0;
    unsigned accn = 0;
    static std::uint64_t mix(std::uint64_t z) {
        z += 0x9E3779B97F4A7C15ull;
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
        z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
        return z ^ (z >> 31);
    }
    bool on() {
        if (!init) {
            init = true;
            if (const char *p = std::getenv("PS2_TEXLOG")) f = std::fopen(p, "w");
        }
        return f != nullptr;
    }
    void word(std::uint64_t w) { sum += mix(w ^ (words++ * 0xD6E8FEB86659FD93ull)); }
    void begin(std::uint64_t bytes) { sum = words = seen = acc = 0; accn = 0; need = bytes; }
    void feed(const std::uint8_t *p, std::size_t n, const Image &im) {
        if (!need || seen >= need) return;
        n = static_cast<std::size_t>(std::min<std::uint64_t>(n, need - seen));
        seen += n;
        while (n) {
            if (!accn && n >= 8) {
                std::uint64_t w;
                std::memcpy(&w, p, 8);
                word(w);
                p += 8;
                n -= 8;
                continue;
            }
            acc |= static_cast<std::uint64_t>(*p++) << (8 * accn);
            --n;
            if (++accn == 8) word(acc), acc = 0, accn = 0;
        }
        if (seen == need) {
            if (accn) word(acc);
            std::fprintf(f, "%u %u %u %u %u %u %u %llu %016llx\\n", im.dbp, im.dbw, im.dpsm, im.dsax, im.dsay, im.rrw, im.rrw ? im.total / im.rrw : 0,
                         static_cast<unsigned long long>(need), static_cast<unsigned long long>(mix(sum + need)));
            std::fflush(f);
            need = 0;
        }
    }
} g_texlog;
'''

EDITS = [
    ('std::uint32_t g_image_ids = 0;\n', 'std::uint32_t g_image_ids = 0;\n' + HELP),
    ('    im.active = im.total != 0;\n}\n',
     '    im.active = im.total != 0;\n    if (g_texlog.on()) g_texlog.begin(im.active ? (static_cast<std::uint64_t>(im.total) * im.bpp + 7) / 8 : 0);  ' + TAG + '\n}\n'),
    ('    Image &im = g_image;\n    if (!im.active) return;\n    if (im.pending.empty() && !im.lead_bits) {\n',
     '    Image &im = g_image;\n    if (!im.active) return;\n    if (g_texlog.f) g_texlog.feed(data, bytes, im);  ' + TAG + '\n    if (im.pending.empty() && !im.lead_bits) {\n'),
]

try:
    with open(root + '/' + REL, newline='') as f:
        t = f.read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + REL)
    raise SystemExit(1)
crlf = '\r\n' in t
t = t.replace('\r\n', '\n')
if TAG in t:
    print("already patched")
    raise SystemExit
for old, _ in EDITS:
    if t.count(old) != 1:
        print("PATCH NOT APPLIED: " + REL + " does not look like the expected source")
        raise SystemExit(1)
for old, new in EDITS:
    t = t.replace(old, new)
with open(root + '/' + REL, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d edits)" % len(EDITS))
