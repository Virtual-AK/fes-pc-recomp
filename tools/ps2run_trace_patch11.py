"""Eleventh trace step: PS2_TRACE_XGK=from,to,RRGGBBAA prints (to the screen, numbers only) the first three VU1 -> GS packets in frames
from..to that contain a colour quadword whose four low bytes are RR GG BB AA (for example 680E680E). For each packet it prints the
address and size, then every quadword as four hex words, and marks the matching one. This shows what the VU1 program really handed to
the GS around a vertex with a suspicious colour. Optional fourth field PS2_TRACE_XGK=from,to,RRGGBBAA,WORDHEX also lists (up to 8) quadwords of the VU1 data memory that contain a
32-bit word equal to WORDHEX (with the two quadwords before and after the first hit), to find where a value came from.
Needs nothing else.
Usage (in the ps2-web-recomp folder): python3 ps2run_trace_patch11.py [runtime/src/vu_micro.cpp]
Safe to run twice. Rebuild afterwards: ninja -C build/native-p3fes ps2run
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/vu_micro.cpp'
s = open(p).read()
if 'PS2_TRACE_XGK' in s:
    if 'have_find' in s:
        print("already patched"); raise SystemExit
    a = s.find('void trace_xgk(const std::uint8_t *buffer')
    b = s.find('void xgkick(Unit &u, std::uint32_t address) {')
    if a < 0 or b < a or s.count('    trace_xgk(buffer, count, address);\n') != 1:
        print("PATCH NOT APPLIED: cannot upgrade"); raise SystemExit(1)
    UPGRADE = True
    s = s[:a] + s[b:]
    s = s.replace('    trace_xgk(buffer, count, address);\n', '', 1)
else:
    UPGRADE = False
OLD = 'void xgkick(Unit &u, std::uint32_t address) {\n'
CALL = '    gif::transfer(1, buffer, count);\n}\n'
if s.count(OLD) != 1 or s.count(CALL) != 1:
    print("PATCH NOT APPLIED: xgkick()"); raise SystemExit(1)
HELP = r'''void trace_xgk(Unit &u, const std::uint8_t *buffer, std::uint32_t count, std::uint32_t address) {
    static const char *spec = std::getenv("PS2_TRACE_XGK");
    if (!spec) return;
    static const unsigned long long from = std::strtoull(spec, nullptr, 10);
    static const char *c1 = std::strchr(spec, ',');
    static const unsigned long long to = c1 ? std::strtoull(c1 + 1, nullptr, 10) : from + 1;
    static const char *c2 = c1 ? std::strchr(c1 + 1, ',') : nullptr;
    static const std::uint32_t pat = c2 ? static_cast<std::uint32_t>(std::strtoul(c2 + 1, nullptr, 16)) : 0u;
    static const char *c3 = c2 ? std::strchr(c2 + 1, ',') : nullptr;
    static const bool have_find = c3 != nullptr;
    static const std::uint32_t find = c3 ? static_cast<std::uint32_t>(std::strtoul(c3 + 1, nullptr, 16)) : 0u;
    static int printed = 0;
    const unsigned long long f = static_cast<unsigned long long>(ps2::frame_count());
    if (!c2 || f < from || f >= to || printed >= 3) return;
    const auto word = [&](std::uint32_t q, int i) { std::uint32_t w; std::memcpy(&w, buffer + q * 16 + i * 4, 4); return w; };
    const auto hit = [&](std::uint32_t q) {
        return (word(q, 0) & 0xFFu) == ((pat >> 24) & 0xFFu) && (word(q, 1) & 0xFFu) == ((pat >> 16) & 0xFFu) &&
               (word(q, 2) & 0xFFu) == ((pat >> 8) & 0xFFu) && (word(q, 3) & 0xFFu) == (pat & 0xFFu);
    };
    bool any = false;
    for (std::uint32_t q = 0; q < count; ++q) if (hit(q)) any = true;
    if (!any) return;
    ++printed;
    std::fprintf(stderr, "[xgk] f%llu addr=%X qwords=%u\n", f, address, count);
    for (std::uint32_t q = 0; q < count && q < 600; ++q)
        std::fprintf(stderr, "[xgk]   q%u %08X %08X %08X %08X%s\n", q, word(q, 0), word(q, 1), word(q, 2), word(q, 3), hit(q) ? "  <== match" : "");
    if (have_find && printed == 1) {
        int hits = 0;
        for (std::uint32_t q = 0; q < u.data_qwords && hits < 8; ++q) {
            std::uint32_t w[4];
            std::memcpy(w, qword(u, q), 16);
            if (w[0] != find && w[1] != find && w[2] != find && w[3] != find) continue;
            ++hits;
            std::fprintf(stderr, "[xgk] vu-mem hit at qword %X\n", q);
            if (hits <= 1) {
                for (std::uint32_t k = q >= 2 ? q - 2 : 0; k <= q + 2 && k < u.data_qwords; ++k) {
                    std::memcpy(w, qword(u, k), 16);
                    std::fprintf(stderr, "[xgk]   m%X %08X %08X %08X %08X\n", k, w[0], w[1], w[2], w[3]);
                }
            }
        }
        std::fprintf(stderr, "[xgk] vu-mem hits: %d\n", hits);
    }
}

'''
s = s.replace(OLD, HELP + OLD, 1)
s = s.replace(CALL, '    trace_xgk(u, buffer, count, address);\n' + CALL, 1)
open(p, 'w').write(s)
print("patched (PS2_TRACE_XGK, find option added)" if UPGRADE else "patched (PS2_TRACE_XGK)")
