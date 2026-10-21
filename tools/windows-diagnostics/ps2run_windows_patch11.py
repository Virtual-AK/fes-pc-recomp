"""Windows PC window, step 11 (measurement): with PS2_STAGES=1 the console also shows, once a second, how long each shown picture
waited between being queued by the game thread and being picked up by the graphics thread, and how long the present call took.
Nothing changes without the variable. Works on the original source (no other patch needed).
Usage (in the ps2-web-recomp folder): python3 ps2run_windows_patch11.py [folder]   Safe to run twice. Changes runtime/src/gs/gs.cpp.
Rebuild with: build_win.bat runtime, then build_win.bat game.
"""
import os, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."

DEFS = r'''std::uint64_t g_post_ts[8] = {};
std::atomic<std::uint64_t> g_lat_pickup{0}, g_lat_present{0}, g_lat_n{0}, g_emu_wait{0};
std::uint64_t stage_now() {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());
}
'''

EDITS = {
    "runtime/src/gs/gs.cpp": [
        ("std::uint32_t g_posted_presents = 0;\n", "std::uint32_t g_posted_presents = 0;\n" + DEFS),
        ("    queue::post(queue::kPresent, 0, 0, &regs, sizeof regs);\n    ++g_posted_presents;\n    for (std::uint32_t done = g_presented.load(); g_posted_presents - done > 2; done = g_presented.load()) queue::wait(g_presented, done);\n",
         "    g_post_ts[g_posted_presents % 8] = stage_now();\n    queue::post(queue::kPresent, 0, 0, &regs, sizeof regs);\n    ++g_posted_presents;\n    const std::uint64_t wait_from = stage_now();\n    for (std::uint32_t done = g_presented.load(); g_posted_presents - done > 2; done = g_presented.load()) queue::wait(g_presented, done);\n    g_emu_wait += stage_now() - wait_from;\n"),
        ("            std::memcpy(&regs, payload, sizeof regs);\n            on_present(regs);\n            presented = true;\n",
         "            std::memcpy(&regs, payload, sizeof regs);\n            const std::uint64_t t_start = stage_now();\n            const std::uint64_t posted_at = g_post_ts[g_presented.load() % 8];\n            on_present(regs);\n            g_lat_pickup += t_start - posted_at;\n            g_lat_present += stage_now() - t_start;\n            ++g_lat_n;\n            presented = true;\n"),
        ("        if (presented) {\n            g_presented.fetch_add(1);\n",
         "        if (presented) {\n            static const bool report = std::getenv(\"PS2_STAGES\") != nullptr;\n            static std::uint64_t last_report = 0;\n            if (report && stage_now() - last_report > 1000000000ull) {\n                const double n = static_cast<double>(std::max<std::uint64_t>(1, g_lat_n.exchange(0)));\n                std::fprintf(stderr, \"[hand-off per frame] queued picture picked up after %.1f ms, present call %.1f ms | game thread waited %.0f ms in the last second\\n\",\n                             static_cast<double>(g_lat_pickup.exchange(0)) / 1.0e6 / n, static_cast<double>(g_lat_present.exchange(0)) / 1.0e6 / n,\n                             static_cast<double>(g_emu_wait.exchange(0)) / 1.0e6);\n                last_report = stage_now();\n            }\n            g_presented.fetch_add(1);\n"),
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
