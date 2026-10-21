"""Windows PC window, step 2: the title bar also shows how busy the three busiest threads are (for example
"threads 99/41/12%"), to find which thread limits the frame rate. Needs ps2run_windows_patch.py first.
Usage (in the ps2-web-recomp folder): python3 ps2run_windows_patch2.py [folder]   Safe to run twice. Changes host/window.cpp.
"""
import os, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."

FUNC = r'''#ifdef _WIN32
std::string busiest_threads(double seconds) {
    static std::unordered_map<DWORD, double> prev;
    std::unordered_map<DWORD, double> cur;
    std::vector<double> load;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snap == INVALID_HANDLE_VALUE) return "";
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
                const double s = (ticks(k) + ticks(u)) / 1.0e7;
                cur[te.th32ThreadID] = s;
                const auto it = prev.find(te.th32ThreadID);
                load.push_back((s - (it == prev.end() ? s : it->second)) / seconds * 100.0);
            }
            CloseHandle(h);
        } while (Thread32Next(snap, &te));
    }
    CloseHandle(snap);
    prev.swap(cur);
    std::sort(load.begin(), load.end(), std::greater<double>());
    char buf[64] = "";
    std::snprintf(buf, sizeof buf, "  threads %.0f/%.0f/%.0f%%", load.size() > 0 ? load[0] : 0.0, load.size() > 1 ? load[1] : 0.0, load.size() > 2 ? load[2] : 0.0);
    return buf;
}
#else
std::string busiest_threads(double) { return ""; }
#endif

'''

EDITS = {
    "host/window.cpp": [
        ("#include <psapi.h>\n", "#include <psapi.h>\n#include <tlhelp32.h>\n"),
        ("#include <thread>\n", "#include <thread>\n#include <unordered_map>\n"),
        ("void show_speed() {\n", FUNC + "void show_speed() {\n"),
        ("    char title[192];\n", "    char title[256];\n"),
        ('audio %.0f ms", static_cast<double>(frames) / seconds,\n                  (cpu - cpu_start) / seconds * 100.0, (gpu - gpu_start) / (seconds * 10.0), resident_mb(), queued);',
         'audio %.0f ms%s", static_cast<double>(frames) / seconds,\n                  (cpu - cpu_start) / seconds * 100.0, (gpu - gpu_start) / (seconds * 10.0), resident_mb(), queued, busiest_threads(seconds).c_str());'),
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
