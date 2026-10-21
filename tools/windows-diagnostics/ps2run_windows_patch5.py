"""Windows PC window, step 5: the profiler can watch the graphics (main) thread instead of the game thread:
set PS2_PROFILE_WIN=render (any other value still watches the game thread). Needs patch 3 first.
Usage (in the ps2-web-recomp folder): python3 ps2run_windows_patch5.py [folder]   Safe to run twice. Changes host/window.cpp.
"""
import os, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."

EDITS = {
    "host/window.cpp": [
        ("std::atomic<DWORD> g_emu_tid{0};\n", "std::atomic<DWORD> g_emu_tid{0};\nstd::atomic<DWORD> g_main_tid{0};\n"),
        ("    while (!(tid = g_emu_tid.load())) Sleep(10);\n",
         "    const char *which = std::getenv(\"PS2_PROFILE_WIN\");\n"
         "    std::atomic<DWORD> &source = (which && !std::strcmp(which, \"render\")) ? g_main_tid : g_emu_tid;\n"
         "    while (!(tid = source.load())) Sleep(10);\n"),
        ("    if (std::getenv(\"PS2_PROFILE_WIN\")) std::thread(win_profiler).detach();\n",
         "    g_main_tid.store(GetCurrentThreadId());\n    if (std::getenv(\"PS2_PROFILE_WIN\")) std::thread(win_profiler).detach();\n"),
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
