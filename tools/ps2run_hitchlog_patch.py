"""Hitch log for the PC window of PS2 Web Recomp (a diagnostic; it changes nothing on screen).

With PS2_HITCHLOG=<ms> set (for example 50), the window writes a line to the log (stderr) every time the time between two game frames is longer
than that many milliseconds, and a line for every saved game state (autosave, in-game save copy, F5/F6) with how long writing it took.
Every line starts with the time of day (HH:MM:SS.mmm, this computer's clock), so a stutter you saw in a clip can be matched to the log.

  [hitch] 14:02:31.482  frame 31872  gap 412 ms  (window part of the last frame: poll 0.1, present 3.2, pace 8.0 ms; game thread about 401 ms)
  [state] 14:02:31.480  timer save took 398 ms

A normal frame is 16.7 ms. "gap" is the time since the previous frame started. "game thread" is what is left of the gap after the window's own work
(polling input, drawing, waiting for the next frame), that is, time spent running the game itself or saving a state.

  PS2_HITCHLOG=50      (in ~/.p3fes-window-env; without the line nothing is logged)

Run in the ps2-web-recomp folder AFTER ps2run_autosave_patch.py:  python3 ps2run_hitchlog_patch.py [folder]
(patches host/window.cpp and runtime/src/system.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
TAG = 'ps2run_hitchlog_patch.py'
WIN = 'host/window.cpp'
SYS = 'runtime/src/system.cpp'

WIN_CODE = r'''// ---- hitch log (%TAG%) ----
std::string hitch_clock() {
    const auto now = std::chrono::system_clock::now();
    const std::time_t t = std::chrono::system_clock::to_time_t(now);
    const int ms = static_cast<int>(std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count() % 1000);
    std::tm tm{};
#ifdef _WIN32
    localtime_s(&tm, &t);
#else
    localtime_r(&t, &tm);
#endif
    char buf[32];
    std::snprintf(buf, sizeof buf, "%02d:%02d:%02d.%03d", tm.tm_hour, tm.tm_min, tm.tm_sec, ms);
    return buf;
}

double hitch_ms() {
    return static_cast<double>(SDL_GetPerformanceCounter()) * 1000.0 / static_cast<double>(SDL_GetPerformanceFrequency());
}

void on_vblank() {
    static double threshold = -1.0, last = 0.0, t_poll = 0.0, t_present = 0.0, t_pace = 0.0;
    static std::uint64_t frame = 0;
    if (threshold < 0.0) {
        const char *e = std::getenv("PS2_HITCHLOG");
        threshold = e ? std::atof(e) : 0.0;
        if (threshold > 0.0) std::fprintf(stderr, "[hitch] logging frames longer than %.0f ms\n", threshold);
    }
    if (threshold <= 0.0) {
        show_speed();
        poll();
        present();   // turbo draws every frame: skipping frames could leave the game waiting forever
        pace();
        return;
    }
    const double t0 = hitch_ms();
    ++frame;
    if (last > 0.0 && t0 - last > threshold) {
        const double gap = t0 - last;
        std::fprintf(stderr, "[hitch] %s  frame %llu  gap %.0f ms  (window part of the last frame: poll %.1f, present %.1f, pace %.1f ms; game thread about %.0f ms)\n",
                     hitch_clock().c_str(), static_cast<unsigned long long>(frame), gap, t_poll, t_present, t_pace, gap - t_poll - t_present - t_pace);
    }
    last = t0;
    show_speed();
    const double a = hitch_ms();
    poll();
    const double b = hitch_ms();
    present();   // turbo draws every frame: skipping frames could leave the game waiting forever
    const double c = hitch_ms();
    pace();
    const double d = hitch_ms();
    t_poll = b - a;
    t_present = c - b;
    t_pace = d - c;
}
// ---- end hitch log ----
'''.replace('%TAG%', TAG)

WIN_OLD_FN = 'void on_vblank() {\n    show_speed();\n    poll();\n    present();   // turbo draws every frame: skipping frames could leave the game waiting forever\n    pace();\n}\n'

SYS_OLD = ('            g_state_request = false;\n'
           '            save_state(g_options.save_state_path);\n'
           '#ifndef __EMSCRIPTEN__\n'
           '            as_finish();\n'
           '#endif\n')
SYS_NEW = ('            g_state_request = false;\n'
           '#ifndef __EMSCRIPTEN__\n'
           '            const auto hl_t0 = std::chrono::steady_clock::now();   // ' + TAG + '\n'
           '            const std::string hl_kind = g_as_final.empty() ? std::string("other") : [] { const std::string n = std::filesystem::path(g_as_final).filename().string(); return n.substr(0, n.find(\'_\')); }();\n'
           '#endif\n'
           '            save_state(g_options.save_state_path);\n'
           '#ifndef __EMSCRIPTEN__\n'
           '            as_finish();\n'
           '            if (std::getenv("PS2_HITCHLOG")) {   // ' + TAG + '\n'
           '                const auto now = std::chrono::system_clock::now();\n'
           '                const std::time_t tt = std::chrono::system_clock::to_time_t(now);\n'
           '                const int ms = static_cast<int>(std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count() % 1000);\n'
           '                std::tm tm{};\n'
           '#ifdef _WIN32\n'
           '                localtime_s(&tm, &tt);\n'
           '#else\n'
           '                localtime_r(&tt, &tm);\n'
           '#endif\n'
           '                std::fprintf(stderr, "[state] %02d:%02d:%02d.%03d  %s save took %.0f ms\\n", tm.tm_hour, tm.tm_min, tm.tm_sec, ms, hl_kind.c_str(),\n'
           '                             std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - hl_t0).count());\n'
           '            }\n'
           '#endif\n')

FILES = {
    WIN: [
        ('#include <cstdio>\n', '#include <chrono>  // ' + TAG + '\n#include <ctime>\n#include <cstdio>\n'),
        (WIN_OLD_FN, WIN_CODE),
    ],
    SYS: [(SYS_OLD, SYS_NEW)],
}

texts = {}
for path, edits in FILES.items():
    try:
        with open(root + '/' + path, newline='') as f:
            raw = f.read()
    except OSError:
        print("PATCH NOT APPLIED: cannot read " + path)
        raise SystemExit(1)
    texts[path] = (raw, '\r\n' in raw, raw.replace('\r\n', '\n'))
if all(TAG in t for _, _, t in texts.values()):
    print("already patched")
    raise SystemExit
for path, edits in FILES.items():
    t = texts[path][2]
    if TAG in t:
        print("PATCH NOT APPLIED: " + path + " is only partly patched")
        raise SystemExit(1)
    for old, _ in edits:
        if t.count(old) != 1:
            print("PATCH NOT APPLIED: " + path + " does not look like the expected source (run ps2run_autosave_patch.py first)")
            raise SystemExit(1)
n = 0
for path, edits in FILES.items():
    raw, crlf, t = texts[path]
    for old, new in edits:
        t = t.replace(old, new)
        n += 1
    with open(root + '/' + path, 'w', newline='') as f:
        f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d edits)" % n)
