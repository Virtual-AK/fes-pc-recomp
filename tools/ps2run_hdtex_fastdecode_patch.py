"""HD textures: decode the HD pictures much faster, so a picture shown for the first time no longer stalls the game for about 65 ms.

What was slow: every portrait is a 2048x2048 BC7 file. The decoder read each block's bits one at a time, wrote the whole 2048x2048 picture (16 MB) and then
made a second pass to halve it to 1024x1024. A picture the game is waiting for (its first use) was decoded by one thread while the game stood still.

What changes (the result is the same, pixel for pixel; it was compared on every picture of the HQ Portraits and Widescreen packs):
  1. BitReader reads a field with one shift instead of one bit at a time.
  2. decode_dds_fast halves the picture while decoding it, block by block (a 4x4 block gives 2x2 output pixels with the same maths as downscale), so the
     16 MB intermediate picture and the second pass are gone. It is only used when exactly one halving is needed and the size is a multiple of 4;
     anything else goes the old way.
  3. A picture the game is waiting for is decoded in bands on up to 3 threads (only on a CPU with 4 or more threads, and only for urgent pictures; preloads
     stay on one thread so they never take cores from the game).

Run in the ps2-web-recomp folder:  python3 ps2run_hdtex_fastdecode_patch.py [folder]
(patches runtime/src/gs/gpu/hdtex.hpp; idempotent per edit; refuses unknown source; needs ps2run_hdtex_patch.py applied)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
TAG = 'ps2run_hdtex_fastdecode_patch.py'
HDR = 'runtime/src/gs/gpu/hdtex.hpp'

BITREADER_OLD = '''struct BitReader {
    const std::uint8_t *p;
    unsigned pos = 0;
    std::uint32_t get(unsigned n) {
        std::uint32_t v = 0;
        for (unsigned i = 0; i < n; ++i, ++pos) v |= static_cast<std::uint32_t>((p[pos >> 3] >> (pos & 7)) & 1) << i;
        return v;
    }
};
'''
BITREADER_NEW = '''struct BitReader {   // ''' + TAG + ''': the 16 bytes of the block are read once (little endian, as on x86), a field is one shift
    std::uint64_t lo = 0, hi = 0;
    unsigned pos = 0;
    explicit BitReader(const std::uint8_t *p) {
        std::memcpy(&lo, p, 8);
        std::memcpy(&hi, p + 8, 8);
    }
    std::uint32_t get(unsigned n) {
        if (!n) return 0;
        std::uint64_t v;
        if (pos >= 64) v = hi >> (pos - 64);
        else if (pos + n <= 64) v = lo >> pos;
        else v = (lo >> pos) | (hi << (64 - pos));
        pos += n;
        return static_cast<std::uint32_t>(v & ((1ull << n) - 1));
    }
};
'''

FAST_ANCHOR = '// Halves the picture (2x2 average, on premultiplied colour so clear pixels do not bleed)'
FAST_CODE = '''// ''' + TAG + ''': decode and halve in one go. Same result as decode_dds followed by downscale (one halving); false when this shortcut does not apply.
namespace detail {
inline std::uint32_t avg4(std::uint32_t p0, std::uint32_t p1, std::uint32_t p2, std::uint32_t p3) {   // one output pixel of downscale()
    const std::uint32_t p[4] = {p0, p1, p2, p3};
    std::uint32_t sr = 0, sg = 0, sb = 0, sa = 0;
    for (int k = 0; k < 4; ++k) {
        const std::uint32_t a = p[k] >> 24;
        sr += (p[k] & 255) * a;
        sg += ((p[k] >> 8) & 255) * a;
        sb += ((p[k] >> 16) & 255) * a;
        sa += a;
    }
    if (!sa) {
        std::uint32_t r = 0, g = 0, b = 0;
        for (int k = 0; k < 4; ++k) {
            r += p[k] & 255;
            g += (p[k] >> 8) & 255;
            b += (p[k] >> 16) & 255;
        }
        return (r / 4) | ((g / 4) << 8) | ((b / 4) << 16);
    }
    return (sr / sa) | ((sg / sa) << 8) | ((sb / sa) << 16) | (((sa + 2) / 4) << 24);
}
inline void fast_band(const std::uint8_t *blocks, int kind, std::size_t bsz, std::size_t bw, std::size_t b0, std::size_t b1, std::uint32_t *out, std::uint32_t nw) {
    std::uint32_t t[16];
    for (std::size_t by = b0; by < b1; ++by)
        for (std::size_t bx = 0; bx < bw; ++bx) {
            const std::uint8_t *b = blocks + (by * bw + bx) * bsz;
            if (kind == 1) bc1_block(b, t);
            else if (kind == 2) bc2_block(b, t);
            else if (kind == 3) bc3_block(b, t);
            else bc7_block(b, t);
            std::uint32_t *o = out + (by * 2) * nw + bx * 2;
            for (int oy = 0; oy < 2; ++oy)
                for (int ox = 0; ox < 2; ++ox) {
                    const int i = oy * 8 + ox * 2;   // top left of the 2x2 group inside the 4x4 block
                    o[oy * nw + static_cast<std::size_t>(ox)] = avg4(t[i], t[i + 1], t[i + 4], t[i + 5]);
                }
        }
}
}  // namespace detail

inline bool decode_dds_fast(const std::uint8_t *d, std::size_t n, Image &img, std::uint32_t max_dim, std::uint32_t max_pixels, unsigned threads) {
    if (n < 148 || std::memcmp(d, "DDS ", 4) != 0 || detail::rd32(d + 4) != 124) return false;
    const std::uint32_t h = detail::rd32(d + 12), w = detail::rd32(d + 16);
    if (!w || !h || w > 8192 || h > 8192 || (w & 3) || (h & 3)) return false;
    const bool big = w > max_dim || h > max_dim || static_cast<std::uint64_t>(w) * h > max_pixels;
    const std::uint32_t nw = w / 2, nh = h / 2;
    if (!big || nw > max_dim || nh > max_dim || static_cast<std::uint64_t>(nw) * nh > max_pixels) return false;   // not exactly one halving
    std::size_t off = 128;
    int kind = 0;
    if (std::memcmp(d + 84, "DXT1", 4) == 0) kind = 1;
    else if (std::memcmp(d + 84, "DXT3", 4) == 0) kind = 2;
    else if (std::memcmp(d + 84, "DXT5", 4) == 0) kind = 3;
    else if (std::memcmp(d + 84, "DX10", 4) == 0) {
        const std::uint32_t f = detail::rd32(d + 128);
        off = 148;
        if (f == 71 || f == 72) kind = 1;
        else if (f == 74 || f == 75) kind = 2;
        else if (f == 77 || f == 78) kind = 3;
        else if (f == 98 || f == 99) kind = 7;
    }
    if (!kind) return false;
    const std::size_t bsz = kind == 1 ? 8 : 16, bw = w / 4, bh = h / 4;
    if (n < off + bw * bh * bsz) return false;
    img.w = nw;
    img.h = nh;
    img.px.assign(static_cast<std::size_t>(nw) * nh, 0);
    const std::uint8_t *blocks = d + off;
    std::uint32_t *out = img.px.data();
    if (threads < 2 || bh < 16) {
        detail::fast_band(blocks, kind, bsz, bw, 0, bh, out, nw);
    } else {
        std::vector<std::thread> helpers;
        const std::size_t step = (bh + threads - 1) / threads;
        for (unsigned k = 1; k < threads; ++k) {
            const std::size_t b0 = std::min<std::size_t>(bh, k * step), b1 = std::min<std::size_t>(bh, (k + 1) * step);
            if (b0 < b1) helpers.emplace_back([=] { detail::fast_band(blocks, kind, bsz, bw, b0, b1, out, nw); });
        }
        detail::fast_band(blocks, kind, bsz, bw, 0, std::min<std::size_t>(bh, step), out, nw);
        for (std::thread &t : helpers) t.join();
    }
    return true;
}

'''

RUN_OLD1 = '''                state_[static_cast<std::size_t>(i)] = 4;
                ++busy_;
            }
'''
RUN_NEW1 = '''                state_[static_cast<std::size_t>(i)] = 4;
                ++busy_;
                urgent_now = urgent_[static_cast<std::size_t>(i)] != 0;   // ''' + TAG + '''
            }
'''
RUN_OLD0 = '''            int i;
            {
                std::unique_lock<std::mutex> lock(mu_);
                cv_.wait(lock, [this] { return stop_ || !todo_.empty(); });'''
RUN_NEW0 = '''            int i;
            bool urgent_now = false;
            {
                std::unique_lock<std::mutex> lock(mu_);
                cv_.wait(lock, [this] { return stop_ || !todo_.empty(); });'''
RUN_OLD2 = '''                err = decode_dds(data.data(), data.size(), img);
                if (err.empty()) {
                    downscale(img, max_dim, max_pixels);
                    if (e.afix) fix_alpha(img);
                }
'''
RUN_NEW2 = '''                const unsigned hw = std::thread::hardware_concurrency();   // ''' + TAG + ''': a picture the game is waiting for is decoded on up to 3 threads
                if (!decode_dds_fast(data.data(), data.size(), img, max_dim, max_pixels, urgent_now && hw >= 4 ? 3u : 1u)) {
                    err = decode_dds(data.data(), data.size(), img);
                    if (err.empty()) downscale(img, max_dim, max_pixels);
                }
                if (err.empty() && e.afix) fix_alpha(img);
'''

EDITS = [
    (BITREADER_OLD, BITREADER_NEW),
    (FAST_ANCHOR, FAST_CODE + FAST_ANCHOR),
    (RUN_OLD0, RUN_NEW0),
    (RUN_OLD1, RUN_NEW1),
    (RUN_OLD2, RUN_NEW2),
]

try:
    with open(root + '/' + HDR, newline='') as f:
        raw = f.read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + HDR)
    raise SystemExit(1)
crlf = '\r\n' in raw
t = raw.replace('\r\n', '\n')
# an edit whose replacement is already in the file is skipped, so a half-patched file is finished
todo = [(o, n) for o, n in EDITS if n not in t]
if not todo:
    print("already patched")
    raise SystemExit
for old, _ in todo:
    if t.count(old) != 1:
        print("PATCH NOT APPLIED: " + HDR + " does not look like the expected source (" + old.strip().split('\n')[0][:60] + ")")
        raise SystemExit(1)
for old, new in todo:
    t = t.replace(old, new)
with open(root + '/' + HDR, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d edits)" % len(todo))
