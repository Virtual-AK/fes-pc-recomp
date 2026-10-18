"""Add an F12 "rewind capture" to the game window of PS2 Web Recomp (host/window.cpp).

The window keeps the last 300 shown frames in memory (about 12 seconds; change with the environment variable
PS2_CAPTURE_FRAMES). Press F12 (or F9, F8 or C; set PS2_LOG_KEYS=1 to log every key press) right after something odd flashes by, and those frames are written as picture
files (PPM) to a numbered folder under capture (change with the environment variable PS2_CAPTURE_DIR). Contact sheets of them can then be made with
p3fes_contact.py, and the pictures stay on your PC like every other game picture.
Run in the ps2-web-recomp folder: python3 ps2run_window_capture_patch.py [host/window.cpp]
(idempotent; refuses unknown source). Rebuild afterwards: ninja -C build/native-p3fes ps2run
"""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else 'host/window.cpp'
s = open(path).read()
KEY_LINE_OLD = '        if (e.type == SDL_KEYDOWN && e.key.keysym.scancode == SDL_SCANCODE_F12 && !e.key.repeat) g_capture_now.store(true);\n'
KEY_BLOCK = """        if (e.type == SDL_KEYDOWN && !e.key.repeat) {
            const SDL_Scancode k = e.key.keysym.scancode;
            static const bool log_keys = std::getenv("PS2_LOG_KEYS") != nullptr;
            if (log_keys) std::fprintf(stderr, "[key] scancode %d (%s)\\n", static_cast<int>(k), SDL_GetScancodeName(k));
            if (k == SDL_SCANCODE_F12 || k == SDL_SCANCODE_F9 || k == SDL_SCANCODE_F8 || k == SDL_SCANCODE_C) {
                std::fprintf(stderr, "[capture] requested\\n");
                g_capture_now.store(true);
            }
        }
"""
if 'g_capture_now' in s:
    # upgrades of trees patched by older versions: longer window, then more keys and a log line
    ups = []
    old = '    if (g_capture_ring.size() > 90) g_capture_ring.pop_front();\n'
    if old in s:
        s = s.replace(old, '    static const std::size_t keep = std::getenv("PS2_CAPTURE_FRAMES") ? static_cast<std::size_t>(std::atoi(std::getenv("PS2_CAPTURE_FRAMES"))) : 300;\n    while (g_capture_ring.size() > keep) g_capture_ring.pop_front();\n', 1)
        ups.append("longer capture window")
    if KEY_LINE_OLD in s:
        s = s.replace(KEY_LINE_OLD, KEY_BLOCK, 1)
        ups.append("more keys and log line")
    if not ups:
        print("already patched"); raise SystemExit
    open(path, 'w').write(s)
    print("patched (" + ", ".join(ups) + ")"); raise SystemExit

inc = '#include <vector>\n'
poll = 'void poll() {\n'
ev = '        if (e.type == SDL_WINDOWEVENT && e.window.event == SDL_WINDOWEVENT_SIZE_CHANGED && g_gpu_present) {\n'
show = 'void show_pixels(const std::uint32_t *rgba, std::uint32_t w, std::uint32_t h) {\n'
for what, text in (('include', inc), ('poll()', poll), ('window event', ev), ('show_pixels()', show)):
    if s.count(text) != 1:
        print("PATCH NOT APPLIED:", what); raise SystemExit(1)

helper = r'''// F12 rewind capture: the last 300 shown frames are written to a numbered folder (see ps2run_window_capture_patch.py)
std::atomic<bool> g_capture_now{false};
std::deque<std::vector<std::uint32_t>> g_capture_ring;
std::uint32_t g_capture_w = 0, g_capture_h = 0;
int g_capture_count = 0;

void capture_push(const std::uint32_t *rgba, std::uint32_t w, std::uint32_t h) {
    if (w != g_capture_w || h != g_capture_h) {
        g_capture_ring.clear();
        g_capture_w = w;
        g_capture_h = h;
    }
    g_capture_ring.emplace_back(rgba, rgba + static_cast<std::size_t>(w) * h);
    static const std::size_t keep = std::getenv("PS2_CAPTURE_FRAMES") ? static_cast<std::size_t>(std::atoi(std::getenv("PS2_CAPTURE_FRAMES"))) : 300;
    while (g_capture_ring.size() > keep) g_capture_ring.pop_front();
    if (!g_capture_now.exchange(false)) return;
    const char *base = std::getenv("PS2_CAPTURE_DIR");
    const std::string dir = std::string(base ? base : "capture") + "/" + std::to_string(++g_capture_count);
    std::filesystem::create_directories(dir);
    int n = 0;
    for (const std::vector<std::uint32_t> &f : g_capture_ring) {
        char name[32];
        std::snprintf(name, sizeof name, "/frame_%03d.ppm", n++);
        std::FILE *out = std::fopen((dir + name).c_str(), "wb");
        if (!out) continue;
        std::fprintf(out, "P6\n%u %u\n255\n", w, h);
        std::vector<std::uint8_t> row(static_cast<std::size_t>(w) * 3);
        for (std::uint32_t y = 0; y < h; ++y) {
            for (std::uint32_t x = 0; x < w; ++x) {
                const std::uint32_t p = f[static_cast<std::size_t>(y) * w + x];
                row[x * 3] = static_cast<std::uint8_t>(p);
                row[x * 3 + 1] = static_cast<std::uint8_t>(p >> 8);
                row[x * 3 + 2] = static_cast<std::uint8_t>(p >> 16);
            }
            std::fwrite(row.data(), 1, row.size(), out);
        }
        std::fclose(out);
    }
    std::fprintf(stderr, "[capture] wrote %d frames to %s\n", n, dir.c_str());
}

'''
s = s.replace(inc, '#include <deque>\n#include <filesystem>\n#include <string>\n' + inc, 1)
s = s.replace(poll, helper + poll, 1)
s = s.replace(ev, KEY_BLOCK + ev, 1)
s = s.replace(show, show + '    capture_push(rgba, w, h);\n', 1)
open(path, 'w').write(s)
print("patched (F12 capture)")
