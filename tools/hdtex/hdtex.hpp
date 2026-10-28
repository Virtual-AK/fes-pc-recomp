// HD texture replacement for the PC window of PS2 Web Recomp (header only; written into runtime/src/gs/gpu/ by ps2run_hdtex_patch.py).
//
// What it does: the game uploads each texture to the graphics chip; this code hashes the uploaded bytes (same hash as
// tools/p3fes_texhash.py), looks the hash up in a table (PS2_HDTEX=<map file>) and, when it knows an HD picture for it, decodes that
// picture (DDS: BC1, BC2, BC3, BC7) on a worker thread. The GPU code in gpu.cpp then draws the HD picture instead of the original.
// Nothing here touches the GPU; it is tested on its own by tests/hdtex_test.cpp.
#pragma once
#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

namespace hdtex {

// ------------------------------------------------------------------------------------------------ hash
inline std::uint64_t mix64(std::uint64_t z) {
    z += 0x9E3779B97F4A7C15ull;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}

// Streams the bytes of one upload; same value as p3fes_texhash.upload_hash over the same bytes, however they are cut into pieces.
struct Hasher {
    std::uint64_t sum = 0, words = 0, seen = 0, need = 0, acc = 0;
    unsigned accn = 0;
    void begin(std::uint64_t bytes) {
        sum = words = seen = acc = 0;
        accn = 0;
        need = bytes;
    }
    void word(std::uint64_t w) { sum += mix64(w ^ (words++ * 0xD6E8FEB86659FD93ull)); }
    // Returns true once, when the last byte has arrived; key is then the hash.
    bool feed(const std::uint8_t *p, std::size_t n, std::uint64_t &key) {
        if (!need || seen >= need) return false;
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
        if (seen < need) return false;
        if (accn) word(acc);
        key = mix64(sum + need);
        need = 0;
        return true;
    }
};

// ------------------------------------------------------------------------------------------------ image
struct Image {
    std::uint32_t w = 0, h = 0;
    std::vector<std::uint32_t> px;   // RGBA, red in the low byte; alpha in the console's range (0x80 = opaque) once fix_alpha ran
};

// ------------------------------------------------------------------------------------------------ DDS block decoders
#include "bc7_tables.inc"

namespace detail {
inline std::uint32_t pack(std::uint32_t r, std::uint32_t g, std::uint32_t b, std::uint32_t a) { return r | (g << 8) | (b << 16) | (a << 24); }
inline std::uint32_t rd32(const std::uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | (static_cast<std::uint32_t>(p[3]) << 24); }

inline void bc1_colors(const std::uint8_t *b, std::uint32_t col[4], bool &four, bool always_four) {
    const std::uint32_t c0 = b[0] | (b[1] << 8), c1 = b[2] | (b[3] << 8);
    const auto ex = [](std::uint32_t c, std::uint32_t &r, std::uint32_t &g, std::uint32_t &bl) {
        r = (c >> 11) & 31;
        g = (c >> 5) & 63;
        bl = c & 31;
        r = (r << 3) | (r >> 2);
        g = (g << 2) | (g >> 4);
        bl = (bl << 3) | (bl >> 2);
    };
    std::uint32_t r0, g0, b0, r1, g1, b1;
    ex(c0, r0, g0, b0);
    ex(c1, r1, g1, b1);
    col[0] = pack(r0, g0, b0, 255);
    col[1] = pack(r1, g1, b1, 255);
    four = always_four || c0 > c1;
    if (four) {
        col[2] = pack((2 * r0 + r1) / 3, (2 * g0 + g1) / 3, (2 * b0 + b1) / 3, 255);
        col[3] = pack((r0 + 2 * r1) / 3, (g0 + 2 * g1) / 3, (b0 + 2 * b1) / 3, 255);
    } else {
        col[2] = pack((r0 + r1) / 2, (g0 + g1) / 2, (b0 + b1) / 2, 255);
        col[3] = 0;
    }
}

inline void bc1_block(const std::uint8_t *b, std::uint32_t out[16], bool always_four = false) {
    std::uint32_t col[4];
    bool four;
    bc1_colors(b, col, four, always_four);
    const std::uint32_t bits = rd32(b + 4);
    for (int i = 0; i < 16; ++i) out[i] = col[(bits >> (2 * i)) & 3];
}

inline void bc3_alpha(const std::uint8_t *b, std::uint8_t a[16]) {
    std::uint32_t t[8];
    t[0] = b[0];
    t[1] = b[1];
    if (t[0] > t[1]) {
        for (int i = 1; i < 7; ++i) t[1 + i] = ((7 - i) * t[0] + i * t[1]) / 7;
    } else {
        for (int i = 1; i < 5; ++i) t[1 + i] = ((5 - i) * t[0] + i * t[1]) / 5;
        t[6] = 0;
        t[7] = 255;
    }
    std::uint64_t bits = 0;
    for (int i = 0; i < 6; ++i) bits |= static_cast<std::uint64_t>(b[2 + i]) << (8 * i);
    for (int i = 0; i < 16; ++i) a[i] = static_cast<std::uint8_t>(t[(bits >> (3 * i)) & 7]);
}

inline void bc2_block(const std::uint8_t *b, std::uint32_t out[16]) {
    bc1_block(b + 8, out, true);
    for (int i = 0; i < 16; ++i) {
        const std::uint32_t a4 = (b[i / 2] >> ((i & 1) * 4)) & 15;
        out[i] = (out[i] & 0x00FFFFFFu) | ((a4 * 17) << 24);
    }
}

inline void bc3_block(const std::uint8_t *b, std::uint32_t out[16]) {
    std::uint8_t a[16];
    bc3_alpha(b, a);
    bc1_block(b + 8, out, true);
    for (int i = 0; i < 16; ++i) out[i] = (out[i] & 0x00FFFFFFu) | (static_cast<std::uint32_t>(a[i]) << 24);
}

struct BitReader {
    const std::uint8_t *p;
    unsigned pos = 0;
    std::uint32_t get(unsigned n) {
        std::uint32_t v = 0;
        for (unsigned i = 0; i < n; ++i, ++pos) v |= static_cast<std::uint32_t>((p[pos >> 3] >> (pos & 7)) & 1) << i;
        return v;
    }
};

inline void bc7_block(const std::uint8_t *blk, std::uint32_t out[16]) {
    struct Mode { int ns, pb, rb, isb, cb, ab, epb, spb, ib, ib2; };
    static const Mode kModes[8] = {{3, 4, 0, 0, 4, 0, 1, 0, 3, 0}, {2, 6, 0, 0, 6, 0, 0, 1, 3, 0}, {3, 6, 0, 0, 5, 0, 0, 0, 2, 0}, {2, 6, 0, 0, 7, 0, 1, 0, 2, 0},
                                   {1, 0, 2, 1, 5, 6, 0, 0, 2, 3}, {1, 0, 2, 0, 7, 8, 0, 0, 2, 2}, {1, 0, 0, 0, 7, 7, 1, 0, 4, 0}, {2, 6, 0, 0, 5, 5, 1, 0, 2, 0}};
    static const std::uint8_t kW2[4] = {0, 21, 43, 64}, kW3[8] = {0, 9, 18, 27, 37, 46, 55, 64}, kW4[16] = {0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64};
    int mode = 0;
    while (mode < 8 && !((blk[0] >> mode) & 1)) ++mode;
    if (mode >= 8) {
        for (int i = 0; i < 16; ++i) out[i] = 0;
        return;
    }
    const Mode m = kModes[mode];
    BitReader br{blk};
    br.pos = static_cast<unsigned>(mode + 1);
    const unsigned part = br.get(static_cast<unsigned>(m.pb));
    const unsigned rot = br.get(static_cast<unsigned>(m.rb));
    const unsigned isel = br.get(static_cast<unsigned>(m.isb));
    int ep[6][4] = {};
    const int ne = m.ns * 2;
    for (int ch = 0; ch < 3; ++ch)
        for (int e = 0; e < ne; ++e) ep[e][ch] = static_cast<int>(br.get(static_cast<unsigned>(m.cb)));
    if (m.ab)
        for (int e = 0; e < ne; ++e) ep[e][3] = static_cast<int>(br.get(static_cast<unsigned>(m.ab)));
    int pbit[6] = {};
    if (m.epb)
        for (int e = 0; e < ne; ++e) pbit[e] = static_cast<int>(br.get(1));
    else if (m.spb)
        for (int s = 0; s < m.ns; ++s) pbit[2 * s] = pbit[2 * s + 1] = static_cast<int>(br.get(1));
    const bool has_p = m.epb || m.spb;
    for (int e = 0; e < ne; ++e)
        for (int ch = 0; ch < 4; ++ch) {
            const int bits = ch < 3 ? m.cb : m.ab;
            if (ch == 3 && !m.ab) {
                ep[e][3] = 255;
                continue;
            }
            int v = ep[e][ch];
            int n = bits;
            if (has_p) {
                v = (v << 1) | pbit[e];
                ++n;
            }
            ep[e][ch] = (v << (8 - n)) | (v >> (2 * n - 8));
        }
    const auto subset_of = [&](int i) -> int {
        if (m.ns == 1) return 0;
        if (m.ns == 2) return (kPart2[part] >> i) & 1;
        return static_cast<int>((kPart3[part] >> (2 * i)) & 3);
    };
    const auto is_anchor = [&](int i) -> bool {
        if (i == 0) return true;
        if (m.ns == 2) return i == kAnch2[part];
        if (m.ns == 3) return i == kAnch3[part][0] || i == kAnch3[part][1];
        return false;
    };
    int idx1[16], idx2[16] = {};
    for (int i = 0; i < 16; ++i) idx1[i] = static_cast<int>(br.get(static_cast<unsigned>(is_anchor(i) ? m.ib - 1 : m.ib)));
    if (m.ib2)
        for (int i = 0; i < 16; ++i) idx2[i] = static_cast<int>(br.get(static_cast<unsigned>(i == 0 ? m.ib2 - 1 : m.ib2)));
    const auto weight = [&](int bits, int idx) -> int { return bits == 2 ? kW2[idx] : bits == 3 ? kW3[idx] : kW4[idx]; };
    for (int i = 0; i < 16; ++i) {
        const int s = subset_of(i);
        const int *e0 = ep[2 * s], *e1 = ep[2 * s + 1];
        int wc, wa;
        if (m.ib2) {
            const int c_bits = isel ? m.ib2 : m.ib, a_bits = isel ? m.ib : m.ib2;
            wc = weight(c_bits, isel ? idx2[i] : idx1[i]);
            wa = weight(a_bits, isel ? idx1[i] : idx2[i]);
        } else {
            wc = wa = weight(m.ib, idx1[i]);
        }
        int c[4];
        for (int ch = 0; ch < 3; ++ch) c[ch] = (e0[ch] * (64 - wc) + e1[ch] * wc + 32) >> 6;
        c[3] = (e0[3] * (64 - wa) + e1[3] * wa + 32) >> 6;
        if (rot == 1) std::swap(c[0], c[3]);
        else if (rot == 2) std::swap(c[1], c[3]);
        else if (rot == 3) std::swap(c[2], c[3]);
        out[i] = pack(static_cast<std::uint32_t>(c[0]), static_cast<std::uint32_t>(c[1]), static_cast<std::uint32_t>(c[2]), static_cast<std::uint32_t>(c[3]));
    }
}
}  // namespace detail

// Decodes the top picture of a DDS file (BC1, BC2, BC3 or BC7; no mip levels are read). Returns an empty error text on success.
inline std::string decode_dds(const std::uint8_t *d, std::size_t n, Image &img) {
    if (n < 128 || std::memcmp(d, "DDS ", 4) != 0 || detail::rd32(d + 4) != 124) return "not a DDS file";
    const std::uint32_t h = detail::rd32(d + 12), w = detail::rd32(d + 16);
    if (!w || !h || w > 8192 || h > 8192) return "odd size";
    std::size_t off = 128;
    int kind = 0;   // 1 BC1, 2 BC2, 3 BC3, 7 BC7
    if (std::memcmp(d + 84, "DXT1", 4) == 0) kind = 1;
    else if (std::memcmp(d + 84, "DXT3", 4) == 0) kind = 2;
    else if (std::memcmp(d + 84, "DXT5", 4) == 0) kind = 3;
    else if (std::memcmp(d + 84, "DX10", 4) == 0) {
        if (n < 148) return "short file";
        const std::uint32_t f = detail::rd32(d + 128);
        off = 148;
        if (f == 71 || f == 72) kind = 1;
        else if (f == 74 || f == 75) kind = 2;
        else if (f == 77 || f == 78) kind = 3;
        else if (f == 98 || f == 99) kind = 7;
    }
    if (!kind) return "unsupported DDS format";
    const std::size_t bsz = kind == 1 ? 8 : 16, bw = (w + 3) / 4, bh = (h + 3) / 4;
    if (n < off + bw * bh * bsz) return "short file";
    img.w = w;
    img.h = h;
    img.px.assign(static_cast<std::size_t>(w) * h, 0);
    std::uint32_t tmp[16];
    for (std::size_t by = 0; by < bh; ++by)
        for (std::size_t bx = 0; bx < bw; ++bx) {
            const std::uint8_t *b = d + off + (by * bw + bx) * bsz;
            if (kind == 1) detail::bc1_block(b, tmp);
            else if (kind == 2) detail::bc2_block(b, tmp);
            else if (kind == 3) detail::bc3_block(b, tmp);
            else detail::bc7_block(b, tmp);
            for (int y = 0; y < 4; ++y)
                for (int x = 0; x < 4; ++x) {
                    const std::size_t px = bx * 4 + static_cast<std::size_t>(x), py = by * 4 + static_cast<std::size_t>(y);
                    if (px < w && py < h) img.px[py * w + px] = tmp[y * 4 + x];
                }
        }
    return "";
}

// Halves the picture (2x2 average, on premultiplied colour so clear pixels do not bleed) until it is at most max_dim wide and high and max_pixels in size.
inline void downscale(Image &img, std::uint32_t max_dim, std::uint32_t max_pixels) {
    while ((img.w > max_dim || img.h > max_dim || static_cast<std::uint64_t>(img.w) * img.h > max_pixels) && img.w >= 2 && img.h >= 2) {
        const std::uint32_t nw = img.w / 2, nh = img.h / 2;
        std::vector<std::uint32_t> out(static_cast<std::size_t>(nw) * nh);
        for (std::uint32_t y = 0; y < nh; ++y)
            for (std::uint32_t x = 0; x < nw; ++x) {
                std::uint32_t sr = 0, sg = 0, sb = 0, sa = 0;
                for (int k = 0; k < 4; ++k) {
                    const std::uint32_t p = img.px[(2 * y + static_cast<std::uint32_t>(k >> 1)) * img.w + 2 * x + static_cast<std::uint32_t>(k & 1)];
                    const std::uint32_t a = p >> 24;
                    sr += (p & 255) * a;
                    sg += ((p >> 8) & 255) * a;
                    sb += ((p >> 16) & 255) * a;
                    sa += a;
                }
                if (!sa) {
                    // all four clear: keep the plain average of the colours so edges stay clean when drawn smoothed
                    std::uint32_t r = 0, g = 0, b = 0;
                    for (int k = 0; k < 4; ++k) {
                        const std::uint32_t p = img.px[(2 * y + static_cast<std::uint32_t>(k >> 1)) * img.w + 2 * x + static_cast<std::uint32_t>(k & 1)];
                        r += p & 255;
                        g += (p >> 8) & 255;
                        b += (p >> 16) & 255;
                    }
                    out[y * nw + x] = (r / 4) | ((g / 4) << 8) | ((b / 4) << 16);
                } else {
                    out[y * nw + x] = (sr / sa) | ((sg / sa) << 8) | ((sb / sa) << 16) | (((sa + 2) / 4) << 24);
                }
            }
        img.px.swap(out);
        img.w = nw;
        img.h = nh;
    }
}

// The game's alpha runs 0..0x80 (0x80 = opaque); pictures made for emulators with full-range alpha are scaled to it.
inline void fix_alpha(Image &img) {
    for (std::uint32_t &p : img.px) {
        const std::uint32_t a = p >> 24;
        p = (p & 0x00FFFFFFu) | (((a * 128 + 127) / 255) << 24);
    }
}

// ------------------------------------------------------------------------------------------------ the table and the loader
struct Entry {
    std::uint32_t w = 0, h = 0, tpsm = 0;   // size and pixel format (0x13 or 0x14) of the game's own texture
    float sx = 1, sy = 1, ox = 0, oy = 0;   // game texture position (0..1) -> HD picture position: u * s + o
    bool afix = false;                      // the HD picture has full-range alpha
    std::string path;
};

class Store {
  public:
    std::uint32_t max_dim = 1024, max_pixels = 1u << 20;

