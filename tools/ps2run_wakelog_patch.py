"""Long-wait log for the PS2 Web Recomp runtime (research tool, see docs/known-issues.md).

With PS2_WAKE_TRACE=N (a number of frames, e.g. 30) every time a game thread that waited N frames or more on a semaphore or in
SleepThread is released, the window log gets
  [wake] frame F thread T waited W frames (semaphore|sleep ID, blocked at ra R)  woken by thread G [in an interrupt handler] ra R2  stack: ...
so the thing that ended a long wait (a sound, a disc read, a timer, another game thread) can be named by its code address.
Nothing changes in the game; without the variable each wait costs one flag test.
Put the line in ~/.p3fes-window-env (like PS2_STORE_WATCH) and play; log: ~/.p3fes-window.log.

Run in the ps2-web-recomp folder:  python3 ps2run_wakelog_patch.py [folder]
(patches runtime/src/kernel.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
path = root + '/runtime/src/kernel.cpp'

INC_OLD = '#include <map>\n'
INC_NEW = '#include <map>\n#include <unordered_map>\n'
BLK_OLD = 'void block_current(Cpu &c, WaitType type, int id) {\n'
BLK_NEW = r'''// ---- long-wait log (ps2run_wakelog_patch.py)
struct WakeNote { std::uint64_t frame; int type; int id; std::uint32_t ra; };
std::unordered_map<int, WakeNote> g_wake_notes;
int g_wake_min = -1;

void wake_note_block(int tid, int type, int id, std::uint32_t ra) {
    if (g_wake_min < 0) {
        const char *e = std::getenv("PS2_WAKE_TRACE");
        g_wake_min = (e && *e) ? std::max(1, std::atoi(e)) : 0;
        if (g_wake_min) std::fprintf(stderr, "[wake] logging waits of %d frames or more\n", g_wake_min);
    }
    if (g_wake_min > 0) g_wake_notes[tid] = WakeNote{frame_count(), type, id, ra};
}

void wake_note_release(const Thread &t, std::int64_t result) {
    if (g_wake_min <= 0) return;
    const auto it = g_wake_notes.find(t.id);
    if (it == g_wake_notes.end()) return;
    const WakeNote n = it->second;
    g_wake_notes.erase(it);
    const std::uint64_t now = frame_count();
    if (now - n.frame < static_cast<std::uint64_t>(g_wake_min)) return;
    std::fprintf(stderr, "[wake] frame %llu thread %d waited %llu frames (%s %d, blocked at ra %08x) result %lld  woken by thread %d%s ra %08x  stack:",
                 static_cast<unsigned long long>(now), t.id, static_cast<unsigned long long>(now - n.frame), n.type == 2 ? "semaphore" : "sleep", n.id, n.ra,
                 static_cast<long long>(result), g_current, g_in_handler ? " in an interrupt handler" : "", g_cpu.r[31].w[0]);
    const std::uint32_t sp = g_cpu.r[29].w[0];
    int shown = 0;
    for (std::uint32_t k = 0; k < 256 && shown < 8; ++k) {
        const std::uint32_t at = sp + k * 4u;
        if (at + 4 > kRamSize) break;
        const std::uint32_t v = ld32(at);
        if (v < 0x100000u || v >= 0x1F00000u || (v & 3u)) continue;
        const std::uint32_t prev = ld32(v - 8);
        if ((prev >> 26) == 3u || (prev & 0xFC00003Fu) == 9u) {
            std::fprintf(stderr, " %08x", v);
            ++shown;
        }
    }
    std::fprintf(stderr, "\n");
}

void block_current(Cpu &c, WaitType type, int id) {
'''
BLK2_OLD = '    t->wait_id = id;\n    save_context(c, t->context);\n'
BLK2_NEW = '    t->wait_id = id;\n    wake_note_block(t->id, static_cast<int>(type), id, c.r[31].w[0]);\n    save_context(c, t->context);\n'
REL_OLD = 'void release(Thread &t, std::int64_t result) {\n'
REL_NEW = REL_OLD + '    wake_note_release(t, result);\n'
EDITS = [(INC_OLD, INC_NEW), (BLK_OLD, BLK_NEW), (BLK2_OLD, BLK2_NEW), (REL_OLD, REL_NEW)]

try:
    with open(path, newline='') as fh:
        text = fh.read()
except OSError:
    print("PATCH NOT APPLIED: cannot read runtime/src/kernel.cpp")
    raise SystemExit(1)
crlf = '\r\n' in text
t = text.replace('\r\n', '\n')
if 'PS2_WAKE_TRACE' in t:
    print("already patched")
    raise SystemExit
for old, new in EDITS:
    if t.count(old) != 1:
        print("PATCH NOT APPLIED: kernel.cpp does not look like the expected source (cannot find: %s)" % old.strip().splitlines()[0][:60])
        raise SystemExit(1)
for old, new in EDITS:
    t = t.replace(old, new)
with open(path, 'w', newline='') as fh:
    fh.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (4 edits)")
