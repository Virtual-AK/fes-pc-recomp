"""Twelfth trace step: PS2_TRACE_VULQ=from,to,LO,HI,RRGGBBAA (use together with PS2_VU_INTERPRET=1) follows every VU1 load (LQ) and
store (SQ) that touches data-memory quadword LO..HI (decimal) during frames from..to, in order. When a VU1 -> GS packet is sent that
contains a colour quadword whose four low bytes are RR GG BB AA (for example D370D370), it prints the accesses recorded since the
previous packet: instruction address (pc), the integer register and its value, the offset, the quadword reached and the four words
that were loaded or stored. This shows which part of a VU1 program wrote or read the values behind a bad vertex. Numbers only.
Example: PS2_VU_INTERPRET=1 PS2_TRACE_VULQ=25077,25078,0,2,D370D370
Usage (in the ps2-web-recomp folder): python3 ps2run_trace_patch12.py [runtime/src/vu_micro.cpp]
Safe to run twice; the first version of this patch is replaced. Rebuild afterwards: ninja -C build/native-p3fes ps2run
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/vu_micro.cpp'
s = open(p).read()
LQ0 = '        trace_vulq(u, "LQ", pc, is, r.vi[is], imm11, w);\n'
SQ0 = '        trace_vulq(u, "SQ", pc, it, r.vi[it], imm11, w);\n'
UPG = False
if 'PS2_TRACE_VULQ' in s:
    if 'vulq_kick' in s:
        print("already patched"); raise SystemExit
    a = s.find('void trace_vulq(const Unit &u, const char *kind')
    b = s.find('void lower(Unit &u, std::uint32_t w, std::uint32_t pc, std::uint32_t &npc, bool &branch) {')
    if a < 0 or b < a or s.count(LQ0) != 1 or s.count(SQ0) != 1:
        print("PATCH NOT APPLIED: cannot upgrade"); raise SystemExit(1)
    s = s[:a] + s[b:]
    s = s.replace(LQ0, '', 1).replace(SQ0, '', 1)
    UPG = True
LQ = '    case 0x00: {\n        const std::uint8_t *q = qword(u, r.vi[is] + static_cast<std::uint32_t>(imm11));\n'
SQ = '    case 0x01: {\n        std::uint8_t *q = qword(u, r.vi[it] + static_cast<std::uint32_t>(imm11));\n'
OLD = 'void lower(Unit &u, std::uint32_t w, std::uint32_t pc, std::uint32_t &npc, bool &branch) {\n'
XG = '    gif::transfer(1, buffer, count);\n}\n'
if s.count(LQ) != 1 or s.count(SQ) != 1 or s.count(OLD) != 1 or s.count(XG) != 1:
    print("PATCH NOT APPLIED: lower() or xgkick()"); raise SystemExit(1)
# the log and the packet check must come before xgkick(); the recorder comes before lower() (which is after xgkick)
XOLD = 'void xgkick(Unit &u, std::uint32_t address) {\n'
if s.count(XOLD) != 1:
    print("PATCH NOT APPLIED: xgkick()"); raise SystemExit(1)
LOG = r'''struct VulqCfg {
    bool on = false;
    unsigned long long from = 0, to = 0;
    unsigned long lo = 0, hi = 0;
    std::uint32_t pat = 0;
};
const VulqCfg &vulq_cfg() {
    static const VulqCfg c = [] {
        VulqCfg v;
        const char *spec = std::getenv("PS2_TRACE_VULQ");
        if (!spec) return v;
        char *e = nullptr;
        v.from = std::strtoull(spec, &e, 10);
        if (!e || *e != ',') return v;
        v.to = std::strtoull(e + 1, &e, 10);
        if (!e || *e != ',') return v;
        v.lo = std::strtoul(e + 1, &e, 10);
        if (!e || *e != ',') return v;
        v.hi = std::strtoul(e + 1, &e, 10);
        if (!e || *e != ',') return v;
        v.pat = static_cast<std::uint32_t>(std::strtoul(e + 1, nullptr, 16));
        v.on = true;
        return v;
    }();
    return c;
}
std::vector<std::string> g_vulq_log;
int g_vulq_printed = 0;

void vulq_kick(const std::uint8_t *buffer, std::uint32_t count, std::uint32_t address) {
    const VulqCfg &c = vulq_cfg();
    if (!c.on) return;
    const unsigned long long f = static_cast<unsigned long long>(ps2::frame_count());
    if (f < c.from || f >= c.to) { g_vulq_log.clear(); return; }
    bool hit = false;
    for (std::uint32_t q = 0; q < count && !hit; ++q) {
        std::uint32_t w[4];
        std::memcpy(w, buffer + q * 16, 16);
        hit = (w[0] & 0xFFu) == ((c.pat >> 24) & 0xFFu) && (w[1] & 0xFFu) == ((c.pat >> 16) & 0xFFu) &&
              (w[2] & 0xFFu) == ((c.pat >> 8) & 0xFFu) && (w[3] & 0xFFu) == (c.pat & 0xFFu);
    }
    if (hit && g_vulq_printed < 1) {
        ++g_vulq_printed;
        std::fprintf(stderr, "[vulq] packet at %X (%u qwords) in frame %llu; accesses to quadwords %lu..%lu since the previous packet (%zu):\n",
                     address, count, f, c.lo, c.hi, g_vulq_log.size());
        for (const std::string &l : g_vulq_log) std::fputs(l.c_str(), stderr);
    }
    g_vulq_log.clear();
}

'''
s = s.replace(XOLD, LOG + XOLD, 1)
s = s.replace(XG, '    vulq_kick(buffer, count, address);\n' + XG, 1)
REC = r'''void trace_vulq(const Unit &u, const char *kind, std::uint32_t pc, unsigned reg, std::uint32_t regval, int imm, std::uint32_t w, const std::uint8_t *data) {
    const VulqCfg &c = vulq_cfg();
    if (!c.on) return;
    const unsigned long long f = static_cast<unsigned long long>(ps2::frame_count());
    if (f < c.from || f >= c.to) return;
    const std::uint32_t qi = (regval + static_cast<std::uint32_t>(imm)) & (u.data_qwords - 1);
    if (qi < c.lo || qi > c.hi || g_vulq_log.size() > 400) return;
    std::uint32_t v[4];
    std::memcpy(v, data, 16);
    char line[200];
    std::snprintf(line, sizeof line, "[vulq] %s pc=%04X vi%u=%u imm=%d -> qword %u  %08X %08X %08X %08X\n", kind, pc, reg, regval, imm, qi, v[0], v[1], v[2], v[3]);
    g_vulq_log.emplace_back(line);
}

'''
s = s.replace(OLD, REC + OLD, 1)
s = s.replace(LQ, LQ + '        trace_vulq(u, "LQ", pc, is, r.vi[is], imm11, w, q);\n', 1)
s = s.replace(SQ, SQ + '        trace_vulq(u, "SQ", pc, it, r.vi[it], imm11, w, reinterpret_cast<const std::uint8_t *>(&r.vf[fs].w[0]));\n', 1)
for inc in ('#include <vector>', '#include <string>'):
    if inc not in s:
        s = s.replace('#include <unordered_set>\n', '#include <unordered_set>\n' + inc + '\n', 1)
open(p, 'w').write(s)
print("patched (PS2_TRACE_VULQ, packet-linked version)" if UPG else "patched (PS2_TRACE_VULQ)")
