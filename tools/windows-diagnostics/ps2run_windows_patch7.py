"""Windows PC window, step 7 (the frame-rate fix): the graphics thread used to wait for new work by sleeping 1 ms at a time
on Windows (Windows sleeps are coarse, so every hand-off from the game thread arrived late). It now waits on the queue's
counter with WaitOnAddress, so it wakes the moment work is posted. Also switches the per-second thread readout in the title
bar off unless PS2_THREADS=1 is set (it cost the graphics thread about 10%).
Needs patch 2 first (patches 3 to 6 are not needed). Usage (in the ps2-web-recomp folder):
python3 ps2run_windows_patch7.py [folder]   Safe to run twice. Changes runtime/src/gs/queue.cpp and host/window.cpp.
Rebuild with: build_win.bat runtime, then build_win.bat game.
"""
import os, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."

EDITS = {
    "runtime/src/gs/queue.cpp": [
        ("#else\n#include <chrono>\n#include <thread>\n#endif\n",
         "#elif defined(_WIN32)\n#define NOMINMAX\n#define WIN32_LEAN_AND_MEAN\n#include <windows.h>\n#include <synchapi.h>\n#pragma comment(lib, \"synchronization.lib\")\n#else\n#include <chrono>\n#include <thread>\n#endif\n"),
        ("#else\n    (void)seen;\n    std::this_thread::sleep_for(std::chrono::milliseconds(std::min(timeout_ms, 1)));\n#endif\n",
         "#elif defined(_WIN32)\n    std::uint32_t expected = seen;\n    WaitOnAddress(reinterpret_cast<volatile void *>(&posted_), &expected, sizeof expected, timeout_ms < 0 ? INFINITE : static_cast<DWORD>(timeout_ms));\n#else\n    (void)seen;\n    std::this_thread::sleep_for(std::chrono::milliseconds(std::min(timeout_ms, 1)));\n#endif\n"),
    ],
    "host/window.cpp": [
        ("std::string busiest_threads(double seconds) {\n    static std::unordered_map<DWORD, double> prev;\n",
         "std::string busiest_threads(double seconds) {\n    static const bool enabled = std::getenv(\"PS2_THREADS\") != nullptr;\n    if (!enabled) return \"\";\n    static std::unordered_map<DWORD, double> prev;\n"),
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
