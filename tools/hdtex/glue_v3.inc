// ps2run_hdtex_patch.py: HD texture glue (PS2_HDTEX=<map file>). See hdtex.hpp for what the pieces do.
static_assert(kDecodedWords == (4u << 20), "gs.wgsl HD_BASE must match kDecodedWords");
constexpr std::uint32_t kHdBase = kDecodedWords;   // the HD picture slots follow the per-batch decoded area in g_decoded
hdtex::Store g_hd;
bool g_hd_on = false;
std::uint32_t g_hd_slot_words = 0;
struct HdSlot {
    int entry = -1;
    std::uint64_t used = 0;
};
std::vector<HdSlot> g_hd_slots;
std::unordered_map<int, int> g_hd_slot_of;
hdtex::Hasher g_hd_hasher;
std::uint64_t g_hd_key = 0;
bool g_hd_key_ready = false;
struct HdResident {
    int entry = -1;
    std::uint32_t tpsm = 0, tw = 0, th = 0;
    std::uint64_t stamp = 0;
    Range range;
};
std::unordered_map<std::uint32_t, HdResident> g_hd_res;   // by the texture's base block
std::uint32_t g_hd_loaded = 0, g_hd_dropped = 0, g_hd_waited = 0;
std::vector<std::uint8_t> g_hd_want;                       // entries the game has drawn (or is about to draw) with, as opposed to preloads
std::unordered_map<std::uint64_t, std::uint32_t> g_hd_hot;   // how often each known picture was uploaded: the preload list for next time
std::string g_hd_hot_path;
bool g_hd_hot_dirty = false;
std::chrono::steady_clock::time_point g_hd_hot_saved = std::chrono::steady_clock::now();

// The pictures used most (kept next to the map file) are decoded when the game starts, so they are ready before they appear.
void hd_hot_save() {
    if (g_hd_hot_path.empty() || !g_hd_hot_dirty) return;
    g_hd_hot_dirty = false;
    g_hd_hot_saved = std::chrono::steady_clock::now();
    std::vector<std::pair<std::uint32_t, std::uint64_t>> v;
    for (const auto &kv : g_hd_hot) v.emplace_back(kv.second, kv.first);
    std::sort(v.begin(), v.end(), [](const auto &a, const auto &b) { return a.first > b.first; });
    if (v.size() > 200) v.resize(200);
    const std::string tmp = g_hd_hot_path + ".tmp";
    std::FILE *f = std::fopen(tmp.c_str(), "wb");
    if (!f) return;
    for (const auto &p : v) std::fprintf(f, "%016llx %u\n", static_cast<unsigned long long>(p.second), p.first);
    std::fclose(f);
    std::remove(g_hd_hot_path.c_str());
    std::rename(tmp.c_str(), g_hd_hot_path.c_str());
}
struct HdHotSaver {
    ~HdHotSaver() { hd_hot_save(); }
} g_hd_hot_saver;

std::uint32_t hd_log2(std::uint32_t v) {
    std::uint32_t n = 0;
    while ((1u << n) < v && n < 16) ++n;
    return n;
}

std::uint64_t hd_stamp(const Range &r) {
    std::uint64_t s = 0;
    for (std::uint64_t at = r.lo; at < r.hi; at += 8192) s += g_hd_epoch[(at >> 13) & 511u];
    return s;
}

void hd_note_write(const Range &r) {
    for (std::uint64_t at = r.lo; at < r.hi; at += 8192) {
        const std::uint32_t pg = (at >> 13) & 511u;
        ++g_hd_epoch[pg];
        g_hd_last[pg] = HdLast{r.lo, r.hi, 1};
    }
}

void hd_forget_all() {
    g_hd_res.clear();
    g_hd_key_ready = false;
}

