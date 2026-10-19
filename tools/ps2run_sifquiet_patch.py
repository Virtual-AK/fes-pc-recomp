"""Print the "[sif] command 0x........ has no handler" message once for each command number instead of every time.
The message is harmless (the game sends a status command the runner does not need), but it filled the terminal.
Patches runtime/src/iop/sif.cpp, used by both the PC runner and the browser build.
Usage (in the ps2-web-recomp folder): python3 ps2run_sifquiet_patch.py [runtime/src/iop/sif.cpp]
Safe to run twice. Rebuild afterwards (ninja -C build/native-p3fes ps2run, or scripts/build_web.sh p3fes)
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/iop/sif.cpp'
s = open(p).read()
if 'has no handler (shown once)' in s:
    print("already patched"); raise SystemExit
OLD = """            std::fprintf(stderr, "[sif] command 0x%08X has no handler\\n", h->cid);
"""
NEW = """            static std::uint32_t seenCommands[32];
            static int seenCount = 0;
            bool again = false;
            for (int i = 0; i < seenCount; ++i) again = again || seenCommands[i] == h->cid;
            if (!again) {
                if (seenCount < 32) seenCommands[seenCount++] = h->cid;
                std::fprintf(stderr, "[sif] command 0x%08X has no handler (shown once)\\n", h->cid);
            }
"""
if s.count(OLD) != 1:
    print("PATCH NOT APPLIED: runtime/src/iop/sif.cpp does not look like the expected source"); raise SystemExit(1)
open(p, 'w').write(s.replace(OLD, NEW, 1))
print("patched (the no-handler message is shown once per command)")
