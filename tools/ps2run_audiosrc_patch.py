"""Music and voice volume for the PC window of PS2 Web Recomp (runtime/src/disc.cpp).

The game mixes its music and its voice lines into one stream before the sound chip sees it, so they cannot be told apart there. They can be
told apart on the disc: the music is the ADX files in BGM.CVM and the voice lines are the ADX clips inside the SOUND/V*.AFS archives in DATA.CVM.
This patch turns them down as they are read: every ADX block starts with a 16-bit scale and the decoded sound is proportional to it, so
multiplying that number by a percentage makes that sound quieter without touching anything else.
  PS2_VOL_MUSIC=<0..100>   percent for the music (default 100)
  PS2_VOL_VOICE=<0..100>   percent for the voice lines (default 100)
At 100 for both nothing is touched and nothing is indexed. Lower values index the two archives once, on the first disc read.

Run in the ps2-web-recomp folder:  python3 ps2run_audiosrc_patch.py [folder]
(idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
REL = 'runtime/src/disc.cpp'

INC_OLD = '#include <map>\n'
INC_NEW = INC_OLD + '#include <mutex>\n#include <utility>\n#include <vector>\n'
FN_OLD = 'bool open(const std::string &name, std::uint64_t size, Reader reader, Probe probe) {\n'
FN_NEW = r'''// ---- music and voice volume (ps2run_audiosrc_patch.py)
struct AdxFile {
    std::uint64_t start, end;   // bytes on the disc image
    std::uint32_t data;         // where the 18-byte blocks start, from the file start
};
struct PendingAfs {
    std::uint64_t start, end;
    bool done;
};
struct IsoFile {
    std::string path;
    std::uint32_t lba, size;
};
std::vector<AdxFile> g_adx[2];   // 0 music (BGM.CVM), 1 voice lines (SOUND/V*.AFS in DATA.CVM), sorted by start
std::vector<PendingAfs> g_afs;
int g_adx_pct[2] = {100, 100};
bool g_adx_init = false;
bool g_adx_ready = false;   // set when the disc index is complete (reads while indexing must not start the audio index)

std::size_t raw_read(std::uint64_t off, void *out, std::size_t n) { return g_reader ? g_reader(off, out, n) : 0; }

std::uint32_t le32(const std::uint8_t *p) {
    return static_cast<std::uint32_t>(p[0]) | static_cast<std::uint32_t>(p[1]) << 8 | static_cast<std::uint32_t>(p[2]) << 16 | static_cast<std::uint32_t>(p[3]) << 24;
}

void iso_dir(std::uint64_t base, std::uint32_t lba, std::uint32_t size, const std::string &prefix, std::vector<IsoFile> &out, int depth) {
    if (size == 0 || size > (16u << 20)) return;
    std::vector<std::uint8_t> d(size);
    d.resize(raw_read(base + static_cast<std::uint64_t>(lba) * kSector, d.data(), size));
    std::size_t pos = 0;
    while (pos < d.size()) {
        const std::uint8_t ln = d[pos];
        if (ln == 0) {
            pos = (pos / kSector + 1) * kSector;
            continue;
        }
        if (ln < 34 || pos + ln > d.size()) {
            pos += ln;
            continue;
        }
        const std::uint8_t *rec = &d[pos];
        pos += ln;
        const std::uint32_t ext = le32(rec + 2), sz = le32(rec + 10);
        const std::uint8_t flags = rec[25], nlen = rec[32];
        if (33u + nlen > ln) continue;
        std::string nm(reinterpret_cast<const char *>(rec + 33), nlen);
        if (nm.size() == 1 && (nm[0] == '\0' || nm[0] == '\1')) continue;
        const auto semi = nm.find(';');
        if (semi != std::string::npos) nm.resize(semi);
        for (char &c : nm) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
        if (flags & 2) {
            if (depth < 6) iso_dir(base, ext, sz, prefix + nm + "/", out, depth + 1);
        } else {
            out.push_back({prefix + nm, ext, sz});
        }
    }
}

// The .cvm archives hold a small header and then an ISO9660 volume of their own (it starts 3 sectors in).
bool cvm_volume(const char *name, std::uint64_t &base, std::vector<IsoFile> &out) {
    const auto it = g_index.find(name);
    if (it == g_index.end()) return false;
    for (const std::uint32_t shift : {3u, 0u}) {
        base = static_cast<std::uint64_t>(it->second.sector + shift) * kSector;
        std::uint8_t pvd[kSector];
        if (raw_read(base + 16u * kSector, pvd, kSector) < kSector || std::memcmp(pvd + 1, "CD001", 5) != 0) continue;
        iso_dir(base, le32(pvd + 156 + 2), le32(pvd + 156 + 10), "", out, 0);
        return true;
    }
    return false;
}

bool adx_head(std::uint64_t at, std::uint32_t &data) {
    std::uint8_t h[32];
    if (raw_read(at, h, sizeof h) < sizeof h) return false;
    if (h[0] != 0x80 || h[1] != 0x00 || h[4] != 3 || h[5] != 18 || h[6] != 4) return false;
    data = ((static_cast<std::uint32_t>(h[2]) << 8) | h[3]) + 4u;
    return data >= 0x14 && data < 0x4000;
}

void adx_sort(int k) {
    std::sort(g_adx[k].begin(), g_adx[k].end(), [](const AdxFile &x, const AdxFile &y) { return x.start < y.start; });
}

void afs_expand(PendingAfs &a) {
    a.done = true;
    std::uint8_t h[8];
    if (raw_read(a.start, h, 8) < 8 || std::memcmp(h, "AFS\0", 4) != 0) return;
    const std::uint32_t n = le32(h + 4);
    if (n == 0 || n > 4096) return;
    std::vector<std::uint8_t> t(static_cast<std::size_t>(n) * 8);
    if (raw_read(a.start + 8, t.data(), t.size()) < t.size()) return;
    for (std::uint32_t i = 0; i < n; ++i) {
        const std::uint32_t off = le32(&t[i * 8]), len = le32(&t[i * 8 + 4]);
        const std::uint64_t at = a.start + off;
        std::uint32_t data = 0;
        if (len > 0x20 && at + len <= a.end && adx_head(at, data)) g_adx[1].push_back({at, at + len, data});
    }
    adx_sort(1);
}

void adx_init() {
    g_adx_init = true;
    for (int k = 0; k < 2; ++k) {
        const char *e = std::getenv(k ? "PS2_VOL_VOICE" : "PS2_VOL_MUSIC");
        if (e && *e) {
            const int v = std::atoi(e);
            g_adx_pct[k] = v < 0 ? 0 : (v > 100 ? 100 : v);
        }
    }
    if (g_adx_pct[0] == 100 && g_adx_pct[1] == 100) return;
    std::uint64_t base = 0;
    std::vector<IsoFile> files;
    if (g_adx_pct[0] != 100 && cvm_volume("BGM.CVM", base, files)) {
        for (const IsoFile &f : files) {
            const std::uint64_t at = base + static_cast<std::uint64_t>(f.lba) * kSector;
            std::uint32_t data = 0;
            if (f.size > 0x20 && adx_head(at, data)) g_adx[0].push_back({at, at + f.size, data});
        }
        adx_sort(0);
    }
    files.clear();
    if (g_adx_pct[1] != 100 && cvm_volume("DATA.CVM", base, files)) {
        for (const IsoFile &f : files)
            if (f.path.compare(0, 7, "SOUND/V") == 0 && f.path.size() > 4 && f.path.compare(f.path.size() - 4, 4, ".AFS") == 0) {
                const std::uint64_t at = base + static_cast<std::uint64_t>(f.lba) * kSector;
                g_afs.push_back({at, at + f.size, false});
            }
    }
    std::fprintf(stderr, "[audio] music %d%% (%zu files), voices %d%% (%zu archives)\n", g_adx_pct[0], g_adx[0].size(), g_adx_pct[1], g_afs.size());
}

// Turn the ADX blocks inside a block of sectors that was just read down to the chosen percentage.
void scale_adx(std::uint32_t sector, std::uint32_t count, void *out) {
    static std::mutex lock;
    std::lock_guard<std::mutex> guard(lock);
    if (!g_adx_ready) return;
    if (!g_adx_init) adx_init();
    if (g_adx_pct[0] == 100 && g_adx_pct[1] == 100) return;
    const std::uint64_t a = static_cast<std::uint64_t>(sector) * kSector, b = a + static_cast<std::uint64_t>(count) * kSector;
    auto *buf = static_cast<std::uint8_t *>(out);
    for (PendingAfs &p : g_afs)
        if (!p.done && p.start < b && p.end > a) afs_expand(p);
    auto byte_at = [&](std::uint64_t p) -> int {
        if (p >= a && p < b) return buf[p - a];
        std::uint8_t x = 0;
        return raw_read(p, &x, 1) == 1 ? x : -1;
    };
    for (int k = 0; k < 2; ++k) {
        const int pct = g_adx_pct[k];
        const std::vector<AdxFile> &v = g_adx[k];
        if (pct == 100 || v.empty()) continue;
        auto it = std::upper_bound(v.begin(), v.end(), a, [](std::uint64_t x, const AdxFile &f) { return x < f.start; });
        if (it != v.begin()) --it;
        for (; it != v.end() && it->start < b; ++it) {
            const AdxFile &f = *it;
            const std::uint64_t first = f.start + f.data;
            if (f.end <= a || f.end <= first) continue;
            const std::uint64_t lo = std::max(a, first), hi = std::min(b, f.end);
            for (std::uint64_t fs = first + (lo - first) / 18 * 18; fs < hi; fs += 18) {
                if (fs + 18 > f.end || fs + 2 <= a) continue;
                const int b0 = byte_at(fs), b1 = byte_at(fs + 1);
                if (b0 < 0 || b1 < 0) continue;
                const unsigned old = static_cast<unsigned>(b0) << 8 | static_cast<unsigned>(b1);
                if (old & 0x8000u) continue;   // the end-of-stream block
                const unsigned scaled = (old & 0xE000u) | ((old & 0x1FFFu) * static_cast<unsigned>(pct) + 50u) / 100u;
                if (fs >= a && fs < b) buf[fs - a] = static_cast<std::uint8_t>(scaled >> 8);
                if (fs + 1 >= a && fs + 1 < b) buf[fs + 1 - a] = static_cast<std::uint8_t>(scaled & 0xFFu);
            }
        }
    }
}

''' + FN_OLD
READ_OLD = '    if (got < want) std::memset(static_cast<std::uint8_t *>(out) + got, 0, want - got);\n'
READ_NEW = READ_OLD + '    if (got > 0) scale_adx(sector, count, out);   // ps2run_audiosrc_patch.py\n'
OPEN_OLD = '    std::fprintf(stderr, "[disc] %s: %zu files, %llu sectors, layer 1 at %u\\n", name.c_str(), g_index.size(),\n'
OPEN_NEW = '    g_adx_init = false;\n    g_adx_ready = true;   // ps2run_audiosrc_patch.py: the disc index is complete\n' + OPEN_OLD
EDITS = [(INC_OLD, INC_NEW), (FN_OLD, FN_NEW), (OPEN_OLD, OPEN_NEW), (READ_OLD, READ_NEW)]


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
