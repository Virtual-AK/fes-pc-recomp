"""Store watch for the PS2 Web Recomp runtime (research tool, see docs/known-issues.md).

With PS2_STORE_WATCH=0xADDR,0xADDR,... every time the game WRITES a different value into one of those 32-bit words, the window log gets
  [store] frame F 0xADDR: OLD -> NEW  size S  ra RA  sp SP  a0 .. a1 ..  stack: R1 R2 R3 ...
where ra is the game's last call return address and "stack" lists return addresses found on the game's stack (the call chain, innermost
first), so the function that moves a value can be named. At most 4000 lines. Nothing changes in the game; without the variable each
store costs one range test. Wide stores (64/128 bit) covering a watched word are reported too (size 8/16).
Put the variable in ~/.p3fes-window-env (like PS2_WATCH) and play; log: ~/.p3fes-window.log.

Run in the ps2-web-recomp folder:  python3 ps2run_storewatch_patch.py [folder]
(patches runtime/include/ps2/memory.hpp and runtime/src/system.cpp; idempotent; refuses unknown source; a full rebuild follows because memory.hpp is included everywhere)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'

HPP_OLD = 'extern std::uint8_t g_ram[];\n'
HPP_NEW = HPP_OLD + ('extern std::uint32_t g_swlo, g_swlen;   // store watch range (ps2run_storewatch_patch.py); length 0 = off\n'
                     'void store_watch_hit(std::uint32_t a, std::uint32_t size, const void *value);\n')
ST_EDITS = [
    ('inline void st32(std::uint32_t a, std::uint32_t v) {\n', 'inline void st32(std::uint32_t a, std::uint32_t v) {\n    if (a - g_swlo < g_swlen) [[unlikely]] store_watch_hit(a, 4, &v);\n'),
    ('inline void st64(std::uint32_t a, std::uint64_t v) {\n', 'inline void st64(std::uint32_t a, std::uint64_t v) {\n    if (a + 4u - g_swlo < g_swlen + 4u) [[unlikely]] store_watch_hit(a, 8, &v);\n'),
    ('inline void st128(std::uint32_t a, const Reg128 &v) {\n', 'inline void st128(std::uint32_t a, const Reg128 &v) {\n    if (a + 12u - g_swlo < g_swlen + 12u) [[unlikely]] store_watch_hit(a, 16, &v);\n'),
]

CPP_OLD = 'Cpu g_cpu;\nOptions g_options;\n'
CPP_NEW = CPP_OLD + r'''
// ---- store watch (ps2run_storewatch_patch.py)
std::uint32_t g_swlo = 0, g_swlen = 0;
static std::uint32_t g_swaddr[16];
static int g_swn = 0;
static int g_swlines = 0;
static const bool g_sw_init = [] {
    if (const char *e = std::getenv("PS2_STORE_WATCH")) {
        const std::string s = e;
        std::size_t pos = 0;
        std::uint32_t lo = 0xFFFFFFFFu, hi = 0;
        while (pos < s.size() && g_swn < 16) {
            std::size_t end = s.find(',', pos);
            if (end == std::string::npos) end = s.size();
            const std::uint32_t a = static_cast<std::uint32_t>(std::strtoul(s.substr(pos, end - pos).c_str(), nullptr, 16)) & ~3u;
            pos = end + 1;
            if (a < kRamSize) {
                g_swaddr[g_swn++] = a;
                if (a < lo) lo = a;
                if (a > hi) hi = a;
            }
        }
        if (g_swn) {
            g_swlo = lo;
            g_swlen = hi - lo + 4u;
            std::fprintf(stderr, "[store] watching %d words between %08x and %08x\n", g_swn, lo, hi);
        }
    }
    return true;
}();

void store_watch_hit(std::uint32_t a, std::uint32_t size, const void *value) {
    if (g_swlines >= 4000) return;
    for (int i = 0; i < g_swn; ++i) {
        const std::uint32_t w = g_swaddr[i];
        if (w < a || w + 4 > a + size) continue;
        std::uint32_t nv, old;
        std::memcpy(&nv, static_cast<const std::uint8_t *>(value) + (w - a), 4);
        std::memcpy(&old, g_ram + w, 4);
        if (nv == old) continue;
        ++g_swlines;
        const std::uint32_t sp = g_cpu.r[29].w[0];
        std::fprintf(stderr, "[store] frame %llu %08x: %08x -> %08x  size %u  ra %08x  sp %08x  a0 %08x a1 %08x  stack:",
                     static_cast<unsigned long long>(frame_count()), w, old, nv, size, g_cpu.r[31].w[0], sp, g_cpu.r[4].w[0], g_cpu.r[5].w[0]);
        int shown = 0;
        for (std::uint32_t k = 0; k < 256 && shown < 10; ++k) {
            const std::uint32_t at = sp + k * 4u;
            if (at + 4 > kRamSize) break;
            std::uint32_t v;
            std::memcpy(&v, g_ram + at, 4);
            if (v < 0x100000u || v >= 0x1F00000u || (v & 3u)) continue;
            std::uint32_t prev;
            std::memcpy(&prev, g_ram + v - 8, 4);
            if ((prev >> 26) == 3u || (prev & 0xFC00003Fu) == 9u) {   // preceded by JAL / JALR: a real return address
                std::fprintf(stderr, " %08x", v);
                ++shown;
            }
        }
        std::fprintf(stderr, "\n");
    }
}
'''
EDITS = [('runtime/include/ps2/memory.hpp', [(HPP_OLD, HPP_NEW)] + ST_EDITS), ('runtime/src/system.cpp', [(CPP_OLD, CPP_NEW)])]

texts = {}
for rel, edits in EDITS:
    try:
        with open(root + '/' + rel, newline='') as fh:
            raw = fh.read()
    except OSError:
        print("PATCH NOT APPLIED: cannot read " + rel)
        raise SystemExit(1)
    texts[rel] = (raw.replace('\r\n', '\n'), '\r\n' in raw)
if all('store_watch_hit' in t for t, _ in texts.values()):
    print("already patched")
    raise SystemExit
n = 0
for rel, edits in EDITS:
    t, crlf = texts[rel]
    for old, new in edits:
        if t.count(old) != 1:
            print("PATCH NOT APPLIED: %s does not look like the expected source (cannot find: %s)" % (rel, old.strip().splitlines()[0][:60]))
            raise SystemExit(1)
    for old, new in edits:
        t = t.replace(old, new)
        n += 1
    texts[rel] = (t, crlf)
for rel, (t, crlf) in texts.items():
    with open(root + '/' + rel, 'w', newline='') as fh:
        fh.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d edits)" % n)
