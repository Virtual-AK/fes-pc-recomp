"""Windows PC window, step 9 (experiment): with PS2_SPIN_WAIT=1 the queue's blocking waits (game thread waiting for the
screen, for queue space, for downloads) poll with a thread yield instead of using the system wait/wake. If the frame rate
changes, wake-up delay is the cause. Without the variable nothing changes. Needs patch 7 first.
Usage (in the ps2-web-recomp folder): python3 ps2run_windows_patch9.py [folder]   Safe to run twice.
Changes runtime/src/gs/queue.cpp. Rebuild with: build_win.bat runtime, then build_win.bat game.
"""
import os, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."

EDITS = {
    "runtime/src/gs/queue.cpp": [
        ("#pragma comment(lib, \"synchronization.lib\")\n", "#pragma comment(lib, \"synchronization.lib\")\n#include <cstdlib>\n#include <thread>\n"),
        ("#else\n    value.wait(seen);\n#endif\n",
         "#elif defined(_WIN32)\n    static const bool spin = std::getenv(\"PS2_SPIN_WAIT\") != nullptr;\n    if (spin) {\n        while (value.load() == seen) std::this_thread::yield();\n    } else {\n        value.wait(seen);\n    }\n#else\n    value.wait(seen);\n#endif\n"),
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
