"""Windows PC window, step 4: the profiler's CALLER list now finds the first return address inside ps2run.exe on the
game thread's stack (instead of the top word), so time spent waiting inside Windows is blamed on the function that waits.
Needs patch 3 first. Usage (in the ps2-web-recomp folder): python3 ps2run_windows_patch4.py [folder]   Safe to run twice.
Changes host/window.cpp.
"""
import os, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."

EDITS = {
    "host/window.cpp": [
        ("    std::uint64_t window_start = GetTickCount64();\n    for (;;) {\n        Sleep(1);\n",
         "    std::uint64_t window_start = GetTickCount64();\n"
         "    const std::uint64_t exe = reinterpret_cast<std::uint64_t>(GetModuleHandleA(nullptr));\n"
         "    const std::uint64_t exe_end = exe + reinterpret_cast<const IMAGE_NT_HEADERS64 *>(exe + reinterpret_cast<const IMAGE_DOS_HEADER *>(exe)->e_lfanew)->OptionalHeader.SizeOfImage;\n"
         "    for (;;) {\n        Sleep(1);\n"),
        ("                rets[n] = *reinterpret_cast<const std::uint64_t *>(ctx.Rsp);\n",
         "                const std::uint64_t *sp = reinterpret_cast<const std::uint64_t *>(ctx.Rsp);\n"
         "                std::uint64_t found = sp[0];\n"
         "                for (int i = 0; i < 512; ++i) {\n"
         "                    if (sp[i] >= exe && sp[i] < exe_end) { found = sp[i]; break; }\n"
         "                }\n"
         "                rets[n] = found;\n"),
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
