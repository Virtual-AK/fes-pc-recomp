"""Windows PC window, step 6: PS2_PROFILE_WIN=busy makes the profiler find the busiest thread by itself (after 6 seconds of
play it measures all threads for 3 seconds) and sample that one; the file header says which thread it chose.
Needs patch 3 first. Usage (in the ps2-web-recomp folder): python3 ps2run_windows_patch6.py [folder]   Safe to run twice.
Changes host/window.cpp.
"""
import os, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."

BUSY = r'''DWORD busiest_tid() {
    Sleep(6000);
    const auto times = [] {
        std::unordered_map<DWORD, double> m;
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
        if (snap == INVALID_HANDLE_VALUE) return m;
        THREADENTRY32 te{};
        te.dwSize = sizeof te;
        const DWORD pid = GetCurrentProcessId();
        if (Thread32First(snap, &te)) {
            do {
                if (te.th32OwnerProcessID != pid) continue;
                HANDLE h = OpenThread(THREAD_QUERY_LIMITED_INFORMATION, FALSE, te.th32ThreadID);
                if (!h) continue;
                FILETIME c, e, k, u;
                if (GetThreadTimes(h, &c, &e, &k, &u)) {
                    const auto ticks = [](const FILETIME &f) { return static_cast<double>((static_cast<std::uint64_t>(f.dwHighDateTime) << 32) | f.dwLowDateTime); };
                    m[te.th32ThreadID] = (ticks(k) + ticks(u)) / 1.0e7;
                }
                CloseHandle(h);
            } while (Thread32Next(snap, &te));
        }
        CloseHandle(snap);
        return m;
    };
    const auto a = times();
    Sleep(3000);
    const auto b = times();
    DWORD best = 0;
    double top = -1.0;
    for (const auto &kv : b) {
        if (kv.first == GetCurrentThreadId()) continue;
        const auto it = a.find(kv.first);
        const double d = kv.second - (it == a.end() ? kv.second : it->second);
        if (d > top) {
            top = d;
            best = kv.first;
        }
    }
    return best;
}

'''

EDITS = {
    "host/window.cpp": [
        ("std::atomic<DWORD> g_main_tid{0};\n", "std::atomic<DWORD> g_main_tid{0};\n\n" + BUSY),
        ("    while (!(tid = source.load())) Sleep(10);\n",
         "    if (which && !std::strcmp(which, \"busy\")) tid = busiest_tid();\n    else while (!(tid = source.load())) Sleep(10);\n"),
        ('            std::fprintf(f, "samples %zu\\n", n);\n',
         '            std::fprintf(f, "samples %zu\\n", n);\n            std::fprintf(f, "# sampled thread %lu (game thread %lu, main thread %lu)\\n", static_cast<unsigned long>(tid), static_cast<unsigned long>(g_emu_tid.load()), static_cast<unsigned long>(g_main_tid.load()));\n'),
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