    ~Store() {
        {
            std::lock_guard<std::mutex> lock(mu_);
            stop_ = true;
        }
        cv_.notify_all();
        for (std::thread &t : workers_)
            if (t.joinable()) t.join();
    }

    // Map file: one line per picture, tab separated:
    //   key(hex) width height psm sx sy ox oy alphafix path      (path is relative to the map file; lines starting with # are skipped)
    std::size_t load(const std::string &mapfile) {
        std::FILE *f = std::fopen(mapfile.c_str(), "rb");
        if (!f) return 0;
        std::string text;
        char buf[65536];
        std::size_t got;
        while ((got = std::fread(buf, 1, sizeof buf, f)) > 0) text.append(buf, got);
        std::fclose(f);
        std::size_t slash = mapfile.find_last_of("/\\");
        dir_ = slash == std::string::npos ? std::string() : mapfile.substr(0, slash + 1);
        std::size_t at = 0;
        while (at < text.size()) {
            std::size_t end = text.find('\n', at);
            if (end == std::string::npos) end = text.size();
            std::string line = text.substr(at, end - at);
            at = end + 1;
            while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
            if (line.empty() || line[0] == '#') continue;
            std::vector<std::string> cols;
            std::size_t c = 0;
            while (true) {
                std::size_t t = line.find('\t', c);
                if (t == std::string::npos || cols.size() == 9) {
                    cols.push_back(line.substr(c));
                    break;
                }
                cols.push_back(line.substr(c, t - c));
                c = t + 1;
            }
            if (cols.size() != 10) continue;
            Entry e;
            const std::uint64_t key = std::strtoull(cols[0].c_str(), nullptr, 16);
            e.w = static_cast<std::uint32_t>(std::strtoul(cols[1].c_str(), nullptr, 10));
            e.h = static_cast<std::uint32_t>(std::strtoul(cols[2].c_str(), nullptr, 10));
            e.tpsm = static_cast<std::uint32_t>(std::strtoul(cols[3].c_str(), nullptr, 10));
            e.sx = static_cast<float>(std::atof(cols[4].c_str()));
            e.sy = static_cast<float>(std::atof(cols[5].c_str()));
            e.ox = static_cast<float>(std::atof(cols[6].c_str()));
            e.oy = static_cast<float>(std::atof(cols[7].c_str()));
            e.afix = cols[8] == "1";
            e.path = cols[9];
            if (!key || !e.w || !e.h || (e.tpsm != 19 && e.tpsm != 20) || e.path.empty() || index_.count(key)) continue;
            index_[key] = static_cast<int>(entries_.size());
            entries_.push_back(e);
        }
        state_.assign(entries_.size(), 0);
        urgent_.assign(entries_.size(), 0);
        const unsigned hw = std::thread::hardware_concurrency();
        max_workers_ = hw > 2 ? std::min(3u, hw - 1) : 1u;   // leave the game its own cores
        return entries_.size();
    }

