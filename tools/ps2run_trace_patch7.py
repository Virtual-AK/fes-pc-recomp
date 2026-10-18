"""Seventh trace step: PS2_TRACE_VIF=from,to prints, for frames from..to, one line per VIF UNPACK ("[vifu] f<frame> u<unit> unpack
vn vl usn masked flg addr num cl wl mode mask") and one per VU program start ("[vifu] f<frame> u<unit> run addr tops itops"). Numbers only,
no game content. Usage (in the ps2-web-recomp folder): python3 ps2run_trace_patch7.py [runtime/src/vif.cpp]
Safe to run twice. Rebuild afterwards: ninja -C build/native-p3fes ps2run
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/vif.cpp'
s = open(p).read()
if 'PS2_TRACE_VIF' in s:
    print("already patched"); raise SystemExit
A1 = '    const std::uint32_t components = vn + 1;\n    const std::uint32_t bits = element_bits(vl);\n    std::size_t bit_pos = 0;\n'
A2 = '    vu::run(unit, address);\n'
A3 = '#include "ps2/state.hpp"\n'
for what, old in (('unpack', A1), ('run_vu', A2), ('include', A3)):
    if s.count(old) != 1:
        print("PATCH NOT APPLIED:", what); raise SystemExit(1)
HELP = r'''bool trace_vif() {
    static const char *spec = std::getenv("PS2_TRACE_VIF");
    if (!spec) return false;
    static const unsigned long long from = std::strtoull(spec, nullptr, 10);
    static const unsigned long long to = std::strchr(spec, ',') ? std::strtoull(std::strchr(spec, ',') + 1, nullptr, 10) : from + 1;
    const unsigned long long f = static_cast<unsigned long long>(ps2::frame_count());
    return f >= from && f < to;
}

'''
T1 = '''    if (!dry && trace_vif())
        std::fprintf(stderr, "[vifu] f%llu u%d unpack vn=%u vl=%u usn=%u masked=%u flg=%u addr=%u num=%u cl=%u wl=%u mode=%u mask=%08X\\n",
                     static_cast<unsigned long long>(ps2::frame_count()), unit, vn, vl, usn ? 1u : 0u, masked ? 1u : 0u, static_cast<unsigned>((cmd >> 15) & 1u), addr, num, cl, wl, u.mode, u.mask);
'''
T2 = '''    if (!shadow(unit) && trace_vif())
        std::fprintf(stderr, "[vifu] f%llu u%d run addr=%04X tops=%u itops=%u\\n", static_cast<unsigned long long>(ps2::frame_count()), unit, address, u.tops, u.itops);
'''
s = s.replace(A3, A3 + '#include "ps2/system.hpp"\n', 1)
if '#include <cstdlib>' not in s:
    s = s.replace('#include <cstdio>\n', '#include <cstdio>\n#include <cstdlib>\n', 1)
# trace_vif does not need Unit; place it before unpack_words
B = 'std::uint32_t unpack_words('
if s.count(B) != 1:
    print("PATCH NOT APPLIED: unpack_words"); raise SystemExit(1)
s = s.replace(B, HELP + B, 1)
s = s.replace(A1, T1 + A1, 1)
s = s.replace(A2, T2 + A2, 1)
open(p, 'w').write(s)
print("patched (PS2_TRACE_VIF)")
