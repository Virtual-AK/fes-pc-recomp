"""Subtitles over the movies of the PC window of PS2 Web Recomp (docs/subtitles.md).

Put a folder of plain subtitle files (NAME.srt, UTF-8, for example P3CTOP.srt) next to a movies.txt (p3fes_subs.py movies "game.iso" -o FOLDER)
and start the PC window with PS2_SUBS=FOLDER. While a movie plays, its subtitles are drawn over the bottom of the game window.

How it works: the disc reader notices when the game reads the sectors of a known movie (movies.txt: NAME first-sector sector-count) and tells the
system which movie, and at which frame, it started. The PC window keeps its own clock from that frame (59.94 per second), picks the line of
the .srt that belongs to the time, and draws it in a small borderless always-on-top window (transparent on Windows) over the bottom of the
game window, with a built-in font (Latin with accents, Greek, Cyrillic; no Chinese/Japanese/Korean letters). It works whichever way the game
itself is drawn, nothing about the game changes.
Timing: the movie starts a little after its first sector is read. Press ] (subtitles later) or [ (earlier) in the game window while the movie plays;
each press moves them 0.25 s. To keep the setting, start with PS2_SUBS_DELAY=seconds (negative = earlier).
Font: DejaVu Sans Bold (Bitstream Vera licence, free to use and share), pre-rendered into the patch.

Run in the ps2-web-recomp folder:  python3 ps2run_subs_patch.py [folder]
(patches runtime/include/ps2/system.hpp, runtime/src/system.cpp, runtime/src/disc.cpp, host/window.cpp and writes host/subs.inc, host/subs_font.inc;
idempotent; refuses unknown source) Rebuild afterwards.
"""
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
MARK = 'ps2run_subs_patch.py'

SUBS_INC = r'''// subs.inc - subtitles over the game's movies (ps2run_subs_patch.py). Included once by host/window.cpp.
// Reads NAME.srt from the folder in PS2_SUBS while the movie NAME plays and shows each line in a small transparent window over the bottom of the game window.
// Everything is drawn on the CPU from a built-in letter table (subs_font.inc): Latin with accents, Greek, Cyrillic.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>
#if defined(_WIN32) && defined(_MSC_VER)
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "user32.lib")
#endif

namespace {
namespace subs {
#include "subs_font.inc"   // static const char *const kFontParts[] = { "...", ... };

struct Glyph { int adv = 0, w = 0, h = 0, xo = 0, yo = 0; std::size_t off = 0; };
std::unordered_map<std::uint32_t, Glyph> g_glyphs;
std::vector<std::uint8_t> g_alpha;     // all glyph shapes, one byte (0..255) per pixel
int g_line_h = 36;
bool g_font_ok = false;

int b64v(int c) {
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 'a' + 26;
    if (c >= '0' && c <= '9') return c - '0' + 52;
    if (c == '+') return 62;
    if (c == '/') return 63;
    return -1;
}

void font_init() {
    if (g_font_ok) return;
    std::string b64;
    for (const char *part : kFontParts) b64 += part;
    std::vector<std::uint8_t> blob;
    blob.reserve(b64.size() * 3 / 4);
    unsigned acc = 0;
    int bits = 0;
    for (char ch : b64) {
        const int v = b64v(static_cast<unsigned char>(ch));
        if (v < 0) continue;
        acc = (acc << 6) | static_cast<unsigned>(v);
        bits += 6;
        if (bits >= 8) {
            bits -= 8;
            blob.push_back(static_cast<std::uint8_t>((acc >> bits) & 0xFF));
        }
    }
    if (blob.size() < 6) return;
    auto u16 = [&](std::size_t p) { return static_cast<unsigned>(blob[p] | (blob[p + 1] << 8)); };
    auto u32 = [&](std::size_t p) { return static_cast<std::uint32_t>(blob[p] | (blob[p + 1] << 8) | (blob[p + 2] << 16) | (static_cast<std::uint32_t>(blob[p + 3]) << 24)); };
    const unsigned n = u16(0);
    g_line_h = static_cast<int>(u16(2));
    const std::size_t table = 6, data = table + static_cast<std::size_t>(n) * 13;
    if (blob.size() < data) return;
    g_alpha.assign((blob.size() - data) * 2, 0);
    for (std::size_t i = data; i < blob.size(); ++i) {
        g_alpha[(i - data) * 2] = static_cast<std::uint8_t>((blob[i] & 15) * 17);
        g_alpha[(i - data) * 2 + 1] = static_cast<std::uint8_t>((blob[i] >> 4) * 17);
    }
    for (unsigned i = 0; i < n; ++i) {
        const std::size_t p = table + static_cast<std::size_t>(i) * 13;
        Glyph g;
        const std::uint32_t cp = u32(p);
        g.adv = blob[p + 4];
        g.w = blob[p + 5];
        g.h = blob[p + 6];
        g.xo = static_cast<std::int8_t>(blob[p + 7]);
        g.yo = static_cast<std::int8_t>(blob[p + 8]);
        g.off = u32(p + 9);
        g_glyphs[cp] = g;
    }
    g_font_ok = !g_glyphs.empty();
}

const Glyph *glyph(std::uint32_t cp) {
    auto it = g_glyphs.find(cp);
    if (it == g_glyphs.end()) it = g_glyphs.find('?');
    return it == g_glyphs.end() ? nullptr : &it->second;
}

// ---- subtitle files (SubRip, UTF-8)
struct Cue { double a = 0, b = 0; std::u32string text; };

std::u32string utf8(const std::string &s) {
    std::u32string out;
    for (std::size_t i = 0; i < s.size();) {
        const unsigned char c = static_cast<unsigned char>(s[i]);
        std::uint32_t cp = c;
        int n = 0;
        if (c >= 0xF0) { cp = c & 7; n = 3; }
        else if (c >= 0xE0) { cp = c & 15; n = 2; }
        else if (c >= 0xC0) { cp = c & 31; n = 1; }
        ++i;
        while (n-- > 0 && i < s.size() && (static_cast<unsigned char>(s[i]) & 0xC0) == 0x80) cp = (cp << 6) | (static_cast<unsigned char>(s[i++]) & 63);
        out.push_back(cp);
    }
    return out;
}

bool parse_time(const std::string &s, std::size_t &pos, double &out) {
    // H:MM:SS,mmm (comma or dot)
    unsigned h = 0, m = 0, sec = 0, ms = 0;
    int digits = 0;
    std::size_t p = pos;
    auto num = [&](unsigned &v) {
        v = 0;
        int d = 0;
        while (p < s.size() && std::isdigit(static_cast<unsigned char>(s[p]))) { v = v * 10 + static_cast<unsigned>(s[p] - '0'); ++p; ++d; }
        return d;
    };
    if (!num(h) || p >= s.size() || s[p] != ':') return false;
    ++p;
    if (!num(m) || p >= s.size() || s[p] != ':') return false;
    ++p;
    if (!num(sec)) return false;
    if (p < s.size() && (s[p] == ',' || s[p] == '.')) {
        ++p;
        unsigned v = 0;
        while (p < s.size() && std::isdigit(static_cast<unsigned char>(s[p]))) {
            if (digits < 3) { v = v * 10 + static_cast<unsigned>(s[p] - '0'); ++digits; }
            ++p;
        }
        while (digits++ < 3) v *= 10;
        ms = v;
    }
    out = h * 3600.0 + m * 60.0 + sec + ms / 1000.0;
    pos = p;
    return true;
}

std::string strip_tags(const std::string &l) {
    std::string o;
    for (std::size_t i = 0; i < l.size(); ++i) {
        if (l[i] == '<') { const std::size_t e = l.find('>', i); if (e != std::string::npos) { i = e; continue; } }
        if (l[i] == '{' && i + 1 < l.size() && l[i + 1] == '\\') { const std::size_t e = l.find('}', i); if (e != std::string::npos) { i = e; continue; } }
        o += l[i];
    }
    return o;
}

std::vector<Cue> parse_srt(std::string text) {
    std::vector<Cue> cues;
    if (text.size() >= 3 && static_cast<unsigned char>(text[0]) == 0xEF && static_cast<unsigned char>(text[1]) == 0xBB && static_cast<unsigned char>(text[2]) == 0xBF) text.erase(0, 3);
    std::vector<std::string> lines;
    {
        std::string cur;
        for (char c : text) {
            if (c == '\r') continue;
            if (c == '\n') { lines.push_back(cur); cur.clear(); }
            else cur += c;
        }
        lines.push_back(cur);
    }
    for (std::size_t i = 0; i < lines.size(); ++i) {
        const std::size_t arrow = lines[i].find("-->");
        if (arrow == std::string::npos) continue;
        Cue c;
        std::size_t p = 0;
        const std::string &l = lines[i];
        while (p < l.size() && !std::isdigit(static_cast<unsigned char>(l[p]))) ++p;
        if (!parse_time(l, p, c.a)) continue;
        p = arrow + 3;
        while (p < l.size() && !std::isdigit(static_cast<unsigned char>(l[p]))) ++p;
        if (!parse_time(l, p, c.b)) continue;
        std::string body;
        for (std::size_t k = i + 1; k < lines.size(); ++k) {
            const std::string t = strip_tags(lines[k]);
            if (t.find_first_not_of(" \t") == std::string::npos) break;
            if (lines[k].find("-->") != std::string::npos) break;
            std::size_t b = t.find_first_not_of(" \t"), e = t.find_last_not_of(" \t");
            if (!body.empty()) body += '\n';
            body += t.substr(b, e - b + 1);
        }
        if (body.empty()) continue;
        c.text = utf8(body);
        cues.push_back(c);
    }
    std::stable_sort(cues.begin(), cues.end(), [](const Cue &x, const Cue &y) { return x.a < y.a; });
    return cues;
}

// ---- drawing: text -> premultiplied BGRA picture (white letters, dark outline)
struct Img { int w = 0, h = 0; std::vector<std::uint32_t> px; };

Img render(const std::u32string &text, int win_w, int win_h) {
    Img im;
    if (!g_font_ok) return im;
    double s = std::clamp(win_h * 0.052 / g_line_h, 0.45, 2.2);
    const double maxw = std::max(120.0, win_w * 0.84);
    // lines: split at newlines, then wrap at spaces
    std::vector<std::u32string> lines;
    {
        std::u32string cur;
        for (char32_t c : text) {
            if (c == U'\n') { lines.push_back(cur); cur.clear(); }
            else cur.push_back(c);
        }
        lines.push_back(cur);
    }
    auto width = [&](const std::u32string &l) {
        double w = 0;
        for (char32_t c : l) { const Glyph *g = glyph(c); if (g) w += g->adv * s; }
        return w;
    };
    std::vector<std::u32string> wrapped;
    for (const auto &l : lines) {
        std::u32string cur, word;
        auto flush_word = [&]() {
            if (word.empty()) return;
            std::u32string trial = cur.empty() ? word : cur + U" " + word;
            if (!cur.empty() && width(trial) > maxw) { wrapped.push_back(cur); cur = word; }
            else cur = trial;
            word.clear();
        };
        for (char32_t c : l) {
            if (c == U' ') flush_word();
            else word.push_back(c);
        }
        flush_word();
        wrapped.push_back(cur);
    }
    const int r = std::max(1, static_cast<int>(std::lround(2.2 * s)));
    const int pad = r + 3;
    double wmax = 0;
    for (const auto &l : wrapped) wmax = std::max(wmax, width(l));
    const int lh = static_cast<int>(std::lround(g_line_h * s));
    im.w = static_cast<int>(std::ceil(wmax)) + 2 * pad;
    im.h = lh * static_cast<int>(wrapped.size()) + 2 * pad;
    if (im.w < 8 || im.h < 8 || im.w > 8192 || im.h > 4096) { im.w = im.h = 0; return im; }
    std::vector<std::uint8_t> A(static_cast<std::size_t>(im.w) * im.h, 0);
    for (std::size_t li = 0; li < wrapped.size(); ++li) {
        double pen = pad + (wmax - width(wrapped[li])) / 2.0;     // centred
        const double top = pad + static_cast<double>(li) * lh;
        for (char32_t c : wrapped[li]) {
            const Glyph *g = glyph(c);
            if (!g) continue;
            if (g->w > 0 && g->h > 0) {
                const int dw = std::max(1, static_cast<int>(std::lround(g->w * s))), dh = std::max(1, static_cast<int>(std::lround(g->h * s)));
                const int dx0 = static_cast<int>(std::lround(pen + g->xo * s)), dy0 = static_cast<int>(std::lround(top + g->yo * s));
                const std::uint8_t *src = &g_alpha[g->off * 2];
                for (int y = 0; y < dh; ++y) {
                    const double sy = std::clamp((y + 0.5) * g->h / dh - 0.5, 0.0, g->h - 1.0);
                    const int y0 = static_cast<int>(sy), y1 = std::min(g->h - 1, y0 + 1);
                    const double fy = sy - y0;
                    for (int x = 0; x < dw; ++x) {
                        const double sx = std::clamp((x + 0.5) * g->w / dw - 0.5, 0.0, g->w - 1.0);
                        const int x0 = static_cast<int>(sx), x1 = std::min(g->w - 1, x0 + 1);
                        const double fx = sx - x0;
                        const double v = (src[y0 * g->w + x0] * (1 - fx) + src[y0 * g->w + x1] * fx) * (1 - fy) +
                                         (src[y1 * g->w + x0] * (1 - fx) + src[y1 * g->w + x1] * fx) * fy;
                        const int px = dx0 + x, py = dy0 + y;
                        if (px < 0 || py < 0 || px >= im.w || py >= im.h) continue;
                        std::uint8_t &a = A[static_cast<std::size_t>(py) * im.w + px];
                        a = static_cast<std::uint8_t>(std::max<int>(a, static_cast<int>(v + 0.5)));
                    }
                }
            }
            pen += g->adv * s;
        }
    }
    // outline = the letters grown by r pixels (a round brush)
    std::vector<std::uint8_t> O(A.size(), 0);
    std::vector<std::pair<int, int>> brush;
    for (int oy = -r; oy <= r; ++oy)
        for (int ox = -r; ox <= r; ++ox)
            if (ox * ox + oy * oy <= r * r + 1) brush.emplace_back(ox, oy);
    for (int y = 0; y < im.h; ++y)
        for (int x = 0; x < im.w; ++x) {
            std::uint8_t m = 0;
            for (const auto &b : brush) {
                const int xx = x + b.first, yy = y + b.second;
                if (xx < 0 || yy < 0 || xx >= im.w || yy >= im.h) continue;
                m = std::max(m, A[static_cast<std::size_t>(yy) * im.w + xx]);
            }
            O[static_cast<std::size_t>(y) * im.w + x] = m;
        }
    im.px.resize(A.size());
    for (std::size_t i = 0; i < A.size(); ++i) {
        const std::uint32_t a = std::max<std::uint32_t>(A[i], static_cast<std::uint32_t>(O[i] * 0.92));   // outline is a little see-through
        const std::uint32_t c = std::min<std::uint32_t>(A[i], a);                                           // white, premultiplied
        im.px[i] = (a << 24) | (c << 16) | (c << 8) | c;
    }
    return im;
}

// ---- the window
SDL_Window *g_win = nullptr;
bool g_shown_win = false;
int g_wx = 0, g_wy = 0, g_ww = 0, g_wh = 0;

void window_hide() {
    if (!g_win || !g_shown_win) return;
#ifdef _WIN32
    SDL_SysWMinfo wi;
    SDL_VERSION(&wi.version);
    if (SDL_GetWindowWMInfo(g_win, &wi)) ShowWindow(wi.info.win.window, SW_HIDE);
#else
    SDL_HideWindow(g_win);
#endif
    g_shown_win = false;
}

// where the game picture is on screen: (x, y, w, h)
void game_rect(SDL_Window *game, int &x, int &y, int &w, int &h) {
    SDL_GetWindowPosition(game, &x, &y);
    SDL_GetWindowSize(game, &w, &h);
    if (SDL_GetWindowFlags(game) & SDL_WINDOW_FULLSCREEN) {
        SDL_Rect r;
        if (SDL_GetDisplayBounds(SDL_GetWindowDisplayIndex(game), &r) == 0) { x = r.x; y = r.y; w = r.w; h = r.h; }
    }
}

void window_show(SDL_Window *game, const Img &im) {
    if (im.w <= 0 || im.h <= 0) { window_hide(); return; }
    int gx, gy, gw, gh;
    game_rect(game, gx, gy, gw, gh);
    const int x = gx + (gw - im.w) / 2, y = gy + gh - im.h - gh * 6 / 100;
    if (!g_win) {
        SDL_SetHint(SDL_HINT_WINDOW_NO_ACTIVATION_WHEN_SHOWN, "1");
        g_win = SDL_CreateWindow("Subtitles", x, y, im.w, im.h, SDL_WINDOW_BORDERLESS | SDL_WINDOW_ALWAYS_ON_TOP | SDL_WINDOW_SKIP_TASKBAR | SDL_WINDOW_HIDDEN);
        if (!g_win) { std::fprintf(stderr, "[subs] cannot open the subtitle window: %s\n", SDL_GetError()); return; }
#ifdef _WIN32
        SDL_SysWMinfo wi;
        SDL_VERSION(&wi.version);
        if (SDL_GetWindowWMInfo(g_win, &wi)) {
            HWND h = wi.info.win.window;
            SetWindowLongPtrW(h, GWL_EXSTYLE, GetWindowLongPtrW(h, GWL_EXSTYLE) | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW);
        }
#endif
    }
    g_wx = x; g_wy = y; g_ww = im.w; g_wh = im.h;
#ifdef _WIN32
    SDL_SysWMinfo wi;
    SDL_VERSION(&wi.version);
    if (!SDL_GetWindowWMInfo(g_win, &wi)) return;
    HWND hwnd = wi.info.win.window;
    HDC screen = GetDC(nullptr);
    HDC mem = CreateCompatibleDC(screen);
    BITMAPINFO bi;
    std::memset(&bi, 0, sizeof(bi));
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = im.w;
    bi.bmiHeader.biHeight = -im.h;          // top-down
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    void *bits = nullptr;
    HBITMAP bmp = CreateDIBSection(screen, &bi, DIB_RGB_COLORS, &bits, nullptr, 0);
    if (bmp && bits) {
        std::memcpy(bits, im.px.data(), im.px.size() * 4);
        HGDIOBJ old = SelectObject(mem, bmp);
        POINT pos{x, y};
        SIZE sz{im.w, im.h};
        POINT src{0, 0};
        BLENDFUNCTION bf;
        bf.BlendOp = AC_SRC_OVER;
        bf.BlendFlags = 0;
        bf.SourceConstantAlpha = 255;
        bf.AlphaFormat = AC_SRC_ALPHA;
        UpdateLayeredWindow(hwnd, screen, &pos, &sz, mem, &src, 0, &bf, ULW_ALPHA);
        SelectObject(mem, old);
    }
    if (bmp) DeleteObject(bmp);
    DeleteDC(mem);
    ReleaseDC(nullptr, screen);
    SetWindowPos(hwnd, HWND_TOPMOST, x, y, im.w, im.h, SWP_NOACTIVATE | SWP_SHOWWINDOW);
#else
    // no transparent windows here: a dark box with the letters on it
    SDL_SetWindowSize(g_win, im.w, im.h);
    SDL_SetWindowPosition(g_win, x, y);
    SDL_ShowWindow(g_win);
    if (SDL_Surface *sf = SDL_GetWindowSurface(g_win)) {
        SDL_LockSurface(sf);
        for (int yy = 0; yy < std::min(sf->h, im.h); ++yy) {
            std::uint32_t *row = reinterpret_cast<std::uint32_t *>(static_cast<std::uint8_t *>(sf->pixels) + static_cast<std::size_t>(yy) * sf->pitch);
            for (int xx = 0; xx < std::min(sf->w, im.w); ++xx) {
                const std::uint32_t p = im.px[static_cast<std::size_t>(yy) * im.w + xx];
                const std::uint32_t a = p >> 24, c = p & 255;
                const std::uint32_t v = std::min<std::uint32_t>(255, c + (16 * (255 - a)) / 255);   // letters over near-black
                row[xx] = 0xFF000000u | (v << 16) | (v << 8) | v;
            }
        }
        SDL_UnlockSurface(sf);
        SDL_UpdateWindowSurface(g_win);
    }
#endif
    g_shown_win = true;
}

// ---- per frame
std::vector<Cue> g_cues;
std::string g_name;
std::uint64_t g_start = ~0ull;
int g_cue = -2;                // the cue on screen: -1 none, -2 nothing decided yet
double g_delay = 0.0;
bool g_delay_read = false;
std::uint64_t g_last_pos = 0;
int g_gw = 0, g_gh = 0;
std::string g_dir;

void load(const std::string &name) {
    g_cues.clear();
    std::ifstream f(g_dir + "/" + name + ".srt", std::ios::binary);
    if (f) {
        std::stringstream ss;
        ss << f.rdbuf();
        g_cues = parse_srt(ss.str());
    }
    std::fprintf(stderr, "[subs] %s: %zu subtitle lines%s\n", name.c_str(), g_cues.size(), f ? "" : " (no file)");
}

void tick(SDL_Window *game) {
    static const char *dir = std::getenv("PS2_SUBS");
    if (!dir || !*dir || !game) return;
    if (!g_delay_read) {
        g_delay_read = true;
        g_dir = dir;
        if (const char *d = std::getenv("PS2_SUBS_DELAY")) g_delay = std::atof(d);
        font_init();
        std::fprintf(stderr, "[subs] on, folder %s, delay %.2f s (keys [ and ] change it while a movie plays)\n", dir, g_delay);
    }
    {   // only while the game window is in front: alt+tab, minimise or a closed window hides the subtitles (the overlay is always-on-top)
        const Uint32 fl = SDL_GetWindowFlags(game);
        if (!(fl & SDL_WINDOW_INPUT_FOCUS) || (fl & (SDL_WINDOW_MINIMIZED | SDL_WINDOW_HIDDEN))) {
            window_hide();
            g_cue = -2;
            return;
        }
    }
    std::string name;
    std::uint64_t start = 0, last = 0;
    const std::uint64_t now = ps2::frame_count();
    const bool on = ps2::movie_now(name, start, last) && now - last < 150;   // a skipped movie stops being read: hide after 2.5 s without a read (a late read just brings the line back)
    if (!on) {
        if (g_cue != -2) { g_cue = -2; g_name.clear(); g_start = ~0ull; window_hide(); }
        return;
    }
    if (name != g_name || start != g_start) {
        g_name = name;
        g_start = start;
        g_cue = -2;
        load(name);
    }
    const double t = static_cast<double>(now - start) / 59.94 + g_delay;
    int idx = -1;
    for (std::size_t i = 0; i < g_cues.size(); ++i)
        if (t >= g_cues[i].a && t < g_cues[i].b) { idx = static_cast<int>(i); break; }
    int gx, gy, gw, gh;
    game_rect(game, gx, gy, gw, gh);
    const bool moved = idx >= 0 && (now - g_last_pos > 20) && (gx + (gw - g_ww) / 2 != g_wx || gy + gh - g_wh - gh * 6 / 100 != g_wy);
    if (idx == g_cue && !(moved) && gw == g_gw && gh == g_gh) return;
    g_cue = idx;
    g_gw = gw;
    g_gh = gh;
    g_last_pos = now;
    if (idx < 0) { window_hide(); return; }
    window_show(game, render(g_cues[static_cast<std::size_t>(idx)].text, gw, gh));
}

void key(const SDL_Event &e) {
    if (e.type != SDL_KEYDOWN || e.key.repeat) return;
    const SDL_Scancode k = e.key.keysym.scancode;
    if (k != SDL_SCANCODE_LEFTBRACKET && k != SDL_SCANCODE_RIGHTBRACKET) return;
    if (!std::getenv("PS2_SUBS")) return;
    g_delay += k == SDL_SCANCODE_RIGHTBRACKET ? 0.25 : -0.25;     // ] = subtitles come later, [ = earlier
    g_cue = -2;
    std::fprintf(stderr, "[subs] delay %.2f s\n", g_delay);
}
}  // namespace subs
}  // namespace

static void subs_draw(SDL_Window *game) { subs::tick(game); }
static void subs_event(const SDL_Event &e) { subs::key(e); }
'''