    std::size_t size() const { return entries_.size(); }
    int find(std::uint64_t key) const {
        const auto it = index_.find(key);
        return it == index_.end() ? -1 : it->second;
    }
    const Entry &at(int i) const { return entries_[static_cast<std::size_t>(i)]; }

    // Starts decoding entry i in the background (once). urgent: the game is drawing with it right now (goes to the front of the line);
    // otherwise it is a preload (goes to the back, and its result is handed over only when asked for with allow_low).
    void request(int i, bool urgent = true) {
        std::lock_guard<std::mutex> lock(mu_);
        const std::size_t k = static_cast<std::size_t>(i);
        if (urgent) urgent_[k] = 1;
        if (state_[k] != 0) {
            if (urgent && state_[k] == 1) todo_.push_front(i);   // already waiting as a preload: move up
            if (urgent && state_[k] == 2) {                      // decoded as a preload and not collected yet: hand it over now
                for (auto it = done_low_.begin(); it != done_low_.end(); ++it)
                    if (it->first == i) {
                        done_.push_back(std::move(*it));
                        done_low_.erase(it);
                        break;
                    }
            }
            return;
        }
        state_[k] = 1;
        if (urgent) todo_.push_front(i);
        else todo_.push_back(i);
        if (workers_.size() < max_workers_ && workers_.size() < todo_.size() + busy_) workers_.emplace_back([this] { run(); });
        cv_.notify_one();
    }
    // Forget that entry i was decoded (its slot was reused), so it can be requested again.
    void forget(int i) {
        std::lock_guard<std::mutex> lock(mu_);
        if (state_[static_cast<std::size_t>(i)] == 2) {
            state_[static_cast<std::size_t>(i)] = 0;
            urgent_[static_cast<std::size_t>(i)] = 0;
        }
    }
    bool failed(int i) {
        std::lock_guard<std::mutex> lock(mu_);
        return state_[static_cast<std::size_t>(i)] == 3;
    }
    // Takes one finished picture, if any. Pictures the game is waiting for come first; preloads only when allow_low.
    bool poll(int &i, Image &img, bool allow_low = true) {
        std::lock_guard<std::mutex> lock(mu_);
        std::deque<std::pair<int, Image>> &q = !done_.empty() ? done_ : done_low_;
        if (q.empty() || (&q == &done_low_ && !allow_low)) return false;
        i = q.front().first;
        img = std::move(q.front().second);
        q.pop_front();
        return true;
    }
    // Waits (at most ms) until entry i has been decoded (or has failed). True when its picture is ready to be collected with poll.
    bool wait_ready(int i, int ms) {
        std::unique_lock<std::mutex> lock(mu_);
        const std::size_t k = static_cast<std::size_t>(i);
        done_cv_.wait_for(lock, std::chrono::milliseconds(ms), [&] { return state_[k] == 2 || state_[k] == 3; });
        return state_[k] == 2;
    }
    std::string last_error;

