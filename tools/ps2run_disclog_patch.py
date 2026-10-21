"""Disc read log for the PC window of PS2 Web Recomp (research for the dialogue Log, see docs/log-plan.md).

With the environment variable PS2_LOG_DISC=1 the runner prints one line to stderr for every read from the disc:
  [disc] frame N sector S xC  PATH/OF/FILE
so a voice clip (a file, or part of a big archive, read at the moment a line is spoken) shows up next to the frame it was read in.
Nothing changes in the game. The launcher passes variables listed in ~/.p3fes-window-env (lines like PS2_LOG_DISC=1).

Run in the ps2-web-recomp folder:  python3 ps2run_disclog_patch.py [folder]
(patches runtime/src/disc.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
REL = 'runtime/src/disc.cpp'

INC_OLD = '#include "ps2/disc.hpp"\n'
INC_NEW = '#include "ps2/disc.hpp"\n#include "ps2/system.hpp"\n#include <cstdlib>\n'
READ_OLD = 'bool read(std::uint32_t sector, std::uint32_t count, void *out) {\n    if (!g_reader) return false;\n'
READ_NEW = READ_OLD + r'''    static const bool log_disc = std::getenv("PS2_LOG_DISC") != nullptr;   // ps2run_disclog_patch.py
    if (log_disc) {
        const char *name = "?";
        for (const auto &kv : g_index)
            if (!kv.second.directory && sector >= kv.second.sector && sector < kv.second.sector + (kv.second.size + kSector - 1) / kSector) {
                name = kv.first.c_str();
                break;
            }
        std::fprintf(stderr, "[disc] frame %llu sector %u x%u  %s\n", static_cast<unsigned long long>(frame_count()), sector, count, name);
    }
'''
EDITS = [(INC_OLD, INC_NEW), (READ_OLD, READ_NEW)]


def fail(msg):
    print("PATCH NOT APPLIED:", msg)
    raise SystemExit(1)


try:
    with open(root + '/' + REL, newline='') as f:
        t = f.read()
except OSError:
    fail("cannot read " + REL)
crlf = '\r\n' in t
t = t.replace('\r\n', '\n')
if all(new in t for _, new in EDITS):
    print("already patched")
    raise SystemExit
done = 0
for old, new in EDITS:
    if new in t:
        continue
    if t.count(old) != 1:
        fail(REL + " does not look like the expected source (cannot find: " + old.strip().splitlines()[0][:70] + ")")
    t = t.replace(old, new)
    done += 1
with open(root + '/' + REL, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d edits)" % done)