FONT_B64 = '''
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
AD0EAAAVERACDARSAQA+BAAAFRMQAQyMUgEAPwQAABUREAIMJFMBAEAEAAAVExYCDKxTAQBBBAAAEg8QAQx9VAEAQgQAABESEAAM
9VQBAEMEAAAUExYADIVVAQBEBAAAHhwdAQVWVgEARQQAABMTEAAM7FcBAEYEAAAWExQCDIRYAQBHBAAAFREQAQxCWQEASAQAACAc
EAIMylkBAEkEAAAhHhQCDKpaAQBKBAAAFxYRAAvWWwEASwQAABsXEAIMkVwBAEwEAAATEBACDEldAQBNBAAAEg8SAgvJXQEATgQA
AB0aEAIMUF4BAE8EAAATERAADCBfAQBRBAAAFBIXAQWoXwEAEyAAAA8NBAERd2ABABQgAAAeHAQBEZFgAQAYIAAACwcJAwbJYAEA
GSAAAAsICQEG6WABABogAAALBwkCFg1hAQAbIAAACwgKAQYtYQEAHCAAABQOCQMGVWEBAB0gAAAUDwkCBpRhAQAeIAAAFA8JAhbY
YQEAIiAAABMLCwQMHGIBACYgAAAeGgYCFlliAQA5IAAADAgOAgynYgEAOiAAAAwJDgIM32IBAKwgAAAVFBb/Bh5jAQD8/3/8/3/8
/3/8/3/8/3/8/3/8/3/8/3/8/3/7/2/5/0/3/y/1/w/z/w7y/wwAAAAAAAD8/3/8/3/8/3/8/3/8/3/y/wWw/yz/XwD7z/L/BbD/
LP9fAPvP8v8FsP8s/18A+8/y/wWw/yz/XwD7zwAAABD/PwDQ/wUAAAAAQP8PAPL/AgAAAACA/wsA9d8AAAAAALD/CAD5rwAAAAAA
4P8EAP1vAAAAAADz/wEQ/y8AAED///////////8fQP///////////x9A////////////HwAAQP8fAPL/AgAAAACA/wsA9t8AAAAA
AMD/BwD6nwAAAAAA8f8EAP5vAAAA////////////bwD///////////9vAP///////////28AAAD/TwDQ/wYAAAAAMP8fAPL/AgAA
AABw/wwA9e8AAAAAALD/CQD5rwAAAAAA4P8FAPx/AAAAAADy/wEQ/z8AAAAAAAAAsK8AAAAAAAAA+woAAAAAAACwrwAAAAAAgtv/
36w3AAD5//////+PAPr///////8I8//PtK9S6Y+A//8C+woAcQf5/x+wrwAAAJD//wj7CgAAAPb//+2/AwAAEP3/////vxYAMP3/
/////z0AEMf//////y4AABDU7////wgAAAD7Gvj/vwAAALCvAP7/jBYAAPsK4P+/+Z4lsK+C//+X/////////x35////////KxB0
yu3/74wEAAAAALCvAAAAAAAAAPsKAAAAAAAAsK8AAAAAAAAA+woAAAAAINnvfAEAAAAg/j8AAAAA9f///xwAAACg/wgAAAAg/58x
/b8AAAD13wEAAACQ/x8A9v8EABD9XwAAAADQ/wsA8v8IAID/CwAAAADw/woA8f8JAPPvAgAAAADw/woA8f8JAPx/AAAAAADQ/wsA
8v8IYP8MAAAAAACQ/x8A9v8D4f8DAAAAAAAg/58x/b8A+p8AAAAAAAAA9f///xxA/x4Ax/6tAwAAINnvfAHQ/wXB////bwAAAAAA
AAD4vwD77xP5/wMAAAAAACD/LjD/fwDh/woAAAAAALD/B3D/PwCw/w4AAAAAAPbfAJD/HwCQ/x8AAAAAEP5PAJD/LwCQ/x8AAAAA
kP8JAHD/PwCw/w4AAAAA9O8BADD/fwDg/woAAAAA/V8AAAD77xP5/wMAAABw/wsAAADB////bwAAAADy/wIAAAAAx/6tAwAAAABh
6++9SAEAAAAAADD9/////woAAAAAAOL//////woAAAAAAPn/3wNR+woAAAAAAP3/XwAAQAgAAAAAAP7/bwAAAAAAAAAAAPv/3wAA
AAAAAAAAAPT//wkAAAAAAAAAAOP//38AAAAAAAAAYP////8FAAD7/w0A9v////9PAAD8/wow//+f/f/vAxD//wiw//8K4///LlD/
/wTx//8CQP//38L/7wDz/+8AAPb///7/nwDy/+8AAHD/////LwDx//8EAAD5////BwCw//8cAADA///PAAAw///fFTD5////BwAA
9v//////////fwAAQP3/////3/z//wcAAFDa/t6LBMH//2/y/yX/X/L/Jf9f8v8l/1/y/yX/XwAA9f8vAAD9/wkAcP//AgDh/68A
APb/XwAA/P8OADD//wkAgP//BgDA//8CAPD/7wAA8//PAAD1/78AAPb/nwAA9v+fAAD2/68AAPX/vwAA8//PAADw/+8AAMD//wIA
gP//BQAw//8JAAD8/w4AAPb/XwAA4f+vAABw//8CABD9/wkAAPX/L/X/HgAA0P+fAABg//8CAAD+/woAAPn/LwAA9P+PAADg/98A
AKD//wMAcP//BwAw//8LABD//w0AAP//DwAA/v8fAAD9/y8AAP7/HwAA//8PABD//w4AMP//CwBw//8HAKD//wMA4P/fAAD0/48A
APn/LwAA/v8KAGD//wIA0P+fAAD1/x4AAAAAAPYfAAAAAAAA9h8AAACAGAD2HwCyA+HfBfYfgf8Lsv+/+X/9/wkA1f////8rAAAA
5v//TAAAAADn//9NAAAA1f////8rALL/v/hv/f8J4d8F9h+B/wuAGAD2HwCyAwAAAPYfAAAAAAAA9h8AAAAAAAAw/18AAAAAAAAA
8/8FAAAAAAAAMP9fAAAAAAAAAPP/BQAAAAAAADD/XwAAAAAAAADz/wUAAAAAAAAw/18AAAAAAAAA8/8FAAAA/P//////////zv//
////////7/z//////////w4AAADz/wUAAAAAAAAw/18AAAAAAAAA8/8FAAAAAAAAMP9fAAAAAAAAAPP/BQAAAAAAADD/XwAAAAAA
AADz/wUAAAAAAAAw/18AAAAAAP7/XwD+/18A/v9fAP7/XwD+/08w//8KcP/vAbD/XwDx/wsA9O8CAPb////P9v///8/2////z/b/
///P/v9f/v9f/v9f/v9f/v9f/v9fAAAAcP8MAAAA+38AAADx/wMAAGD/DQAAAPqPAAAA4P8EAABQ/w4AAAD5rwAAAOD/BQAAMP8f
AAAA+L8AAADQ/wYAACD/HwAAAPfPAAAAwP8HAAAQ/y8AAAD23wAAAKD/CAAAEP5PAAAA9e8AAACQ/wkAAAD+XwAAAPPvAQAAgP8K
AAAA/W8AAAAAAAAwyP7OKAAAAACh/////48AAADB//////+vAACg////////jwBA//+/AsP//y8A+v/fAQDh//8I8P//CAAA+v/f
MP//XwAAcP//H/b//wMAAPX//3T//y8AAED//1/4//8BAADz//+G//8fAAAw//9v9///AgAA9P//Zf//PwAAUP//T/P//wUAAPf/
/wH//48AAKD//w2g//8dABD+/48A9P//KzD8//8CAPr///////8IABD8//////8KAAAQ+v////8IAAAAAIPs74wCAAAxlvz//wwA
APn/////DAAA+f////8MAAD5/////wwAAMlpg///DAAAAACA//8MAAAAAID//wwAAAAAgP//DAAAAACA//8MAAAAAID//wwAAAAA
gP//DAAAAACA//8MAAAAAID//wwAAAAAgP//DAAAAACA//8MAAAAAID//wwAAAAAgP//DAAAAACA//8MAAD3////////z/f/////
///P9////////8/3////////zzCW2/7eewIAgP///////wgA+P///////wuA/////////wb4niUg5v//z3AXAAAA4v//DwAAAAAA
+v//AQAAAACQ//8PAAAAAAD8/78AAAAAAPX//wUAAAAA4///CgAAAADk//8cAAAAAPb//xwAAAAA+P//GwAAAAD5//8JAAAAEPv/
/wcAAAAg/P//BgAAADD9/+8EAAAAAPn/////////lP////////9P+f////////+U/////////08gldv+3osEABD///////8sAPH/
//////8eEP////////8I0VkTIMX//98AAAAAANH//w4AAAAAAPv/3wAAAAAA0f//CQAAABDF//8uAAD0/////ywAAED/////GQAA
APT/////bgAAQP//////fwAAAABB+f//HgAAAAAA9///BQAAAAAw//9/OwAAAAD3///2vzYBQfn//z//////////z/D////////f
AsT//////68BADC4/u+sJwAAAAAAAPP//28AAAAAANH///8GAAAAAID///9vAAAAAED/////BgAAABD9////bwAAAAD4/+j//wYA
AAD0/wz+/28AAADR/z/g//8GAACA/48A/v9vAABA/88A4P//BgAQ/f8DAP7/bwAA+P8IAOD//wYA9P8MAAD+/28AoP8/AADg//8G
APr//////////6j//////////4/6//////////+o//////////+PAAAAAAD+/28AAAAAAADg//8GAAAAAAAA/v9vAAAAAAAA4P//
BgDA////////PwD8////////A8D///////8/APz///////8DwP+vAAAAAAAA/P8KAAAAAADA/68AAAAAAAD8/83+zkkAAMD/////
/78CAPz//////98CwP///////78A/GwCQfv//0+QBAAAAPj//wgAAAAAEP//rwAAAAAA0P//CwAAAAAQ//+vaQAAAAD4//+o71kC
Qfv//z/6////////r6D////////PAZL//////58BABCV7O+9JwAAAAAAcdvurQQAAAAA6P////88AAAQ+///////DAAA+///////
zwAA9///WwJB+gwA4f//CAAAAJIAYP//DAAAAAAAAPr/f5P9zjkAAOD///z///+PAAD/////////rwDx/////////18g////XiH3
//8M8f//XwAA+f//Af///wAAQP//P9D//w4AAPP//wP5//8AAED//y9A//9fAAD5/+8A0P//XiH3//8JAPT///////8uAAD3////
//9PAAAA5v////89AAAAAHHb760FAAD///////////f/////////f///////////9/////////9fAAAAAAD6/98AAAAAAPL//wcA
AAAAkP//HgAAAAAQ/v+PAAAAAAD3//8CAAAAAND//wkAAAAAYP//PwAAAAAA/P+/AAAAAAD0//8EAAAAALD//wwAAAAAMP//XwAA
AAAA+f/fAAAAAADx//8HAAAAAID//x4AAAAAEP7/jwAAAAAA9v//AgAAAADQ//8KAAAAAFD//z8AAAAAAACD2/7eewIAAKH/////
/58AAPz///////8KUP////////8/kP//jwKS//9/oP//CwAA/v+PcP//CwAA/v9vIP7/jwKS//8eAOX//////98DACDo////7xcA
AFD8/////0sAAPn///////8HYP//jxKS//9P0P//CAAA+v+/8f//BAAA9v/v8v//BAAA9v//8f//CAAA+v/v0P//fwKS//+/cP//
//////9fAPz///////8KAJH//////48AAACC2/7eewIAAABh2+6tBgAAAFD+////3wQAAPf//////18AQP///////+8CwP//bhHm
//8K8v//BgBw//8v9f//AgAw//9v9v//AAAQ//+v9v//AgAw///P9P//BgBw///f4f//XhHm///vgP/////////vEPz////////P
ALH//////P+/AACk7d4p+v9/AAAAAAAQ/v8/ABoAAACw//8MAO84AWL9//8EAP///////58AAP///////wkAANX/////bgAAAACm
/t5qAQAA+v+v+v+v+v+v+v+v+v+v+v+vAAAAAAAAAAAAAAAA+v+v+v+v+v+v+v+v+v+v+v+vAPr/rwD6/68A+v+vAPr/rwD6/68A
+v+vAAAAAAAAAAAAAAAAAAAAAAD6/68A+v+vAPr/rwD6/68A+v+PAP7/HjD//wVw/68AsP8eAOD/BQAAAAAAAAAAAHIMAAAAAAAA
YfvvAAAAAABQ+v//DgAAADDp////zwAAINj////fKAAQxv///984AACl////7zkAAADA///vSQAAAAAA/P+PAAAAAAAAwP//7zkA
AAAAALX////fOAAAAAAQxv///984AAAAACDY////3ycAAAAAMOn////PAAAAAABQ+v//DgAAAAAAAGH77wAAAAAAAAAAcgz8////
///////O///////////v/P//////////DgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD8///////////O///////////v/P//
////////DosCAAAAAAAAAMD/fAEAAAAAAAD8//9bAQAAAACg////70kAAAAAIMf////fOAAAAAAg1////88nAAAAADDY////vwYA
AAAAMNj//+8AAAAAAABw//8OAAAAADDY///vAAAAINf///+/BgAgx////88nACDH////7zgAAKD////vSgAAAAD8//9bAQAAAADA
/3wBAAAAAAAAiwIAAAAAAAAAAP7//++MAwD+/////58A/v//////Cf5aArP//x86AAAQ//9fAAAAAP3/bwAAACD//18AAACw//8f
AAAA+f//CQAAkP//zwEAAPf//xwAADD//88BAACQ//8eAAAA0P//CAAAAOD//wYAAAAAAAAAAAAAAAAAAAAAAOD//wYAAADg//8G
AAAA4P//BgAAAOD//wYAAADg//8GAAAAAAAAYtv+zmoBAAAAAAAAo///////nwIAAAAAgP////////9uAAAAEPv/rzYBMrf//wgA
ALD/nwEAAAAAs/9/AAD57wUAAAAAAAD4/wNA/08AAAAAAAAAgP8MwP8HADDq3wf8TwD8P/PPAAD2//+f/E8A9Y/3XwAw//////5P
APG/+x8AsP9/Efb/TwDgz/0NAPH/CABw/08A0N//CwDy/wQAMP9PAPG//wsA8v8EADD/TwD2j/0NAPH/CABw/08g/j/8HwCw/28R
5v9P1f8K+F8AQP/////+///PAfPPAAD2//+f/P//GQDA/wYAMOrfB/zOKAAAQP8+AAAAAAABAAAAAAD67wQAAAAAAIAEAAAAwf+P
AQAAADD7DQAAACD8/54lEVL6/28AAAAAof////////8JAAAAAAC0//////9LAAAAAAAAAHPb/r03AAAAAAAAAAD+//8vAAAAAAAA
AFD///+PAAAAAAAAAKD////fAAAAAAAAAPH/////BAAAAAAAAPb/////CQAAAAAAAPz/z///HgAAAAAAIP//P/7/XwAAAAAAgP//
DPn/vwAAAAAA0P//B/T//wIAAAAA9P//AuD//wcAAAAA+f/PAJD//w0AAAAQ/v9/AED//z8AAABQ//8vAAD9/58AAACw//8MAAD4
/+8AAADy//////////8FAAD3//////////8KAAD8//////////8fADD///////////9vAJD//x8AAAAA/P/PAOD//woAAAAA9///
AvX//wUAAAAA8v//CPr/7wEAAAAAwP//DfT/////3osDAED/////////GgD0/////////wxA//////////8G9P//BgCi//+vQP//
bwAA4f//DPT//wYAAPz/z0D//28AAOH//wr0//8GAKL//19A/////////68A9P///////38AQP////////9+APT/////////n0D/
/28AEMT//z/0//8GAADy//9I//9vAAAA/v+v9P//BgAA8v//Sv//bwAQxP//j/T//////////0T//////////wn0/////////whA
///////eegIAAAAAQLjt76wmAAAAUPz//////xoAEPr///////8fALD/////////HwD5///PJRBi+h8w////BwAAACAaoP//nwAA
AAAAAOD//x4AAAAAAAD0//8KAAAAAAAA9v//BwAAAAAAAPf//wUAAAAAAAD3//8FAAAAAAAA9v//BwAAAAAAAPT//woAAAAAAADg
//8eAAAAAAAAoP//nwAAAAAAADD///8HAAAAIBoA+f//zyUQUvofALD/////////HwAQ+v///////x8AAFD8//////8aAAAAQLjt
760mAPT////uvWkCAAAA9P///////78EAAD0/////////48AAPT//////////wkA9P//BhBz/f//bwD0//8GAACh///vAfT//wYA
AAD7//8I9P//BgAAAPP//wz0//8GAAAAwP//H/T//wYAAACQ//8/9P//BgAAAID//0/0//8GAAAAgP//T/T//wYAAACQ//8/9P//
BgAAAMD//x/0//8GAAAA8///DPT//wYAAAD7//8I9P//BgAAof//7wH0//8GEHP+//9vAPT//////////wkA9P////////9/AAD0
////////rwMAAPT////vvWkCAAAA9P////////9A/////////w/0/////////0D/////////D/T//wYAAAAAQP//bwAAAAAA9P//
BgAAAABA//9vAAAAAAD0//8GAAAAAED/////////BvT///////9vQP////////8G9P///////29A//9vAAAAAAD0//8GAAAAAED/
/28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P////////9E/////////0/0/////////0T/////////T/T/////////9P/////////0
//////////T/////////9P//BgAAAAD0//8GAAAAAPT//wYAAAAA9P//BgAAAAD0//8GAAAAAPT///////9v9P///////2/0////
////b/T///////9v9P//BgAAAAD0//8GAAAAAPT//wYAAAAA9P//BgAAAAD0//8GAAAAAPT//wYAAAAA9P//BgAAAAD0//8GAAAA
APT//wYAAAAAAAAAMLft785qAwAAAED8///////PBQAQ+f////////8JALD//////////wkA+f//3zYBMab/CTD///8IAAAAAHEI
oP//nwAAAAAAAADg//8eAAAAAAAAAPT//woAAAAAAAAA9v//BwAAAAAAAAD3//8FAAD2////b/f//wUAAPb///9v9v//BwAA9v//
/2/0//8KAAD2////b+D//x4AAAAA/v9voP//jwAAAAD+/28w////BwAAAP7/bwD5///PJgFB/v9vALD//////////28AEPr/////
////bwAAUPz//////88GAAAAQLjt771pAQD0//8GAAAA9P//Rf//bwAAAED//1/0//8GAAAA9P//Rf//bwAAAED//1/0//8GAAAA
9P//Rf//bwAAAED//1/0//8GAAAA9P//Rf//bwAAAED//1/0//8GAAAA9P//Rf///////////1/0////////////Rf//////////
/1/0////////////Rf//bwAAAED//1/0//8GAAAA9P//Rf//bwAAAED//1/0//8GAAAA9P//Rf//bwAAAED//1/0//8GAAAA9P//
Rf//bwAAAED//1/0//8GAAAA9P//Rf//bwAAAED//1/0//9G//9v9P//Rv//b/T//0b//2/0//9G//9v9P//Rv//b/T//0b//2/0
//9G//9v9P//Rv//b/T//0b//2/0//9G//9v9P//Rv//bwAA9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//bwAA9P//BgBA
//9vAAD0//8GAED//28AAPT//wYAQP//bwAA9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//bwAA9P//BgBA//9vAAD1//8F
AHD//08AAP3//wIx+///DPr///9foP///58A+v//fwCg760XAAD0//8GAAAg/f//CUD//28AACD9//8IAPT//wYAIP3//wgAQP//
bwAg/f//CAAA9P//BiD9//8IAABA//9vIP3//wgAAAD0//8m/v//CAAAAED//4/+//8IAAAAAPT//////wcAAAAAQP//////BwAA
AAAA9P////8MAAAAAABA//////8JAAAAAAD0//////8JAAAAAED//8////8JAAAAAPT//3b///8JAAAAQP//b3D///8JAAAA9P//
BmD///8JAABA//9vAGD///8JAAD0//8GAGD///8KAED//28AAGD///8KAPT//wYAAGD///8KQP//bwAAAGD///8K9P//BgAAAABA
//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED//28AAAAA
APT//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P//////
//9E/////////0/0/////////0T/////////T/T///8CAAAAQP///x/0////CAAAALD///8f9P///x4AAADy////H/T///9vAAAA
+P///x/0////zwAAEP7///8f9P////8DAGD/////H/T///z/CgDA/8///x/0///1/x8A9P9v//8f9P//0f9/APr/Sv//H/T//2H/
3xD//0T//x/0//8R/v91/99A//8f9P//Afn/2/9/QP//H/T//wHz////HkD//x/0//8BsP///wlA//8f9P//AVD///8DQP//H/T/
/wEA/f+/AED//x/0//8BAPf/XwBA//8f9P//AQDx/w4AQP//H/T//wEAAAAAAED//x/0//8BAAAAAABA//8f9P//AQAAAAAAQP//
H/T//wEAAAAAAED//x/0//9fAAAA8P//Rf///wwAAAD//1/0////BQAA8P//Rf///98AAAD//1/0////bwAA8P//Rf////8eAAD/
/1/0/////wcA8P//Rf//r//vAQD//1/0///j/48A8P//Rf//H/j/HgD//1/0//8R/v8J8P//Rf//H3D//wL//1/0//8B4f+f8P//
Rf//HwD2/z///1/0//8BAP3/+v//Rf//HwBg/////1/0//8BAMD/////Rf//HwAA9f///1/0//8BAAD8////Rf//HwAAQP///1/0
//8BAACw////Rf//HwAAAPP//18AAABhyf7eiwMAAAAAEOj//////0wAAAAg/P///////38AABD9/////////38AAPv//34CQfv/
/08A9f//PgAAAPn//wyw//9fAAAAAPz//xT//98AAAAAYP//j/T//wkAAAAA8f//bP//bwAAAAAA/v/f9///BQAAAADQ//9+//9f
AAAAAAD9/+/2//8GAAAAAOD//03//58AAAAAEP//z/H//w0AAAAA9v//CPv//wUAAADA//9PUP//7wIAAJD//88AwP//7ycQtP//
/wQA0f//////////BwAAwv////////8HAAAAgf7/////zwQAAAAAEKbt7704AAAA9P/////vnAQAQP////////88APT/////////
PkD//////////w30//8GAHL///9F//9vAABw//+f9P//BgAA8v//S///bwAAIP//v/T//wYAAPf//0n//28AIPf//1/0////////
/99A/////////+8D9P///////88DQP//////zkkAAPT//wYAAAAAAED//28AAAAAAAD0//8GAAAAAABA//9vAAAAAAAA9P//BgAA
AAAAQP//bwAAAAAAAPT//wYAAAAAAED//28AAAAAAAAAAABhyf7eiwQAAAAAEOj//////0wAAAAg/P///////48AABD9////////
/48AAPv//34CQfv//08A9f//PgAAAPn//wyw//9fAAAAAPz//xT//98AAAAAYP//j/T//wkAAAAA8f//bP//bwAAAAAA/v/f9///
BQAAAADQ//9+//9fAAAAAAD9///2//8GAAAAAOD//07//58AAAAAEP//v/H//w0AAAAA9v//CPz//wQAAADA//8/UP//3wIAAJD/
/88AwP//7ycQtP///wMA4v//////////BgAA0v////////8GAAAAgf7/////vwMAAAAAEJbs////BAAAAAAAAAAA9P/vAwAAAAAA
AAAA9f/vAgAAAAAAAAAA9v/fAQAAAAAAAAAA+P/PAfT/////3nsCAABA/////////wkAAPT/////////CgBA//////////8DAPT/
/wYQ1P//jwBA//9vAADz//8KAPT//wYAAP//rwBA//9vAADw//8JAPT//wYAMP//XwBA//9vAEH9/98AAPT////////vAwBA////
////ngEAAPT//////+8ZAABA/////////wwAAPT//wZB/P//CQBA//9vABD9//8DAPT//wYAUP//rwBA//9vAADA//8/APT//wYA
APT//wtA//9vAAAA/P//A/T//wYAAED//79A//9vAAAAsP//TwAQpu3vzXoUAADm///////vAHD/////////APL/////////APj/
/ycAQtj/APv/jwAAAAC0APz/XwAAAAAAAPz/rwAAAAAAAPn//30UAAAAAPP/////rRYAAID///////8ZAADn///////vAgAQt///
////DAAAADCm/v//LwAAAAAAkf//XwAAAAAAIP//b4gCAAAAQP//T/rPRxIg5v//H/r/////////C/r////////vAtb///////8s
AABiue3vzkkAAP3////////////U////////////T/3////////////U////////////TwAAAJD//x8AAAAAAAAA+f//AQAAAAAA
AJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA
+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD/
/x8AAAAAAAAA+f//AQAAAPT//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//
n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/z//8G
AAAQ//+f8v//BwAAIP//j/H//woAAFD//2/A//8vAACw//8vYP//3xQw+v//DBD9/////////wQA4////////38AACD8/////+8F
AAAAMMju75wFAAD6/+8BAAAAAMD//w31//8FAAAAAPL//wjg//8LAAAAAPf//wKQ//8fAAAAAP3/zwAw//9vAAAAMP//bwAA/f/P
AAAAgP//HwAA9///AgAA4P//CgAA8v//BwAA9P//BQAAsP//DQAA+f/vAAAAUP//PwAQ/v+fAAAAEP7/jwBQ//8/AAAAAPn/7wCw
//8NAAAAAPT//wTx//8HAAAAAND//wn2//8CAAAAAID//x78/78AAAAAACD//3///18AAAAAAAD8/////x4AAAAAAAD2/////wkA
AAAAAADx/////wQAAAAAAACg////3wAAAAAAAABQ////jwAAAAAAAAAA/v//LwAAAADw//8GAABA//9vAAAA9f//Afv/rwAAAPj/
/wkAAID//wyA//8NAACw///fAAAA/P+fAPT//wIAAP///x8AAPH//wUQ//9fAADz////BQBA//8fAMD//wkAcP/f/48AAPj/3wAA
+f/fAAD7//b/DACw//8JAFD//x8A4P8f/v8BAP7/bwAA8f//BTD/z7D/TwDz//8CAAD9/48A9v8I9/8HcP//DgAAkP//DKD/XzD/
vwD6/68AAAD2//8B/f8B8P8O4P//BwAAIP//T/L/DAD7/yP//z8AAADg//9X/58AgP9v9v//AAAAAPr/v/n/BQD0/6r//wsAAABw
///O/y8AEP/v/f+PAAAAAPP////fAADA/////wQAAAAA/v///woAAPn///8fAAAAALD///9vAABQ////zwAAAAAA+P///wMAAPH/
//8JAAAAAED///8OAAAA/f//XwAAAAAA8f//vwAAAJD///8CAADA//8uAAAAEP7/3wHy//8LAAAA+v//AwD3//8HAAD2//8IAAD7
/+8CAOL//wwAACD+/88AsP//PwAAAGD//39g//+PAAAAALD//0/+/88AAAAAAOL//////wMAAAAAAPb/////BwAAAAAAAPv///8M
AAAAAAAAEP7//y8AAAAAAAAA9f///wYAAAAAAADh////7wIAAAAAAKD/////zwAAAAAAUP//z///fwAAAAAg/v/fsf//LwAAAAD7
//8D4v//DAAAAPb//wgA9v//BwAA4v//DAAA+///AwCw//8/AAAg/v/PAGD//38AAABg//+PIP7/zwAAAACg//8/4f//PwAAAAD3
//8K9f//DAAAAPL//x4A+v//BwAAsP//bwAQ/v/vAgBg//+/AABQ//+/ABD+/+8CAACg//9vAPr//wYAAADi//8e9P//CwAAAAD2
///a//8uAAAAAAD7/////38AAAAAACD+////zwAAAAAAAGD/////AwAAAAAAALD///8HAAAAAAAAAPL//w0AAAAAAAAAAP7/rwAA
AAAAAAAA4P//CgAAAAAAAAAA/v+vAAAAAAAAAADg//8KAAAAAAAAAAD+/68AAAAAAAAAAOD//woAAAAAAAAAAP7/rwAAAAAAAAAA
4P//CgAAAAAAAAAA/v+vAAAAAPX//////////x/1//////////8f9f//////////H/X//////////w4AAAAAAFD///8EAAAAAADj
//9vAAAAAAAQ/f//CQAAAAAAsP//zwAAAAAAAPj//y4AAAAAAGD///8DAAAAAADz//9vAAAAAAAQ/f//CQAAAAAAwP//vwAAAAAA
APn//x0AAAAAAGD//+8DAAAAAAD0//9fAAAAAAAg/v//CAAAAAAAwf//vwAAAAAAAPj//////////2/6//////////9v+v//////
////b/r//////////2/2////r/b///+v9v///6/2/48AAPb/jwAA9v+PAAD2/48AAPb/jwAA9v+PAAD2/48AAPb/jwAA9v+PAAD2
/48AAPb/jwAA9v+PAAD2/48AAPb/jwAA9v+PAAD2/48AAPb/jwAA9v+PAAD2/48AAPb/jwAA9v+PAAD2////r/b///+v9v///6/9
bwAAAID/CgAAAPPvAQAAAP5fAAAAkP8JAAAA9e8AAAAQ/k8AAACg/wgAAAD23wAAABD/LwAAAMD/BwAAAPfPAAAAIP8fAAAA0P8G
AAAA+L8AAAAw/x8AAADg/wUAAAD5rwAAAFD/DgAAAOD/BAAAAPqPAAAAYP8NAAAA8f8DAAAA+38AAABw/wz/////L/////8v////
/y8AAP3/LwAA/f8vAAD9/y8AAP3/LwAA/f8vAAD9/y8AAP3/LwAA/f8vAAD9/y8AAP3/LwAA/f8vAAD9/y8AAP3/LwAA/f8vAAD9
/y8AAP3/LwAA/f8vAAD9/y8AAP3/LwAA/f8vAAD9/y//////L/////8v/////y8AAACg/88BAAAAAAAA+v//HAAAAAAAoP///78B
AAAAAPn/3///CwAAAJD//wfl/78AAAD4/z0AIPz/CgCA/58BAACA/68A9+8FAAAAANT/Cf////////////////////////////8P
4/8MAAD0/wgAAPb/BAAA998BAAD5nwAAAPpfQP///+++SQAA9P//////zwJA////////3wHESBIQYv7/fwAAAAAAcP//CwCE2/7/
///fEPv///////8N/P///////9/1//86AWD//53//wwAAPf/3/r/nwAAsP//nf//DABA///f9v//GFH+//8N/f/////5/98w/f//
72X//w0QyO6NAvb/3/f/zwAAAAAAAHD//wwAAAAAAAD3/88AAAAAAABw//8MAAAAAAAA9//PAAAAAAAAcP//DAAAAAAAAPf/zwAA
AAAAAHD//wxg698pAAD3/8/B////bwBw///M/////18A9///jwLU//8ecP//jwAA4v//B/f//wIAAPr/z3D//w0AAGD//w/3/88A
AAD1//9x//8MAABQ//8f9//fAAAA9v//cP//LwAAoP//DPf//wgAIP7/f3D///8YQP3/7wH3/8/8/////wVw//8c/P///wYA9//P
AMb+nQIAAAAAUMn+zmoBAOX/////zwD4//////8M9v//XQFyzuH//xwAABBY//9PAAAAAPn/7wAAAACg//8MAAAAAPr/zwAAAACQ
//8OAAAAAPX//wMAAAAQ/v/PAQAAgWD//98VIOYMgP//////zwBg/v////8MAACV7O+sFgAAAAAAAPX/7wAAAAAAAPX/7wAAAAAA
APX/7wAAAAAAAPX/7wAAAAAAAPX/7wAAAAAAAPX/7wAAAAAAAPX/7wAAtv6dAvX/7wDB////XvX/7xD9//////n/74D//48C1P//
7+H//wgAIP//7/X//wIAAPr/7/j/3wAAAPb/7/n/zwAAAPX/7/n/zwAAAPX/7/j/3wAAAPb/7/X//wIAAPr/7+H//wgAIP//75D/
/48B1P//7xD9//////n/7wDB////XvX/7wAAtv6dAvX/7wAAYdr+zigAAABg/v////8IAAD5//////+vAHD//48C1P//B+H//wkA
MP//HvX//wEAAPv/b/n/zwAAAPn/r/r/////////z/r/////////3/n/////////3/X/zwAAAAAAAOH//wQAAAAwKnD//44TEHT9
LwD5////////LwBg/v//////LwAAYdr+3rxYAgAAMNn+/18AAPf///9fADD/////XwCQ//89AAAAsP//CAAAAMD//wYAAADA//8G
AAD2//////8O9v//////Dvb//////w4AwP//BgAAAMD//wYAAADA//8GAAAAwP//BgAAAMD//wYAAADA//8GAAAAwP//BgAAAMD/
/wYAAADA//8GAAAAwP//BgAAAMD//wYAAADA//8GAAAAwP//BgAAAAC2/p0C9f/vAMH///9e9f/vEPz/////+f/vgP//jwLU///v
4f//CQAg///v9f//AgAA+v/v+P/vAAAA9//v+f/PAAAA9f/v+f/PAAAA9f/v+P/fAAAA9//v9f//AgAA+v/v4f//CAAg///vgP//
fwHU///vEPz/////+f/vAMH///9e9f/vAAC2/p0C9v/fAAAAAAAA+v+vAEgAAABA//9fAPpbAjH4//8MAPr//////98BAPr/////
/xkAAEHI7e+tFwAA9//PAAAAAAAA9//PAAAAAAAA9//PAAAAAAAA9//PAAAAAAAA9//PAAAAAAAA9//PAAAAAAAA9//PAAAAAAAA
9//PALX+rQQA9//Psf///38A9//P+/////8E9///jxL2//8K9///CQCA//8N9///AgBQ//8P9//vAABA//8P9//PAABA//8P9//P
AABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//P9//P
9//P9//P9//PAAAAAAAA9//P9//P9//P9//P9//P9//P9//P9//P9//P9//P9//P9//P9//P9//P9//P9//PAHD//wwA9//PAHD/
/wwA9//PAHD//wwAAAAAAAAAAAAA9//PAHD//wwA9//PAHD//wwA9//PAHD//wwA9//PAHD//wwA9//PAHD//wwA9//PAHD//wwA
9//PAHD//wwA9//PAHD//wsA+P+/AKD//wlh//9f////z/D//98C/+98AQD3/88AAAAAAABw//8MAAAAAAAA9//PAAAAAAAAcP//
DAAAAAAAAPf/zwAAAAAAAHD//wwAAAAAAAD3/88AAAAAAABw//8MAAD6//8F9//PAAD7/+8EcP//DBD7/+8DAPf/zxD7/98DAHD/
/xz8/98CAAD3/8/8/88BAABw/////78BAAAA9/////8CAAAAcP/////fAgAAAPf/3/7/3wIAAHD//zz+/98CAAD3/88w/v/fAgBw
//8MQP7/3wIA9//PAED//98CcP//DABQ///fAvf/zwAAUP//3wL3/8/3/8/3/8/3/8/3/8/3/8/3/8/3/8/3/8/3/8/3/8/3/8/3
/8/3/8/3/8/3/8/3/8/3/8/3/8/3/8/3/8/3/8/3/8/4/88Qx+5LAADG/p0DgP//LPz//58g/P///wX4/8/8////f/z/////gv//
/xay////PFH+/4/4//8HAPP//x4AkP//jP//HwAQ//+vAAD3/9/4/98AAPD//wYAYP//jf//DAAA/v9fAAD2/9/4/88AAOD//wUA
YP//jf//DAAA/v9fAAD2/9/4/88AAOD//wUAYP//jf//DAAA/v9fAAD2/9/4/88AAOD//wUAYP//jf//DAAA/v9fAAD2/9/4/88A
AOD//wUAYP//jf//DAAA/v9fAAD2/9/3/88Atf6tBAD3/8+x////fwD3/8/7/////wT3//+PEvb//wr3//8JAID//w33//8CAFD/
/w/3/+8AAED//w/3/88AAED//w/3/88AAED//w/3/88AAED//w/3/88AAED//w/3/88AAED//w/3/88AAED//w/3/88AAED//w/3
/88AAED//w/3/88AAED//w8AAGHa/s5JAAAAAOf/////3wMAAPr///////8EAPf//ygw/P/vAuH//wgAEP3/n1D//y8AAHD//w75
/98AAAD0//+j//8MAAAw//9P+v/PAAAA8///lP//DQAAQP//P/X//wEAAPf/7xD+/48AANH//wlw//+PAsP//y4AoP///////08A
AHD+/////z0AAAAQpu3vnAQAAPf/zwC2/p0CAHD//xz8////BgD3/8/8/////wVw////KED9/+8B9///CAAg/v9/cP//LwAAoP//
DPf/3wAAAPb//3D//wwAAFD//x/3/88AAAD1//9x//8NAABg//8P9///AgAA+v/PcP//jwAA4v//B/f//48B1P//HnD//8z/////
XwD3/8/B////bwBw//8MYOzfKQAA9//PAAAAAAAAcP//DAAAAAAAAPf/zwAAAAAAAHD//wwAAAAAAAD3/88AAAAAAABw//8MAAAA
AAAAAAC2/p0C9f/vAMH///9e9f/vEP3/////+f/vkP//jwLU///v4f//CAAg///v9f//AgAA+v/v+P/fAAAA9v/v+f/PAAAA9f/v
+f/PAAAA9f/v+P/fAAAA9v/v9f//AgAA+v/v4f//CAAg///vgP//jwHU///vEP3/////+f/vAMH///9e9f/vAAC2/p0C9f/vAAAA
AAAA9f/vAAAAAAAA9f/vAAAAAAAA9f/vAAAAAAAA9f/vAAAAAAAA9f/vAAAAAAAA9f/v9//PAMf+ev//LPz/r/f/z/z//3r/////
/6/3//+/FFF4//+/AAAA9///AwAAcP//DgAAAPf/zwAAAHD//wwAAAD3/88AAABw//8MAAAA9//PAAAAcP//DAAAAPf/zwAAAHD/
/wwAAAAAYNr+3pw3ADD9//////8F0P///////wX0/88TIKX/Bfb/TwAAAIEF9v+PAAAAAADy//++eRUAAID//////2wAALX/////
/wkAAEGG6v//LwAAAAAA/P9vkwIAAAD5/2/zrzYBYv//T/P///////8M8///////zwIgldv+75wEAADw//8EAAAA8P//BAAAAPD/
/wQAAADw//8EAAAA8P//BAAA+f//////r/n//////6/5//////+vAPD//wQAAADw//8EAAAA8P//BAAAAPD//wQAAADw//8EAAAA
8P//BAAAAPD//wQAAADw//8EAAAA4P//BQAAAND//ysAAACA/////z8AEP3///8/AACB7P//P/r/nwAAYP//rf//CQAA9v/f+v+f
AABg//+t//8JAAD2/9/6/58AAGD//63//wkAAPb/3/r/nwAAYP//rf//CQAA9v/f+v+fAABw//+t//8JAAD4/9/5/68AAMD//43/
/w0AQP//3/X//xpR/v//Df3////v+f/fMP7//99j//8NEMjujAH2/9/1/98AAABQ//8N4P//BAAAoP//CID//wkAAPH//wIg//8e
AAD3/68AAPv/XwAA/P9PAAD1/78AMP//DQAA4P//AoD//wcAAID//wfQ//8BAAAg//8N9P+vAAAAAPv/P/r/TwAAAAD1/5/+/w0A
AAAA0P////8HAAAAAID/////AQAAAAAg////rwAAAAAAAPv//08AAAAAAAD0//8NAAAA/P9PAAD3/z8AAPj/j/j/jwAA+/9/AAD8
/0/0/88AAP7/rwAQ//8O4P//ATD//+8AUP//C7D//wRw////A4D//wdw//8IsP/8/wfA//8DMP//DOD/x/8K8f/vAAD+/x/z/4P/
DvX/rwAA+v9P9+9A/z/5/28AAPb/j/u/EP9//P8vAADy/8/+fwD7z///DQAA0P///z8A+P///wkAAJD///8OAPT///8EAABQ////
CwDw////AQAAEP///wcAsP//vwAAAAD7//8DAID//38AAMH//woAAPT//wTi//8FAOH//wcA9f/vArD//wsAAPn/v3D//x0AAAD8
/5///z8AAAAg/v///28AAAAAUP///68AAAAAAJD//98BAAAAAAD8//9PAAAAAAD5////HQAAAAD2/////wsAAADj///V//8HAADR
//8I8///BACg//8MAPf/7wFg//8uAAD7/78w//9fAAAg/v+P9v/PAAAAYP//HP7/PwAAAPv/b4D//wkAAPL//wHy/+8BAHD//woA
+v9/AAD8/08AMP//DQDy/98AAMD//wRw//8HAAD1/68A/P8fAAAA/f8f8/+vAAAAcP//h///BAAAAOH/3/3/DQAAAAD5////fwAA
AAAg/////wIAAAAAsP///wsAAAAAAPT//18AAAAAAAD8/98AAAAAAABw//8IAAAAAAAA+v8vAAAAAAAQ9/+vAAAAAAD////vAgAA
AADw///vBAAAAAAA/++MAgAAAAD0////////D/T///////8P9P///////w8AAAAA9///DwAAAGD///8FAAAA9f//bwAAAFD///8H
AAAA9P//jwAAADD+//8JAAAA4///rwAAACD+//8LAAAA0v//vwEAAAD5//8cAAAAAPr///////8P+v///////w/6////////DwAA
ADDZ/v8JAABg////nwAAIP////8JAAD3/+8VAAAAkP//CAAAAAD6/18AAAAAoP//BAAAAAD6/08AAAAAoP//BAAAAAD7/08AAAAA
0P//AwAAADD//y8AAABB/f/PAABA////3wIAAPT//98CAABA/////wUAAABB/P/vAAAAACD//y8AAAAAwP//BAAAAAD7/08AAAAA
oP//BAAAAAD6/08AAAAAoP//BQAAAAD6/48AAAAAcP//XgEAAADy////nwAAAPf///8JAAAAk+3/n/P/Mv8v8/8y/y/z/zL/L/P/
Mv8v8/8y/y/z/zL/L/P/Mv8v8/8y/y/z/zL/L/P/Mv8v8/8y/y/z/zL/L/P/Mv8v8/8y/y/z/zL/L/T/31sAAABA////vwAAAPT/
//9/AAAAEMP//wwAAAAA8///AAAAAAD//x8AAAAA4P//AQAAAAD+/x8AAAAA4P//AQAAAAD+/x8AAAAA0P//AwAAAAD7/48AAAAA
cP//fwIAAACg////nwAAAJH///8JAADB////nwAAgP//bgIAAAD8/38AAAAA4P//AgAAAAD+/x8AAAAA4P//AQAAAAD+/x8AAAAA
8P//AQAAACD//w8AAAAw+//fAABA/////wgAAPT///8cAABA//++BgAAAAAAAAAAAAAAAAFA2e97AgAAANSy/////2sTUfvO////
///////v/FsCYvv////PwwUAAABh299aAAEAAAAAAAAAAAD8/3/8/3/8/3/8/3/8/38AAAAAAADy/wzz/w71/w/3/y/5/0/7/2/8
/3/8/3/8/3/8/3/8/3/8/3/8/3/8/3/8/38AAAAA+woAAAAAALCvAAAAAAAA+woAAAAAALCvAAAAAFDa/997AgDV//////8A9///
////D/T//++vYf3A//9P+woAKf//j7CvAAD1//8D+woAYP//H7CvAAD2//8B+woAUP//P7CvAADx//8I+woAAPv//7SvAIAw////
/hrFD1D///////8AMPz/////DwAAg/z/zicAAAAA+woAAAAAALCvAAAAAAAA+woAAAAAALCvAAAAAAAA+woAAAAAACC4/s4YAAAA
APf/////BwAAYP//////PwAA4f//////PwAA9v//TBG0PwAA+f/vAQAANgAA+/+vAAAAAAAA/P+PAAAAAAAA/f+PAAAAAAAA/f+P
AAAAAKD///////8PAKD///////8PAKD///////8PAAAA/f+PAAAAAAAA/f+PAAAAAAAA/f+PAAAAAAAA/f+PAAAAAAAA/f+PAAAA
APP/////////b/P/////////b/P/////////b/P/////////bwAAAAAAAAAAALQBAAAAALEG5N8CAAAAwf93/9+V/a3F/49g////
////jwBg//////+PAADh/zwg+/8DAGD/HgAA/Y8AAPmPAABg/wsAoP8GAAD0zwAA+Y8AAGD/CwBg/x4AAP2PAADx/0wh+/8CAGD/
/////48AYP///////49w/9+l/a3F/5/13wIAAACx/wW0AQAAAACgBPX//wgAAAD6//8D+///AgAA9P//CSD//78AAND//x4AcP//
bwCA//9fAADQ//8eIP//vwAAAPT//wn7//8CAAAA+v//+P//CAAAABD+/////x0AAPD//////////98A////////////DfD/////
/////98AAAAA+///CQAAAAAAAFD//08AAAAA////////////DfD//////////98A////////////DQAAAFD//08AAAAAAAAA9f//
BAAAAAAAAFD//08AAAAAAAAA9f//BAAAAAAAAFD//08AAAAAAAAA9f//BAAAAPP/Mv8v8/8y/y/z/zL/L/P/Mv8v8/8y/y/z/wIA
AAAAAAAAAAAw/y/z/zL/L/P/Mv8v8/8y/y/z/zL/L/P/Mv8vABDH/t57BABA/v////8AIP7/////DwD3/58CQsgAgP//BAAAAAD2
/98DAAAAEP3//0sAAAAg/f//zwQAAPj/////GgD6/8////8M9f8+IPj//6f/fwAA0//P/P8HAAD1/63/7wMAQP+/9v//KAD7/wf8
//+//f8dEPv/////LAAA5v///x0AAABg/P//HQAAAADU//8IAAAAAPL/vwDESAKB//8JUP//////PwD1/////14AEIXb/r4XAADy
/wX1/yL/X1D/L/L/BfX/Iv9fUP8vAAAAYdrurRYAAAAAAHD+////7wcAAAAQ+88mEWL8vwEAAMHvBQAAAFD+HAAA+z4AAAAAAOOv
AGD/BBC3/t46QP8G0I8A0////28A+A30HyD+7xUxWADxT/kLoP9PAAAAALCP+wfx/wwAAAAAgL/8BvL/CQAAAABgz/wG8v8JAAAA
AGDP+wfx/wwAAAAAcL/5C6D/TwAAAACwj/QfIP7vFTFYAPFP0I8A0////28A+A1g/wMQt/7eOjD/BgD7PgAAAAAA478AAMHvBQAA
AFD+HAAAEPvPJhFi/L8BAAAAcP7////vBwAAAAAAYdrurRYAAABAuO3vjAIA+/////8GkFkTMfz/AgAAAFD/fwCl7f///wn6////
/6/1/zoB9P+a/x8AcP+v+v8AAP3/ev+PIfr/r9H////r/wqB/c4G/q8AAAAAAAAAAAAAAAAA9v//////Z///////f/b//////wcA
AABjAAAwBgAA9ggAYI8AEPqPAJH/CCD8/wfC/39Q/v8H5f9/cP/vBPf/TgD6zwKg/ywAoP8sAPrPAgD3/05w/+8EAOX/f1D+/wcA
0v9/IPz/BwCh/wgQ+o8AAHCPAAD2CAAAMAYAAGP8///////////O///////////v/P//////////DgAAAAAAAAD37wAAAAAAAABw
/w4AAAAAAAAA9+8AAAAAAAAAcP8OAAAAAAAAAPfvAAAAAAAAAHD/DgAAAGHa7q0WAAAAAABw/v///+8HAAAAEPvPJhFi/L8BAADB
7wUAAABQ/hwAAPs+AAAAAADjrwBg/wT3/++dAkD/BtCPAPf///8+APgN9B8A968w/a8A8U/5CwD3rwD5zwCwj/sHAPevMP2fAIC/
/AYA9////y0AYM/8BgD3//9/AQBgz/sHAPev9t8BAHC/+QsA96+g/wsAsI/0HwD3ryD/TwDxT9CPAPevAPjPAPgNYP8D968A4f81
/wYA+z4AAAAAAOO/AADB7wUAAABQ/hwAABD7zyYRYvy/AQAAAHD+////7wcAAAAAAGHa7q0WAAAA8v////8i/////y/y/////wIA
gf2NAQDS///fAbDvFeWvIP8GAPYv9R8AEP9V/wEA8V/zXwBQ/wL7TlH+CyD9//8dABDZ3xgAAAAAMP9fAAAAAAAAAPP/BQAAAAAA
ADD/XwAAAAAAAADz/wUAAAAAAAAw/18AAADA///////////v/P//////////zv//////////7wAAADD/XwAAAAAAAADz/wUAAAAA
AAAw/18AAAAAAAAA8/8FAAAAAAAAMP9fAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD8///////////O///////////v
/P//////////DnHa/r0EUP////8IpDYh+/8CAAAw/18AAAD1/wQAANH/HgAAwf9fAADC/28AANL/bwAA4/9/AADj/48AAGD/////
f/b/////B6Ls/r4FQP////8JpCUw/P8BAABw/y8AADH9zwBQ//+vAQD1//88AAAQxP8eAAAA8v8GAAAg/3+JE0H8/6T/////CaXt
/60FAAAA/O8DAPj/BAD0/wYA0f8HAJD/CQBQ/woAAPf/3wAAQP//HwD3/98AAED//x8A9//fAABA//8fAPf/3wAAQP//HwD3/98A
AED//x8A9//fAABA//8fAPf/3wAAQP//HwD3/98AAED//x8A9//fAABA//8fAPf/3wAAQP//HwD3/+8AAFD//x8A9///AwCQ//8f
APf//00h9///bxL3//////////8v9///////2f//L/f/39fvXCDq3xr3/98AAAAAAAAA9//fAAAAAAAAAPf/3wAAAAAAAAD3/98A
AAAAAAAA9//fAAAAAAAAAPf/3wAAAAAAAAAAAKX9////fwDC//////9/EP3//+8A9X+Q////7wD1f+D////vAPV/8f///+8A9X/x
////7wD1f+D////vAPV/kP///+8A9X8Q/f//7wD1fwDC///vAPV/AACl/e8A9X8AAADQ7wD1fwAAANDvAPV/AAAA0O8A9X8AAADQ
7wD1fwAAANDvAPV/AAAA0O8A9X8AAADQ7wD1fwAAANDvAPV/AAAA0O8A9X8AAADQ7wD1fwAAANDvAPV/AAAA0O8A9X8AAADQ7wD1
f/7/X/7/X/7/X/7/X/7/X/7/XwAQ/QQAAPUdAADwXwAA9m/y//8v8v/OBDDI/38AMP///wcA03r+fwAAAOD/BwAAAP5/AAAA4P8H
AAAA/n8AAADg/wcAAAD+fwAAAOD/BwAAAP5/AAD+////f+D/////BwAQyP7OFwAAUP7///9OAED/7wTk/z4A/P8GAPf/C/L/HwAg
//9B/+8AAPH/L/T/DgAA//8i//8BAPL/H8D/bwBw/78A9P9NQP7vAwDl////7wQAAILs73wBAAAAAAAAAAAAAAAAAAAAAID/////
/38A+P//////B4D//////38AcgAAIAcAAADzGgAgvwEAAPPfAyD/PQAA8v9eIP//BgAw/f8J0/+fAACx/88Q+/8MAAD4/wCA/x8A
APj/AHD/HwCx/88Q+/8MMP3/CdP/nwHy/24g//8GAPPfAyD/PQAA8xoAIL8BAAByAAAgBwAAAFHp/y8AAAAAADD/LwAA+P//LwAA
AAAAwP8IAADIif8vAAAAAAD23wAAAABA/y8AAAAAEP5PAAAAAED/LwAAAACg/woAAAAAQP8vAAAAAPTvAQAAAABA/y8AAAAA/W8A
AAAAAED/LwAAAID/CwAAAAAAQP8vAAAA8v8DAAAAAABA/y8AAAD7jwAAAAAAAED/LwAAYP8dAFD/vwD0/////wLh/wQA4v+/APT/
////AvmvAAD8/78AAAAAAABA/x4AgM/7vwAAAAAAAND/BgD0Lvq/AAAAAAAA988AEP4F+r8AAAAAACD/PwCwnwD6vwAAAAAAsP8I
APV/ZvzPRgAAAAD13wEA9v////+/AAAAEP5fAADV3d3+750AAACQ/woAAAAAAPq/AAAAAPPvAgAAAAAA+r8AAAAAAAAAAAAAAAAy
IwBR6f8vAAAAAAAw/y8AAID///8CAAAAAAD8jwAAAMiJ/y8AAAAAAPbfAAAAAAD0/wIAAAAA4f8EAAAAAED/LwAAAACg/woAAAAA
APT/AgAAAED/HgAAAAAAQP8vAAAAAP1vAAAAAAAA9P8CAAAA+L8AAAAAAABA/y8AAADy/wMAAAAAAAD0/wIAALD/CAAAAAAAAED/
LwAAYP8dYcr+vQVA/////y8Q/k8g/////wr0/////wL5rwCyNhH5/wUAAAAAAPTvAQAAABD/jwAAAAAA0P8GAAAAAPP/BwAAAABw
/wwAAAAAsP8vAAAAACD/PwAAAACg/38AAAAAAPuPAAAAALH/jwAAAAAA9d8BAAAAwf+fAAAAAADh/wUAAADS/58AAAAAAJD/CgAA
AOL/rwAAAAAAMP8uAAAAQP////+fAAAAAAAAAAAA9P////8Jkez+zhcAAAAAMP8vAADx////zwAAAADA/wgAALElIPr/BAAAAPbf
AAAAAAAA8/8FAAAQ/k8AAAAAADD77wEAAKD/CgAAAADy//87AAAA9O8BAAAAAPL//10AAAD9bwAAAAAAADH6/wQAgP8LAAAAAAAA
AOD/CQDy/wMAAAAAAAAA4P8KAPuPAAAAAACXFDD6/wdg/x0AUP+/APf////PAeH/BADi/78Ak+z/vgYA+a8AAPz/vwAAAAAAAED/
HgCAz/u/AAAAAAAA0P8GAPQu+r8AAAAAAAD3zwAQ/gX6vwAAAAAAIP8/ALCfAPq/AAAAAACw/wgA9X9m/M9GAAAAAPXfAQD2////
/78AAAAQ/l8AANXd3f7vnQAAAJD/CgAAAAAA+r8AAAAA8+8CAAAAAAD6vwAAAAAAAAAAAAAAADIjAAAA0P//BgAAAND//wYAAADQ
//8GAAAA0P//BgAAAND//wYAAAAAAAAAAAAAAAAAAAAAAND//wYAAADg//8FAAAA9///AgAAUP//vwAAAPX//x0AAFD//+8DAADi
//8+AAAA+f//BAAAAP3/nwAAAAD+/28AAAAA/f+PAAAAZ/n//xYx13/i//////9/MP3/////fwBh2v7//38AAADj/wwAAAAAAAAA
AAAw/p8AAAAAAAAAAAAA0v8FAAAAAAAAAAAAIP0uAAAAAAAAAAAAAAAAAAAAAAAAAAAA/v//LwAAAAAAAABQ////jwAAAAAAAACg
////3wAAAAAAAADx/////wQAAAAAAAD2/////wkAAAAAAAD8/8///x4AAAAAACD//z/+/18AAAAAAID//wz5/78AAAAAAND//wf0
//8CAAAAAPT//wLg//8HAAAAAPn/zwCQ//8NAAAAEP7/fwBA//8/AAAAUP//LwAA/f+fAAAAsP//DAAA+P/vAAAA8v//////////
BQAA9///////////CgAA/P//////////HwAw////////////bwCQ//8fAAAAAPz/zwDg//8KAAAAAPf//wL1//8FAAAAAPL//wj6
/+8BAAAAAMD//w0AAAAAAFD/nwAAAAAAAAAAAOL/CQAAAAAAAAAAAPyPAAAAAAAAAAAAgP8HAAAAAAAAAAAAAAAAAAAAAAAAAAAA
/v//LwAAAAAAAABQ////jwAAAAAAAACg////3wAAAAAAAADx/////wQAAAAAAAD2/////wkAAAAAAAD8/8///x4AAAAAACD//z/+
/18AAAAAAID//wz5/78AAAAAAND//wf0//8CAAAAAPT//wLg//8HAAAAAPn/zwCQ//8NAAAAEP7/fwBA//8/AAAAUP//LwAA/f+f
AAAAsP//DAAA+P/vAAAA8v//////////BQAA9///////////CgAA/P//////////HwAw////////////bwCQ//8fAAAAAPz/zwDg
//8KAAAAAPf//wL1//8FAAAAAPL//wj6/+8BAAAAAMD//w0AAAAA4v//BAAAAAAAAAAQ/M//LgAAAAAAAACg/wfl3wEAAAAAAAD4
XgAw/QsAAAAAAAAAAAAAAAAAAAAAAAAA/v//LwAAAAAAAABQ////jwAAAAAAAACg////3wAAAAAAAADx/////wQAAAAAAAD2////
/wkAAAAAAAD8/8///x4AAAAAACD//z/+/18AAAAAAID//wz5/78AAAAAAND//wf0//8CAAAAAPT//wLg//8HAAAAAPn/zwCQ//8N
AAAAEP7/fwBA//8/AAAAUP//LwAA/f+fAAAAsP//DAAA+P/vAAAA8v//////////BQAA9///////////CgAA/P//////////HwAw
////////////bwCQ//8fAAAAAPz/zwDg//8KAAAAAPf//wL1//8FAAAAAPL//wj6/+8BAAAAAMD//w0AAAAw7DsA9goAAAAAAADh
//8X+ggAAAAAAAD1HeX//wMAAAAAAAD3CSDqXQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/v//LwAAAAAAAABQ////
jwAAAAAAAACg////3wAAAAAAAADx/////wQAAAAAAAD2/////wkAAAAAAAD8/8///x4AAAAAACD//z/+/18AAAAAAID//wz5/78A
AAAAAND//wf0//8CAAAAAPT//wLg//8HAAAAAPn/zwCQ//8NAAAAEP7/fwBA//8/AAAAUP//LwAA/f+fAAAAsP//DAAA+P/vAAAA
8v//////////BQAA9///////////CgAA/P//////////HwAw////////////bwCQ//8fAAAAAPz/zwDg//8KAAAAAPf//wL1//8F
AAAAAPL//wj6/+8BAAAAAMD//w0AAADx/wX1/wIAAAAAAADx/wX1/wIAAAAAAADx/wX1/wIAAAAAAADx/wX1/wIAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAA/v//LwAAAAAAAABQ////jwAAAAAAAACg////3wAAAAAAAADx/////wQAAAAAAAD2/////wkA
AAAAAAD8/8///x4AAAAAACD//z/+/18AAAAAAID//wz5/78AAAAAAND//wf0//8CAAAAAPT//wLg//8HAAAAAPn/zwCQ//8NAAAA
EP7/fwBA//8/AAAAUP//LwAA/f+fAAAAsP//DAAA+P/vAAAA8v//////////BQAA9///////////CgAA/P//////////HwAw////
////////bwCQ//8fAAAAAPz/zwDg//8KAAAAAPf//wL1//8FAAAAAPL//wj6/+8BAAAAAMD//w0AAAAAYP2NAAAAAAAAAAAA+f//
CwAAAAAAAAAw/xfkbwAAAAAAAABwzwCQvwAAAAAAAACAzwCQvwAAAAAAAABA/xfkjwAAAAAAAAAQ////TwAAAAAAAABQ////jwAA
AAAAAACw////7wAAAAAAAADx/////wQAAAAAAAD3/////woAAAAAAAD8/7///x8AAAAAADD//y/+/28AAAAAAID//wz5/78AAAAA
AND//wf0//8CAAAAAPT//wLg//8HAAAAAPr/zwCQ//8NAAAAEP7/fwBA//8/AAAAYP//LwAA/f+fAAAAsP//DAAA+P/vAAAA8v//
////////BQAA9///////////CgAA/f//////////HwAw////////////bwCQ//8fAAAAAPz/zwDg//8KAAAAAPf//wL1//8FAAAA
APL//wj6/+8BAAAAAMD//w0AAAAA8f////////////8AAAAAcP////////////8PAAAAAP3/////////////AAAAAPX//5j/////
////DwAAALD//wrz//8HAAAAAAAAACD//08w//9/AAAAAAAAAAD4/98A8///BwAAAAAAAADh//8HMP//fwAAAAAAAABg//8fAPP/
/wcAAAAAAAAA/P+vADD/////////BwAA8///BADz////////fwAAoP//DQAw/////////wcAEP//fwAA8////////38AAPf/////
////fwAAAAAAAND//////////wcAAAAAAED//////////38AAAAAAAD7//////////8HAAAAAADy//8GAAAw//9/AAAAAACA//8O
AAAA8/////////8F/v+PAAAAMP////////9f9v//AgAAAPP/////////xf//CgAAADD/////////XwAAAEC47e+sJgAAAFD8////
//8aABD6////////HwCw/////////x8A+f//zyUQYvofMP///wcAAAAgGqD//58AAAAAAADg//8eAAAAAAAA9P//CgAAAAAAAPb/
/wcAAAAAAAD3//8FAAAAAAAA9///BQAAAAAAAPb//wcAAAAAAAD0//8KAAAAAAAA4P//HgAAAAAAAKD//58AAAAAAAAw////BwAA
ACAaAPn//88lEFL6HwCw/////////x8AEPr///////8fAABQ/P//////GgAAAEC47e+tJgAAAAAAAHCvAAAAAAAAAAAA/QUAAAAA
AAAAAPgMAAAAAAAAACD8DQAAAAAAAPv//wkAAAAAAAD7/40BAAAAQP6/AAAAAAAAQP5/AAAAAAAAMP4/AAAAAAAAMP4dAAAAAAAA
AAAAAABA/////////w/0/////////0D/////////D/T/////////QP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED/
/28AAAAAAPT///////9vQP////////8G9P///////29A/////////wb0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//bwAAAAAA
9P//BgAAAABA/////////0/0/////////0T/////////T/T/////////BAAAAAD3/wgAAAAAAPP/BwAAAAAA0f8GAAAAAACg/wYA
AAAAAAAAAAAAAED/////////D/T/////////QP////////8P9P////////9A//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYA
AAAAQP//bwAAAAAA9P///////29A/////////wb0////////b0D/////////BvT//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9v
AAAAAAD0//8GAAAAAED/////////T/T/////////RP////////9P9P////////8EAACA//8MAAAAAFD/3v8JAAAAMP4tof8GAAAQ
/RsAgP8EAAAAAAAAAAAAQP////////8P9P////////9A/////////w/0/////////0D//28AAAAAAPT//wYAAAAAQP//bwAAAAAA
9P//BgAAAABA//9vAAAAAAD0////////b0D/////////BvT///////9vQP////////8G9P//BgAAAABA//9vAAAAAAD0//8GAAAA
AED//28AAAAAAPT//wYAAAAAQP////////9P9P////////9E/////////0/0/////////wQAcP8PoP8LAAAA9/8A+r8AAABw/w+g
/wsAAAD3/wD6vwAAAAAAAAAAAAAAAAAAAAAAAAD0/////////0D/////////D/T/////////QP////////8P9P//BgAAAABA//9v
AAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP////////8G9P///////29A/////////wb0////////b0D//28AAAAAAPT/
/wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0/////////0T/////////T/T/////////RP////////9P4/8MAADj/wgA
AOL/BAAA0u8BAAAAAABA//9vAPT//wZA//9vAPT//wZA//9vAPT//wZA//9vAPT//wZA//9vAPT//wZA//9vAPT//wZA//9vAPT/
/wZA//9vAPT//wZA//9vAPT//wZA//9vAPT//wZA//9vAPT//wYAYP+fACD+jwAA/I8AAPl/AAAAAAAAQP//bwD0//8GQP//bwD0
//8GQP//bwD0//8GQP//bwD0//8GQP//bwD0//8GQP//bwD0//8GQP//bwD0//8GQP//bwD0//8GQP//bwD0//8GQP//bwD0//8G
QP//bwD0//8GAADi//8EANH//O8CsP8H9c+B7wUA468AAAAAAABA//9vAAD0//8GAED//28AAPT//wYAQP//bwAA9P//BgBA//9v
AAD0//8GAED//28AAPT//wYAQP//bwAA9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//bwAA9P//BgBA//9vAAD0//8GAED/
/28AAPT//wYA8f8G9P8T/29A/z/x/wb0/xP/b0D/PwAAAAAAAAAAAAAAAPT//wYAQP//bwAA9P//BgBA//9vAAD0//8GAED//28A
APT//wYAQP//bwAA9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//bwAA9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//
bwAA9P//BgBA//9vAADw////7816AwAAAADw////////3wYAAADw/////////78BAADw//////////8cAADw//8KEGL8//+vAADw
//8KAABw////BADw//8KAAAA9///DADw//8KAAAA0P//HwDw//8KAAAAgP//X/j//////wIAUP//f/j//////wIAQP//n/j/////
/wIAQP//j/j//////wIAUP//fwDw//8KAAAAgP//XwDw//8KAAAA0P//HwDw//8KAAAA9///DADw//8KAABw////BADw//8KEGL8
//+vAADw//////////8cAADw/////////68BAADw////////zwUAAADw////7816AwAAAAAAAOltAOAfAAAAAAD4/79S7wAAAAAA
0F+y//8JAAAAAAD/AHDtGgAAAAAAAAAAAAAAAABA////BQAAAP//X/T//88AAADw//9F////XwAAAP//X/T///8NAADw//9F////
/wYAAP//X/T////vAQDw//9F/////38AAP//X/T///r/HgDw//9F//8//v8IAP//X/T//4H/7wHw//9F//8f4f+fAP//X/T//wH3
/y/w//9F//8fEP7/Cf//X/T//wFg///z//9F//8fAND/r///X/T//wEA9v////9F//8fAAD8////X/T//wEAUP////9F//8fAADA
////X/T//wEAAPT///9F//8fAAAA+///X/T//wEAADD///8FAAAA0v8eAAAAAAAAAAAA0v8LAAAAAAAAAAAAwf8HAAAAAAAAAAAA
wf8DAAAAAAAAAAAAAAAAAAAAAAAAEJbs7704AAAAAACB/v/////PBAAAAML/////////BwAA0f//////////BwCw///vJxC0////
BFD//+8DAACQ///PAPv//wUAAADA//9P8f//DQAAAAD2//9I//+fAAAAABD//8/2//8GAAAAAOD//33//18AAAAAAP3/7/f//wUA
AAAA0P//bv//bwAAAAAA/v/f9P//CQAAAADx//8c///fAAAAAGD//4+w//9fAAAAAPz//wT1//8uAAAA+f//DAD8//9+AkH7//9P
ABD9/////////38AACD8////////fwAAABDo//////9MAAAAAABh2v7eiwMAAAAAAAAAAED/vwEAAAAAAAAAEP2vAAAAAAAAAAAA
+q8AAAAAAAAAAAD2nwAAAAAAAAAAAAAAAAAAAAAAAAAQluzvvTgAAAAAAIH+/////88EAAAAwv////////8HAADR//////////8H
ALD//+8nELT///8EUP//7wMAAJD//88A+///BQAAAMD//0/x//8NAAAAAPb//0j//58AAAAAEP//z/b//wYAAAAA4P//ff//XwAA
AAAA/f/v9///BQAAAADQ//9u//9vAAAAAAD+/9/0//8JAAAAAPH//xz//98AAAAAYP//j7D//18AAAAA/P//BPX//y4AAAD5//8M
APz//34CQfv//08AEP3/////////fwAAIPz///////9/AAAAEOj//////0wAAAAAAGHa/t6LAwAAAAAAAAD0/+8CAAAAAAAAAOL/
/M8BAAAAAAAA0e8F968AAAAAAACw3wMA5X8AAAAAAAAAAAAAAAAAAAAAABCW7O+9OAAAAAAAgf7/////zwQAAADC/////////wcA
ANH//////////wcAsP//7ycQtP///wRQ///vAwAAkP//zwD7//8FAAAAwP//T/H//w0AAAAA9v//SP//nwAAAAAQ///P9v//BgAA
AADg//99//9fAAAAAAD9/+/3//8FAAAAAND//27//28AAAAAAP7/3/T//wkAAAAA8f//HP//3wAAAABg//+PsP//XwAAAAD8//8E
9f//LgAAAPn//wwA/P//fgJB+///TwAQ/f////////9/AAAg/P///////38AAAAQ6P//////TAAAAAAAYdr+3osDAAAAAAAAIOtM
APMMAAAAAAAA/P+fga8AAAAAAADyLtT//wUAAAAAAEC/AJHeBwAAAAAAAAAAAAAAAAAAAAAAEJbs7704AAAAAACB/v/////PBAAA
AML/////////BwAA0f//////////BwCw///vJxC0////BFD//+8DAACQ///PAPv//wUAAADA//9P8f//DQAAAAD2//9I//+fAAAA
ABD//8/2//8GAAAAAOD//33//18AAAAAAP3/7/f//wUAAAAA0P//bv//bwAAAAAA/v/f9P//CQAAAADx//8c///fAAAAAGD//4+w
//9fAAAAAPz//wT1//8uAAAA+f//DAD8//9+AkH7//9PABD9/////////38AACD8////////fwAAABDo//////9MAAAAAABh2v7e
iwMAAAAAAADQ/wnx/wUAAAAAAAD9nxD/XwAAAAAAAND/CfH/BQAAAAAAAP2fEP9fAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AABhyf7eiwMAAAAAEOj//////0wAAAAg/P///////38AABD9/////////38AAPv//34CQfv//08A9f//PgAAAPn//wyw//9fAAAA
APz//xT//98AAAAAYP//j/T//wkAAAAA8f//bP//bwAAAAAA/v/f9///BQAAAADQ//9+//9fAAAAAAD9/+/2//8GAAAAAOD//03/
/58AAAAAEP//z/H//w0AAAAA9v//CPv//wUAAADA//9PUP//7wIAAJD//88AwP//7ycQtP///wQA0f//////////BwAAwv//////
//8HAAAAgf7/////zwQAAAAAEKbt7704AAAAAKQAAAAAAIAGAPSvAAAAAID/BuH/rwAAAID//wL1/58AAID//wYA9f+fAHD//wcA
APX/n3D//wcAAAD1/7///wcAAAAA9v///wgAAAAAAPb//wgAAAAAAGD//48AAAAAAFD///9/AAAAAFD///z/fwAAAFD//wn3/38A
AFD//wkA+P9/AFD//woAAPj/bxD+/woAAAD4/y9A/woAAAAA+G8AQAoAAAAAAGgAAAAAAAAAAAAAAABDAAAAAGHJ/t6LAwDjTgAA
EOj//////zzk7wMAIPz/////////7wMAEP3/////////7wMAAPv//34CQfv//z8AAPX//z4AAAD6//8MALD//18AAAD1////AxD/
/98AAAD27///jwD0//8JAAD2z/P//wtg//9vAAD3zwH+/98A9///BQD3zwHQ//8OcP//XwD4vwEA/f/vAPb//wb4vwEA4P//DUD/
/5/5vwAAEP//zwDx////rwAAAPb//wgA+///rwAAAMD//08AUP///wMAAJD//88AALD//+8nELT///8EAAD7//////////8HAAD5
7/////////8HAAD4j3D+/////88EAADifwAQluzvvTgAAAAAYgAAAAAAAAAAAAAAAACA/38AAAAAAAAAAPj/AwAAAAAAAABw/x0A
AAAAAAAAAPafAAAAAAAAAAAAAAAAAAD0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T/
/wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA
//+f8///BgAAEP//n/L//wcAACD//4/x//8KAABQ//9vwP//LwAAsP//L2D//98UMPr//wwQ/f////////8EAOP///////9/AAAg
/P/////vBQAAADDI7u+cBQAAAAAAAAD87wQAAAAAAACA/z4AAAAAAAAA9O8DAAAAAAAAEP0uAAAAAAAAAAAAAAAAAAD0//8GAAAA
//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T/
/wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f8///BgAAEP//n/L//wcAACD//4/x//8KAABQ
//9vwP//LwAAsP//L2D//98UMPr//wwQ/f////////8EAOP///////9/AAAg/P/////vBQAAADDI7u+cBQAAAAAAcP//HAAAAAAA
APTv/K8AAAAAACD+PaH/BwAAAADRzwEA+F8AAAAAAAAAAAAAAAD0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA
//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T/
/wYAAAD//5/0//8GAAAA//+f8///BgAAEP//n/L//wcAACD//4/x//8KAABQ//9vwP//LwAAsP//L2D//98UMPr//wwQ/f//////
//8EAOP///////9/AAAg/P/////vBQAAADDI7u+cBQAAAABg/w+g/wwAAAAAYP8PoP8MAAAAAGD/D6D/DAAAAABg/w+g/wwAAAAA
AAAAAAAAAAAAAAAAAAAAAAAA9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA
//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/P/
/wYAABD//5/y//8HAAAg//+P8f//CgAAUP//b8D//y8AALD//y9g///fFDD6//8MEP3/////////BADj////////fwAAIPz/////
7wUAAAAwyO7vnAUAAAAAAAAAIP7PAQAAAAAAAAAA/M8BAAAAAAAAAAD5vwEAAAAAAAAAAPS/AAAAAAAAAAAAAAAAAAAAABD+//8D
AAAAcP//r1D//88AAAAg///vAaD//38AAAD7//8GAOH//y4AAPb//wsAAPX//wsA4f//LgAAAPr//wag//9vAAAAIP7/70H//78A
AAAAYP//r/3/7wIAAAAAsP//////BwAAAAAA4v////8MAAAAAAAA9v///z8AAAAAAAAA+///fwAAAAAAAAAg///fAAAAAAAAAADg
//8KAAAAAAAAAAD+/68AAAAAAAAAAOD//woAAAAAAAAAAP7/rwAAAAAAAAAA4P//CgAAAAAAAAAA/v+vAAAAAAAAAADg//8KAAAA
AAAAAAD+/68AAAAAAAAAAOD//woAAAAA9P//BgAAAAAAQP//bwAAAAAAAPT//wYAAAAAAED//28AAAAAAAD0/////++cBABA////
/////zwA9P////////8+QP//////////DfT//wYAcv///0X//28AAHD//5/0//8GAADy//9L//9vAAAg//+/9P//BgAA9///Sf//
bwAg9///X/T/////////30D/////////7wP0////////zwNA///////OSQAA9P//BgAAAAAAQP//bwAAAAAAAPT//wYAAAAAAED/
/28AAAAAAAAAELft760WAAAAYP7/////TQAAYP///////z4AEP7/zxSC//8LAPX//wIAsP//AXD//w0AAPr/PwD3/88AYP7//wNw
//8MgP//axQA9//PMP//BQAAcP//DPj/DgAAAPf/z6D//wQAAHD//wz4/+8HAAD3/89A////TQBw//8MkP///38A9//PAHD+//9v
cP//DAAg+v//Dff/zwAAAPj//3L//wwAAAD+/0/3/88AAADw//9z//8MhxOi//8O9//PgP////+PcP//DPj///+vAPf/zxC1/d5K
AAAAcP+fAAAAAAAAgP9PAAAAAAAAoP8dAAAAAAAAsP8KAAAAAAAAwf8FAAAAAAAA0e8CAAAAAAAAAAAAAAAAAAAAAAAAAED////v
vkkAAPT//////88CQP///////98BxEgSEGL+/38AAAAAAHD//wsAhNv+////3xD7////////Dfz////////f9f//OgFg//+d//8M
AAD3/9/6/58AALD//53//wwAQP//3/b//xhR/v//Df3/////+f/fMP3//+9l//8NEMjujQL2/98AAAAAAPP/HAAAAAAAwP8tAAAA
AACA/y4AAAAAADD/PgAAAAAAEP1fAAAAAAAA+W8AAAAAAAAAAAAAAAAAAAAAAAAAAED////vvkkAAPT//////88CQP///////98B
xEgSEGL+/38AAAAAAHD//wsAhNv+////3xD7////////Dfz////////f9f//OgFg//+d//8MAAD3/9/6/58AALD//53//wwAQP//
3/b//xhR/v//Df3/////+f/fMP3//+9l//8NEMjujQL2/98AAADQ/08AAAAAAHD//x0AAAAAIP++/wgAAAAA+1/R/wMAAAD1jwDi
zwAAAOG/AAD0bwAAAAAAAAAAAAAAAAAAAAAAAED////vvkkAAPT//////88CQP///////98BxEgSEGL+/38AAAAAAHD//wsAhNv+
////3xD7////////Dfz////////f9f//OgFg//+d//8MAAD3/9/6/58AALD//53//wwAQP//3/b//xhR/v//Df3/////+f/fMP3/
/+9l//8NEMjujQL2/98AAFDeAwDqBAAAIP7vAcBPAAAA9zq+AP4CAACgX0B/9A4AAAD8A5D/jwAAAMAuAKCuAQAAAAAAAAAAAAAA
AAAAAAAAAED////vvkkAAPT//////88CQP///////98BxEgSEGL+/38AAAAAAHD//wsAhNv+////3xD7////////Dfz////////f
9f//OgFg//+d//8MAAD3/9/6/58AALD//53//wwAQP//3/b//xhR/v//Df3/////+f/fMP3//+9l//8NEMjujQL2/98AAPb/AfnP
AAAAYP8fkP8MAAAA9v8B+c8AAABg/x+Q/wwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD0////7psEAED///////8sAPT/////
//8dQIwkASHm//8HAAAAAAD3/78AQLjt/////w2x////////38D/////////Xf//rxMA9v/f+f/PAABw//+t//8JAAD7/9/5/88A
APT//23//48R5f//39D/////n///DdP///9e9v/fAIHs3ihg//8NAAAAkv5cAAAAAADS//9/AAAAAKDfE/kfAAAAAP4GAP4FAAAA
4G8A4F8AAAAA+j2R/wEAAAAg/f//BwAAAAAg6s8FAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPT////umwQAQP///////ywA
9P///////x1AjCQBIeb//wcAAAAAAPf/vwBAuO3/////DbH////////fwP////////9d//+vEwD2/9/5/88AAHD//63//wkAAPv/
3/n/zwAA9P//bf//jxHl///f0P////+f//8N0////172/98AgezeKGD//w1A////75wEAIPs75wEAAD0//////88+v////8rAED/
//////////////8uAMRIEhBi/v//nwLD//8MAAAAAABw//+/AADy//8GAITb/v////8DAAD6/78Q+////////w4AAHD//w38////
//////////////X//zoBYP//////////n///DAAA9v//////////+v+fAABw//8NAAAAAACQ//8MABD9//8FAAAAMDr2//8YQfz/
//84AUHH/xP9/////5/1////////PyD9////fgDE////////AxDH/s4XAABQyf7evFgCAABQyf7OagEA5f/////PAPj//////wz2
//9dAXLO4f//HAAAEFj//08AAAAA+f/vAAAAAKD//wwAAAAA+v/PAAAAAJD//w4AAAAA9f//AwAAABD+/88BAACBYP//3xUg5gyA
///////PAGD+/////wwAAJXs76wWAAAAAPMdAAAAAAAA+QkAAAAAAED/AQAAAAAQ+S8AAABw///fAAAAAPf/rgIAACD97wIAAAAA
AADj/wsAAAAAAABA/28AAAAAAAAA9e8CAAAAAAAAYP8MAAAAAAAAAPd/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAABh2v7OKAAAAGD+
/////wgAAPn//////68AcP//jwLU//8H4f//CQAw//8e9f//AQAA+/9v+f/PAAAA+f+v+v/////////P+v/////////f+f//////
///f9f/PAAAAAAAA4f//BAAAADAqcP//jhMQdP0vAPn///////8vAGD+//////8vAABh2v7evFgCAAAAAACg/18AAAAAAAD2/wcA
AAAAACD+jwAAAAAAALD/CgAAAAAAAPe/AAAAAAAAMP8cAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABh2v7OKAAAAGD+/////wgAAPn/
/////68AcP//jwLU//8H4f//CQAw//8e9f//AQAA+/9v+f/PAAAA+f+v+v/////////P+v/////////f+f/////////f9f/PAAAA
AAAA4f//BAAAADAqcP//jhMQdP0vAPn///////8vAGD+//////8vAABh2v7evFgCAAAAYP+/AAAAAAAA4f//BgAAAAAA+r//HgAA
AABA/wv3nwAAAADR3wGg/wQAAAD4PwAA/A0AAAAAAAAAAAAAAAAAAAAAAAAAAABh2v7OKAAAAGD+/////wgAAPn//////68AcP//
jwLU//8H4f//CQAw//8e9f//AQAA+/9v+f/PAAAA+f+v+v/////////P+v/////////f+f/////////f9f/PAAAAAAAA4f//BAAA
ADAqcP//jhMQdP0vAPn///////8vAGD+//////8vAABh2v7evFgCAADg/wjy/wQAAADg/wjy/wQAAADg/wjy/wQAAADg/wjy/wQA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABh2v7OKAAAAGD+/////wgAAPn//////68AcP//jwLU//8H4f//CQAw//8e9f//
AQAA+/9v+f/PAAAA+f+v+v/////////P+v/////////f+f/////////f9f/PAAAAAAAA4f//BAAAADAqcP//jhMQdP0vAPn/////
//8vAGD+//////8vAABh2v7evFgC4/8MAAD0/wgAAPb/BAAA998BAAD5nwAAAPpfAAAAAAAAAAAAAHD//wwA9//PAHD//wwA9//P
AHD//wwA9//PAHD//wwA9//PAHD//wwA9//PAHD//wwA9//PAHD//wwA9//PAHD//wwA9//PAADA/z4AAPj/BABA/28AANH/BwAA
+Z8AAFD/CgAAAAAAAAAAAAAAAPf/zwAA9//PAAD3/88AAPf/zwAA9//PAAD3/88AAPf/zwAA9//PAAD3/88AAPf/zwAA9//PAAD3
/88AAPf/zwAA9//PAAD3/88AAPf/zwAAABD9/wMAAJD//wwAAPPv/H8AAPxP0e8CcP8GMP8L4p8AAPZfAAAAAAAAAAAAAAAAAHD/
/wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwA
AHD//wwAAHD//wwAAHD//wwA9+8A+7/37wD7v/fvAPu/9+8A+78AAAAAAAAAAAAAAAAAAAAA9//PAAD3/88AAPf/zwAA9//PAAD3
/88AAPf/zwAA9//PAAD3/88AAPf/zwAA9//PAAD3/88AAPf/zwAA9//PAAD3/88AAPf/zwAA9//PAAAA+/9/ABC2BAAAEPz/b7b/
jwAAACD9////fAIAABDG//+PAgAAAKX/////CwAAAKD/jWL//wkAAACFAwCQ//8GAAAAAAAAsP//BAAAAJTs7/3/7wIAMPz/////
/78AMP7///////9PAP3//xcx1///C/X//wYAAPb//5H//w4AADD//z/6/88AAADy//+k//8MAAAw//9P+P/vAAAA9P//U///PwAA
gP//DuH//woAEP7/nwD2//8pMPz/7wEA+f///////wQAAOb/////zwMAAABh2v7OSQAAAAAAcM4CAO0CAAAA9P8MAP4BAAAA+liP
EO8AAAAA/QL3db8AAAAA/wGw/18AAAAA7gAQ6wgAAAAAAAAAAAAAAAAAAAAAAAAAAPf/zwC1/q0EAPf/z7H///9/APf/z/v/////
BPf//48S9v//Cvf//wkAgP//Dff//wIAUP//D/f/7wAAQP//D/f/zwAAQP//D/f/zwAAQP//D/f/zwAAQP//D/f/zwAAQP//D/f/
zwAAQP//D/f/zwAAQP//D/f/zwAAQP//D/f/zwAAQP//D/f/zwAAQP//DwAg/e8BAAAAAAAAMP6/AAAAAAAAAED/bwAAAAAAAABQ
/y4AAAAAAAAAYP8LAAAAAAAAAID/BwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGHa/s5JAAAAAOf/////3wMAAPr///////8EAPf/
/ygw/P/vAuH//wgAEP3/n1D//y8AAHD//w75/98AAAD0//+j//8MAAAw//9P+v/PAAAA8///lP//DQAAQP//P/X//wEAAPf/7xD+
/48AANH//wlw//+PAsP//y4AoP///////08AAHD+/////z0AAAAQpu3vnAQAAAAAAAAAsP9fAAAAAAAAYP9vAAAAAAAAIP6PAAAA
AAAAAPufAAAAAAAAAPe/AAAAAAAAAPPPAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGHa/s5JAAAAAOf/////3wMAAPr///////8E
APf//ygw/P/vAuH//wgAEP3/n1D//y8AAHD//w75/98AAAD0//+j//8MAAAw//9P+v/PAAAA8///lP//DQAAQP//P/X//wEAAPf/
7xD+/48AANH//wlw//+PAsP//y4AoP///////08AAHD+/////z0AAAAQpu3vnAQAAAAAAMD/bwAAAAAAAGD//x4AAAAAABD+v/8J
AAAAAAD6b8D/BAAAAAD0nwDi3wAAAADRzwAA838AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGHa/s5JAAAAAOf/////3wMAAPr/////
//8EAPf//ygw/P/vAuH//wgAEP3/n1D//y8AAHD//w75/98AAAD0//+j//8MAAAw//9P+v/PAAAA8///lP//DQAAQP//P/X//wEA
APf/7xD+/48AANH//wlw//+PAsP//y4AoP///////08AAHD+/////z0AAAAQpu3vnAQAAAAAQN0EAOkFAAAAEP7vArBfAAAAAPY7
vgD9AwAAAJBvQI/0DgAAAAD7BID/nwAAAACwPgCQvgEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGHa/s5JAAAAAOf/////3wMAAPr/
//////8EAPf//ygw/P/vAuH//wgAEP3/n1D//y8AAHD//w75/98AAAD0//+j//8MAAAw//9P+v/PAAAA8///lP//DQAAQP//P/X/
/wEAAPf/7xD+/48AANH//wlw//+PAsP//y4AoP///////08AAHD+/////z0AAAAQpu3vnAQAAAAA9f8C+N8AAAAAUP8vgP8NAAAA
APX/AvjfAAAAAFD/L4D/DQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEKbt75wEAAAAcP7/////PQAAoP///////08A
cP//jwLD//8uEP7/jwAA0f//CfX//wIAAPf/75D//w0AAED//z/6/88AAADz//+k//8MAAAw//9P+f/fAAAA9P//U///HwAAcP//
DuH//wgAEP3/nwD3//8oMPz/7wIA+v///////wQAAOf/////3wMAAABh2v7OSQAAAAAAAKD/zwAAAAAAAAD6/wwAAAAAAACg/88A
AAAAAAAA+v8MAAAAAAAAoP/PAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMD//////////+/8///////////O///////////vAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAKD/zwAAAAAAAAD6/wwAAAAAAACg/88AAAAAAAAA+v8MAAAAAAAAoP/PAAAAAAAAAAAAAAAQawAAEKbt
760m/B4AYP7//////y0AgP///////58AYP//jxLE//9PEP7/jwAg/v//C/T//wIQ/f///4H//w0Q/G7//z/6/88A+0/y//+l//8M
+l8w//9P+f/f+W8A9P//c////38AcP//DvL//48AEP3/nwD6//8pMPz/7wEg/v///////wQA9f//////zwMA9Y+V3P7OSQAAMGsA
AAAAAAAAAACQ/28AAAAAAACw/y4AAAAAAADB/wwAAAAAAADR/wcAAAAAAADi/wMAAAAAAADjzwAAAAAAAAAAAAAAAAAAAAAAAAAA
+v+fAABg//+t//8JAAD2/9/6/58AAGD//63//wkAAPb/3/r/nwAAYP//rf//CQAA9v/f+v+fAABg//+t//8JAAD2/9/6/58AAHD/
/63//wkAAPj/3/n/rwAAwP//jf//DQBA///f9f//GlH+//8N/f///+/5/98w/v//32P//w0QyO6MAfb/3wAAAAAA9f8LAAAAAADh
/xwAAAAAAKD/HQAAAAAAYP8tAAAAAAAg/j4AAAAAAAD7TwAAAAAAAAAAAAAAAAAAAAAAAAAA+v+fAABg//+t//8JAAD2/9/6/58A
AGD//63//wkAAPb/3/r/nwAAYP//rf//CQAA9v/f+v+fAABg//+t//8JAAD2/9/6/58AAHD//63//wkAAPj/3/n/rwAAwP//jf//
DQBA///f9f//GlH+//8N/f///+/5/98w/v//32P//w0QyO6MAfb/3wAAAPf/CgAAAAAA4v//BQAAAACw//vfAQAAAFD/C/iPAAAA
EP4dAPo/AAAA+S4AEP0MAAAAAAAAAAAAAAAAAAAAAAAA+v+fAABg//+t//8JAAD2/9/6/58AAGD//63//wkAAPb/3/r/nwAAYP//
rf//CQAA9v/f+v+fAABg//+t//8JAAD2/9/6/58AAHD//63//wkAAPj/3/n/rwAAwP//jf//DQBA///f9f//GlH+//8N/f///+/5
/98w/v//32P//w0QyO6MAfb/3wAA/38w/z8AAADw/wfz/wMAAAD/fzD/PwAAAPD/B/P/AwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAoP//CQAA9v/f+v+fAABg//+t//8JAAD2/9/6/58AAGD//63//wkAAPb/3/r/nwAAYP//rf//CQAA9v/f+v+fAABg//+t//8J
AAD3/9/6/58AAID//53//woAAPz/3/j/3wAA9P//Xf//rxHl///f0P////+e//8N4////z32/98AgezOGGD//w0AAAAAAJD/fwAA
AAAAAED/jwAAAAAAABD9rwAAAAAAAAD6vwAAAAAAAAD1zwEAAAAAAADi3wEAAAAAAAAAAAAAAAAAAAAAAAAAAAAA9v/PAAAAYP//
HP7/PwAAAPv/b4D//wkAAPL//wHy/+8BAHD//woA+v9/AAD8/08AMP//DQDy/98AAMD//wRw//8HAAD1/68A/P8fAAAA/f8f8/+v
AAAAcP//h///BAAAAOH/3/3/DQAAAAD5////fwAAAAAg/////wIAAAAAsP///wsAAAAAAPT//18AAAAAAAD8/98AAAAAAABw//8I
AAAAAAAA+v8vAAAAAAAQ9/+vAAAAAAD////vAgAAAADw///vBAAAAAAA/++MAgAAAAD3/88AAAAAAABw//8MAAAAAAAA9//PAAAA
AAAAcP//DAAAAAAAAPf/zwAAAAAAAHD//wwAAAAAAAD3/88AAAAAAABw//8MYOvfKQAA9//Pwf///28AcP//zP////9fAPf//48C
1P//HnD//48AAOL//wf3//8CAAD6/89w//8NAABg//8P9//PAAAA9f//cf//DAAAUP//H/f/3wAAAPb//3D//y8AAKD//wz3//8I
ACD+/39w////GED9/+8B9//P/P////8FcP//HPz///8GAPf/zwDG/p0CAHD//wwAAAAAAAD3/88AAAAAAABw//8MAAAAAAAA9//P
AAAAAAAAcP//DAAAAAAAAPf/zwAAAAAAAAAAAMD/CfH/BgAAAAD8nxD/bwAAAADA/wnx/wYAAAAA/J8Q/28AAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAABg//8MAAAA9v/P4f//AwAAsP//Bvj/nwAAIP//HyD//x4AAPf/rwCg//8HAMD//wQA8//fACD//w0A
APz/TwD3/38AAFD//wrA//8BAADQ//8x//8KAAAA9/9/+P9PAAAAEP7/3f/fAAAAAJD/////BwAAAADy////LwAAAAAA+///vwAA
AAAAQP///wUAAAAAAMD//w0AAAAAAAD3/48AAAAAAACg//8CAAAAAABx//8KAAAAAPD///8uAAAAAAD///9OAAAAAADw/84oAAAA
AAAAAADw/////wMAAAAAAADw/////wMAAAAAAADw/////wMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAA/v//LwAAAAAAAABQ////jwAAAAAAAACg////3wAAAAAAAADx/////wQAAAAAAAD2/////wkAAAAAAAD8/8///x4AAAAAACD/
/z/+/18AAAAAAID//wz5/78AAAAAAND//wf0//8CAAAAAPT//wLg//8HAAAAAPn/zwCQ//8NAAAAEP7/fwBA//8/AAAAUP//LwAA
/f+fAAAAsP//DAAA+P/vAAAA8v//////////BQAA9///////////CgAA/P//////////HwAw////////////bwCQ//8fAAAAAPz/
zwDg//8KAAAAAPf//wL1//8FAAAAAPL//wj6/+8BAAAAAMD//w0AIP////8vAAAA8v////8CAAAg/////y8AAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD0////7psEAED///////8sAPT///////8dQIwkASHm//8HAAAAAAD3/78AQLjt/////w2x
////////38D/////////Xf//rxMA9v/f+f/PAABw//+t//8JAAD7/9/5/88AAPT//23//48R5f//39D/////n///DdP///9e9v/f
AIHs3ihg//8NAAAA9A0AAPwGAAAAAAAA8a8Ckv8CAAAAAAAAYP///48AAAAAAAAAALT+vgUAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAP7//y8AAAAAAAAAUP///48AAAAAAAAAoP///98AAAAAAAAA8f////8EAAAAAAAA9v////8J
AAAAAAAA/P/P//8eAAAAAAAg//8//v9fAAAAAACA//8M+f+/AAAAAADQ//8H9P//AgAAAAD0//8C4P//BwAAAAD5/88AkP//DQAA
ABD+/38AQP//PwAAAFD//y8AAP3/nwAAALD//wwAAPj/7wAAAPL//////////wUAAPf//////////woAAPz//////////x8AMP//
/////////28AkP//HwAAAAD8/88A4P//CgAAAAD3//8C9f//BQAAAADy//8I+v/vAQAAAADA//8NAADzHwAA+ggAAAD9OyD4TwAA
AFD///+vAAAAADDq72wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABA////775JAAD0///////PAkD////////f
AcRIEhBi/v9/AAAAAABw//8LAITb/v///98Q+////////w38////////3/X//zoBYP//nf//DAAA9//f+v+fAACw//+d//8MAED/
/9/2//8YUf7//w39//////n/3zD9///vZf//DRDI7o0C9v/fAAAAAP7//y8AAAAAAAAAUP///48AAAAAAAAAoP///98AAAAAAAAA
8f////8EAAAAAAAA9v////8JAAAAAAAA/P/P//8eAAAAAAAg//8//v9fAAAAAACA//8M+f+/AAAAAADQ//8H9P//AgAAAAD0//8C
4P//BwAAAAD5/88AkP//DQAAABD+/38AQP//PwAAAFD//y8AAP3/nwAAALD//wwAAPj/7wAAAPL//////////wUAAPf/////////
/woAAPz//////////x8AMP///////////28AkP//HwAAAAD8/88A4P//CgAAAAD3//8C9f//BQAAAADy//8I+v/vAQAAAADA//8N
AAAAAAAAAADhLwAAAAAAAAAAAAD6CAAAAAAAAAAAABD/AwAAAAAAAAAAADD/GQAAAAAAAAAAAAD9//8BAAAAAAAAAACi/v8BQP//
/+++SQAA9P//////zwJA////////3wHESBIQYv7/fwAAAAAAcP//CwCE2/7////fEPv///////8N/P///////9/1//86AWD//53/
/wwAAPf/3/r/nwAAsP//nf//DABA///f9v//GFH+//8N/f/////5/98w/f//72X//w0QyO6NAvb/3wAAAAAAsG8AAAAAAABgzwAA
AAAAAAD8BwAAAAAAAODPAQAAAAAAAPr//wUAAAAAENn/XwAAAAAAEPzvAwAAAAAAAJD/PgAAAAAAAAD13wIAAAAAAAAg/i0AAAAA
AAAAAAAAAAAAAAAAQLjt76wmAAAAUPz//////xoAEPr///////8fALD/////////HwD5///PJRBi+h8w////BwAAACAaoP//nwAA
AAAAAOD//x4AAAAAAAD0//8KAAAAAAAA9v//BwAAAAAAAPf//wUAAAAAAAD3//8FAAAAAAAA9v//BwAAAAAAAPT//woAAAAAAADg
//8eAAAAAAAAoP//nwAAAAAAADD///8HAAAAIBoA+f//zyUQUvofALD/////////HwAQ+v///////x8AAFD8//////8aAAAAQLjt
760mAAAAAAAAsP9PAAAAAAD3/wYAAAAAMP9/AAAAAADA/wgAAAAAAPivAAAAAAAw/wsAAAAAAAAAAAAAAAAAAAAAAAAAAFDJ/s5q
AQBQ/v////8MAPj//////wxg///fFSDnDOH//xwAABAI9f//BAAAAAD5/+8AAAAAAPr/zwAAAAAA+v/PAAAAAAD5/+8AAAAAAPX/
/wMAAAAA4f//HAAAEAhg///fFSDmDAD4//////8MAGD+/////wwAAFDJ/s5qAQAAAABQ//8tAAAAAAAA4//8zwAAAAAAEP1OgP8J
AAAAALDfAgD2fwAAAAAAAAAAAAAAAAAAQLjt76wmAAAAUPz//////xoAEPr///////8fALD/////////HwD5///PJRBi+h8w////
BwAAACAaoP//nwAAAAAAAOD//x4AAAAAAAD0//8KAAAAAAAA9v//BwAAAAAAAPf//wUAAAAAAAD3//8FAAAAAAAA9v//BwAAAAAA
APT//woAAAAAAADg//8eAAAAAAAAoP//nwAAAAAAADD///8HAAAAIBoA+f//zyUQUvofALD/////////HwAQ+v///////x8AAFD8
//////8aAAAAQLjt760mAAAAAFD/zwAAAAAA4f//BwAAAAD5v/8uAAAAMP8c9q8AAADA7wKQ/wUAAPdPAAD7HQAAAAAAAAAAAAAA
AAAAAAAAAFDJ/s5qAQBQ/v////8MAPj//////wxg///fFSDnDOH//xwAABAI9f//BAAAAAD5/+8AAAAAAPr/zwAAAAAA+v/PAAAA
AAD5/+8AAAAAAPX//wMAAAAA4f//HAAAEAhg///fFSDmDAD4//////8MAGD+/////wwAAFDJ/s5qAQAAAAAA+v8FAAAAAAAAAPr/
BQAAAAAAAAD6/wUAAAAAAAAA+v8FAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEC47e+sJgAAAFD8//////8aABD6////////HwCw
/////////x8A+f//zyUQYvofMP///wcAAAAgGqD//58AAAAAAADg//8eAAAAAAAA9P//CgAAAAAAAPb//wcAAAAAAAD3//8FAAAA
AAAA9///BQAAAAAAAPb//wcAAAAAAAD0//8KAAAAAAAA4P//HgAAAAAAAKD//58AAAAAAAAw////BwAAACAaAPn//88lEFL6HwCw
/////////x8AEPr///////8fAABQ/P//////GgAAAEC47e+tJgAAAADQ//8FAAAAAP3/XwAAAADQ//8FAAAAAP3/XwAAAADQ//8F
AAAAAP3/XwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlezvrBYAUP7/////DID//////89g///fFSDnHP7/zwEAAIH1//8EAAAA
kP//DgAAAAD6/88AAAAAoP//DAAAAAD5/+8AAAAAUP//PwAAAADh//8cAAAQCPb//10BYs4A+P//////DADm/////88AAFDJ/s5q
AQAAAPV/ACD8HAAAAACA/wnj7wIAAAAAAPvP/08AAAAAAADR//8GAAAAAAAAAAAAAAAAAAAAQLjt76wmAAAAUPz//////xoAEPr/
//////8fALD/////////HwD5///PJRBi+h8w////BwAAACAaoP//nwAAAAAAAOD//x4AAAAAAAD0//8KAAAAAAAA9v//BwAAAAAA
APf//wUAAAAAAAD3//8FAAAAAAAA9v//BwAAAAAAAPT//woAAAAAAADg//8eAAAAAAAAoP//nwAAAAAAADD///8HAAAAIBoA+f//
zyUQUvofALD/////////HwAQ+v///////x8AAFD8//////8aAAAAQLjt760mAAAA+S4AEP0MAADh3wGg/wMAAFD/CviPAAAAAPuv
/x0AAAAA8v//BAAAAABw/68AAAAAAAAAAAAAAAAAAAAAAAAAAFDJ/s5qAQBQ/v////8MAPj//////wxg///fFSDnDOH//xwAABAI
9f//BAAAAAD5/+8AAAAAAPr/zwAAAAAA+v/PAAAAAAD5/+8AAAAAAPX//wMAAAAA4f//HAAAEAhg///fFSDmDAD4//////8MAGD+
/////wwAAFDJ/s5qAQAA+j0AUP4IAAAAAADR7wX3rwAAAAAAACD+v/8cAAAAAAAAAPT/7wIAAAAAAAAAAAAAAAAAAAD0////7r1p
AgAAAPT///////+/BAAA9P////////+PAAD0//////////8JAPT//wYQc/3//28A9P//BgAAof//7wH0//8GAAAA+///CPT//wYA
AADz//8M9P//BgAAAMD//x/0//8GAAAAkP//P/T//wYAAACA//9P9P//BgAAAID//0/0//8GAAAAkP//P/T//wYAAADA//8f9P//
BgAAAPP//wz0//8GAAAA+///CPT//wYAAKH//+8B9P//BhBz/v//bwD0//////////8JAPT/////////fwAA9P///////68DAAD0
////771pAgAAAAAAAAAAAPX/7wDy/w4AAAAAAAD1/+8A9f8IAAAAAAAA9f/vAPj/AgAAAAAAAPX/7wD7vwAAAAAAAAD1/+8A/k8A
AAAAAAAA9f/vEP8NAAAAAAAAAPX/7wAAAAAAALb+nQL1/+8AAAAAAMH///9e9f/vAAAAABD9//////n/7wAAAACA//+PAtT//+8A
AAAA4f//CAAg///vAAAAAPX//wIAAPr/7wAAAAD4/98AAAD2/+8AAAAA+f/PAAAA9f/vAAAAAPn/zwAAAPX/7wAAAAD4/98AAAD2
/+8AAAAA9f//AgAA+v/vAAAAAOH//wgAIP//7wAAAACQ//+PAdT//+8AAAAAEP3/////+f/vAAAAAADB////XvX/7wAAAAAAALb+
nQL1/+8AAAAAAPD////vzXoDAAAAAPD////////fBgAAAPD/////////vwEAAPD//////////xwAAPD//woQYvz//68AAPD//woA
AHD///8EAPD//woAAAD3//8MAPD//woAAADQ//8fAPD//woAAACA//9f+P//////AgBQ//9/+P//////AgBA//+f+P//////AgBA
//+P+P//////AgBQ//9/APD//woAAACA//9fAPD//woAAADQ//8fAPD//woAAAD3//8MAPD//woAAHD///8EAPD//woQYvz//68A
APD//////////xwAAPD/////////rwEAAPD////////PBQAAAPD////vzXoDAAAAAAAAAAAA9f/vAAAAAAAAAFD//w4AAAAAAAAA
9f/vAAAAAADx//////8/AAAAEP///////wMAAADx//////8/AAAAAAAA9f/vAAAAYOvfKVD//w4AAMH///9e9f/vAADR/////5//
/w4AgP//jwLU///vABD+/48AAPL//w4A9f//AgAA+v/vAID//w0AAGD//w4A+f/PAAAA9f/vAJD//wwAAFD//w4A+P/fAAAA9v/v
AFD//y8AAKD//w4A4f//CAAg///vAAD5//8YQP3//w4AEP3/////+f/vAAAQ/P//71X//w4AAAC2/p0C9f/vAAAAQP////8PAAAA
9P////8AAABA/////w8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD0/////////0D/////////D/T/////////QP////////8P
9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP////////8G9P///////29A/////////wb0////////
b0D//28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0/////////0T/////////T/T/////////RP//////
//9PAAD5////rwAAAAD5////rwAAAAD5////rwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABh2v7OKAAA
AGD+/////wgAAPn//////68AcP//jwLU//8H4f//CQAw//8e9f//AQAA+/9v+f/PAAAA+f+v+v/////////P+v/////////f+f//
///////f9f/PAAAAAAAA4f//BAAAADAqcP//jhMQdP0vAPn///////8vAGD+//////8vAABh2v7evFgCAKCPAAD0DgAAAPZ/EdSv
AAAAAPv//98CAAAAAMf+nQEAAAAAAAAAAAAAQP////////8P9P////////9A/////////w/0/////////0D//28AAAAAAPT//wYA
AAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0////////b0D/////////BvT///////9vQP////////8G9P//BgAAAABA//9v
AAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP////////9P9P////////9E/////////0/0/////////wQAAPMeAAD6CAAA
AOC/A4L/BAAAAFD///+vAAAAAACj/s4GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGHa/s4oAAAAYP7/
////CAAA+f//////rwBw//+PAtT//wfh//8JADD//x71//8BAAD7/2/5/88AAAD5/6/6/////////8/6/////////9/5////////
/9/1/88AAAAAAADh//8EAAAAMCpw//+OExB0/S8A+f///////y8AYP7//////y8AAGHa/t68WAIAAAD9/wIAAAAAAND/LwAAAAAA
AP3/AgAAAAAA0P8vAAAAAAAAAAAAAAAAAAAAAAAAAAD0/////////0D/////////D/T/////////QP////////8P9P//BgAAAABA
//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP////////8G9P///////29A/////////wb0////////b0D//28AAAAA
APT//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0/////////0T/////////T/T/////////RP////////9PAAAA4P//
BAAAAAAA4P//BAAAAAAA4P//BAAAAAAA4P//BAAAAAAA4P//BAAAAAAA4P//BAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AABh2v7OKAAAAGD+/////wgAAPn//////68AcP//jwLU//8H4f//CQAw//8e9f//AQAA+/9v+f/PAAAA+f+v+v/////////P+v//
///////f+f/////////f9f/PAAAAAAAA4f//BAAAADAqcP//jhMQdP0vAPn///////8vAGD+//////8vAABh2v7evFgC9P//////
//9A/////////w/0/////////0D/////////D/T//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED/////
////BvT///////9vQP////////8G9P///////29A//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P//
//////9E/////////0/0/////////0T/////////TwAAAAAAsG8AAAAAAABgzwAAAAAAAAD8BwAAAAAAAODPAQAAAAAAAPr//wUA
AAAAENn/XwAAYdr+zigAAABg/v////8IAAD5//////+vAHD//48C1P//B+H//wkAMP//HvX//wEAAPv/b/n/zwAAAPn/r/r/////
////z/r/////////3/n/////////3/X/zwAAAAAAAOH//wQAAAAwKnD//44TEHT9LwD5////////LwBg/v//////LwAAYdr+3rxY
AgAAAAAAsF8AAAAAAAAA9wsAAAAAAAAA/QcAAAAAAAAA/hsAAAAAAAAA+v//BAAAAAAAkf3/BACg7wMA5I8AAADB/wX3vwAAAADi
//vfAQAAAAD0/+8CAAAAAAAAAAAAAED/////////D/T/////////QP////////8P9P////////9A//9vAAAAAAD0//8GAAAAAED/
/28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P///////29A/////////wb0////////b0D/////////BvT//wYAAAAAQP//bwAAAAAA
9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED/////////T/T/////////RP////////9P9P////////8EAAD5LgAQ/QwAAADh3wGg
/wMAAABQ/wr4jwAAAAAA+6//HQAAAAAA8v//BAAAAAAAcP+vAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABh2v7OKAAAAGD+/////wgA
APn//////68AcP//jwLU//8H4f//CQAw//8e9f//AQAA+/9v+f/PAAAA+f+v+v/////////P+v/////////f+f/////////f9f/P
AAAAAAAA4f//BAAAADAqcP//jhMQdP0vAPn///////8vAGD+//////8vAABh2v7evFgCAAAAACD+/18AAAAAAAAAwP/87wMAAAAA
AAD6j0D+HQAAAAAAcP8GANO/AAAAAAAAAAAAAAAAAAAAADC37e/OagMAAABA/P//////zwUAEPn/////////CQCw//////////8J
APn//982ATGm/wkw////CAAAAABxCKD//58AAAAAAAAA4P//HgAAAAAAAAD0//8KAAAAAAAAAPb//wcAAAAAAAAA9///BQAA9v//
/2/3//8FAAD2////b/b//wcAAPb///9v9P//CgAA9v///2/g//8eAAAAAP7/b6D//48AAAAA/v9vMP///wcAAAD+/28A+f//zyYB
Qf7/bwCw//////////9vABD6/////////28AAFD8///////PBgAAAEC47e+9aQEAAAAA0P9PAAAAAAAA9//fAQAAAAAg/77/CAAA
AACw/xX9PwAAAAD1jwDizwAAABD+CwBA/wYAAAAAAAAAAAAAAAAAAAAAAAAAAAC2/p0C9f/vAMH///9e9f/vEPz/////+f/vgP//
jwLU///v4f//CQAg///v9f//AgAA+v/v+P/vAAAA9//v+f/PAAAA9f/v+f/PAAAA9f/v+P/fAAAA9//v9f//AgAA+v/v4f//CAAg
///vgP//fwHU///vEPz/////+f/vAMH///9e9f/vAAC2/p0C9v/fAAAAAAAA+v+vAEgAAABA//9fAPpbAjH4//8MAPr//////98B
APr//////xkAAEHI7e+tFwAAAAAA/QYAcM8AAAAAAAD4XhHmfwAAAAAAANH///8cAAAAAAAAENj/jAEAAAAAAAAAAAAAAAAAAAAA
ADC37e/OagMAAABA/P//////zwUAEPn/////////CQCw//////////8JAPn//982ATGm/wkw////CAAAAABxCKD//58AAAAAAAAA
4P//HgAAAAAAAAD0//8KAAAAAAAAAPb//wcAAAAAAAAA9///BQAA9v///2/3//8FAAD2////b/b//wcAAPb///9v9P//CgAA9v//
/2/g//8eAAAAAP7/b6D//48AAAAA/v9vMP///wcAAAD+/28A+f//zyYBQf7/bwCw//////////9vABD6/////////28AAFD8////
///PBgAAAEC47e+9aQEAAADyHwAA+QkAAADQzxNx/wUAAABA////vwAAAAAAo/3OBgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAC2/p0C9f/vAMH///9e9f/vEPz/////+f/vgP//jwLU///v4f//CQAg///v9f//AgAA+v/v+P/vAAAA9//v
+f/PAAAA9f/v+f/PAAAA9f/v+P/fAAAA9//v9f//AgAA+v/v4f//CAAg///vgP//fwHU///vEPz/////+f/vAMH///9e9f/vAAC2
/p0C9v/fAAAAAAAA+v+vAEgAAABA//9fAPpbAjH4//8MAPr//////98BAPr//////xkAAEHI7e+tFwAAAAAAAAD1/woAAAAAAAAA
APX/CgAAAAAAAAAA9f8KAAAAAAAAAAD1/woAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMLft785qAwAAAED8///////PBQAQ
+f////////8JALD//////////wkA+f//3zYBMab/CTD///8IAAAAAHEIoP//nwAAAAAAAADg//8eAAAAAAAAAPT//woAAAAAAAAA
9v//BwAAAAAAAAD3//8FAAD2////b/f//wUAAPb///9v9v//BwAA9v///2/0//8KAAD2////b+D//x4AAAAA/v9voP//jwAAAAD+
/28w////BwAAAP7/bwD5///PJgFB/v9vALD//////////28AEPr/////////bwAAUPz//////88GAAAAQLjt771pAQAAAAD2/98A
AAAAAAD2/98AAAAAAAD2/98AAAAAAAD2/98AAAAAAAD2/98AAAAAAAD2/98AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
ALb+nQL1/+8Awf///171/+8Q/P/////5/++A//+PAtT//+/h//8JACD//+/1//8CAAD6/+/4/+8AAAD3/+/5/88AAAD1/+/5/88A
AAD1/+/4/98AAAD3/+/1//8CAAD6/+/h//8IACD//++A//9/AdT//+8Q/P/////5/+8Awf///171/+8AALb+nQL2/98AAAAAAAD6
/68ASAAAAED//18A+lsCMfj//wwA+v//////3wEA+v//////GQAAQcjt760XAAAAAAAwt+3vzmoDAAAAQPz//////88FABD5////
/////wkAsP//////////CQD5///fNgExpv8JMP///wgAAAAAcQig//+fAAAAAAAAAOD//x4AAAAAAAAA9P//CgAAAAAAAAD2//8H
AAAAAAAAAPf//wUAAPb///9v9///BQAA9v///2/2//8HAAD2////b/T//woAAPb///9v4P//HgAAAAD+/2+g//+PAAAAAP7/bzD/
//8HAAAA/v9vAPn//88mAUH+/28AsP//////////bwAQ+v////////9vAABQ/P//////zwYAAABAuO3vvWkBAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA+P8dAAAAAAAAAAD9/wMAAAAAAAAAMP9fAAAAAAAAAACA/wgAAAAAAAAAAED/DQAA
AAAAAOL/CAAAAAAAEPz/AwAAAAAAoP/fAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAC2/p0C9f/vAMH///9e9f/vEPz/
////+f/vgP//jwLU///v4f//CQAg///v9f//AgAA+v/v+P/vAAAA9//v+f/PAAAA9f/v+f/PAAAA9f/v+P/fAAAA9//v9f//AgAA
+v/v4f//CAAg///vgP//fwHU///vEPz/////+f/vAMH///9e9f/vAAC2/p0C9v/fAAAAAAAA+v+vAEgAAABA//9fAPpbAjH4//8M
APr//////98BAPr//////xkAAEHI7e+tFwAAAAAAIP7/PwAAAAAAABD9z/8uAAAAAAAA+39Q/xwAAAAAAPhOADD+CgAAAAAAAAAA
AAAAAED//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA
//9f9P//BgAAAPT//0X//28AAABA//9f9P///////////0X///////////9f9P///////////0X///////////9f9P//BgAAAPT/
/0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f
9P//BgAAAPT//wUAYP//HQAAAAAAAED/z/8LAAAAAAAg/j6Q/wgAAAAAEPwsAHD/BQAAAAAAcP//DAAAAAAAAAD3/88AAAAAAAAA
cP//DAAAAAAAAAD3/88AAAAAAAAAcP//DAAAAAAAAAD3/88AAAAAAAAAcP//DAAAAAAAAAD3/88Atf6tBAAAcP//HPv///8HAAD3
/8/7/////wQAcP///yhh//+vAAD3//8JAID//w0AcP//LwAA9f//AAD3/+8AAED//w8AcP//DAAA9P//AAD3/88AAED//w8AcP//
DAAA9P//AAD3/88AAED//w8AcP//DAAA9P//AAD3/88AAED//w8AcP//DAAA9P//AAD3/88AAED//w8AcP//DAAA9P//AADz//8H
AAAA9P//BgAw//9/AAAAQP//bwAA8///BwAAAPT//wZA//////////////9/9P//////////////R///////////////fwDz//8H
AAAA9P//BgAw//9/AAAAQP//bwAA8///BwAAAPT//wYAMP///////////28AAPP///////////8GADD///////////9vAADz////
////////BgAw//9/AAAAQP//bwAA8///BwAAAPT//wYAMP//fwAAAED//28AAPP//wcAAAD0//8GADD//38AAABA//9vAADz//8H
AAAA9P//BgAw//9/AAAAQP//bwAA8///BwAAAPT//wYAMP//fwAAAED//28AAPP//wAAAAAAAADz//8AAAAAAAD4//////9fAAAA
+P//////XwAAAPj//////18AAAAA8///AAAAAAAAAPP//wAAAAAAAADz//8Ao/2+BQAA8///gP///68AAPP///j/////BwDz//+/
A+P//w0A8///DQBA//8vAPP//wYAEP//PwDz//8CAAD//08A8///AQAA//9PAPP//wAAAP//TwDz//8AAAD//08A8///AAAA//9P
APP//wAAAP//TwDz//8AAAD//08A8///AAAA//9PAPP//wAAAP//TwDz//8AAAD//08w7DsA9hn+/3+xf/Uc5v//co8Aot4FAAAA
AAAAQP//bwAA9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//bwAA9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//bwAA
9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//bwAA9P//BgBA//9vAAD0//8GAGDOAgDrI//fAdAv+EmeAP/BT2Bv9Qz9AqD/
b9AeAKGeAAAAAAAAAAAAAAAAAPf/zwAAcP//DAAA9//PAABw//8MAAD3/88AAHD//wwAAPf/zwAAcP//DAAA9//PAABw//8MAAD3
/88AAHD//wwAAPf/zwAAcP//DAAA9//PAABw//8MAPH/////E/////8/8f////8DAAAAAAAAAAAAAAAAAAAAAAD0//8GAED//28A
APT//wYAQP//bwAA9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//bwAA9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//
bwAA9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//bwD3////v/f///+/9////78AAAAAAAAAAAAAAAAAAAAAAAAAAAD3/88A
APf/zwAA9//PAAD3/88AAPf/zwAA9//PAAD3/88AAPf/zwAA9//PAAD3/88AAPf/zwAA9//PAAD3/88AAPf/zwAA9//PAAD3/88A
9B4AAP0G/jsg+h9Q////fwAw6u9LAAAAAAAAAED//28AAPT//wYAQP//bwAA9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//
bwAA9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//bwAA9P//BgBA//9vAAD0//8GAED//28AAPT//wYAQP//bwAA9P//BgD7
BwAw/3DvFkH9C8H///8+AHHs3ykAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD3/88AAHD//wwAAPf/zwAAcP//DAAA9//PAABw//8M
AAD3/88AAHD//wwAAPf/zwAAcP//DAAA9//PAABw//8MAAD3/88AAHD//wwAAPf/zwAAcP//DAD0//8GQP//bwD0//8GQP//bwD0
//8GQP//bwD0//8GQP//bwD0//8GQP//bwD0//8GQP//bwD0//8GQP//bwD0//8GQP//bwD0//8GQP//bwD0//8GQP//bwD0//8G
QP//bwAAIO4CAAD7BwAA8i8AAED/CAAA4f//DwCz/v/3/88AcP//DAD3/88AcP//DAD3/88AAAAAAAAAAAAAcP//DAD3/88AcP//
DAD3/88AcP//DAD3/88AcP//DAD3/88AcP//DAD3/88AcP//DAD3/88AcP//DAD3/88AcP//DAD3/88AAAD6BwAA9gwAAMCPAAAA
/SwAAJD//18Agf3/BWD/nwD2/wlg/58A9v8JAAAAAAAAAPT//0b//2/0//9G//9v9P//Rv//b/T//0b//2/0//9G//9v9P//Rv//
b/T//0b//2/0//9G//9v9P//Rv//b/T//0b//2/0//9G//9v9//P9//P9//P9//P9//P9//P9//P9//P9//P9//P9//P9//P9//P
9//P9//P9//P9P//BgAg//+P9P//BgAg//+P9P//BgAg//+P9P//BgAg//+P9P//BgAg//+P9P//BgAg//+P9P//BgAg//+P9P//
BgAg//+P9P//BgAg//+P9P//BgAg//+P9P//BgAg//+P9P//BgAg//+P9P//BgAg//+P9P//BgAg//+P9P//BgAg//+P9P//BgAg
//+P9P//BgAg//+P9P//BgAg//+P9P//BgAg//+P9P//BgAg//+P9P//BgAw//9/9P//BgBQ//9vAAAAAACw//9PAAAAADH6//8O
AAAAgP////8HAAAAgP///78AAAAAgP///xkAAAAAgO+9JwAA9//PAADz//9x//8MADD//x/3/88AAPP//3H//wwAMP//H/f/zwAA
8///AQAAAAAAAAAAAAAAAAAAAABw//8MADD//x/3/88AAPP//3H//wwAMP//H/f/zwAA8///cf//DAAw//8f9//PAADz//9x//8M
ADD//x/3/88AAPP//3H//wwAMP//H/f/zwAA8///cf//DAAw//8f9//PAADz//9x//8MADD//x/3/88AAPP//3H//wwAMP//H/f/
zwAA8///AQAAAABA//8PAAAAAAD2/98AAAAAENT//wkAAACw////LwAAAAD7//9fAAAAALD/3ikAAAAA4v//BAAA0f/87wIAsP8H
9c8BgO8FAOOvAAAAAAAAAABA//9vAAAA9P//BgAAQP//bwAAAPT//wYAAED//28AAAD0//8GAABA//9vAAAA9P//BgAAQP//bwAA
APT//wYAAED//28AAAD0//8GAABA//9vAAAA9P//BgAAQP//bwAAAPT//wYAAED//28AAAD0//8GAABA//9vAAAA9P//BgAAUP//
XwAAAPf//wQAAND//y8AELP//88AoP////8FAPr///8JAKD///8HAAD63noBAAAAABD9/wMAAJD//wwAAPPv/H8AAPxP0e8CcP8H
MP8L4q8AAPVfAAAAAAAAAAAAAAAAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwA
AHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wwAAHD//wsAAID//wsAAKD//wkAEPb//wUA////zwAA////LQAA/+98
AQAA9P//BgAAIP3//wlA//9vAAAg/f//CAD0//8GACD9//8IAED//28AIP3//wgAAPT//wYg/f//CAAAQP//byD9//8IAAAA9P//
Jv7//wgAAABA//+P/v//CAAAAAD0//////8HAAAAAED//////wcAAAAAAPT/////DAAAAAAAQP//////CQAAAAAA9P//////CQAA
AABA///P////CQAAAAD0//92////CQAAAED//29w////CQAAAPT//wZg////CQAAQP//bwBg////CQAA9P//BgBg////CgBA//9v
AABg////CgD0//8GAABg////CkD//28AAABg////CgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGD/7wIAAAAAAAAAAPv/BAAA
AAAAAAAA8f8HAAAAAAAAAABg/woAAAAAAPf/zwAAAAAAAHD//wwAAAAAAAD3/88AAAAAAABw//8MAAAAAAAA9//PAAAAAAAAcP//
DAAAAAAAAPf/zwAAAAAAAHD//wwAAPr//wX3/88AAPv/7wRw//8MEPv/7wMA9//PEPv/3wMAcP//HPz/3wIAAPf/z/z/zwEAAHD/
////vwEAAAD3/////wIAAABw/////98CAAAA9//f/v/fAgAAcP//PP7/3wIAAPf/zzD+/98CAHD//wxA/v/fAgD3/88AQP//3wJw
//8MAFD//98C9//PAABQ///fAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAD1/z4AAAAAAACg/18AAAAAAAAQ/o8AAAAAAAAA9b8AAAAA
APf/zwAAoP//X3D//wwAsP//TgD3/88Asf//PgBw//8Msf//PQAA9//Pwf//LQAAcP//zP//HAAAAPf/////GwAAAHD/////LwAA
AAD3/////y0AAABw///t//8tAAAA9//P4///LQAAcP//DOP//y0AAPf/zwDk//8tAHD//wwA9P//LQD3/88AAPX//y1w//8MAAD1
//8tAADi/xwAAAAAAMD/HAAAAAAAgP8cAAAAAABA/xsAAAAAAAAAAAAAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8G
AAAAAED//28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//
bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP////////9P9P////////9E/////////0/0
/////////wQAAPzvBAD47wMA9O8DAOHfAgD3/88AcP//DAD3/88AcP//DAD3/88AcP//DAD3/88AcP//DAD3/88AcP//DAD3/88A
cP//DAD3/88AcP//DAD3/88AcP//DAD3/88AcP//DAD3/88AcP//DAD3/88AcP//DAD3/88AAPT//wYAAAAAQP//bwAAAAAA9P//
BgAAAABA//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED/
/28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT/////////RP////////9P
9P////////9E/////////08AAAAAAAAAAAAAAAAAAAAAAAAAAPX/PgAAAAAAoP9fAAAAAAAQ/o8AAAAAAAD1vwAAAAD3/89w//8M
9//PcP//DPf/z3D//wz3/89w//8M9//PcP//DPf/z3D//wz3/89w//8M9//PcP//DPf/z3D//wz3/89w//8M9//PcP//DPf/zwAA
AAAAAAAA+/8L8f8dYP8+APtfAAD0//8GAAD//0H//28AAPP/CvT//wYAYP8/QP//bwAA+c8A9P//BgDA/wZA//9vAAD+HgD0//8G
AAAAAED//28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//
bwAAAAAA9P//BgAAAABA//9vAAAAAAD0/////////0T/////////T/T/////////RP////////9P9//PAP3/c///DPH/C/f/z0D/
X3D//wz37wD3/8+g/whw//8M/S8A9//PAAAAcP//DAAAAPf/zwAAAHD//wwAAAD3/88AAABw//8MAAAA9//PAAAAcP//DAAAAPf/
zwAAAHD//wwAAAD3/88AAABw//8MAAAA9//PAAAAcP//DAAAAPf/zwAAAHD//wwAAAD3/88AAAAA9P//BgAAAABA//9vAAAAAAD0
//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P//BgD4/79A//9vAID//wv0//8GAPj/v0D//28AgP//C/T//wYA+P+/
QP//bwCA//8L9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P////////9E////////
/0/0/////////0T/////////T/f/zwAAAHD//wwAAAD3/88AAABw//8MAAAA9//PAAAAcP//DAAAAPf/zwAAAHD//wz7/4/3/8+w
//94//8M+/+P9//PsP//eP//DPv/j/f/z7D//3j//wwAAAD3/88AAABw//8MAAAA9//PAAAAcP//DAAAAPf/zwAAAHD//wwAAAD3
/88AAABw//8MAAAA9//PAAAAAAAA8f//CAAAAAAAABD//48AAAAAAAAA8f//CAAAAAAAABD//48AMQAAAAAA8f//CNMuAAAAABD/
/5/3/wsAAAAA8f///v/fAgAAABD/////rwEAAAAA8f///14AAAAAABD///8rAAAAAAAA9v//CgAAAAAAEPv//48AAAAAAFD+////
CAAAAAAg/////48AAAAAAGD//f//CAAAAAAAoCj//48AAAAAAAAA8f//CAAAAAAAABD//48AAAAAAAAA8f////////8HABD/////
////fwAA8f////////8HABD/////////fwAQ//8/AAAA8f//AwAAEP//PwAAAPH//wMAABD//z8AAADx//8DAAAQ//8/VwAA8f//
/S4AEP////8GAPH//98DAJH//58BANP///8DAPT///8/AAD8/f//AwAwGP//PwAAAPH//wMAABD//z8AAADx//8DAAAQ//8/AAAA
8f//AwAAEP//PwAAAPH//wMAABD//z8AAAAAAAAA++8EAAAAAAAAAPfvBAAAAAAAAADz7wMAAAAAAAAA0e8DAAAAAAAAAAAAAAAA
AABA////BQAAAP//X/T//88AAADw//9F////XwAAAP//X/T///8NAADw//9F/////wYAAP//X/T////vAQDw//9F/////38AAP//
X/T///r/HgDw//9F//8//v8IAP//X/T//4H/7wHw//9F//8f4f+fAP//X/T//wH3/y/w//9F//8fEP7/Cf//X/T//wFg///z//9F
//8fAND/r///X/T//wEA9v////9F//8fAAD8////X/T//wEAUP////9F//8fAADA////X/T//wEAAPT///9F//8fAAAA+///X/T/
/wEAADD///8FAAAAAOL/LQAAAAAAAPvvAwAAAAAAYP8+AAAAAAAA4v8FAAAAAAAA/G8AAAAAAABw/wcAAAAAAAAAAAAAAAAAAAAA
AAAAAAAA9//PALX+rQQA9//Psf///38A9//P+/////8E9///jxL2//8K9///CQCA//8N9///AgBQ//8P9//vAABA//8P9//PAABA
//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P
9P//XwAAAPD//0X///8MAAAA//9f9P///wUAAPD//0X////fAAAA//9f9P///28AAPD//0X/////HgAA//9f9P////8HAPD//0X/
/6//7wEA//9f9P//4/+PAPD//0X//x/4/x4A//9f9P//Ef7/CfD//0X//x9w//8C//9f9P//AeH/n/D//0X//x8A9v8///9f9P//
AQD9//r//0X//x8AYP////9f9P//AQDA/////0X//x8AAPX///9f9P//AQAA/P///0X//x8AAED///9f9P//AQAAsP///0X//x8A
AADz//9fAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPX/PwAAAAAAAACg/28AAAAAAAAAAP6PAAAAAAAAAAD1vwAAAAAA9//PALX+
rQQA9//Psf///38A9//P+/////8E9///jxL2//8K9///CQCA//8N9///AgBQ//8P9//vAABA//8P9//PAABA//8P9//PAABA//8P
9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8PAAAAAAAAAAAAAAAA
AAAAAAAAAAAA8v9vAAAAAAAA9/8JAAAAAAAA+78AAAAAAAAQ/x0AAAAAAAAw/wkAse8CAAAAAGD/G9L/AwAAAAAAkP/t/wYAAAAA
AACw//8IAAAAAAAAAAAAAAAAAED///8FAAAA//9f9P//zwAAAPD//0X///9fAAAA//9f9P///w0AAPD//0X/////BgAA//9f9P//
/+8BAPD//0X/////fwAA//9f9P//+v8eAPD//0X//z/+/wgA//9f9P//gf/vAfD//0X//x/h/58A//9f9P//Aff/L/D//0X//x8Q
/v8J//9f9P//AWD///P//0X//x8A0P+v//9f9P//AQD2/////0X//x8AAPz///9f9P//AQBQ/////0X//x8AAMD///9f9P//AQAA
9P///0X//x8AAAD7//9f9P//AQAAMP///wUA9H8AAPg/AAAAkP8EUP8IAAAAEP4u498BAAAAAPXP/U8AAAAAALD//woAAAAAACD/
7wIAAAAAAAAAAAAAAAAAAAAAAAAAAAD3/88Atf6tBAD3/8+x////fwD3/8/7/////wT3//+PEvb//wr3//8JAID//w33//8CAFD/
/w/3/+8AAED//w/3/88AAED//w/3/88AAED//w/3/88AAED//w/3/88AAED//w/3/88AAED//w/3/88AAED//w/3/88AAED//w/3
/88AAED//w/3/88AAED//w8A//8PAAAAAAAAAAAAAP//DwAAAAAAAAAAAAD//w8AAAAAAAAAAAAA//8PAAAAAAAAAAAAIP//CgAA
AAAAAAAAAHD/7wEAAAAAAAAAAACw/18AwP//B3Hs3ikA8f8KAMD//zf9///vBPXvAQDA///p/////x4AAAAAwP//7xaR//9vAAAA
AMD//18AAPz/nwAAAADA//8NAAD5/78AAAAAwP//CgAA+f+/AAAAAMD//wgAAPj/vwAAAADA//8HAAD4/78AAAAAwP//BwAA+P+/
AAAAAMD//wcAAPj/vwAAAADA//8HAAD4/78AAAAAwP//BwAA+P+/AAAAAMD//wcAAPj/vwAAAADA//8HAAD4/78AAAAAwP//BwAA
+P+/9///AFDa7p0DAPf//zD9////bwD3///0//////8E9////v//////Dff///85EdX//0/3//9/AAAg//+P9///DAAAAPv/v/f/
/wYAAAD4/9/3//8CAAAA9//f9///AAAAAPb/7/f/7wAAAAD2/+/3/+8AAAAA9v/v9//vAAAAAPb/7/f/7wAAAAD2/+/3/+8AAAAA
9v/v9//vAAAAAPb/7/f/7wAAAAD2/+/3/+8AAAAA9v/v9//vAAAAAPb/7/f/7wAAAAD2/+/3/+8AAAAA9//f9//vAAAAAPn/zwAA
AAAAACD//68AAAAAABDU//9/AAAAAAD9////HgAAAAAA/f///wYAAAAAAP3//14AAAAAAAD93moBAPf/zwC1/q0DAPf/z7H///9v
APf/z/v/////Avf//48C9v//CPf//wkAgP//DPf//wIAUP//Dvf/7wAAQP//D/f/zwAAQP//D/f/zwAAQP//D/f/zwAAQP//D/f/
zwAAQP//D/f/zwAAQP//D/f/zwAAQP//D/f/zwAAQP//D/f/zwAAQP//D/f/zwAAQP//DwAAAAAAUP//DgAAAAAAcP//DAAAAAAQ
5P//CAAAAPT////vAQAAAPT///9OAAAAAPT/74wCAAAAAND/////BQAAAAAAAP3///9fAAAAAAAA0P////8FAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGHJ/t6LAwAAAAAQ6P//////TAAAACD8////////fwAAEP3/////////fwAA+///
fgJB+///TwD1//8+AAAA+f//DLD//18AAAAA/P//FP//3wAAAABg//+P9P//CQAAAADx//9s//9vAAAAAAD+/9/3//8FAAAAAND/
/37//18AAAAAAP3/7/b//wYAAAAA4P//Tf//nwAAAAAQ///P8f//DQAAAAD2//8I+///BQAAAMD//09Q///vAgAAkP//zwDA///v
JxC0////BADR//////////8HAADC/////////wcAAACB/v/////PBAAAAAAQpu3vvTgAAAAAAPT////vAAAAAED/////DgAAAAD0
////7wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABCm7e+cBAAAAHD+/////z0AAKD///////9PAHD/
/48Cw///LhD+/48AANH//wn1//8CAAD3/++Q//8NAABA//8/+v/PAAAA8///pP//DAAAMP//T/n/3wAAAPT//1P//x8AAHD//w7h
//8IABD9/58A9///KDD8/+8CAPr///////8EAADn/////98DAAAAYdr+zkkAAAAAAADzHwAA+wcAAAAAAAD9PCD5PwAAAAAAAED/
//+PAAAAAAAAADDq71sAAAAAAAAAAAAAAAAAAAAAAAAQluzvvTgAAAAAAIH+/////88EAAAAwv////////8HAADR//////////8H
ALD//+8nELT///8EUP//7wMAAJD//88A+///BQAAAMD//0/x//8NAAAAAPb//0j//58AAAAAEP//z/b//wYAAAAA4P//ff//XwAA
AAAA/f/v9///BQAAAADQ//9u//9vAAAAAAD+/9/0//8JAAAAAPH//xz//98AAAAAYP//j7D//18AAAAA/P//BPX//y4AAAD5//8M
APz//34CQfv//08AEP3/////////fwAAIPz///////9/AAAAEOj//////0wAAAAAAGHa/t6LAwAAAAAA+AoAEP8CAAAAQP8XMPsN
AAAAAKD///9PAAAAAABg7O86AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGHa/s5JAAAAAOf/////
3wMAAPr///////8EAPf//ygw/P/vAuH//wgAEP3/n1D//y8AAHD//w75/98AAAD0//+j//8MAAAw//9P+v/PAAAA8///lP//DQAA
QP//P/X//wEAAPf/7xD+/48AANH//wlw//+PAsP//y4AoP///////08AAHD+/////z0AAAAQpu3vnAQAAAAAAAD0/xv77wQAAAAA
ANH/CvfvBAAAAAAAoP8K8+8DAAAAAABg/wnR7wMAAAAAAAAAAAAAAAAAAAAAABCW7O+9OAAAAAAAgf7/////zwQAAADC////////
/wcAANH//////////wcAsP//7ycQtP///wRQ///vAwAAkP//zwD7//8FAAAAwP//T/H//w0AAAAA9v//SP//nwAAAAAQ///P9v//
BgAAAADg//99//9fAAAAAAD9/+/3//8FAAAAAND//27//28AAAAAAP7/3/T//wkAAAAA8f//HP//3wAAAABg//+PsP//XwAAAAD8
//8E9f//LgAAAPn//wwA/P//fgJB+///TwAQ/f////////9/AAAg/P///////38AAAAQ6P//////TAAAAAAAYdr+3osDAAAAAAAA
YP8K8v8DAAAAAP0uoP8IAAAAAPV/MP8NAAAAAMDfAPo/AAAAAFD/BPOPAAAAAAD8CrDfAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
Ydr+zkkAAAAA5//////fAwAA+v///////wQA9///KDD8/+8C4f//CAAQ/f+fUP//LwAAcP//Dvn/3wAAAPT//6P//wwAADD//0/6
/88AAADz//+U//8NAABA//8/9f//AQAA9//vEP7/jwAA0f//CXD//48Cw///LgCg////////TwAAcP7/////PQAAABCm7e+cBAAA
AAAAAAAAAAAAAAAAAAAAAAAAABCW3P7//////////38AADD6//////////////9/AAD4////////////////fwCg////////////
/////38A+f//71oSAPv/7wAAAAAAMP///ysAAAD7/+8AAAAAAKD//78AAAAA+//vAAAAAADg//8vAAAAAPv/7wAAAAAA9P//CgAA
AAD7/+8AAAAAAPb//wcAAAAA+////////w73//8FAAAAAPv///////8O9///BgAAAAD7////////Dvb//wcAAAAA+////////w70
//8KAAAAAPv/7wAAAAAA4P//LwAAAAD7/+8AAAAAAKD//78AAAAA+//vAAAAAAAw////KwAAAPv/7wAAAAAAAPj//+9aEgD7/+8A
AAAAAACg/////////////////88AAPj////////////////PAAAw+v//////////////zwAAABCW3P7//////////88AAAAAAAAA
AAAAAAAAAAAAAABh2v7OKAAwyP7eSQAAAADn/////5+R/////88CAAD6///////////////vAwD3//8oMPz///9NIPj/3wHh//8I
ABD9//8uAAD6/49Q//8vAABw//+PAABA//8O+f/fAAAA9P//BAAA8f//ov//DAAAMP//////////T/r/zwAAAPP//////////5X/
/w0AAED//////////2/1//8BAAD3//8EAAAAAAAQ/v+PAADR//+/AAAAAHEIcP//jwLD////vyUQY/qfAKD/////////////////
CQBw/v////87+///////nwAAEKbt74wDAJPs/96cNgEAAAAA9v8JAAAAAAAAAPP/CAAAAAAAAADB/wcAAAAAAAAAkP8HAAAAAAAA
AAAAAAAAAAAAQP/////vvScAAAD0////////nwAAQP////////+vAAD0/////////z8AQP//bwBB/f//CAD0//8GADD//68AQP//
bwAA8P//CgD0//8GAAD//58AQP//bwAA8///BQD0//8GENT//w0AQP////////8+AAD0///////vGQAAQP///////54BAAD0////
////zwAAQP//bxDE//+fAAD0//8GANH//z8AQP//bwAA9f//CgD0//8GAAD8//8DQP//bwAAQP//vwD0//8GAADA//8/QP//bwAA
APT//wv0//8GAAAA+///BAAAAADi/y0AAAAA++8DAAAAYP8+AAAAAOL/BQAAAAD8bwAAAABw/wcAAAAAAAAAAAAAAAAAAAAA9//P
AMf+Cvf/z8L//wr3/8/8//8K9///////Cvf//78UUQj3//8LAAAA9///AwAAAPf/7wAAAAD3/88AAAAA9//PAAAAAPf/zwAAAAD3
/88AAAAA9//PAAAAAPf/zwAAAAD3/88AAAAA9//PAAAAAPT/////3nsCAABA/////////wkAAPT/////////CgBA//////////8D
APT//wYQ1P//jwBA//9vAADz//8KAPT//wYAAP//rwBA//9vAADw//8JAPT//wYAMP//XwBA//9vAEH9/98AAPT////////vAwBA
////////ngEAAPT//////+8ZAABA/////////wwAAPT//wZB/P//CQBA//9vABD9//8DAPT//wYAUP//rwBA//9vAADA//8/APT/
/wYAAPT//wtA//9vAAAA/P//A/T//wYAAED//79A//9vAAAAsP//TwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD0/08AAAAAAAAA
kP9/AAAAAAAAAAD9rwAAAAAAAAAA888AAAAAAPf/zwDH/nr//yz8/6/3/8/8//96//////+v9///vxRReP//vwAAAPf//wMAAHD/
/w4AAAD3/88AAABw//8MAAAA9//PAAAAcP//DAAAAPf/zwAAAHD//wwAAAD3/88AAABw//8MAAAAAAAAAAAAAAAAAAAAALD/vwAA
ABD/3wEAAAD27wMAAACw/wUAAAAAAKDvAwDkjwAAAAAAwf8F978AAAAAAADi//vfAQAAAAAAAPT/7wIAAAAAAAAAAAAAAAAAAED/
////770nAAAA9P///////58AAED/////////rwAA9P////////8/AED//28AQf3//wgA9P//BgAw//+vAED//28AAPD//woA9P//
BgAA//+fAED//28AAPP//wUA9P//BhDU//8NAED/////////PgAA9P//////7xkAAED///////+eAQAA9P///////88AAED//28Q
xP//nwAA9P//BgDR//8/AED//28AAPX//woA9P//BgAA/P//A0D//28AAED//78A9P//BgAAwP//P0D//28AAAD0//8L9P//BgAA
APv//wRw/wQAsN8BwO8CgP8FAPPPUf8LAAD5v/4uAAAQ/f9/AAAAUP/PAAAAAAAAAAAAAAAAAAAA9//PAMf+ev//LPz/r/f/z/z/
/3r//////6/3//+/FFF4//+/AAAA9///AwAAcP//DgAAAPf/zwAAAHD//wwAAAD3/88AAABw//8MAAAA9//PAAAAcP//DAAAAPf/
zwAAAHD//wwAAAAAAAAA9v8JAAAAAAAw/48AAAAAAADB/wcAAAAAAAD5fwAAAAAAAAAAAAAAAAAAEKbt7816FAAA5v//////7wBw
/////////wDy/////////wD4//8nAELY/wD7/48AAAAAtAD8/18AAAAAAAD8/68AAAAAAAD5//99FAAAAADz/////60WAACA////
////GQAA5///////7wIAELf//////wwAAAAwpv7//y8AAAAAAJH//18AAAAAACD//2+IAgAAAED//0/6z0cSIOb//x/6////////
/wv6////////7wLW////////LAAAYrnt785JAAAAAAAAIP7fAgAAAACw/z4AAAAAAPbvAwAAAAAg/l8AAAAAAMD/BgAAAAAA938A
AAAAAAAAAAAAAAAAAAAAAAAAAGDa/t6cNwAw/f//////BdD///////8F9P/PEyCl/wX2/08AAACBBfb/jwAAAAAA8v//vnkVAACA
//////9sAAC1//////8JAABBhur//y8AAAAAAPz/b5MCAAAA+f9v8682AWL//0/z////////DPP//////88CIJXb/u+cBAAAAFD/
/x0AAAAAAOP//M8AAAAAEP1OgP8JAAAAsN8CAPZ/AAAAAAAAAAAAAAAAEKbt7816FAAA5v//////7wBw/////////wDy////////
/wD4//8nAELY/wD7/48AAAAAtAD8/18AAAAAAAD8/68AAAAAAAD5//99FAAAAADz/////60WAACA////////GQAA5///////7wIA
ELf//////wwAAAAwpv7//y8AAAAAAJH//18AAAAAACD//2+IAgAAAED//0/6z0cSIOb//x/6/////////wv6////////7wLW////
////LAAAYrnt785JAAAAAED/3wAAAAAA0P//CAAAAAD4z/4vAAAAIP8d9b8AAACw7wNw/wYAAPZfAAD6HgAAAAAAAAAAAAAAAAAA
AAAAAGDa/t6cNwAw/f//////BdD///////8F9P/PEyCl/wX2/08AAACBBfb/jwAAAAAA8v//vnkVAACA//////9sAAC1//////8J
AABBhur//y8AAAAAAPz/b5MCAAAA+f9v8682AWL//0/z////////DPP//////88CIJXb/u+cBAAAEKbt7816FAAA5v//////7wBw
/////////wDy/////////wD4//8nAELY/wD7/48AAAAAtAD8/18AAAAAAAD8/68AAAAAAAD5//99FAAAAADz/////60WAACA////
////GQAA5///////7wIAELf//////wwAAAAwpv7//y8AAAAAAJH//18AAAAAACD//2+IAgAAAED//0/6z0cSIOb//x/6////////
/wv6////////7wLW////////LAAAYrnt785JAAAAAAAA+gcAAAAAAAAA8j8AAAAAAAAAsJ8AAAAAAAAA468AAAAAAOD//28AAAAA
AOD/zgcAAAAAYNr+3pw3ADD9//////8F0P///////wX0/88TIKX/Bfb/TwAAAIEF9v+PAAAAAADy//++eRUAAID//////2wAALX/
/////wkAAEGG6v//LwAAAAAA/P9vkwIAAAD5/2/zrzYBYv//T/P///////8M8///////zwIgldv+75wEAAAAAHCvAAAAAAAAAP0F
AAAAAAAA+AwAAAAAACD8DQAAAAD7//8JAAAAAPv/jQEAAACg7wMA5I8AAAAQ/F9w/wsAAAAA4v/73wEAAAAAQP//LgAAAAAAAAAA
AAAAAAAQpu3vzXoUAADm///////vAHD/////////APL/////////APj//ycAQtj/APv/jwAAAAC0APz/XwAAAAAAAPz/rwAAAAAA
APn//30UAAAAAPP/////rRYAAID///////8ZAADn///////vAgAQt///////DAAAADCm/v//LwAAAAAAkf//XwAAAAAAIP//b4gC
AAAAQP//T/rPRxIg5v//H/r/////////C/r////////vAtb///////8sAABiue3vzkkAAAD2XwAA+h4AALDvAnD/BgAAIP8d9L8A
AAAA+L/+LwAAAADQ//8IAAAAAED/3wAAAAAAAAAAAAAAAAAAAAAAAAAAYNr+3pw3ADD9//////8F0P///////wX0/88TIKX/Bfb/
TwAAAIEF9v+PAAAAAADy//++eRUAAID//////2wAALX//////wkAAEGG6v//LwAAAAAA/P9vkwIAAAD5/2/zrzYBYv//T/P/////
//8M8///////zwIgldv+75wEAP3////////////U////////////T/3////////////U////////////TwAAAJD//x8AAAAAAAAA
+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD/
/x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//
AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAAAg3wEAAAAAAAAAAICvAAAAAAAAAAAA8y8AAAAAAAAAAJH/AwAAAAAAAPb//w0A
AAAAAABg/+86AAAAAADw//8EAAAA8P//BAAAAPD//wQAAADw//8EAAAA8P//BAAA+f//////r/n//////6/5//////+vAPD//wQA
AADw//8EAAAA8P//BAAAAPD//wQAAADw//8EAAAA8P//BAAAAPD//wQAAADw//8EAAAA4P//BQAAAND//ysAAACA/////z8AEP3/
//8/AACB7P//PwAAANFPAAAAAABQ3wEAAAAAAP8FAAAAAGD/BgAAIP///wIAACD/70wAAAAA0c8BAPdfAAAAAADi3wP6fwAAAAAA
APTv/K8AAAAAAAAA9//PAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP3////////////U////////////T/3////////////U////
////////TwAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD/
/x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//
AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAAAA8f8eAAAAAADz/wkAAAAAAPb/AwDw//8E
+c8AAPD//wT8bwAA8P//BP8eAADw//8EAAAAAPD//wQAAAD5//////+vAPn//////68A+f//////rwAA8P//BAAAAADw//8EAAAA
APD//wQAAAAA8P//BAAAAADw//8EAAAAAPD//wQAAAAA8P//BAAAAADw//8EAAAAAOD//wUAAAAA0P//KwAAAACA/////z8AABD9
////PwAAAIHs//8/AP3////////////U////////////T/3////////////U////////////TwAAAJD//x8AAAAAAAAA+f//AQAA
AAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAw////////CgAAAPP//////68AAAAw////////CgAA
APP//////68AAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAA
AJD//x8AAAAAAAAA+f//AQAAAADw//8EAAAA8P//BAAAAPD//wQAAADw//8EAAAA8P//BAAA+f//////r/n//////6/5//////+v
APD//wQAAADw//8EAAD5//////+v+f//////r/n//////6/5//////+vAPD//wQAAADw//8EAAAA4P//BQAAALD//ywAAABg////
/z8AAPv///8/AABw6///PwAAAOeNAcA/AAAAAGD//z3zHwAAAACwf6L//wsAAAAA0C8Axb4BAAAAAAAAAAAAAAAA9P//BgAAAP//
n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8G
AAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/P//wYAABD//5/y//8HAAAg//+P8f//CgAAUP//
b8D//y8AALD//y9g///fFDD6//8MEP3/////////BADj////////fwAAIPz/////7wUAAAAwyO7vnAUAAAAAcM4CAO0CAABA/88A
4B8AAAD6WI8Q7wAAANAvcF/3CwAAAP8BsP9fAAAA4A4AsY4AAAAAAAAAAAAAAAAAAAAAAAAA+v+fAABg//+t//8JAAD2/9/6/58A
AGD//63//wkAAPb/3/r/nwAAYP//rf//CQAA9v/f+v+fAABg//+t//8JAAD2/9/6/58AAHD//63//wkAAPj/3/n/rwAAwP//jf//
DQBA///f9f//GlH+//8N/f///+/5/98w/v//32P//w0QyO6MAfb/3wAAYP////8MAAAAAGD/////DAAAAABg/////wwAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPT//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f
9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYA
AAD//5/z//8GAAAQ//+f8v//BwAAIP//j/H//woAAFD//2/A//8vAACw//8vYP//3xQw+v//DBD9/////////wQA4////////38A
ACD8/////+8FAAAAMMju75wFAAAAAP////8/AAAA8P////8DAAAA/////z8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAKD//wkAAPb/3/r/nwAAYP//rf//CQAA9v/f+v+fAABg//+t//8JAAD2/9/6/58AAGD//63//wkAAPb/3/r/nwAAYP//rf//
CQAA9//f+v+fAACA//+d//8KAAD8/9/4/98AAPT//13//68R5f//39D/////nv//DeP///899v/fAIHszhhg//8NAACgnwAA8w8A
AAAAUP8XQf0KAAAAAAD6///vAgAAAAAAYOzfKQAAAAAAAAAAAAAAAAD0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8G
AAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//
n/T//wYAAAD//5/0//8GAAAA//+f8///BgAAEP//n/L//wcAACD//4/x//8KAABQ//9vwP//LwAAsP//L2D//98UMPr//wwQ/f//
//////8EAOP///////9/AAAg/P/////vBQAAADDI7u+cBQAAAAD8BgBQ7wAAAIDvFUH9CgAAANH///8uAAAAAIH93xkAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD6/58AAGD//63//wkAAPb/3/r/nwAAYP//rf//CQAA9v/f+v+fAABg//+t//8J
AAD2/9/6/58AAGD//63//wkAAPb/3/r/nwAAcP//rf//CQAA+P/f+f+vAADA//+N//8NAED//9/1//8aUf7//w39////7/n/3zD+
///fY///DRDI7owB9v/fAAAAEOnPBQAAAAAAANH//38AAAAAAAD5PYH/AgAAAAAA/QYA/gYAAAAAAP0GAP4GAAAAAAD5PYH/AgAA
9P//1///j///n/T//xbpzwX//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYA
AAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/P//wYAABD//5/y//8HAAAg//+P
8f//CgAAUP//b8D//y8AALD//y9g///fFDD6//8MEP3/////////BADj////////fwAAIPz/////7wUAAAAwyO7vnAUAAAAAAMXv
GQAAAAAA+P//HQAAAADyjzH+CQAAAGDfAHDfAAAAAPYNAPcNAAAAIP8Y458AAAAAgP//3wEAAAAAYPyeAQAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAKD//wkAAPb/3/r/nwAAYP//rf//CQAA9v/f+v+fAABg//+t//8JAAD2/9/6/58AAGD//63//wkAAPb/3/r/
nwAAYP//rf//CQAA9//f+v+fAACA//+d//8KAAD8/9/4/98AAPT//13//68R5f//39D/////nv//DeP///899v/fAIHszhhg//8N
AAAAwP9O9f8KAAAAAPjvI/6fAAAAAED/PrD/CQAAAADR7wL3jwAAAAAAAAAAAAAAAAD0//8GAAAA//+f9P//BgAAAP//n/T//wYA
AAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f
9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f8///BgAAEP//n/L//wcAACD//4/x//8KAABQ//9vwP//LwAAsP//L2D//98U
MPr//wwQ/f////////8EAOP///////9/AAAg/P/////vBQAAADDI7u+cBQAAAAAA4e8C+58AAABw/wf03wEAABD+DcD/BAAAAPdP
QP8JAAAA0K8A/B0AAABg7wL1TwAAAAAAAAAAAAAAAAAAAAAAAAD6/58AAGD//63//wkAAPb/3/r/nwAAYP//rf//CQAA9v/f+v+f
AABg//+t//8JAAD2/9/6/58AAGD//63//wkAAPb/3/r/nwAAcP//rf//CQAA+P/f+f+vAADA//+N//8NAED//9/1//8aUf7//w39
////7/n/3zD+///fY///DRDI7owB9v/f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0
//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAAAP//n/T//wYAAAD//5/0//8GAAAA//+f9P//BgAA
AP//n/P//wYAABD//5/y//8HAAAg//+P8f//CgAAUP//b8D//y8AALD//y9g///fFDD6//8MEP3/////////BADj////////fwAA
IPz/////7wUAAAAwyO7vnAUAAAAAAAD0HQAAAAAAAAAQ/QQAAAAAAAAAUO8AAAAAAAAAAGD/BQAAAAAAAAAw///PAAAAAAAAAMT+
zwAAAPr/nwAAYP//DQD6/58AAGD//w0A+v+fAABg//8NAPr/nwAAYP//DQD6/58AAGD//w0A+v+fAABg//8NAPr/nwAAYP//DQD6
/58AAGD//w0A+v+fAABw//8NAPr/nwAAgP//DQD5/68AAMD//w0A+P/fAAD0//8NAPX//xpR/v//DQDQ/////57//w0AMP7//99j
//8NAACB7M4YYP//DQAAAAAAAAAA+AkAAAAAAAAAQO8BAAAAAAAAAKCvAAAAAAAAAACw3wIAAAAAAAAAcP//fwAAAAAAAADX/38A
AAAAAAAw/v8/AAAAAAAAAAAAAAAAEP3P/y4AAAAAAAAAAAAAAAD7b2D/DAAAAAAAAAAAAAAA+U4AQP4KAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAADw//8GAABA//9vAAAA9f//Afv/rwAAAPj//wkAAID//wyA//8NAACw///fAAAA/P+fAPT/
/wIAAP///x8AAPH//wUQ//9fAADz////BQBA//8fAMD//wkAcP/f/48AAPj/3wAA+f/fAAD7//b/DACw//8JAFD//x8A4P8f/v8B
AP7/bwAA8f//BTD/z7D/TwDz//8CAAD9/48A9v8I9/8HcP//DgAAkP//DKD/XzD/vwD6/68AAAD2//8B/f8B8P8O4P//BwAAIP//
T/L/DAD7/yP//z8AAADg//9X/58AgP9v9v//AAAAAPr/v/n/BQD0/6r//wsAAABw///O/y8AEP/v/f+PAAAAAPP////fAADA////
/wQAAAAA/v///woAAPn///8fAAAAALD///9vAABQ////zwAAAAAA+P///wMAAPH///8JAAAAAED///8OAAAA/f//XwAAAAAA8f//
vwAAAJD///8CAAAAAAAAAPP/HQAAAAAAAAAAAAD8/48AAAAAAAAAAABw/+z/AwAAAAAAAAAA4t9B/wwAAAAAAAAAAPs/APd/AAAA
AAAAAFD/BQCg7wIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPz/TwAA9/8/AAD4/4/4/48AAPv/fwAA/P9P9P/PAAD+/68A
EP//DuD//wEw///vAFD//wuw//8EcP///wOA//8HcP//CLD//P8HwP//AzD//wzg/8f/CvH/7wAA/v8f8/+D/w71/68AAPr/T/fv
QP8/+f9vAAD2/4/7vxD/f/z/LwAA8v/P/n8A+8///w0AAND///8/APj///8JAACQ////DgD0////BAAAUP///wsA8P///wEAABD/
//8HALD//78AAAAA+///AwCA//9/AAAAAAAAwP//CAAAAAAAAACQ/+3/BQAAAAAAAHD/GtLvAwAAAAAAQP8IALHfAQAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAADh//8/AAAAAPf//wr1//8MAAAA8v//HgD6//8HAACw//9vABD+/+8CAGD//78AAFD//78AEP7/7wIA
AKD//28A+v//BgAAAOL//x70//8LAAAAAPb//9r//y4AAAAAAPv/////fwAAAAAAIP7////PAAAAAAAAYP////8DAAAAAAAAsP//
/wcAAAAAAAAA8v//DQAAAAAAAAAA/v+vAAAAAAAAAADg//8KAAAAAAAAAAD+/68AAAAAAAAAAOD//woAAAAAAAAAAP7/rwAAAAAA
AAAA4P//CgAAAAAAAAAA/v+vAAAAAAAAAADg//8KAAAAAAAAAAD+/68AAAAAAAAAYP+/AAAAAAAAEP7/bwAAAAAAAPq//x4AAAAA
APTPYP8KAAAAANDfAZD/BAAAAID/AwDA3wAAAAAAAAAAAAAAAAAAAAAAAAAAAPb/zwAAAGD//xz+/z8AAAD7/2+A//8JAADy//8B
8v/vAQBw//8KAPr/fwAA/P9PADD//w0A8v/fAADA//8EcP//BwAA9f+vAPz/HwAAAP3/H/P/rwAAAHD//4f//wQAAADh/9/9/w0A
AAAA+f///38AAAAAIP////8CAAAAALD///8LAAAAAAD0//9fAAAAAAAA/P/fAAAAAAAAcP//CAAAAAAAAPr/LwAAAAAAEPf/rwAA
AAAA////7wIAAAAA8P//7wQAAAAAAP/vjAIAAAAAAAAAsP8K8P8HAAAAAAAA+68A/38AAAAAAACw/wrw/wcAAAAAAAD7rwD/fwAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA4f//PwAAAAD3//8K9f//DAAAAPL//x4A+v//BwAAsP//bwAQ/v/vAgBg//+/AABQ//+/
ABD+/+8CAACg//9vAPr//wYAAADi//8e9P//CwAAAAD2///a//8uAAAAAAD7/////38AAAAAACD+////zwAAAAAAAGD/////AwAA
AAAAALD///8HAAAAAAAAAPL//w0AAAAAAAAAAP7/rwAAAAAAAAAA4P//CgAAAAAAAAAA/v+vAAAAAAAAAADg//8KAAAAAAAAAAD+
/68AAAAAAAAAAOD//woAAAAAAAAAAP7/rwAAAAAAAAAA4P//CgAAAAAAAAAA/v+vAAAAAAAAAABg/58AAAAAAAAA8/8IAAAAAAAA
EPx/AAAAAAAAAJD/BwAAAAAAAAAAAAAAAAAA9f//////////H/X//////////x/1//////////8f9f//////////DgAAAAAAUP//
/wQAAAAAAOP//28AAAAAABD9//8JAAAAAACw///PAAAAAAAA+P//LgAAAAAAYP///wMAAAAAAPP//28AAAAAABD9//8JAAAAAADA
//+/AAAAAAAA+f//HQAAAAAAYP//7wMAAAAAAPT//18AAAAAACD+//8IAAAAAADB//+/AAAAAAAA+P//////////b/r/////////
/2/6//////////9v+v//////////bwAAAAAg/t8CAAAAALD/PgAAAAAA9u8DAAAAACD+XwAAAAAAwP8GAAAAAAD3fwAAAAAAAAAA
AAAAAAAAAAAAAAD0////////D/T///////8P9P///////w8AAAAA9///DwAAAGD///8FAAAA9f//bwAAAFD///8HAAAA9P//jwAA
ADD+//8JAAAA4///rwAAACD+//8LAAAA0v//vwEAAAD5//8cAAAAAPr///////8P+v///////w/6////////DwAAAGD/nwAAAAAA
AABg/58AAAAAAAAAYP+fAAAAAAAAAGD/nwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD1//////////8f9f//////
////H/X//////////x/1//////////8OAAAAAABQ////BAAAAAAA4///bwAAAAAAEP3//wkAAAAAALD//88AAAAAAAD4//8uAAAA
AABg////AwAAAAAA8///bwAAAAAAEP3//wkAAAAAAMD//78AAAAAAAD5//8dAAAAAABg///vAwAAAAAA9P//XwAAAAAAIP7//wgA
AAAAAMH//78AAAAAAAD4//////////9v+v//////////b/r//////////2/6//////////9vAADQ//8FAAAAAND//wUAAAAA0P//
BQAAAADQ//8FAAAAAND//wUAAAAA0P//BQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA9P///////w/0////////D/T///////8P
AAAAAPf//w8AAABg////BQAAAPX//28AAABQ////BwAAAPT//48AAAAw/v//CQAAAOP//68AAAAg/v//CwAAANL//78BAAAA+f//
HAAAAAD6////////D/r///////8P+v///////w8AAPlOAED+CgAAAACw/wb1zwAAAAAAEP2//y4AAAAAAADj//8DAAAAAAAAAAAA
AAAAAPX//////////x/1//////////8f9f//////////H/X//////////w4AAAAAAFD///8EAAAAAADj//9vAAAAAAAQ/f//CQAA
AAAAsP//zwAAAAAAAPj//y4AAAAAAGD///8DAAAAAADz//9vAAAAAAAQ/f//CQAAAAAAwP//vwAAAAAAAPn//x0AAAAAAGD//+8D
AAAAAAD0//9fAAAAAAAg/v//CAAAAAAAwf//vwAAAAAAAPj//////////2/6//////////9v+v//////////b/r//////////28A
908AAPsdAADA7wKA/wUAADD/DPWvAAAAAPm//y4AAAAA4f//BwAAAABQ/88AAAAAAAAAAAAAAAAAAAAAAAAA9P///////w/0////
////D/T///////8PAAAAAPf//w8AAABg////BQAAAPX//28AAABQ////BwAAAPT//48AAAAw/v//CQAAAOP//68AAAAg/v//CwAA
ANL//78BAAAA+f//HAAAAAD6////////D/r///////8P+v///////w8AADDZ/v9fAAD2////XwAg/////18AgP//LAAAALD//wcA
AADA//8GAAAAwP//BgAA9v///wYAAPb///8GAAD2////BgAAAMD//wYAAADA//8GAAAAwP//BgAAAMD//wYAAADA//8GAAAAwP//
BgAAAMD//wYAAADA//8GAAAAwP//BgAAAMD//wYAAADA//8GAAAAwP//BgAAAMD//wYAAAAAAAD+//8vAAAAAAAAAFD///+PAAAA
AAAAAKD////fAAAAAAAAAPH/////BAAAAAAAAPb/////CQAAAAAAAPz/z///HgAAAAAAIP//P/7/XwAAAAAAgP//DPn/vwAAAAAA
0P//B/T//wIAAAAA9P//AuD//wcAAAAA+f/PAJD//w0AAAAQ/v9/AED//z8AAABQ//8vAAD9/58AAACw//8MAAD4/+8AAADy////
//////8FAAD3//////////8KAAD8//////////8fADD///////////9vAJD//x8AAAAA/P/PAOD//woAAAAA9///AvX//wUAAAAA
8v//CPr/7wEAAAAAwP//DfT/////3osDAED/////////GgD0/////////wxA//////////8G9P//BgCi//+vQP//bwAA4f//DPT/
/wYAAPz/z0D//28AAOH//wr0//8GAKL//19A/////////68A9P///////38AQP////////9+APT/////////n0D//28AEMT//z/0
//8GAADy//9I//9vAAAA/v+v9P//BgAA8v//Sv//bwAQxP//j/T//////////0T//////////wn0/////////whA///////eegIA
9P////////9E/////////0/0/////////0T/////////T/T//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAA
AED//28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//bwAA
AAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED//28AAAAAAAAAAAD+//8vAAAAAAAAAFD///+PAAAAAAAAAKD////fAAAAAAAA
APH/////BAAAAAAAAPb/////CQAAAAAAAPz/v///HgAAAAAAIP//P/7/XwAAAAAAgP//DPn/vwAAAAAA0P//B/T//wIAAAAA9P//
AuD//wcAAAAA+f/PAJD//w0AAAAQ/v9/AED//z8AAABQ//8vAAD+/58AAACw//8MAAD5/+8AAADy//8HAAD1//8FAAD3//8CAADg
//8KAAD8/88AAACg//8fADD//38AAABQ//9vAJD////////////PAOD/////////////AvX/////////////CPr/////////////
DfT/////////QP////////8P9P////////9A/////////w/0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P//BgAA
AABA/////////wb0////////b0D/////////BvT///////9vQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED//28A
AAAAAPT/////////RP////////9P9P////////9E/////////0/1//////////8f9f//////////H/X//////////x/1////////
//8OAAAAAABQ////BAAAAAAA4///bwAAAAAAEP3//wkAAAAAALD//88AAAAAAAD4//8uAAAAAABg////AwAAAAAA8///bwAAAAAA
EP3//wkAAAAAAMD//78AAAAAAAD5//8dAAAAAABg///vAwAAAAAA9P//XwAAAAAAIP7//wgAAAAAAMH//78AAAAAAAD4////////
//9v+v//////////b/r//////////2/6//////////9v9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f
9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X///////////9f9P///////////0X/
//////////9f9P///////////0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//
BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9fAAAAYcn+3osDAAAAABDo//////9MAAAAIPz///////9/AAAQ
/f////////9/AAD7//9+AkH7//9PAPX//z4AAAD5//8MsP//XwAAAAD8//8U///fAAAAAGD//4/0//8JAAAAAPH//2z//2/w////
CP7/3/f//wX///+P0P//fv//X/D///8I/f/v9v//Bv///4/g//9N//+fAAAAABD//8/x//8NAAAAAPb//wj7//8FAAAAwP//T1D/
/+8CAACQ///PAMD//+8nELT///8EANH//////////wcAAML/////////BwAAAIH+/////88EAAAAABCm7e+9OAAAAPT//0b//2/0
//9G//9v9P//Rv//b/T//0b//2/0//9G//9v9P//Rv//b/T//0b//2/0//9G//9v9P//Rv//b/T//0b//2/0//9G//9v9P//BgAA
IP3//wlA//9vAAAg/f//CAD0//8GACD9//8IAED//28AIP3//wgAAPT//wYg/f//CAAAQP//byD9//8IAAAA9P//Jv7//wgAAABA
//+P/v//CAAAAAD0//////8HAAAAAED//////wcAAAAAAPT/////DAAAAAAAQP//////CQAAAAAA9P//////CQAAAABA///P////
CQAAAAD0//92////CQAAAED//29w////CQAAAPT//wZg////CQAAQP//bwBg////CQAA9P//BgBg////CgBA//9vAABg////CgD0
//8GAABg////CkD//28AAABg////CgAAAAD+//8vAAAAAAAAAFD///+PAAAAAAAAAKD////fAAAAAAAAAPH/////BAAAAAAAAPb/
////CQAAAAAAAPz/v///HgAAAAAAIP//L/7/XwAAAAAAgP//DPn/vwAAAAAA0P//B/T//wIAAAAA9P//AtD//wcAAAAA+f/PAID/
/w0AAAAQ/v9vADD//z8AAABQ//8fAAD9/58AAACw//8LAAD4/+8AAADy//8GAADz//8FAAD3//8BAADQ//8KAAD8/78AAABw//8f
ADD//18AAAAg//9vAJD//x8AAAAA/P/PAOD//woAAAAA9///AvX//wUAAAAA8v//CPr/7wEAAAAAwP//DfT///8CAAAAQP///x/0
////CAAAALD///8f9P///x4AAADy////H/T///9vAAAA+P///x/0////zwAAEP7///8f9P////8DAGD/////H/T///z/CgDA/8//
/x/0///1/x8A9P9v//8f9P//0f9/APr/Sv//H/T//2H/3xD//0T//x/0//8R/v91/99A//8f9P//Afn/2/9/QP//H/T//wHz////
HkD//x/0//8BsP///wlA//8f9P//AVD///8DQP//H/T//wEA/f+/AED//x/0//8BAPf/XwBA//8f9P//AQDx/w4AQP//H/T//wEA
AAAAAED//x/0//8BAAAAAABA//8f9P//AQAAAAAAQP//H/T//wEAAAAAAED//x/0//9fAAAA8P//Rf///wwAAAD//1/0////BQAA
8P//Rf///98AAAD//1/0////bwAA8P//Rf////8eAAD//1/0/////wcA8P//Rf//r//vAQD//1/0///j/48A8P//Rf//H/j/HgD/
/1/0//8R/v8J8P//Rf//H3D//wL//1/0//8B4f+f8P//Rf//HwD2/z///1/0//8BAP3/+v//Rf//HwBg/////1/0//8BAMD/////
Rf//HwAA9f///1/0//8BAAD8////Rf//HwAAQP///1/0//8BAACw////Rf//HwAAAPP//1/x////////F////////3/x////////
F////////38AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAID/////3wAA+P////8NAID/////3wAA+P////8N
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADx////////F////////3/x////////F////////38AAABhyf7e
iwMAAAAAEOj//////0wAAAAg/P///////38AABD9/////////38AAPv//34CQfv//08A9f//PgAAAPn//wyw//9fAAAAAPz//xT/
/98AAAAAYP//j/T//wkAAAAA8f//bP//bwAAAAAA/v/f9///BQAAAADQ//9+//9fAAAAAAD9/+/2//8GAAAAAOD//03//58AAAAA
EP//z/H//w0AAAAA9v//CPv//wUAAADA//9PUP//7wIAAJD//88AwP//7ycQtP///wQA0f//////////BwAAwv////////8HAAAA
gf7/////zwQAAAAAEKbt7704AAAA9P///////////0X///////////9f9P///////////0X///////////9f9P//BgAAAPT//0X/
/28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//
BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28A
AABA//9f9P//BgAAAPT//0X//28AAABA//9f9P/////vnAQAQP////////88APT/////////PkD//////////w30//8GAHL///9F
//9vAABw//+f9P//BgAA8v//S///bwAAIP//v/T//wYAAPf//0n//28AIPf//1/0/////////99A/////////+8D9P///////88D
QP//////zkkAAPT//wYAAAAAAED//28AAAAAAAD0//8GAAAAAABA//9vAAAAAAAA9P//BgAAAAAAQP//bwAAAAAAAPT//wYAAAAA
AED//28AAAAAAAD4////////j/j///////+P+AMAAAAAMI/4AwAAAAAwj/gDAAAAADCP+AMAAAAAMI/4AwAAAAAwj/gDAAAAADCP
+AMAAAAAMI/4AwAAAAAwj/gDAAAAADCP+AMAAAAAMI/4AwAAAAAwj/gDAAAAADCP+AMAAAAAMI/4AwAAAAAwj/gDAAAAADCP+AMA
AAAAMI/4AwAAAAAwj/gDAAAAADCP+AMAAAAAMI/4AwAAAAAwj/gDAAAAADCP+AMAAAAAMI/4////////j/j///////+P9P//////
//9A/////////w/0/////////0D/////////D8H//xoAAAAAALH//xwAAAAAAJD//y0AAAAAAHD//04AAAAAAFD//28AAAAAAED+
/48AAAAAAID//y4AAAAAYP//PgAAAABg//8+AAAAAFD//04AAAAAUP//TwAAAABA//9fAAAAAED+/18AAAAAIP7/bwAAAAAA9P//
//////9E/////////0/0/////////0T/////////T/3////////////U////////////T/3////////////U////////////TwAA
AJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA
+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAAAAAJD/
/x8AAAAAAAAA+f//AQAAAAAAAJD//x8AAAAAAAAA+f//AQAAAOH//z8AAAAA9///CvX//wwAAADy//8eAPr//wcAALD//28AEP7/
7wIAYP//vwAAUP//vwAQ/v/vAgAAoP//bwD6//8GAAAA4v//HvT//wsAAAAA9v//2v//LgAAAAAA+/////9/AAAAAAAg/v///88A
AAAAAABg/////wMAAAAAAACw////BwAAAAAAAADy//8NAAAAAAAAAAD+/68AAAAAAAAAAOD//woAAAAAAAAAAP7/rwAAAAAAAAAA
4P//CgAAAAAAAAAA/v+vAAAAAAAAAADg//8KAAAAAAAAAAD+/68AAAAAAAAAAOD//woAAAAAAAAAAP7/rwAAAAAAAAAA8f//CQAA
AAAAAAAQ//+fAAAAAAAAEKb+///POAAAAABw/v//////vwIAALD/////////7wQAsP///////////wRg///v9v//qv//3wD9//8U
//+fwP//X/P//wvx//8J9P//Wv//fxD//58A///f9///BfH//wnQ//9+//9fEP//nwD9/+/1//8H8f//CfD//z3//78Q//+fQP//
r9D//0/x//8J/P//Bfb//27//6/6//8NAPv//////////08AAPv/////////TgAAAOf///////8rAAAAAGHq////jAMAAAAAAADx
//8JAAAAAAAAABD//58AAAAAwP//LgAAABD+/98B8v//CwAAAPr//wMA9///BwAA9v//CAAA+//vAgDi//8MAAAg/v/PALD//z8A
AABg//9/YP//jwAAAACw//9P/v/PAAAAAADi//////8DAAAAAAD2/////wcAAAAAAAD7////DAAAAAAAABD+//8vAAAAAAAAAPX/
//8GAAAAAAAA4f///+8CAAAAAACg/////88AAAAAAFD//8///38AAAAAIP7/37H//y8AAAAA+///A+L//wwAAAD2//8IAPb//wcA
AOL//wwAAPv//wMAsP//PwAAIP7/zwBg//9/AAAAYP//jyD+/88AAAAAoP//P/X//wXx//8JwP//Xf//XxD//58A/P/f9f//BfH/
/wnA//9d//9fEP//nwD8/9/1//8F8f//CcD//13//18Q//+fAPz/3/T//wXx//8JwP//PP//bxD//58A/f+/8f//B/H//wng//8J
/f+fEP//nxD//2+Q//8N8f//Cfb//wLy//8X//+f0f//CgD5/+/0//+p//8/ABD9/////////38AACD9////////jwAAACD7////
//9vAAAAAAC1/v//3ykAAAAAAAAQ//+fAAAAAAAAAADx//8JAAAAAAAAABD//58AAAAAAAAAAPH//wkAAAAAAAAAEP//nwAAAAAA
AAAQlezvvTcAAAAAAABw/v////+/AwAAAADB/////////wYAAADR//////////8GAACw///vKBDF////AwBA///vAwAAoP//zwAA
+///BgAAAND//08A8f//DQAAAAD2//8IUP//nwAAAAAQ///PAPb//wYAAAAA4P//DnD//18AAAAAAP3//wD2//8GAAAAAOD//w5Q
//+PAAAAABD//88A8f//DAAAAAD0//8JAPv//wMAAACg//8/ADD//78AAAAw//+vAABw//9/AAAQ/f/fAQAAUP7/jwAg/f+/AQDz
/////w0A9f////86/////98AUP////+v8/////8NAPX/////Ov/////fAFD/////rwAApe3vfIH/7wEw/f///9/+/wow/v//////
/18A/P/vFPX//+8A8v//BgD5//8KUP//DgBQ//9PAPf/zwAA8v/vAID//wsAAP//CQD4/78AAPP/bwBw//8LAID//wgA9f/vAAD8
/78AEP//TwDz//8OALD//z3B////BgDz/////////18A9v/////c//8FAILs/94Jgf1fAABg2v+MAgAAAADT/////wgAAAD0////
//8JAADi/98T5P//AwCg//8EAPb/jwAQ//8PABD//woA9P/fAADx/78AYP//DABA//8IAPf/zwAA+v8/AHD//wxB+v9/AAD3/8+g
//9eAABw//8M+v//rwIA9//PoP///+8EcP//DBCU///vAvf/zwAAYP//r3D//wwAAMD//w73/98AAAD4//9x//8vAACA//8f9///
CQAA/f/fcP///ygw+///B/f/3/3/////HHD//yz8////LAD3/88Axv6tBQBw//8MAAAAAAAA9//PAAAAAAAAcP//DAAAAAAAAPf/
zwAAAAAAAHD//wwAAAAAAAD3/88AAAAAAAAA+O9KAAAAAPf/z/j//woAAAD8/2/4//9vAAAw//8OAOX/3wAAgP//CABw//8FAOD/
/wIAEP//CwD0/68AAAD6/x8A+v9PAAAA9P9/EP//DQAAAND/z2D//wYAAACA///C/+8BAAAAIP//+v+fAAAAAAD7////PwAAAAAA
9f///wsAAAAAAOD///8FAAAAAACA///fAAAAAAAAIP//fwAAAAAAAAD+/08AAAAAAAAA/v9PAAAAAAAAAP7/TwAAAAAAAAD+/08A
AAAAAAAA/v9PAAAAAAAAAP7/TwAAAAAAYdr+3nsBAAAA5f/////vBQAA8///////7wAAkP//KRBS6A4AAPv/HwAAAJEAAKD//wQA
AAAAAAD1//85AAAAAAAA+P///4wDAAAAQP7/////OwAAYP//3////18AQP//PhDV//8/AP3/bwAA4v//C/X//wEAAPf//5H//wwA
ADD//z/6/78AAADy//+l//8LAAAw//9P+P/fAAAA9P//Q///LwAAkP//DtD//wkAEP7/nwD1//8pQPz/7wEA+P//////7wMAAOX/
////zwIAAABh2v7OSQAAAABQ2v6+FwAQ/P///+8FoP//////H+D//zkh+R/g/98AAEAekP//KAEAFRD6////DQAAcf///w0AMP3/
//8NANH//zgBAAD0/48AAABw9f+PAAAQyfP//zgR1c+w///////PEPv/////PAAwyO7fWgD2////////D/b///////8P9v//////
/w/2////////DwAAAADW/78EAAAAw//fBAAAAHD//xkAAAAA+v9vAAAAAKD//wYAAAAA+P+PAAAAAED//w0AAAAAsP//BgAAAADz
//8BAAAAAPf/vwAAAAAA+f+fAAAAAAD6/58AAAAAAPn/vwAAAAAA9///BAAAAADz//+fFAAAAKD/////7xkAEPz/////3wEAkf//
////CgAAYcr+//8fAAAAAABg/z8AAAAAAFD/PwAAAAAA/P8fAAAAAAD8/wwAAAAAAPzvAwAAAAAA2ykA9//PALX+rQQA9//Psf//
/38A9//P+/////8E9///jxL2//8K9///CQCA//8N9///AgBQ//8P9//vAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P
9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8P9//PAABA//8PAAAAAABA//8PAAAAAABA//8PAAAA
AABA//8PAAAAAABA//8PAAAAAABA//8PAAAAAABA//8PAABQ2v7NOAAAAADD/////58BAADi//////+/AADA//89Yf//fwBg//8u
AHD//x4A/P+fAADg//8G8f//AwAA+f+/UP//DwAAUP//Dvf/3wAAAPP//5L//////////0/6//////////+k//////////9f+v/P
AAAA8///lP//DQAAQP//T/j//wAAAPX//1L//y8AAID//w7y//8GAAD7/78A/P/PAADz//8GYP//bwCw//8eAMD//16R//9/AADi
//////+vAAAAw/////+fAAAAAFDZ/s44AAAA+v+fAKD//wkA+v+fAKD//wkA+v+fAKD//wkA+v+fAKD//wkA+v+fAKD//wkA+v+f
AKD//woA+v/vAoD///9/8////we0/u9d9//PAAD5/+8E9//PALH//z4A9//PEPz/3wIA9//P0v//HAAA9//f/v+/AQAA9/////8L
AAAA9/////8uAAAA9/////+/AAAA9///////BwAA9//v5f//PwAA9//PYP//zwAA9//PAPr//wgA9//PAOH//z8A9//PAFD//98B
9//PAAD5//8J9//PAADR//9PMP/vnQIAAAAAAPP///8FAAAAADD////vAgAAAAAAIPr/vwAAAAAAABD+/z8AAAAAAACQ//8JAAAA
AAAA9P/vAAAAAAAAAP7/XwAAAAAAAOH//woAAAAAAGD///8BAAAAAAD9//9/AAAAAAD0////DAAAAACg/////wMAAAAg/////48A
AAAA+P/P//8OAAAA4P//4v//BAAAYP//C/n/rwAAAPz/XzD//x8AAPP/7wDQ//8GAKD//wgA9//PABD//y8AIP//LwD3/78AALD/
/wjQ//8FAAD1/98A9//fAABA//8fAPf/3wAAQP//HwD3/98AAED//x8A9//fAABA//8fAPf/3wAAQP//HwD3/98AAED//x8A9//f
AABA//8fAPf/3wAAQP//HwD3/98AAED//x8A9//fAABA//8fAPf/7wAAUP//HwD3//8DAJD//x8A9///TSH3//9vEvf/////////
/y/3///////Z//8v9//f1+9cIOrfGvf/3wAAAAAAAAD3/98AAAAAAAAA9//fAAAAAAAAAPf/3wAAAAAAAAD3/98AAAAAAAAA9//f
AAAAAAAAAPX/3wAAEPz/CADg//8DAADy/48AgP//CAAAsP//AyD//w0AAGD//wkA+/8/AAAw//8NAPX/jwAAEP//DwDg/98AADD/
/w8AgP//AwBg//8MACD//wgAsP//CAAA+/8NAPP//wEAAPX/PwD9/38AAADQ/4+Q//8KAAAAgP/f+P/PAQAAACD/////LgAAAAAA
+///7wMAAAAAAPT//z4AAAD2////////D/b///////8P9v///////w/2////////DwAw6v+eNhIAAPT/vwEAAAAA+/8vAAAAAAD8
/x8AAAAAAPj/jwAAAAAAwf//WxIAAAAAtf///wwAAIH+////DAAg/f////8MAMD//99HEgAA9f//CAAAAAD5/88AAAAAAPr/nwAA
AAAA+v/PAAAAAAD3//9sEgAAAOL/////7xkAUP//////3wEAxP//////CgAAg9v+//8fAAAAAABg/z8AAAAAAFD/PwAAAAAA/P8f
AAAAAAD8/wwAAAAAAPzvAwAAAAAA2ykAAABh2v7OSQAAAADn/////98DAAD6////////BAD3//8oMPz/7wLh//8IABD9/59Q//8v
AABw//8O+f/fAAAA9P//o///DAAAMP//T/r/zwAAAPP//5T//w0AAED//z/1//8BAAD3/+8Q/v+PAADR//8JcP//jwLD//8uAKD/
//////9PAABw/v////89AAAAEKbt75wEAAD7////////////vv///////////+/7////////////DgD9/28AIP//HwAA0P//BgDy
//8BAAD9/28AIP//HwAA0P//BgDy//8BAAD9/28AIP//HwAA0P//BgDy//8BAAD9/28AIP//HwAA0P//BgDy//8BAAD9/28AIP//
LwAA0P//BgDy//8IAAD9/28AEP///+8A0P//BgCg////DgD9/28AAIH9/64AAEC47u9rAQAAALL/////3wQAAOP///////8FAOL/
/yhA/f/vAqD//wgAIP7/jxD//y8AAKD//wz0/98AAAD2//9g//8MAABQ//8f9//PAAAA9f//cf//DQAAYP//D/f//wIAAPr/z3D/
/48AAOL//wf3//+PAdT//x5w///d/////18A9//P0v///28AcP//DHHs3ykAAPf/zwAAAAAAAHD//wwAAAAAAAD3/88AAAAAAABw
//8MAAAAAAAA9//PAAAAAAAAcP//DAAAAAAAAAAAUMn+zmoBANX/////zwD3//////8M9f//XQFyztD//x0AABBI//9PAAAAAPj/
7wAAAACg//8MAAAAAPr/zwAAAACQ//8NAAAAAPb//wIAAAAg//+/AAAAAJD//98lAAAAwf///+9bAACx/////48AADC47f//TwAA
AAAAwv8JAAAAABD8rwAAAABA//8JAAAAAPT/XwAAAABA/78AAAAAAOR8AAAAk+v+//////8MIPv/////////zxD9//////////8M
+f//KDD8//8IAPL//wgAEP3/3wBg//8vAABw//8vAPn/3wAAAPT//wOg//8MAAAw//9PAPr/zwAAAPP//wSA//8NAABA//8/APX/
/wEAAPf/7wAQ/v+PAADR//8JAGD//48Cw///HgAAkP///////08AAABg/v////88AAAAABCm7e+cBAAAAPb//////////2X/////
/////1/2//////////8FAAAg//8vAAAAAAAA8v//AgAAAAAAIP//LwAAAAAAAPL//wIAAAAAACD//y8AAAAAAADy//8CAAAAAAAg
//8vAAAAAAAA8v//AgAAAAAAIP//PwAAAAAAAPL//wgAAAAAAAD////vAAAAAACg////DgAAAAAAgfz/vgAA+v+fACD+3wKg//8J
AGD/3wH6/58AAOD/n6D//wkAAPr/P/r/nwAAYP//qP//CQAA9P+/+v+fAABA//+t//8JAAD0/8/6/58AAED//6z//wkAAPb/n/r/
nwAAoP//lv//CgBA//8v9v/vFGH+/68Q/v//////7wJA/v/////PAgAQt+3/zkkAAAAAgb0AgezOBgAAAOT/DNL///8sAAD0/8+w
/////x0A0f//Nf//PP//CmD//wz3/4+w//8C+/9/oP//B/n/b+D//wT7/3+A//8J//8/sP//B/j/r/D//wT8/3+Q//8L/v9fwP//
B/v/n7D//wn8/3/g//8H9//vwf//Z///LxD+/7/8/5/+/68AQP/////////fAQAw/f//////rwEAAACl/f//zzgAAAAAAAD8/38A
AAAAAAAAwP//BwAAAAAAAAD8/38AAAAAAAAAwP//BwAAAAAAAAD8/38AAAAAAAAAwP//BwAAAPT/vgUAAPP//0X///8KAMD//wz0
////CFD//z8AAPX//wL9/68AAAD5/5/3//8CAAAg///u//8IAAAAsP////8eAAAAAPX///9vAAAAAAD9///fAAAAAACA////BAAA
AAAA8v//CwAAAAAAYP//fwAAAAAAEP3//w0AAAAAAPf///8EAAAAAOH///+vAAAAAJD/////HwAAADD//+///wcAAAD7/8/0/98A
AAD0//8E/P+fAQDA//8LMP///59g//8vAGD///8Z/v+fAAAw2f+f8f//A/z/f4D//xv//z/A//8H+P+/8f//A/z/f4D//xv//z/A
//8H+P+/8f//A/z/f4D//xv//z/A//8H+P+/8f//A/z/f4D//xv//z/A//8H+P+/8P//A/z/f4D//wr9/1/A//8H+v+PoP//Cfz/
f9D//wX1/+/B//9X//8eAP3/r/z/n/7/jwAw/v///////78AADD8//////+fAQAAAKT9///PKAAAAAAAAPz/fwAAAAAAAADA//8H
AAAAAAAAAPz/fwAAAAAAAADA//8HAAAAAAAAAPz/fwAAAAAAAADA//8HAAAAAPP/bwAAAAD1/z8AAPz/HgAAAADQ/88AUP//CQAA
AACA//8GwP//BQAAAABA//8N8v//AgAAAAAQ//8/9v/vAAAAAAAA/f9/+f/fAJD//woA/P+v+v/PAJD//woA+/+/+v+/AKD//wsA
+v+/+f/PALD//wwA+/+v9//vAMD//w0A/f+P9P//A/H//x8g//9f0P//G/fv/Y+h//8OUP////+v+f////8GAPj///8t0f///58A
AEDa74wBEMf+rgQAAID/DcD/CgAAAPjfAPyvAAAAgP8NwP8KAAAA+N8A/K8AAAAAAAAAAAAAAAAAAAAAAAAA9P////////9A////
/////w/0/////////0D/////////D/T//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED/////////BvT/
//////9vQP////////8G9P///////29A//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P////////9E
/////////0/0/////////0T/////////TwAAAAD+//8vAAAAAAAAAFD///+PAAAAAAAAAKD////fAAAAAAAAAPH/////BAAAAAAA
APb/////CQAAAAAAAPz/z///HgAAAAAAIP//P/7/XwAAAAAAgP//DPn/vwAAAAAA0P//B/T//wIAAAAA9P//AuD//wcAAAAA+f/P
AJD//w0AAAAQ/v9/AED//z8AAABQ//8vAAD9/58AAACw//8MAAD4/+8AAADy//////////8FAAD3//////////8KAAD8////////
//8fADD///////////9vAJD//x8AAAAA/P/PAOD//woAAAAA9///AvX//wUAAAAA8v//CPr/7wEAAAAAwP//DfT/////////T0D/
/////////wT0/////////09A//////////8E9P//BgAAAAAAQP//bwAAAAAAAPT//wYAAAAAAED//28AAAAAAAD0//8GAAAAAABA
///////OWgEA9P///////+8GQP//////////B/T//////////0L//28AEMT//3/0//8GAADy//9K//9vAAAA/v+/9P//BgAA8v//
Sv//bwAQxP//f/T//////////0L//////////wf0////////7wZA///////OWgEA9P/////eiwMAQP////////8aAPT/////////
DED//////////wb0//8GAKL//69A//9vAADh//8M9P//BgAA/P/PQP//bwAA4f//CvT//wYAov//X0D/////////rwD0////////
fwBA/////////34A9P////////+fQP//bwAQxP//P/T//wYAAPL//0j//28AAAD+/6/0//8GAADy//9K//9vABDE//+P9P//////
////RP//////////CfT/////////CED//////956AgD0/////////0T/////////T/T/////////RP////////9P9P//BgAAAABA
//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED//28AAAAA
APT//wYAAAAAQP//bwAAAAAA9P//BgAAAABA//9vAAAAAAD0//8GAAAAAED//28AAAAAAPT//wYAAAAAQP//bwAAAAAAAADz////
/////wwAAADz/////////wwAAADz/////////wwAAADz/////////wwAAADz//8HAMD//wwAAADz//8HAMD//wwAAADz//8HAMD/
/wwAAADz//8GAMD//wwAAADz//8GAMD//wwAAAD0//8GAMD//wwAAAD0//8FAMD//wwAAAD0//8EAMD//wwAAAD1//8DAMD//wwA
AAD2//8CAMD//wwAAAD3//8AAMD//wwAAAD6/88AAMD//wwAACD+/58AAMD//wwAANL//08AAMD//wwA8//////////////v8///
///////////v8//////////////v8//////////////v8/8fAAAAAAAAUP/v8/8fAAAAAAAAUP/v8/8fAAAAAAAAUP/v8/8fAAAA
AAAAUP/v8/8fAAAAAAAAUP/v9P////////9A/////////w/0/////////0D/////////D/T//wYAAAAAQP//bwAAAAAA9P//BgAA
AABA//9vAAAAAAD0//8GAAAAAED/////////BvT///////9vQP////////8G9P///////29A//9vAAAAAAD0//8GAAAAAED//28A
AAAAAPT//wYAAAAAQP//bwAAAAAA9P////////9E/////////0/0/////////0T/////////TzD+/78AAABw//8/AAAA4v//HABA
//+vAAAA9///AwAA0f//HQAAUP//nwAAcP//PwAAwf//LgAAAGD//48AAPf//wMAsP//PgAAAACA//9vAHD//z8AoP//TwAAAAAA
kP//XwD3//8DkP//XwAAAAAAAKD//09w//8/cP//bwAAAAAAAACx//8+9///Y///jwAAAAAAAAAA0f//nv//f///rwAAAAAAAAAA
IP7//////////wwAAAAAAAAAAPv///////////8HAAAAAAAAAPf/////////////AwAAAAAAAOL/////////7///zwAAAAAAAMD/
/3/2////76P//48AAAAAAHD//78A9///7wPh//8/AAAAADD//+8CAPr//wUA9f//DQAAAAD8//8GAHD//z8AAPr//wgAAAD4//8L
AAD3//8DABD+//8DAADz//8uAABw//8/AABA///fAQDQ//9fAAAA9///AwAAkP//nwCA//+vAAAAcP//PwAAANH//08w///vAQAA
APf//wMAAAD0//8dEHTK7u+9WQEAAPj//////+8IAID/////////CgD4/////////wVweiQBINb//68AAAAAAADy//8MAAAAAAAA
/f+/AAAAAAAA8v//BwAAAAAg1f//HQAAQP//////GwAAAPT/////GAAAAED//////14AAAD0//////9fAAAAABBS+v//DQAAAAAA
APn//wMAAAAAAFD//1+wAwAAAAD5//8E/2sTAEH6//8f8P////////+vAP/////////PAUD8//////+fAQAAg9v+3pwWAAD0//8B
AAAw////Rf//HwAAAPv//1/0//8BAAD0////Rf//HwAAwP///1/0//8BAFD/////Rf//HwAA/f///1/0//8BAPb/////Rf//HwDQ
/6///1/0//8BcP//8///Rf//HxD+/wn//1/0//8B+P8v8P//Rf//H+H/nwD//1/0//+R/+8B8P//Rf//P///CAD//1/0///7/x4A
8P//Rf////9/AAD//1/0////7wEA8P//Rf////8GAAD//1/0////DQAA8P//Rf///18AAAD//1/0///PAAAA8P//Rf///wUAAAD/
/18AALB/AAD1DQAAAAAA9m8R5Z8AAAAAAAD8///fAQAAAAAAEMf/jQEAAAAAAAAAAAAAAAAAQP//HwAAAPP//1/0//8BAACw////
Rf//HwAAQP///1/0//8BAAD8////Rf//HwAA9f///1/0//8BAND/////Rf//HwBg/////1/0//8BAP3/+v//Rf//HwD3/z///1/0
//8B4f+f8P//Rf//H4D//wL//1/0//8R/v8J8P//Rf//H/n/HgD//1/0///z/48A8P//Rf//v//vAQD//1/0/////wcA8P//Rf//
//8eAAD//1/0////bwAA8P//Rf///98AAAD//1/0////BQAA8P//Rf///wwAAAD//1/0//9fAAAA8P//BfT//wYAAAD1//8+QP//
bwAAAPT//z4A9P//BgAA5P//PgBA//9vAADk//8+AAD0//8GAOP//04AAED//28A4///TwAAAPT//wbj//9PAAAAQP//b+L//18A
AAAA9P//6P//XwAAAABA////////BQAAAAD0///////vAQAAAED///////+/AAAAAPT////f//9vAAAAQP///3/i//8uAAAA9P//
fwD2//8MAABA//+fAAD6//8IAAD0//8GABD+//8DAED//28AAED//98BAPT//wYAAJD//58AQP//bwAAANH//18A9P//BgAAAPP/
/x5A//9vAAAAAPf//wsAAGD/////////LwAAYP////////8vAABg/////////y8AAGD/////////LwAAYP//TwBw//8vAABg//8/
AHD//y8AAGD//z8AcP//LwAAcP//PwBw//8vAABw//8vAHD//y8AAID//y8AcP//LwAAgP//HwBw//8vAACQ//8PAHD//y8AALD/
/w0AcP//LwAA0P//CwBw//8vAADw//8IAHD//y8AAPX//wUAcP//LwAg/f//AQBw//8vMej//78AAHD//y/5////PgAAcP//L/n/
/+8EAABw//8v+f/vGAAAAHD//y/ZegQAAAAAcP//L/T///8CAAAAQP///x/0////CAAAALD///8f9P///x4AAADy////H/T///9v
AAAA+P///x/0////zwAAEP7///8f9P////8DAGD/////H/T///z/CgDA/8///x/0///1/x8A9P9v//8f9P//0f9/APr/Sv//H/T/
/2H/3xD//0T//x/0//8R/v91/99A//8f9P//Afn/2/9/QP//H/T//wHz////HkD//x/0//8BsP///wlA//8f9P//AVD///8DQP//
H/T//wEA/f+/AED//x/0//8BAPf/XwBA//8f9P//AQDx/w4AQP//H/T//wEAAAAAAED//x/0//8BAAAAAABA//8f9P//AQAAAAAA
QP//H/T//wEAAAAAAED//x/0//8GAAAA9P//Rf//bwAAAED//1/0//8GAAAA9P//Rf//bwAAAED//1/0//8GAAAA9P//Rf//bwAA
AED//1/0//8GAAAA9P//Rf//bwAAAED//1/0//8GAAAA9P//Rf///////////1/0////////////Rf///////////1/0////////
////Rf//bwAAAED//1/0//8GAAAA9P//Rf//bwAAAED//1/0//8GAAAA9P//Rf//bwAAAED//1/0//8GAAAA9P//Rf//bwAAAED/
/1/0//8GAAAA9P//Rf//bwAAAED//18AAABhyf7eiwMAAAAAEOj//////0wAAAAg/P///////38AABD9/////////38AAPv//34C
Qfv//08A9f//PgAAAPn//wyw//9fAAAAAPz//xT//98AAAAAYP//j/T//wkAAAAA8f//bP//bwAAAAAA/v/f9///BQAAAADQ//9+
//9fAAAAAAD9/+/2//8GAAAAAOD//03//58AAAAAEP//z/H//w0AAAAA9v//CPv//wUAAADA//9PUP//7wIAAJD//88AwP//7ycQ
tP///wQA0f//////////BwAAwv////////8HAAAAgf7/////zwQAAAAAEKbt7704AAAA9P///////////0X///////////9f9P//
/////////0X///////////9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28A
AABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAA
APT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P//BgAAAPT//0X//28AAABA//9f9P/////vnAQAQP////////88
APT/////////PkD//////////w30//8GAHL///9F//9vAABw//+f9P//BgAA8v//S///bwAAIP//v/T//wYAAPf//0n//28AIPf/
/1/0/////////99A/////////+8D9P///////88DQP//////zkkAAPT//wYAAAAAAED//28AAAAAAAD0//8GAAAAAABA//9vAAAA
AAAA9P//BgAAAAAAQP//bwAAAAAAAPT//wYAAAAAAED//28AAAAAAAAAAABAuO3vrCYAAABQ/P//////GgAQ+v///////x8AsP//
//////8fAPn//88lEGL6HzD///8HAAAAIBqg//+fAAAAAAAA4P//HgAAAAAAAPT//woAAAAAAAD2//8HAAAAAAAA9///BQAAAAAA
APf//wUAAAAAAAD2//8HAAAAAAAA9P//CgAAAAAAAOD//x4AAAAAAACg//+fAAAAAAAAMP///wcAAAAgGgD5///PJRBS+h8AsP//
//////8fABD6////////HwAAUPz//////xoAAABAuO3vrSYA/f///////////9T///////////9P/f///////////9T/////////
//9PAAAAkP//HwAAAAAAAAD5//8BAAAAAAAAkP//HwAAAAAAAAD5//8BAAAAAAAAkP//HwAAAAAAAAD5//8BAAAAAAAAkP//HwAA
AAAAAAD5//8BAAAAAAAAkP//HwAAAAAAAAD5//8BAAAAAAAAkP//HwAAAAAAAAD5//8BAAAAAAAAkP//HwAAAAAAAAD5//8BAAAA
AAAAkP//HwAAAAAAAAD5//8BAAAAAAAAkP//HwAAAAAAAAD5//8BAAAA0P//HgAAAAD9/+8B9v//BwAAAPb//wgQ/v/vAQAA0P//
HwBw//9/AABQ//+fAADh//8OAAD8//8CAAD4//8GAPT//woAABD+/98AwP//PwAAAJD//29A//+/AAAAAPL//w37//8EAAAAAPn/
//j//wwAAAAAIP//////XwAAAAAAoP/////fAAAAAAAA8/////8GAAAAAAAA+////w0AAAAAAAAw////fwAAAAAAAACw///vAQAA
AAAAAAD2//8IAAAAAAAAANT//x4AAAAAAAD5////jwAAAAAAAJD////fAQAAAAAAAPn//88CAAAAAAAAkO/OWQAAAAAAAAAAAAAA
4P//CwAAAAAAAAAAAADg//8LAAAAAAAAAABzyv7//++cJgAAAAAAxv//////////SwAAAML/////////////CgAQ/f//////////
//+vAJD///9J4f//K7X///8F8f//TwDg//8LAPj//wv0//8KAOD//wsA0P//H/b//wYA4P//CwCg//8v9///BQDg//8LAJD//z/2
//8GAOD//wsAoP//L/T//woA4P//CwDQ//8f8f//TwDg//8LAPj//wyQ////SeH//yu1////BRD9/////////////68AAML/////
////////CgAAANb//////////0sAAAAAAHPK/v//75wmAAAAAAAAAADg//8LAAAAAAAAAAAAAOD//wsAAAAAAAAAAAAA4P//CwAA
AAAAwP//LgAAABD+/98B8v//CwAAAPr//wMA9///BwAA9v//CAAA+//vAgDi//8MAAAg/v/PALD//z8AAABg//9/YP//jwAAAACw
//9P/v/PAAAAAADi//////8DAAAAAAD2/////wcAAAAAAAD7////DAAAAAAAABD+//8vAAAAAAAAAPX///8GAAAAAAAA4f///+8C
AAAAAACg/////88AAAAAAFD//8///38AAAAAIP7/37H//y8AAAAA+///A+L//wwAAAD2//8IAPb//wcAAOL//wwAAPv//wMAsP//
PwAAIP7/zwBg//9/AAAAYP//jyD+/88AAAAAoP//P/T//wYAAAD0//8FAED//28AAABA//9fAAD0//8GAAAA9P//BQBA//9vAAAA
QP//XwAA9P//BgAAAPT//wUAQP//bwAAAED//18AAPT//wYAAAD0//8FAED//28AAABA//9fAAD0//8GAAAA9P//BQBA//9vAAAA
QP//XwAA9P//BgAAAPT//wUAQP//bwAAAED//18AAPT//wYAAAD0//8FAED//28AAABA//9fAAD0//8GAAAA9P//BQBA//9vAAAA
QP//XwAA9P//BgAAAPT//wUAQP//bwAAAED//18AAPT//////////////0D//////////////w/0//////////////9A////////
//////8PAAAAAAAAAAAAQP//AAAAAAAAAAAAAPT/DwAAAAAAAAAAAED//wAAAAAAAAAAAAD0/w8AAAAAAAAAAABA//8A+f//AQAA
IP//f/n//wEAACD//3/5//8BAAAg//9/+f//AQAAIP//f/n//wEAACD//3/5//8CAAAg//9/+f//AwAAIP//f/j//wYAACD//3/2
//89AAAg//9/8v//////////f6D//////////38Q/P////////9/AHHs////////fwAAAAAAACD//38AAAAAAAAg//9/AAAAAAAA
IP//fwAAAAAAACD//38AAAAAAAAg//9/AAAAAAAAIP//fwAAAAAAACD//38AAAAAAAAg//9/AAAAAAAAIP//f/T//wYAAED//18A
AAD1//9E//9vAAAA9P//BQAAUP//T/T//wYAAED//18AAAD1//9E//9vAAAA9P//BQAAUP//T/T//wYAAED//18AAAD1//9E//9v
AAAA9P//BQAAUP//T/T//wYAAED//18AAAD1//9E//9vAAAA9P//BQAAUP//T/T//wYAAED//18AAAD1//9E//9vAAAA9P//BQAA
UP//T/T//wYAAED//18AAAD1//9E//9vAAAA9P//BQAAUP//T/T//wYAAED//18AAAD1//9E//9vAAAA9P//BQAAUP//T/T//wYA
AED//18AAAD1//9E//9vAAAA9P//BQAAUP//T/T//wYAAED//18AAAD1//9E//9vAAAA9P//BQAAUP//T/T/////////////////
//9E////////////////////T/T///////////////////9E////////////////////T/T//wYAAED//18AAAD1//8EAPT//wYA
AED//18AAAD1//8EAPT//wYAAED//18AAAD1//8EAPT//wYAAED//18AAAD1//8EAPT//wYAAED//18AAAD1//8EAPT//wYAAED/
/18AAAD1//8EAPT//wYAAED//18AAAD1//8EAPT//wYAAED//18AAAD1//8EAPT//wYAAED//18AAAD1//8EAPT//wYAAED//18A
AAD1//8EAPT//wYAAED//18AAAD1//8EAPT//wYAAED//18AAAD1//8EAPT//wYAAED//18AAAD1//8EAPT//wYAAED//18AAAD1
//8EAPT//wYAAED//18AAAD1//8EAPT//wYAAED//18AAAD1//8EAPT//wYAAED//18AAAD1//8EAPT//wYAAED//18AAAD1//8E
APT///////////////////////T///////////////////////T///////////////////////T//////////////////////wAA
AAAAAAAAAAAAAAAAAED//wAAAAAAAAAAAAAAAAAAAED//wAAAAAAAAAAAAAAAAAAAED//wAAAAAAAAAAAAAAAAAAAED//wAAAAAA
AAAAAAAAAAAAAED//9fd3d3d3U0AAAAAAAD4//////9fAAAAAAAA+P//////XwAAAAAAAPj//////18AAAAAAABjZmaW//9fAAAA
AAAAAAAAUP//XwAAAAAAAAAAAFD//18AAAAAAAAAAABQ//9fAAAAAAAAAAAAUP//r4iIVwIAAAAAAFD////////fBgAAAABQ////
/////88BAAAAUP//////////CgAAAFD//8+72////z8AAABQ//9fAACx//9/AAAAUP//XwAAIP//nwAAAFD//18AAAD//68AAABQ
//9fAAAw//+fAAAAUP//XwAAw///XwAAAFD//9/d7f///x4AAABQ//////////8FAAAAUP////////9NAAAAAFD//////85ZAAD0
//8GAAAAAAAA9f//Rf//bwAAAAAAAFD//1/0//8GAAAAAAAA9f//Rf//bwAAAAAAAFD//1/0//8GAAAAAAAA9f//Rf//bwAAAAAA
AFD//1/0//8GAAAAAAAA9f//Rf//bwAAAAAAAFD//1/0/////++cBQAA9f//Rf////////9NAFD//1/0/////////18A9f//Rf//
////////HlD//1/0//8GAEH9//8G9f//Rf//bwAAQP//n1D//1/0//8GAADg//8L9f//Rf//bwAAAP7/v1D//1/0//8GAAD0//8J
9f//Rf//bwAQ1f//b1D//1/0/////////+8B9f//Rf//////////BVD//1/0////////3wQA9f//Rf//////zlkAAFD//1/0//8G
AAAAAABA//9vAAAAAAAA9P//BgAAAAAAQP//bwAAAAAAAPT//wYAAAAAAED//28AAAAAAAD0//8GAAAAAABA//9vAAAAAAAA9P//
///vnAUAQP////////9NAPT/////////X0D//////////x70//8GAEH9//9G//9vAABA//+f9P//BgAA4P//S///bwAAAP7/v/T/
/wYAAPT//0n//28AENX//2/0/////////+9B//////////8F9P///////98EQP//////zlkAAAAAEEMjAAAAAAAApf7//78XAAAA
0f///////wgAAPH////////PAgDx///d/v///x0A8Y4DADD5//+/AIEBAAAAUP///wQAAAAAAAD4//8LAAAAAAAA4f//HwAAERER
EaH//08AYP////////9vAGD/////////fwBg/////////38AYP////////9vABAzMzMzs///XwAAAAAAAND//x8AAAAAAAD2//8M
YQAAAAAw/v//BfFsAQAA5v//zwDx/8+r/P///y4A8f///////+8DAPH///////8rAAAQx////+86AAAAAABBZUUDAAAAAPT//wYA
AAAwuO3vrRYAAAD0//8GAAAw/P/////vGAAA9P//BgAA9v///////98CAPT//wYAUP//////////LgD0//8GAPL//88VIOf//88A
9P//BgD7//8KAAAg/f//BfT//wYg///fAQAAAPT//wz0//8GgP//fwAAAADA//8f9P//BrD//y8AAAAAgP//X/T///////8PAAAA
AFD//3/0////////DgAAAABA//+P9P///////w4AAAAAQP//j/T///////8PAAAAAFD//3/0//8GsP//LwAAAACA//9f9P//BoD/
/38AAAAAwP//H/T//wYw///fAAAAAPT//wz0//8GAPv//wkAACD9//8F9P//BgDy///PFSDn///PAPT//wYAYP//////////LgD0
//8GAAD2////////3wMA9P//BgAAMPz/////7xgAAPT//wYAAAAwuO3vrRYAAAAAADC47v////9fABD6////////XwDA////////
/18A9v//OwBA//9fAPz/7wEAQP//XwD//78AAED//18Q//+fAABA//9fAP//nwAAQP//XwD7/78AAED//18A8//vAQBA//9fAFD/
/zwAQP//XwAA5P///////18AACD9//////9fAAAg////////XwAAsP//f0D//18AAPT//w1A//9fAAD9//8EQP//XwBw//+vAED/
/18A4f//HgBA//9fAPn//wcAQP//XzD//88AAED//1/A//8/AABA//9fQP///+++SQAA9P//////zwJA////////3wHESBIQYv7/
fwAAAAAAcP//CwCE2/7////fEPv///////8N/P///////9/1//86AWD//53//wwAAPf/3/r/nwAAsP//nf//DABA///f9v//GFH+
//8N/f/////5/98w/f//72X//w0QyO6NAvb/3wAAAAAAAAARAAAAADF2udz/CQAAIPr//////wEAIP7//+/NmygAAPz/fQMAAAAA
APf/GwAAAAAAAOD/HgAAAAAAAED/nwAAAAAAAAD3/0bJ/t5qAQCQ/+//////7wYA+v////////8JoP///zsg+P//Bvj//x0AAPn/
73H//38AACD//0/2//8DAADg//9o//8vAAAA/f+f9f//AgAA0P//Sf//PwAAAP7/j/H//wcAAPL//wT7/98BAJD//x4w//+/A4L/
/28AYP///////58AAED9/////34AAAAAlezvrRYAAPf////vrQUA9///////zwH3////////Cff/zwBh//8N9//PAAD//w73/88A
YP//Cvf//////+8C9///////TgD3////////B/f/zwAw/P8/9//PAAD1/4/3/88AAPX/r/f/zwAw/P+P9////////z/3////////
Bvf/////vigA9///////fv//////7/f//////37//wwAAAD3/88AAABw//8MAAAA9//PAAAAcP//DAAAAPf/zwAAAHD//wwAAAD3
/88AAABw//8MAAAA9//PAAAAcP//DAAAAPf/zwAAAHD//wwAAAAAAPX///////8MAAAA9f///////wwAAAD1////////DAAAAPX/
3wBg//8MAAAA9v/fAGD//wwAAAD2/98AYP//DAAAAPf/zwBg//8MAAAA+P+/AGD//wwAAAD6/58AYP//DAAAAPz/fwBg//8MAAAQ
//9fAGD//wwAAJD//x8AYP//DAAQ+P//DABg//8MAPX///////////+P9f///////////4/1////////////j/X/BwAAAAAAMP+P
9f8HAAAAAAAw/4/1/wcAAAAAADD/j/X/BwAAAAAAMP+PAABh2v7OKAAAAGD+/////wgAAPn//////68AcP//jwLU//8H4f//CQAw
//8e9f//AQAA+/9v+f/PAAAA+f+v+v/////////P+v/////////f+f/////////f9f/PAAAAAAAA4f//BAAAADAqcP//jhMQdP0v
APn///////8vAGD+//////8vAABh2v7evFgCcP//TwAA+v+PAAD3//8FAPb//wUA+v+PAHD//08AAGD//18A+v+PAPj/7wQAAAD1
//8F+v+PkP//PgAAAABA/v9v+v+P+f/vAwAAAAAA5P///v/v//8tAAAAAAAAYP////////8DAAAAAAAA0f////////8LAAAAAAAA
+v////////+PAAAAAABw//+8////7P//BQAAAAD0/+8S/P/PUf//LgAAACD+/18A+v+PAPj/3wEAAMD//wgA+v+PALD//woAAPn/
vwAA+v+PABD9/38AYP//HgAA+v+PAADz//8E8///BAAA+v+PAABg//8uEJXc/t5qAQD8/////98DwP//////zwDcJxFy//8fgAEA
ALD//wEAAABy//8LAMD/////KwAA/P///xkAAMD/////TgAAABBz/v8uAAAAAGD//3YGAAAA9v9/+H0DIPf//4X///////8N+P//
////LBCE3P7enAQA9//PAAD0//94//8MAND//4/3/88AgP///3j//wwg////j/f/zwD7////eP//DPX///+P9//P4f////94//+c
///+/4/3/+///7n//3j/////Hvv/j/f///9vsP//eP///78A+/+P9////wKw//94////CAD7/4/3//8dALD//3j//08AAPv/jwBQ
3wAA0G8AAADxrwKS/wIAAAD3////BwAAAAC1/r4FAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAcP//DABA//+P9//PAAD9//94
//8MAPj//4/3/88A8v///3j//wyw////j/f/z1D/////eP//HP7///+P9//P+f/v//94///+/5/7/4/3////77H//3j/////Bvv/
j/f///8LsP//eP///y8A+/+P9///jwCw//94///fAQD7/4/3//8EALD//wj3/88AAML//xv3/88AIP3/rwD3/88A4///CgD3/88w
/v+fAAD3/8/k//8IAAD3/+///28AAAD3/////wkAAAD3/////z4AAAD3/////98BAAD3//++//8LAAD3/+8S/P+PAAD3/88A4v//
BQD3/88AQP//PgD3/88AAPf/3wH3/88AAKD//wv3/88AABD9/48AAPv///////8HALD///////9/AAD7////////BwCw//8IAPz/
fwAA+/+PAMD//wcAsP//BwD8/38AAPz/fwDA//8HAMD//wYA/P9/AAD9/18AwP//BwDg//8DAPz/fwAg//8PAMD//wcA+v+/AAD8
/39A+///AwDA//9X////BwAA/P9/9f/vBQAAwP//V95aAQAAAPz/f/f//wwAAED////3//9PAACw////9///vwAA8/////f///8D
APr////3////CiD/////9////y+Q//////f///+f8v/////3/8/+7/n/+///9//P+P//7/X///f/z+H//5/0///3/8+Q//8v9P//
9//PIP//CvT///f/zwD6/wP0///3/88AAAAA9P//9//PAAAAAPT///f/zwAAAAD0///3/88AAPD//3P//wwAAP//P/f/zwAA8P//
c///DAAA//8/9//PAADw//9z//8MAAD//z/3/////////3P/////////P/f/////////c///DAAA//8/9//PAADw//9z//8MAAD/
/z/3/88AAPD//3P//wwAAP//P/f/zwAA8P//c///DAAA//8/AABh2v7OSQAAAADn/////98DAAD6////////BAD3//8oMPz/7wLh
//8IABD9/59Q//8vAABw//8O+f/fAAAA9P//o///DAAAMP//T/r/zwAAAPP//5T//w0AAED//z/1//8BAAD3/+8Q/v+PAADR//8J
cP//jwLD//8uAKD///////9PAABw/v////89AAAAEKbt75wEAAD3/////////3P/////////P/f/////////c///DAAA//8/9//P
AADw//9z//8MAAD//z/3/88AAPD//3P//wwAAP//P/f/zwAA8P//c///DAAA//8/9//PAADw//9z//8MAAD//z/3/88AAPD//3P/
/wwAAP//P/f/zwAA8P//c///DAAA//8/9//PALb+nQIAcP//HPz///8GAPf/z/z/////BXD///8oQP3/7wH3//8IACD+/39w//8v
AACg//8M9//fAAAA9v//cP//DAAAUP//H/f/zwAAAPX//3H//w0AAGD//w/3//8CAAD6/89w//+PAADi//8H9///jwHU//8ecP//
zP////9fAPf/z8H///9vAHD//wxg7N8pAAD3/88AAAAAAABw//8MAAAAAAAA9//PAAAAAAAAcP//DAAAAAAAAPf/zwAAAAAAAHD/
/wwAAAAAAAAAAFDJ/s5qAQDl/////88A+P//////DPb//10Bcs7h//8cAAAQWP//TwAAAAD5/+8AAAAAoP//DAAAAAD6/88AAAAA
kP//DgAAAAD1//8DAAAAEP7/zwEAAIFg///fFSDmDID//////88AYP7/////DAAAlezvrBb9/////////0/9/////////0/9////
/////08AAAD+/18AAAAAAAD+/18AAAAAAAD+/18AAAAAAAD+/18AAAAAAAD+/18AAAAAAAD+/18AAAAAAAD+/18AAAAAAAD+/18A
AAAAAAD+/18AAAAAAAD+/18AAAAAAAD+/18AAAAAAAD+/18AAAAAAAD+/18AAAD2/88AAABg//8c/v8/AAAA+/9vgP//CQAA8v//
AfL/7wEAcP//CgD6/38AAPz/TwAw//8NAPL/3wAAwP//BHD//wcAAPX/rwD8/x8AAAD9/x/z/68AAABw//+H//8EAAAA4f/f/f8N
AAAAAPn///9/AAAAACD/////AgAAAACw////CwAAAAAA9P//XwAAAAAAAPz/3wAAAAAAAHD//wgAAAAAAAD6/y8AAAAAABD3/68A
AAAAAP///+8CAAAAAPD//+8EAAAAAAD/74wCAAAAAAAAAAAAsP//CAAAAAAAAAAAAACw//8IAAAAAAAAAAAAALD//wgAAAAAAAAA
AAAAsP//CAAAAAAAAAAAAACw//8IAAAAAAAAAAAAALD//wgAAAAAAAAAAAAAsP//CAAAAAAAAACk/Uyw//8I1t4pAAAAkP///7T/
/4j///8GAAD5////zf//+////18AQP//rxH3//9eIfz/7wGw//8MALD//wgA8v//B/H//wYAsP//CACg//8M8///AwCw//8IAGD/
/w/1//8CALD//wgAUP//H/X//wEAsP//CABQ//8f8///AwCw//8IAGD//w/x//8GALD//wgAoP//DLD//wwAsP//CADy//8HQP//
rxH3//9eIfz/7wEA+f///87///v///9fAACQ////tP//iP///wYAAACk/Uyw//8I1t8pAAAAAAAAALD//wgAAAAAAAAAAAAAsP//
CAAAAAAAAAAAAACw//8IAAAAAAAAAAAAALD//wgAAAAAAAAAAAAAsP//CAAAAAAAAAAAAACw//8IAAAAAADB//8KAAD0//8E4v//
BQDh//8HAPX/7wKw//8LAAD5/79w//8dAAAA/P+f//8/AAAAIP7///9vAAAAAFD///+vAAAAAACQ///fAQAAAAAA/P//TwAAAAAA
+f///x0AAAAA9v////8LAAAA4///1f//BwAA0f//CPP//wQAoP//DAD3/+8BYP//LgAA+/+/MP//XwAAIP7/j/f/zwAA8P//A3D/
/wwAAP//PwD3/88AAPD//wNw//8MAAD//z8A9//PAADw//8DcP//DAAA//8/APf/zwAA8P//A3D//wwAAP//PwD3/88AAPD//wNw
//8MAAD//z8A9//PAADw//8DcP//DAAA//8/APf/zwAA8P//A3D//////////+/3//////////9+///////////vAAAAAAAAAMD/
DgAAAAAAAAD87wAAAAAAAADA/w4AAAAAAAAA/O/x//8DAPH//xP//z8AEP//P/H//wMA8f//E///PwAQ//8/8f//BQDx//8D/v+/
AhD//z+g/////////wPj////////PwCi/v//////AwAAAAAQ//8/AAAAAADx//8DAAAAABD//z8AAAAAAPH//wMAAAAAEP//PwAA
AAAA8f//AwAAAAAQ//8/9//PAADA//8HABD//y/3/88AAMD//wcAEP//L/f/zwAAwP//BwAQ//8v9//PAADA//8HABD//y/3/88A
AMD//wcAEP//L/f/zwAAwP//BwAQ//8v9//PAADA//8HABD//y/3/88AAMD//wcAEP//L/f/zwAAwP//BwAQ//8v9//PAADA//8H
ABD//y/3/88AAMD//wcAEP//L/f/zwAAwP//BwAQ//8v9//PAADA//8HABD//y/3////////////////L/f///////////////8v
9////////////////y/3/88AAMD//wcAEP//LwD3/88AAMD//wcAEP//LwD3/88AAMD//wcAEP//LwD3/88AAMD//wcAEP//LwD3
/88AAMD//wcAEP//LwD3/88AAMD//wcAEP//LwD3/88AAMD//wcAEP//LwD3/88AAMD//wcAEP//LwD3/88AAMD//wcAEP//LwD3
/88AAMD//wcAEP//LwD3/88AAMD//wcAEP//LwD3/88AAMD//wcAEP//LwD3/88AAMD//wcAEP//LwD3/////////////////9/3
/////////////////9/3/////////////////98AAAAAAAAAAAAAAAAA/d8AAAAAAAAAAAAAAAAA/d8AAAAAAAAAAAAAAAAA/d8A
AAAAAAAAAAAAAAAA/d9iZmZmZjYAAAAAAPb/////fwAAAAAA9v////9/AAAAAADFzMz+/38AAAAAAAAAAPz/fwAAAAAAAAAA/P9/
AAAAAAAAAAD8/48zIwAAAAAAAPz/////zxcAAAAA/P//////3wIAAAD8////////DAAAAPz/fxFS//8vAAAA/P9/AAD6/18AAAD8
/38AAPv/TwAAAPz/n0SV//8vAAAA/P///////wsAAAD8///////PAQAAAPz////vrQUA9//PAAAAAACA//97//8MAAAAAAD4/7/3
/88AAAAAAID//3v//wwAAAAAAPj/v/f/zwAAAAAAgP//e///DAAAAAAA+P+/9////++9FwCA//97////////TgD4/7/3////////
HoD//3v//wwAw///B/j/v/f/zwAA9f+fgP//e///DABQ//8J+P+/9//PADD9/3+A//97////////7wL4/7/3///////vBID//3v/
////33sBAPj/v/f/zwAAAAAA9//PAAAAAAD3/88AAAAAAPf/zwAAAAAA9//PAAAAAAD3/88AAAAAAPf////vvRcA9///////7wT3
////////Hvf/zwAw/P9/9//PAAD1/5/3/88AAPX/n/f/zwAw/f9/9////////y73///////vBPf/////vRcAQai7mhUAAPD/////
jgEA///////PAvD//////88BnwMQ1f//fyAAAADi//8OAAAAAPb//wOxu7vL//9vEP///////wfx//////9/AERERPb//wUAAACQ
//8vBwAAYP//z/CNVrf///8E////////CPD//////wgA6v///64DAAAwZFYDAAAA9//PAAAAlOzvvRcAAPf/zwAAwv//////CAD3
/88AMP7//////78A9//PANH//00R9///Cff/zwD4/+8CAHD//y/3/88A/f+fAAAA/v9/9//Pc///bwAAAPv/r/f//////08AAAD6
/8/3//////9PAAAA+v/P9//fd///bwAAAPv/r/f/zwD9/58AAAD+/3/3/88A9//vAgBg//8v9//PANH//00Q9v//Cff/zwAw/v//
////vwD3/88AAMP//////wgA9//PAAAAlOzvvRcAAAAApOz/////DAD6///////PAPf///////8MsP//KwD3/88A/f9PAHD//wyw
//8EAPf/zwD1/78CcP//DAD6///////PAAD6//////8MABD+/////88AAPn/b3D//wwA9P/PAPf/zwDQ//8DcP//DID//wgA9//P
IP//HQBw//8M+/9fAAD3/88AAPP/A/f/AAAAAPP/A/f/AAAAAPP/A/f/AAAAAPP/A/f/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAGHa/s4oAAAAYP7/////CAAA+f//////rwBw//+PAtT//wfh//8JADD//x71//8BAAD7/2/5/88AAAD5/6/6////////
/8/6/////////9/5/////////9/1/88AAAAAAADh//8EAAAAMCpw//+OExB0/S8A+f///////y8AYP7//////y8AAGHa/t68WAL2
//////9m//////9v9v//////Zv//////b/b///////////////9v9v///////////////2/2////////////////b/b/////////
//////9vANH/BpD/H0D/zxD9/wj5/z/g//8B/v8f4P//Af7/HwAA+v9fAPr/XwD6/18A+v9fAPz/HhD//wVg/68AoP8eAOD/BQBQ
//8J9f+fUP//CfX/n4D//wT8/wny/x1g/08A+p8AANHdzQDy/98A8v/fAPL/3wDh/+8AUP//AwD6/wcA4v8MAGD/HwAAdicA0f8G
APjPAPn/ATD/j0D/zwDA/z/R/48A+P8O+f8/MP//Cf7/H4D//wf+/x+A//8H/v8fgP//B/7/H4D//wcA/P8/UP//CcD//wP1/58A
/P8/UP//CcD//wP1/58A/v8dcP//BfP/TwD8/wqA/48A8f8eAPzfAWD/TwDy/wMA+p8AAFD//wng//8A9f+fAP7/D1D//wng//8A
9f+fAP7/D4D//wTx/78A/P8JYP/vAvL/HQD6/wZg/08A4P8LAPqfAED/HgAAAIH9nQIA0v//7wTA////71H/////f/n/////q///
///f+P////9L/////3/A////7wHS///vAwCB/Z0CAPn/rwAA+v+vAAD6/5/5/68AAPr/rwAA+v+f+f+vAAD6/68AAPr/n/n/rwAA
+v+vAAD6/5/5/68AAPr/rwAA+v+f+f+vAAD6/68AAPr/nwAAAGMAAGCPABD6jwDC/39Q/v8H9/9OAPrPAgD6zwIA9/9OAFD+/wcA
0v9/ABD6jwAAcI8AAABjcgAAADCvAQAA898DACD/7wYAMP3/CQAQ+/8MAAD4/wEAgP8fALH/zwDT/58A8v9vADD/PQAA8xsAACAH
AAAAAAAAAEDJ/t5qAQAAAED9/////34AAAD4///////fAABw////////3wAA8///vyUQlN8AAPz//wcAAACSADD//78AAAAAAID/
////////LwDg/////////woA9f////////8EAADQ//8MAAAAAAAA0P//DAAAAAAAgP///////w0AAOD///////8GAAD1///////v
AQAAADD//78AAAAAAAAA/P//CAAAAJIAAPP//78lEJTfAABw////////3wAAAPj//////98AAABA/f////9+AAAAAEDJ/t5qAQ==
'''

