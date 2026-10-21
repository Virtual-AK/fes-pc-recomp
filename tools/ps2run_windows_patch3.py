"""Windows PC window, step 3: a built-in sampling profiler. With the environment variable PS2_PROFILE_WIN=1 the window
looks at what the game thread is doing about 1000 times a second and writes prof_win.txt (next to ps2run.exe) every
10 seconds, covering just those 10 seconds. The build also writes ps2run.map; tools/winprof_resolve.py turns the two
into a list of the busiest functions. Without the variable nothing changes. Needs patches 1 and 2 first.
Usage (in the ps2-web-recomp folder): python3 ps2run_windows_patch3.py [folder]   Safe to run twice.
Changes host/window.cpp and CMakeLists.txt.
"""
import os, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."

PROF = r'''#ifdef _WIN32
std::atomic<DWORD> g_emu_tid{0};

// Samples the emulation thread: suspend, read its instruction pointer and the word on top of its stack, resume.
// Nothing is allocated while it is suspended (it could be holding the heap lock).
void win_profiler() {
    DWORD tid = 0;
    while (!(tid = g_emu_tid.load())) Sleep(10);
    HANDLE h = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE, tid);
    if (!h) return;
    timeBeginPeriod(1);
    constexpr std::size_t kMax = 20000;
    std::vector<std::uint64_t> pcs(kMax), rets(kMax);
    std::size_t n = 0;
    std::uint64_t window_start = GetTickCount64();
    for (;;) {
        Sleep(1);
        if (SuspendThread(h) != static_cast<DWORD>(-1)) {
            CONTEXT ctx{};
            ctx.ContextFlags = CONTEXT_CONTROL;
            if (GetThreadContext(h, &ctx) && n < kMax) {
                pcs[n] = ctx.Rip;
                rets[n] = *reinterpret_cast<const std::uint64_t *>(ctx.Rsp);
                ++n;
            }
            ResumeThread(h);
        }
        if (GetTickCount64() - window_start < 10000) continue;
        std::unordered_map<std::uint64_t, std::uint32_t> a, b;
        for (std::size_t i = 0; i < n; ++i) {
            ++a[pcs[i]];
            ++b[rets[i]];
        }
        if (std::FILE *f = std::fopen("prof_win.txt", "w")) {
            std::fprintf(f, "samples %zu\n", n);
            const auto dump = [&](const char *name, const std::unordered_map<std::uint64_t, std::uint32_t> &m) {
                std::vector<std::pair<std::uint32_t, std::uint64_t>> v;
                for (const auto &kv : m) v.push_back({kv.second, kv.first});
                std::sort(v.begin(), v.end(), std::greater<std::pair<std::uint32_t, std::uint64_t>>());
                if (v.size() > 6000) v.resize(6000);
                std::fprintf(f, "%s\n", name);
                for (const auto &p : v) {
                    HMODULE mod = nullptr;
                    char path[MAX_PATH] = "?";
                    std::uint64_t rva = p.second;
                    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, reinterpret_cast<LPCSTR>(p.second), &mod) && mod) {
                        GetModuleFileNameA(mod, path, MAX_PATH);
                        rva = p.second - reinterpret_cast<std::uint64_t>(mod);
                    }
                    const char *base = std::strrchr(path, '\\');
                    std::fprintf(f, "%u %s %llx\n", p.first, base ? base + 1 : path, static_cast<unsigned long long>(rva));
                }
            };
            dump("PC", a);
            dump("CALLER", b);
            std::fclose(f);
        }
        n = 0;
        window_start = GetTickCount64();
    }
}
#endif

'''

EDITS = {
    "host/window.cpp": [
        ("#include <tlhelp32.h>\n", "#include <tlhelp32.h>\n#include <mmsystem.h>\n#pragma comment(lib, \"winmm.lib\")\n"),
        ("void on_vblank() {\n", PROF + "void on_vblank() {\n"),
        ("    emulation.start([&] {\n        result = emulate();\n",
         "    emulation.start([&] {\n#ifdef _WIN32\n        g_emu_tid.store(GetCurrentThreadId());\n#endif\n        result = emulate();\n"),
        ("    int result = 0;\n    EmulationThread emulation;\n",
         "    int result = 0;\n    EmulationThread emulation;\n#ifdef _WIN32\n    if (std::getenv(\"PS2_PROFILE_WIN\")) std::thread(win_profiler).detach();\n#endif\n"),
    ],
    "CMakeLists.txt": [
        ('"${SDL2_DIR}/lib/x64/SDL2.lib" psapi)\n',
         '"${SDL2_DIR}/lib/x64/SDL2.lib" psapi)\n            target_link_options(ps2run PRIVATE "/MAP:$<TARGET_FILE_DIR:ps2run>/ps2run.map")\n'),
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