  private:
    void run() {
        while (true) {
            int i;
            {
                std::unique_lock<std::mutex> lock(mu_);
                cv_.wait(lock, [this] { return stop_ || !todo_.empty(); });
                if (stop_) return;
                i = todo_.front();
                todo_.pop_front();
                if (state_[static_cast<std::size_t>(i)] != 1) continue;   // a second copy of an entry that moved up the line
                state_[static_cast<std::size_t>(i)] = 4;
                ++busy_;
            }
            Image img;
            std::string err;
            const Entry &e = entries_[static_cast<std::size_t>(i)];
            const bool absolute = e.path.size() > 1 && (e.path[0] == '/' || e.path[0] == '\\' || e.path[1] == ':');
            const std::string full = absolute ? e.path : dir_ + e.path;
            std::FILE *f = std::fopen(full.c_str(), "rb");
            if (!f) {
                err = "cannot open " + full;
            } else {
                std::vector<std::uint8_t> data;
                std::uint8_t buf[65536];
                std::size_t got;
                while ((got = std::fread(buf, 1, sizeof buf, f)) > 0) data.insert(data.end(), buf, buf + got);
                std::fclose(f);
                err = decode_dds(data.data(), data.size(), img);
                if (err.empty()) {
                    downscale(img, max_dim, max_pixels);
                    if (e.afix) fix_alpha(img);
                }
            }
            std::lock_guard<std::mutex> lock(mu_);
            --busy_;
            if (err.empty()) {
                state_[static_cast<std::size_t>(i)] = 2;
                (urgent_[static_cast<std::size_t>(i)] ? done_ : done_low_).emplace_back(i, std::move(img));
            } else {
                state_[static_cast<std::size_t>(i)] = 3;
                last_error = err;
                std::fprintf(stderr, "[hdtex] %s\n", err.c_str());
            }
            done_cv_.notify_all();
        }
    }

    std::string dir_;
    std::vector<Entry> entries_;
    std::unordered_map<std::uint64_t, int> index_;
    std::vector<std::uint8_t> state_;   // 0 not asked, 1 queued, 2 decoded, 3 failed, 4 being decoded
    std::vector<std::uint8_t> urgent_;  // the game asked for it (not just a preload)
    std::deque<int> todo_;
    std::deque<std::pair<int, Image>> done_, done_low_;
    std::mutex mu_;
    std::condition_variable cv_, done_cv_;
    std::vector<std::thread> workers_;
    unsigned max_workers_ = 1, busy_ = 0;
    bool stop_ = false;
};

}  // namespace hdtex