HPP_OLD = 'std::uint64_t frame_count();\n'
HPP_NEW = HPP_OLD + """// Subtitles (ps2run_subs_patch.py): the disc reader says which movie it is reading; the window asks which one is on
void movie_note(const char *name, std::uint32_t rel_sector);
bool movie_now(std::string &name, std::uint64_t &start_frame, std::uint64_t &last_frame);
"""

CPP_FN_OLD = 'bool load_state(const std::uint8_t *data, std::size_t size) {\n'
CPP_FN_NEW = r"""// ---- Subtitles (ps2run_subs_patch.py)
namespace {
std::atomic_flag g_mv_lock = ATOMIC_FLAG_INIT;
std::string g_mv_name;
std::uint64_t g_mv_start = 0, g_mv_last = 0;
std::uint32_t g_mv_rel = 0;
}

void movie_note(const char *name, std::uint32_t rel_sector) {
    const std::uint64_t now = frame_count();
    while (g_mv_lock.test_and_set(std::memory_order_acquire)) {}
    if (g_mv_name != name || now - g_mv_last > 600 || rel_sector < g_mv_rel) {   // another movie, a long pause, or the movie starts again
        g_mv_name = name;
        g_mv_start = now;
    }
    g_mv_last = now;
    g_mv_rel = rel_sector;
    g_mv_lock.clear(std::memory_order_release);
}

bool movie_now(std::string &name, std::uint64_t &start_frame, std::uint64_t &last_frame) {
    while (g_mv_lock.test_and_set(std::memory_order_acquire)) {}
    const bool have = !g_mv_name.empty();
    name = g_mv_name;
    start_frame = g_mv_start;
    last_frame = g_mv_last;
    g_mv_lock.clear(std::memory_order_release);
    return have;
}

""" + CPP_FN_OLD

