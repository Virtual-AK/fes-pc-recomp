"""Fix for the thin line of coloured specks along the bottom (and right) edge of the anime movies: the game draws the movie
picture one texel larger than it uploads it (640x368 uploaded, 641x369 sampled), so the last row and column showed
leftover video memory. The patch remembers how much of each texture buffer the game really uploaded and, when a texture is
set to CLAMP, keeps sampling inside that uploaded area. Patches runtime/src/gs/gs.cpp (both drawing routes use it).
Switch for comparing: PS2_NO_UPLOADCLAMP=1 turns the fix off.
Usage (in the ps2-web-recomp folder): python3 ps2gs_uploadclamp_patch.py [runtime/src/gs/gs.cpp]
Safe to run twice. Rebuild both builds afterwards.
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gs.cpp'
s = open(p).read()
if 'upload_clamp_on' in s:
    print("already patched"); raise SystemExit
HELPERS = r'''// upload_clamp: remember how much of each texture buffer was really uploaded
struct UploadExt {
    std::uint32_t w = 0, h = 0, dbw = 0, dpsm = 0;
};
std::unordered_map<std::uint32_t, UploadExt> g_upload_ext;

bool upload_clamp_on() {
    static const bool off = std::getenv("PS2_NO_UPLOADCLAMP") != nullptr;
    return !off;
}

void note_upload(const State &s, std::uint64_t dir) {
    if ((dir & 3u) != 0) return;
    const std::uint32_t dbp = static_cast<std::uint32_t>(s.bitbltbuf >> 32) & 0x3FFFu, dbw = static_cast<std::uint32_t>(s.bitbltbuf >> 48) & 0x3Fu,
                        dpsm = static_cast<std::uint32_t>(s.bitbltbuf >> 56) & 0x3Fu;
    const std::uint32_t x = static_cast<std::uint32_t>(s.trxpos >> 32) & 0x7FFu, y = static_cast<std::uint32_t>(s.trxpos >> 48) & 0x7FFu,
                        w = static_cast<std::uint32_t>(s.trxreg) & 0xFFFu, h = static_cast<std::uint32_t>(s.trxreg >> 32) & 0xFFFu;
    UploadExt &e = g_upload_ext[dbp];
    if (e.w == 0 || e.dbw != dbw || e.dpsm != dpsm || (x == 0 && y == 0 && h >= e.h)) {
        e.w = x + w;
        e.h = y + h;
        e.dbw = dbw;
        e.dpsm = dpsm;
    } else {
        e.w = std::max(e.w, x + w);
        e.h = std::max(e.h, y + h);
    }
}

// the clamp register to draw with: CLAMP becomes a region clamp that stops at the uploaded area
std::uint64_t upload_clamped(const State &s, const Context &c) {
    std::uint64_t cl = c.clamp;
    if (!upload_clamp_on() || !(s.prim & 0x10u)) return cl;
    const auto it = g_upload_ext.find(static_cast<std::uint32_t>(c.tex0) & 0x3FFFu);
    if (it == g_upload_ext.end()) return cl;
    const UploadExt &e = it->second;
    if (e.w == 0 || e.dpsm != (static_cast<std::uint32_t>(c.tex0 >> 20) & 0x3Fu) || e.dbw != (static_cast<std::uint32_t>(c.tex0 >> 14) & 0x3Fu)) return cl;
    const std::uint32_t tw = static_cast<std::uint32_t>(c.tex0 >> 26) & 15u, th = static_cast<std::uint32_t>(c.tex0 >> 30) & 15u;
    if ((cl & 3u) == 1 && e.w < (1u << tw))
        cl = (cl & ~(3ull | (0x3FFull << 4) | (0x3FFull << 14))) | 2ull | (static_cast<std::uint64_t>(e.w - 1) << 14);
    if (((cl >> 2) & 3u) == 1 && e.h < (1u << th))
        cl = (cl & ~((3ull << 2) | (0x3FFull << 24) | (0x3FFull << 34))) | (2ull << 2) | (static_cast<std::uint64_t>(e.h - 1) << 34);
    return cl;
}

'''
A_OLD = "bool trace_tex() {\n"
B_OLD = "        s.trxdir = value;\n        g_transfer = Transfer{};\n        g_carried = 0;\n"
B_NEW = "        note_upload(s, value);\n" + B_OLD
C_OLD = """        trace_prim(s, needed);
        dump_tex_draw(s);
        if (cpu_raster()) raster::draw(s, s.queue, needed);
#ifdef PS2_GPU
        if (gpu_on()) gpu::draw(s, s.queue, needed);
#endif
"""
C_NEW = """        trace_prim(s, needed);
        dump_tex_draw(s);
        Context &uc = s.ctx[static_cast<unsigned>(s.prim >> 9) & 1u];
        g_upload_ext.erase((static_cast<std::uint32_t>(uc.frame) & 0x1FFu) * 32u);
        const std::uint64_t saved_clamp = uc.clamp;
        uc.clamp = upload_clamped(s, uc);
        if (cpu_raster()) raster::draw(s, s.queue, needed);
#ifdef PS2_GPU
        if (gpu_on()) gpu::draw(s, s.queue, needed);
#endif
        uc.clamp = saved_clamp;
"""
I_OLD = "#include <stdexcept>\n"
I_NEW = "#include <stdexcept>\n#include <unordered_map>\n"
for o in [A_OLD, B_OLD, C_OLD, I_OLD]:
    if s.count(o) != 1:
        print("PATCH NOT APPLIED: gs.cpp does not look like the expected source"); raise SystemExit(1)
s = s.replace(I_OLD, I_NEW, 1).replace(A_OLD, HELPERS + A_OLD, 1).replace(B_OLD, B_NEW, 1).replace(C_OLD, C_NEW, 1)
open(p, 'w').write(s)
print("patched (texture clamp now stops at the area the game uploaded; PS2_NO_UPLOADCLAMP=1 turns it off)")
