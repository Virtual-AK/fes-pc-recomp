"""Script-command trace for the PS2 Web Recomp runtime (research tool, see docs/known-issues.md).

With PS2_COMM_TRACE=FROM,TO (frame numbers; a single number N means N to N+600) every call the game's script machine makes through its
function table (the 502 "COMM" functions, table at 0x7B92B0 of the boot executable, see docs/script-functions.md) is written to the
window log as one line:
  [comm] frame <F> n <COMM number> argc <values it takes> a0 <..> a1 <..> a2 <..> a3 <..> ra <..>
It prints numbers only. Nothing changes in the game and without the variable it costs one flag test per call.
Put the line in ~/.p3fes-window-env (like PS2_LOG_DISC=1) and play; the window log is ~/.p3fes-window.log.

Run in the ps2-web-recomp folder:  python3 ps2run_commtrace_patch.py [folder]
(patches runtime/src/dispatch.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
path = root + '/runtime/src/dispatch.cpp'

INC_OLD = '#include <cstdio>\n'
INC_NEW = '#include <cstdio>\n#include <cstdlib>\n#include <unordered_map>\n'

HELP_OLD = 'void record_miss(std::uint32_t pc) {\n'
HELP_NEW = r'''// ---- script command trace (ps2run_commtrace_patch.py)
struct CommTrace {
    int enabled = -1;
    std::uint64_t from = 0, to = 0;
    bool table_ready = false;
    std::unordered_map<std::uint32_t, std::pair<std::uint32_t, std::uint32_t>> fn;   // address -> (COMM number, value count)
};
CommTrace g_comm;

void comm_trace(Cpu &c, std::uint32_t pc) {
    CommTrace &t = g_comm;
    if (t.enabled < 0) {
        const char *e = std::getenv("PS2_COMM_TRACE");
        t.enabled = (e && *e) ? 1 : 0;
        if (t.enabled) {
            unsigned long long a = 0, b = 0;
            const int n = std::sscanf(e, "%llu,%llu", &a, &b);
            t.from = a;
            t.to = n >= 2 ? b : a + 600;
            std::fprintf(stderr, "[comm] tracing script calls from frame %llu to %llu\n", static_cast<unsigned long long>(t.from), static_cast<unsigned long long>(t.to));
        }
    }
    if (t.enabled <= 0) return;
    const std::uint64_t f = frame_count();
    if (f < t.from || f > t.to) return;
    if (!t.table_ready) {
        t.table_ready = true;
        for (std::uint32_t n = 0; n < 502; ++n) {
            const std::uint32_t at = 0x7B92B0u + n * 8u;
            const std::uint32_t fa = ld32(at), cnt = ld32(at + 4);
            if (fa >= 0x100000u && fa < 0x2000000u && (fa & 3u) == 0 && cnt < 16) t.fn[fa] = {n, cnt};
        }
        std::fprintf(stderr, "[comm] function table: %zu entries\n", t.fn.size());
    }
    const auto it = t.fn.find(pc);
    if (it == t.fn.end()) return;
    std::fprintf(stderr, "[comm] frame %llu n %u argc %u a0 %08X a1 %08X a2 %08X a3 %08X ra %08X\n", static_cast<unsigned long long>(f), it->second.first,
                 it->second.second, c.r[4].w[0], c.r[5].w[0], c.r[6].w[0], c.r[7].w[0], c.r[31].w[0]);
}

void record_miss(std::uint32_t pc) {
'''
DISP_OLD = '    const std::uint32_t pc = c.pc;\n    if (pc & kUnwind) return;\n'
DISP_NEW = DISP_OLD + '    if (g_comm.enabled != 0) comm_trace(c, pc);\n'
EDITS = [(INC_OLD, INC_NEW), (HELP_OLD, HELP_NEW), (DISP_OLD, DISP_NEW)]

try:
    with open(path, newline='') as fh:
        text = fh.read()
except OSError:
    print("PATCH NOT APPLIED: cannot read runtime/src/dispatch.cpp")
    raise SystemExit(1)
crlf = '\r\n' in text
t = text.replace('\r\n', '\n')
if 'PS2_COMM_TRACE' in t:
    print("already patched")
    raise SystemExit
for old, new in EDITS:
    if t.count(old) != 1:
        print("PATCH NOT APPLIED: dispatch.cpp does not look like the expected source (cannot find: %s)" % old.strip().splitlines()[0][:60])
        raise SystemExit(1)
    t = t.replace(old, new)
with open(path, 'w', newline='') as fh:
    fh.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (3 edits)")
