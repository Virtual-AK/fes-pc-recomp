"""Windows PC window, step 12: the profiler can watch the VU thread (PS2_PROFILE_WIN=vu). The picture hand-off showed that
every frame passes through that thread before it reaches the graphics thread. Needs patches 3 and 5 first.
Usage (in the ps2-web-recomp folder): python3 ps2run_windows_patch12.py [folder]   Safe to run twice. Changes host/window.cpp.
"""
import os, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."

EDITS = {
    "host/window.cpp": [
        ("std::atomic<DWORD> g_main_tid{0};\n", "std::atomic<DWORD> g_main_tid{0};\nstd::atomic<DWORD> g_vu_tid{0};\n"),
        ("    std::atomic<DWORD> &source = (which && !std::strcmp(which, \"render\")) ? g_main_tid : g_emu_tid;\n",
         "    std::atomic<DWORD> &source = (which && !std::strcmp(which, \"vu\")) ? g_vu_tid : (which && !std::strcmp(which, \"render\")) ? g_main_tid : g_emu_tid;\n"),
        ("        std::thread(ps2::run_vu_thread).detach();\n",
         "        std::thread([] {\n#ifdef _WIN32\n            g_vu_tid.store(GetCurrentThreadId());\n#endif\n            ps2::run_vu_thread();\n        }).detach();\n"),
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