// Reads the table (PS2_HDTEX) and returns the size g_decoded must have.
std::uint64_t hd_setup() {
    std::uint64_t bytes = static_cast<std::uint64_t>(kDecodedWords) * 4;
    const char *map = std::getenv("PS2_HDTEX");
    if (!map || !*map) return bytes;
    std::uint32_t dim = 1024, mb = 192;
    if (const char *v = std::getenv("PS2_HDTEX_MAX")) dim = std::clamp<std::uint32_t>(static_cast<std::uint32_t>(std::atoi(v)), 256u, 2048u);
    if (const char *v = std::getenv("PS2_HDTEX_MB")) mb = std::clamp<std::uint32_t>(static_cast<std::uint32_t>(std::atoi(v)), 16u, 2048u);
    const std::size_t n = g_hd.load(map);
    if (!n) {
        std::fprintf(stderr, "[hdtex] no pictures in %s, HD textures are off\n", map);
        return bytes;
    }
    g_hd.max_dim = dim;
    g_hd.max_pixels = dim * dim;
    g_hd_slot_words = 8u + dim * dim;
    const std::uint64_t slot_bytes = static_cast<std::uint64_t>(g_hd_slot_words) * 4;
    const std::uint64_t limit = std::min<std::uint64_t>(g_hd_max_binding ? g_hd_max_binding : (128ull << 20), 3ull << 30);
    std::uint64_t slots = static_cast<std::uint64_t>(mb) * (1ull << 20) / slot_bytes;
    if (limit > bytes) slots = std::min<std::uint64_t>(slots, (limit - bytes) / slot_bytes);
    else slots = 0;
    if (slots < 4) {
        std::fprintf(stderr, "[hdtex] not enough graphics memory for HD textures\n");
        return bytes;
    }
    g_hd_slots.assign(static_cast<std::size_t>(slots), HdSlot{});
    g_hd_want.assign(n, 0);
    g_hd_hot_path = std::string(map) + ".hot";
    std::uint32_t preload = 0;
    if (std::FILE *hf = std::fopen(g_hd_hot_path.c_str(), "rb")) {
        std::vector<std::pair<std::uint32_t, std::uint64_t>> v;
        unsigned long long key;
        unsigned cnt;
        while (std::fscanf(hf, "%llx %u", &key, &cnt) == 2) {
            g_hd_hot[key] = cnt;
            v.emplace_back(cnt, key);
        }
        std::fclose(hf);
        std::sort(v.begin(), v.end(), [](const auto &a, const auto &b) { return a.first > b.first; });
        const std::uint32_t limit = static_cast<std::uint32_t>(std::min<std::uint64_t>(24, slots / 2));
        for (const auto &p : v) {
            if (preload >= limit) break;
            const int e = g_hd.find(p.second);
            if (e >= 0) g_hd.request(e, false), ++preload;
        }
    }
    g_hd_on = true;
    std::fprintf(stderr, "[hdtex] %zu pictures in the table, %llu slots of %ux%u (%llu MB), %u preloaded\n", n, static_cast<unsigned long long>(slots), dim, dim,
                 static_cast<unsigned long long>(slots * slot_bytes >> 20), preload);
    return bytes + slots * slot_bytes;
}

// An upload is starting: hash it if it is big enough to be a texture.
void hd_begin(const Image &im) {
    if (!g_hd_on) return;
    g_hd_key_ready = false;
    const std::uint64_t bytes = im.active ? (static_cast<std::uint64_t>(im.total) * im.bpp + 7) / 8 : 0;
    g_hd_hasher.begin(bytes >= 1024 ? bytes : 0);
}

void hd_feed(const std::uint8_t *data, std::size_t bytes) {
    if (!g_hd_on || !g_hd_hasher.need) return;
    if (g_hd_hasher.feed(data, bytes, g_hd_key)) g_hd_key_ready = true;
}

// The upload is complete and queued: if it is a known texture, remember where it sits so draws from there can use the HD picture.
void hd_image_done(const Image &im) {
    if (!g_hd_on || !g_hd_key_ready) return;
    g_hd_key_ready = false;
    const int e = g_hd.find(g_hd_key);
    const std::uint32_t rows = im.rrw ? im.total / im.rrw : 0;
    if (e < 0 || !rows) return;
    const hdtex::Entry &en = g_hd.at(e);
    HdResident r;
    r.entry = e;
    r.tpsm = en.tpsm;
    r.tw = hd_log2(en.w);
    r.th = hd_log2(en.h);
    r.range = region(im.dbp, im.dbw, im.dpsm, static_cast<int>(im.dsax), static_cast<int>(im.dsay), static_cast<int>(im.dsax + im.rrw - 1), static_cast<int>(im.dsay + rows - 1));
    r.stamp = hd_stamp(r.range);
    g_hd_res[im.dbp] = r;
    ++g_hd_hot[g_hd_key];
    g_hd_hot_dirty = true;
    g_hd_want[static_cast<std::size_t>(e)] = 1;
    g_hd.request(e);
}

