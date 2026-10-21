"""Windows PC window, step 8: a timing report. With PS2_STAGES=1 the window prints one line per second to its console showing
where each thread's second went: the game thread (waiting for the picture to be shown, pacing, or running the game) and the
graphics thread (reading input, drawing, idle). Nothing changes without the variable. Needs patch 2 first.
Usage (in the ps2-web-recomp folder): python3 ps2run_windows_patch8.py [folder]   Safe to run twice. Changes host/window.cpp.
"""
import os, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."

COUNTERS = r'''std::atomic<std::uint64_t> g_t_post{0}, g_t_pace{0}, g_t_poll{0}, g_t_render{0}, g_t_wait{0}, g_frames_emu{0};

std::uint64_t now_ns() {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());
}

'''

REPORT = r'''    if (std::getenv("PS2_STAGES")) {
        const auto ms = [](std::atomic<std::uint64_t> &a) { return static_cast<double>(a.exchange(0)) / 1.0e6; };
        const double post = ms(g_t_post), pace_ms = ms(g_t_pace), poll_ms = ms(g_t_poll), render_ms = ms(g_t_render), wait_ms = ms(g_t_wait);
        std::fprintf(stderr, "[stages per second] game thread: waiting for the screen %.0f ms, pacing %.0f ms, running the game %.0f ms (%llu frames) | graphics thread: input %.0f ms, drawing %.0f ms, idle %.0f ms\n",
                     post, pace_ms, std::max(0.0, seconds * 1000.0 - post - pace_ms), static_cast<unsigned long long>(g_frames_emu.exchange(0)), poll_ms, render_ms, wait_ms);
    }
'''

EDITS = {
    "host/window.cpp": [
        ("#include <atomic>\n", "#include <atomic>\n#include <chrono>\n"),
        ("void show_speed() {\n", COUNTERS + "void show_speed() {\n"),
        ("    SDL_SetWindowTitle(g_window, title);\n", "    SDL_SetWindowTitle(g_window, title);\n" + REPORT),
        ("    ps2::g_options.on_vblank = [] {\n        ps2::post_present();\n        pace();\n    };\n",
         "    ps2::g_options.on_vblank = [] {\n        const std::uint64_t a = now_ns();\n        ps2::post_present();\n        const std::uint64_t b = now_ns();\n        pace();\n        g_t_post += b - a;\n        g_t_pace += now_ns() - b;\n        ++g_frames_emu;\n    };\n"),
        ("        poll();\n        if (ps2::render_pending(g_gpu_present, g_gpu_present ? none : copy, show_speed, 8.0) == ps2::Rendered::idle) ps2::wait_render_work(4);\n",
         "        const std::uint64_t t0 = now_ns();\n        poll();\n        const std::uint64_t t1 = now_ns();\n        const bool idle = ps2::render_pending(g_gpu_present, g_gpu_present ? none : copy, show_speed, 8.0) == ps2::Rendered::idle;\n        const std::uint64_t t2 = now_ns();\n        if (idle) ps2::wait_render_work(4);\n        g_t_poll += t1 - t0;\n        g_t_render += t2 - t1;\n        if (idle) g_t_wait += now_ns() - t2;\n"),
    ],
}


def main():
    done = skipped = 0
    for rel, pairs in EDITS.items():
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            print("PATCH NOT APPLIED: %s not found (run in the ps2-web-recomp folder)" % rel)
            return 1
        text = open(path, newline="").read()
        crlf = "\r\n" in text
        work = text.replace("\r\n", "\n")
        if all(new in work for _, new in pairs):
            skipped += len(pairs)
            continue
        for old, new in pairs:
            if work.count(old) != 1:
                print("PATCH NOT APPLIED: %s does not look like the expected source" % rel)
                return 1
        for old, new in pairs:
            work = work.replace(old, new, 1)
            done += 1
        if crlf:
            work = work.replace("\n", "\r\n")
        if work != text:
            open(path, "w", newline="").write(work)
    print("already patched" if not done else "patched (%d edits, %d already there)" % (done, skipped))
    return 0


sys.exit(main())
