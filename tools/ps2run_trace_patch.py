"""Adds an opt-in trace (environment variable PS2_TRACE_TEX=from,to) to the PS2 Web Recomp GS source.

Usage (in the ps2-web-recomp folder): python3 ps2run_trace_patch.py [runtime/src/gs/gs.cpp]
Prints one line per texture setting (TEX0/TEX2) and per GS transfer for frames from..to,
tagged with the frame number. Prints numbers only, no game content. Safe to run twice.
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gs.cpp'
s = open(p).read()
if 'PS2_TRACE_TEX' in s:
    print("already patched"); raise SystemExit

def sub(old, new):
    global s
    if s.count(old) != 1:
        print("PATCH NOT APPLIED: text not found:", old.strip()[:60]); raise SystemExit(1)
    s = s.replace(old, new)

# 1. include
if '"ps2/system.hpp"' not in s:
    sub('#include "ps2/state.hpp"', '#include "ps2/state.hpp"\n#include "ps2/system.hpp"')

# 2. helper, placed before load_clut
sub('void load_clut(std::uint64_t tex0) {\n    const std::uint32_t cld',
'''bool trace_tex() {
    static const char *spec = std::getenv("PS2_TRACE_TEX");
    if (!spec) return false;
    static const unsigned long long from = std::strtoull(spec, nullptr, 10);
    static const unsigned long long to = std::strchr(spec, ',') ? std::strtoull(std::strchr(spec, ',') + 1, nullptr, 10) : from + 30;
    const unsigned long long f = static_cast<unsigned long long>(ps2::frame_count());
    return f >= from && f < to;
}

void print_tex0(const char *tag, unsigned ctx, std::uint64_t t) {
    std::fprintf(stderr, "[tex] f%llu %s ctx%u TBP0=%llX TBW=%llu PSM=%llX TW=%llu TH=%llu TCC=%llu TFX=%llu CBP=%llX CPSM=%llX CSM=%llu CSA=%llu CLD=%llu\\n",
                 static_cast<unsigned long long>(ps2::frame_count()), tag, ctx,
                 static_cast<unsigned long long>(t & 0x3FFF), static_cast<unsigned long long>((t >> 14) & 0x3F), static_cast<unsigned long long>((t >> 20) & 0x3F),
                 static_cast<unsigned long long>((t >> 26) & 15), static_cast<unsigned long long>((t >> 30) & 15), static_cast<unsigned long long>((t >> 34) & 1),
                 static_cast<unsigned long long>((t >> 35) & 3), static_cast<unsigned long long>((t >> 37) & 0x3FFF), static_cast<unsigned long long>((t >> 51) & 15),
                 static_cast<unsigned long long>((t >> 55) & 1), static_cast<unsigned long long>((t >> 56) & 31), static_cast<unsigned long long>((t >> 61) & 7));
}

void load_clut(std::uint64_t tex0) {
    const std::uint32_t cld''')

# 3. TEX0 writes
sub('        s.ctx[reg - 6].tex0 = value;\n        load_clut(value);',
    '        if (trace_tex()) print_tex0("TEX0", static_cast<unsigned>(reg - 6), value);\n        s.ctx[reg - 6].tex0 = value;\n        load_clut(value);')
sub('        c.tex0 = (c.tex0 & ~mask) | (value & mask);\n        load_clut(c.tex0);',
    '        c.tex0 = (c.tex0 & ~mask) | (value & mask);\n        if (trace_tex()) print_tex0("TEX2", static_cast<unsigned>(reg - 0x16), c.tex0);\n        load_clut(c.tex0);')

# 4. transfers
sub('        s.trxdir = value;\n        g_transfer = Transfer{};',
'''        if (trace_tex())
            std::fprintf(stderr, "[trx] f%llu dir %llu DBP=%llX DBW=%llu DPSM=%llX x=%llu y=%llu w=%llu h=%llu\\n",
                         static_cast<unsigned long long>(ps2::frame_count()), static_cast<unsigned long long>(value & 3u),
                         static_cast<unsigned long long>((s.bitbltbuf >> 32) & 0x3FFF), static_cast<unsigned long long>((s.bitbltbuf >> 48) & 0x3F),
                         static_cast<unsigned long long>((s.bitbltbuf >> 56) & 0x3F), static_cast<unsigned long long>((s.trxpos >> 32) & 0x7FF),
                         static_cast<unsigned long long>((s.trxpos >> 48) & 0x7FF), static_cast<unsigned long long>(s.trxreg & 0xFFF),
                         static_cast<unsigned long long>((s.trxreg >> 32) & 0xFFF));
        s.trxdir = value;
        g_transfer = Transfer{};''')
open(p, 'w').write(s)
print("patched")