// Moves finished pictures into the GPU buffer.
void hd_pump() {
    int e;
    hdtex::Image img;
    int low_budget = 1;   // a preload is a 4 MB copy: one per batch, so a screen never stalls on them
    while (g_hd.poll(e, img, low_budget > 0)) {
        const bool want = g_hd_want[static_cast<std::size_t>(e)] != 0;
        if (!want) --low_budget;
        int slot = -1;
        for (std::size_t s = 0; s < g_hd_slots.size() && slot < 0; ++s)
            if (g_hd_slots[s].entry < 0) slot = static_cast<int>(s);
        if (slot < 0 && !want) {   // a preload never pushes anything out
            g_hd.forget(e);
            continue;
        }
        if (slot < 0) {
            std::uint64_t oldest = ~0ull;
            for (std::size_t s = 0; s < g_hd_slots.size(); ++s)
                if (g_hd_slots[s].used != g_serial && g_hd_slots[s].used < oldest) {
                    oldest = g_hd_slots[s].used;
                    slot = static_cast<int>(s);
                }
            if (slot < 0) {   // everything is in use by the batch being built: ask again later
                g_hd.forget(e);
                continue;
            }
            g_hd_slot_of.erase(g_hd_slots[static_cast<std::size_t>(slot)].entry);
            g_hd.forget(g_hd_slots[static_cast<std::size_t>(slot)].entry);
        }
        const hdtex::Entry &en = g_hd.at(e);
        std::vector<std::uint32_t> buf(8 + img.px.size());
        buf[0] = img.w;
        buf[1] = img.h;
        buf[2] = f2u(en.sx);
        buf[3] = f2u(en.sy);
        buf[4] = f2u(en.ox);
        buf[5] = f2u(en.oy);
        std::memcpy(buf.data() + 8, img.px.data(), img.px.size() * 4);
        wgpuQueueWriteBuffer(g_queue, g_decoded, static_cast<std::uint64_t>(kHdBase + static_cast<std::uint32_t>(slot) * g_hd_slot_words) * 4, buf.data(), buf.size() * 4);
        g_hd_slots[static_cast<std::size_t>(slot)] = HdSlot{e, want ? g_serial : 0};   // an unused preload is the first to go
        g_hd_slot_of[e] = slot;
        if (++g_hd_loaded <= 400) std::fprintf(stderr, "[hdtex] loaded %s (%ux%u)\n", en.path.c_str(), img.w, img.h);
    }
}

// Before a batch is drawn: textured draws whose texture is a known HD picture (already loaded) point their setup at it.
void hd_apply(std::uint32_t) {
    if (!g_hd_on) return;
    hd_pump();
    if (g_hd_hot_dirty && std::chrono::steady_clock::now() - g_hd_hot_saved > std::chrono::seconds(20)) hd_hot_save();
    if (g_hd_res.empty()) return;
    Batch &b = g_batch;
    const std::uint32_t setups = static_cast<std::uint32_t>(b.setups.size() / kSetupWords);
    for (std::uint32_t i = 0; i < setups; ++i) {
        std::uint32_t *w = b.setups.data() + i * kSetupWords;
        if (!(w[0] & 2u)) continue;
        const auto it = g_hd_res.find(w[12]);
        if (it == g_hd_res.end()) continue;
        HdResident &r = it->second;
        if (w[14] != r.tpsm || (w[15] & 0xFFu) != r.tw || (w[15] >> 8) != r.th) continue;
        if (((w[7] >> 24) & 3u) >= 2u || ((w[7] >> 26) & 3u) >= 2u) continue;   // region clamp/repeat: leave to the original
        if (hd_stamp(r.range) != r.stamp) {   // the memory was written again since the upload
            if (++g_hd_dropped <= 60) {   // say who wrote it (a page shared with something else would explain a picture that flickers back to the original)
                std::uint32_t pg = static_cast<std::uint32_t>(r.range.lo >> 13) & 511u;
                for (std::uint64_t at = r.range.lo; at < r.range.hi; at += 8192) {
                    const std::uint32_t q = (at >> 13) & 511u;
                    if (g_hd_epoch[q] != 0 && g_hd_last[q].kind) { pg = q; }
                }
                std::fprintf(stderr, "[hdtex] dropped %s: memory %llx-%llx written again by a %s of %llx-%llx\n", g_hd.at(r.entry).path.c_str(),
                             static_cast<unsigned long long>(r.range.lo), static_cast<unsigned long long>(r.range.hi), g_hd_last[pg].kind == 1 ? "upload" : "draw",
                             static_cast<unsigned long long>(g_hd_last[pg].lo), static_cast<unsigned long long>(g_hd_last[pg].hi));
            }
            g_hd_res.erase(it);
            continue;
        }
        const auto sl = g_hd_slot_of.find(r.entry);
        if (sl == g_hd_slot_of.end()) {
            if (++g_hd_waited <= 60) std::fprintf(stderr, "[hdtex] drawn before it was ready: %s\n", g_hd.at(r.entry).path.c_str());
            g_hd_want[static_cast<std::size_t>(r.entry)] = 1;
            g_hd.request(r.entry);
            continue;
        }
        g_hd_want[static_cast<std::size_t>(r.entry)] = 1;
        w[24] = kHdBase + static_cast<std::uint32_t>(sl->second) * g_hd_slot_words;
        g_hd_slots[static_cast<std::size_t>(sl->second)].used = g_serial;
    }
}