DISC_OLD = '    const std::size_t want = static_cast<std::size_t>(count) * kSector;\n    const std::size_t got = g_reader('
DISC_NEW = r"""    {   // ps2run_subs_patch.py: which movie is this read part of? (movies.txt in the PS2_SUBS folder: NAME first-sector sector-count)
        struct Mv { std::string name; std::uint32_t first, n; };
        static std::vector<Mv> mv;
        static bool tried = false;
        if (!tried) {
            tried = true;
            if (const char *d = std::getenv("PS2_SUBS")) {
                if (std::FILE *f = std::fopen((std::string(d) + "/movies.txt").c_str(), "r")) {
                    char nm[128];
                    unsigned a, n;
                    while (std::fscanf(f, "%127s %u %u", nm, &a, &n) == 3) mv.push_back({nm, a, n});
                    std::fclose(f);
                }
                std::fprintf(stderr, "[subs] %zu movies known from %s/movies.txt\n", mv.size(), d);
            }
        }
        for (const auto &m : mv)
            if (sector >= m.first && sector < m.first + m.n) { movie_note(m.name.c_str(), sector - m.first); break; }
    }
""" + DISC_OLD

WIN_INC_OLD = '#include <vector>\n'
WIN_INC_NEW = WIN_INC_OLD + '\n#include "subs.inc"   // ps2run_subs_patch.py\n'
WIN_DRAW_OLD = 'void poll() {\n'
WIN_DRAW_NEW = 'void poll() {\n    subs_draw(g_window);   // ps2run_subs_patch.py\n'
WIN_EV_OLD = '        if (e.type == SDL_QUIT) ps2::halt("window closed");\n'
WIN_EV_NEW = WIN_EV_OLD + '        subs_event(e);   // ps2run_subs_patch.py\n'


def patch(path, edits):
    p = os.path.join(root, path)
    if not os.path.exists(p):
        sys.exit('missing ' + p + ' (run in the ps2-web-recomp folder)')
    raw = open(p, 'rb').read().decode('utf-8')
    crlf = '\r\n' in raw
    s = raw.replace('\r\n', '\n')
    if MARK in s:
        print('already patched: ' + path)
        return
    for old, new in edits:
        if s.count(old) < 1:
            sys.exit('unknown source: ' + path + ' has no ' + repr(old[:60]))
        s = s.replace(old, new, 1)
    if crlf:
        s = s.replace('\n', '\r\n')
    open(p, 'wb').write(s.encode('utf-8'))
    print('patched: ' + path)


def write(path, text):
    p = os.path.join(root, path)
    if not os.path.isdir(os.path.dirname(p)):
        sys.exit('missing ' + os.path.dirname(p))
    old = open(p, encoding='utf-8').read() if os.path.exists(p) else None
    if old != text:
        open(p, 'w', encoding='utf-8', newline='\n').write(text)
        print('wrote: ' + path)


patch('runtime/include/ps2/system.hpp', [(HPP_OLD, HPP_NEW)])
patch('runtime/src/system.cpp', [(CPP_FN_OLD, CPP_FN_NEW)])
patch('runtime/src/disc.cpp', [(DISC_OLD, DISC_NEW)])
patch('host/window.cpp', [(WIN_INC_OLD, WIN_INC_NEW), (WIN_DRAW_OLD, WIN_DRAW_NEW), (WIN_EV_OLD, WIN_EV_NEW)])
parts = FONT_B64.split()
chunks = [''.join(parts)[i:i + 4000] for i in range(0, len(''.join(parts)), 4000)]
write('host/subs_font.inc', '// generated by ps2run_subs_patch.py: DejaVu Sans Bold (Bitstream Vera licence), 30 px, 4-bit alpha, base64\nstatic const char *const kFontParts[] = {\n' + ',\n'.join('"%s"' % c for c in chunks) + '\n};\n')
write('host/subs.inc', SUBS_INC.lstrip('\n'))
