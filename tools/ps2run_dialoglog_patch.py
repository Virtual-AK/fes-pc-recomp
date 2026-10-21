"""Dialogue log for the PC window of PS2 Web Recomp (first step of the Log feature, see docs/log-plan.md).

With the environment variable PS2_DIALOG_LOG=1 (or a file name) the runner appends one line to dialog_log.tsv (in the folder it runs in)
every time the game shows a new page of dialogue:
  frame <TAB> speaker number <TAB> voice clip number (-1 = none) <TAB> script block <TAB> page number <TAB> text (\\n = line break) <TAB> recent disc reads
How it works: the game keeps a message-window record in memory (found by its fixed pattern) that holds a pointer to the script block
being read and the number of the page on screen; the page text and its codes are read from the script. A page with the code f2 48 NN has
a voice clip NN. The last column lists the sector:count of the most recent reads from DATA.CVM, so the launcher can tell which voice
archive (SOUND/V*.AFS) the clip comes from. Nothing changes in the game. The launcher passes variables listed in ~/.p3fes-window-env (lines like PS2_DIALOG_LOG=1).

Run in the ps2-web-recomp folder:  python3 ps2run_dialoglog_patch.py [folder]
(patches runtime/src/system.cpp, runtime/src/disc.cpp, runtime/include/ps2/disc.hpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'

FN_OLD = 'std::uint64_t g_iop_synced = 0;\n'
FN_NEW = FN_OLD + r'''// ---- dialogue log (ps2run_dialoglog_patch.py)
void dlog_tick() {
    static int enabled = -1;
    static std::FILE *out = nullptr;
    struct S { std::uint32_t addr, blk, idx; };
    static std::vector<S> seen;
    if (enabled < 0) {
        const char *e = std::getenv("PS2_DIALOG_LOG");
        enabled = (e && *e) ? 1 : 0;
        if (enabled) {
            const char *path = (e[0] == '1' && !e[1]) ? "dialog_log.tsv" : e;
            out = std::fopen(path, "ab");
            std::fprintf(stderr, "[dialog] %s %s\n", out ? "logging to" : "cannot open", path);
        }
    }
    if (!enabled || !out) return;
    auto rd = [](std::uint32_t a) -> std::uint32_t {
        std::uint32_t v = 0;
        if (a + 4 <= kRamSize) std::memcpy(&v, g_ram + a, 4);
        return v;
    };
    auto is_page = [&](std::uint32_t p) {
        return p >= 0x100000 && p + 8 < kRamSize && g_ram[p] == 0xf2 && g_ram[p + 1] == 0x08 && g_ram[p + 2] == 0xff && g_ram[p + 3] == 0xff;
    };
    for (std::uint32_t a = 0x1060000; a < 0x1070000; a += 4) {
        if (rd(a) != 0x290 || rd(a + 4) != 0xa48 || rd(a + 0x10) != 0x360 || rd(a + 0x14) != 0xb18) continue;
        const std::uint32_t blk = rd(a + 0x18);
        const std::uint32_t idx = rd(a + 0x28) & 0xffff;
        S *s = nullptr;
        for (S &x : seen) if (x.addr == a) s = &x;
        if (!s) { seen.push_back({a, 0, 0}); s = &seen.back(); }
        if (blk < 0x100000 || blk + 0x400 >= kRamSize) { s->blk = 0; continue; }
        if (s->blk == blk && s->idx == idx) continue;
        // the table of page pointers: the first run of pointers to pages after the block name
        std::vector<std::uint32_t> pages;
        for (std::uint32_t o = 0; o < 0x80 && pages.empty(); o += 4)
            if (is_page(rd(blk + o))) {
                for (std::uint32_t q = blk + o; is_page(rd(q)) && pages.size() < 256; q += 4) pages.push_back(rd(q));
            }
        if (idx >= pages.size()) continue;
        s->blk = blk;
        s->idx = idx;
        auto speaker_of = [&](std::uint32_t p) -> int {
            for (std::uint32_t i = p; i < p + 64 && g_ram[i] != 0x00; ++i) {
                if (g_ram[i] == 0xf1 && g_ram[i + 1] == 0x04) break;
                if (g_ram[i] == 0xf5 && g_ram[i + 1] == 0x1f) return g_ram[i + 2];
            }
            return -1;
        };
        int speaker = -1;
        for (int k = static_cast<int>(idx); k >= 0 && speaker < 0; --k) speaker = speaker_of(pages[k]);
        int clip = -1;
        std::string text;
        for (std::uint32_t i = pages[idx]; i < pages[idx] + 700 && i + 4 < kRamSize;) {
            const std::uint8_t b = g_ram[i];
            if (b == 0xf1) { if (g_ram[i + 1] == 0x04) break; i += 2; }
            else if (b == 0xf2) { if (g_ram[i + 1] == 0x48) clip = g_ram[i + 2]; i += 4; }
            else if (b == 0xf5) { i += (g_ram[i + 1] == 0x1f) ? 10 : 2; }
            else if (b == 0x0a) { text += "\\n"; ++i; }
            else if (b >= 0x20 && b < 0x7f) { text += static_cast<char>(b); ++i; }
            else if (b == 0x00) break;
            else { text += '?'; ++i; }
        }
        std::string name;
        for (std::uint32_t i = blk; i < blk + 16 && name.size() < 15; ++i)
            if (std::isalnum(g_ram[i]) || g_ram[i] == '_') name += static_cast<char>(g_ram[i]);
            else if (!name.empty()) break;
        std::fprintf(out, "%llu\t%d\t%d\t%s\t%u\t%s\t%s\n", static_cast<unsigned long long>(g_frames), speaker, clip, name.c_str(), idx, text.c_str(), disc::recent_data_reads().c_str());
        std::fflush(out);
    }
}

'''
CALL_OLD = '    iop::sio2::flush_cards();\n    if (g_options.trace_iop_modules && g_frames % 25 == 0)'
CALL_NEW = '    iop::sio2::flush_cards();\n#ifndef __EMSCRIPTEN__\n    dlog_tick();\n#endif\n    if (g_options.trace_iop_modules && g_frames % 25 == 0)'
HPP_OLD = 'std::uint64_t sector_count();\n'
HPP_NEW = HPP_OLD + 'std::string recent_data_reads();   // ps2run_dialoglog_patch.py\n'
RING_OLD = 'std::map<std::string, Entry> g_index;\n'
RING_NEW = RING_OLD + """// ---- recent DATA.CVM reads (ps2run_dialoglog_patch.py)
std::uint32_t g_recent[48][2];
std::uint32_t g_recent_n = 0;
"""
REC_OLD = """    const std::size_t want = static_cast<std::size_t>(count) * kSector;
    const std::size_t got = g_reader(static_cast<std::uint64_t>(sector) * kSector, out, want);
"""
REC_NEW = """    {   // ps2run_dialoglog_patch.py: remember the last DATA.CVM reads (the Log works out which voice clip from them)
        static std::uint32_t d0 = 0, d1 = 0;
        static bool have = false;
        if (!have) {
            auto it = g_index.find("DATA.CVM");
            if (it != g_index.end()) {
                d0 = it->second.sector;
                d1 = d0 + (it->second.size + kSector - 1) / kSector;
                have = true;
            }
        }
        if (have && sector >= d0 && sector < d1) {
            g_recent[g_recent_n % 48][0] = sector;
            g_recent[g_recent_n % 48][1] = count;
            ++g_recent_n;
        }
    }
""" + REC_OLD
FN_OLD2 = 'bool ready(std::uint32_t sector, std::uint32_t count) {\n'
FN_NEW2 = """std::string recent_data_reads() {   // ps2run_dialoglog_patch.py
    std::string s;
    const std::uint32_t n = g_recent_n < 48 ? g_recent_n : 48;
    for (std::uint32_t k = 0; k < n; ++k) {
        const std::uint32_t i = (g_recent_n - n + k) % 48;
        s += std::to_string(g_recent[i][0]) + ":" + std::to_string(g_recent[i][1]) + ",";
    }
    return s;
}

""" + FN_OLD2
EDITS = [('runtime/src/system.cpp', [(FN_OLD, FN_NEW), (CALL_OLD, CALL_NEW)]),
         ('runtime/include/ps2/disc.hpp', [(HPP_OLD, HPP_NEW)]),
         ('runtime/src/disc.cpp', [(RING_OLD, RING_NEW), (REC_OLD, REC_NEW), (FN_OLD2, FN_NEW2)])]


def fail(msg):
    print("PATCH NOT APPLIED:", msg)
    raise SystemExit(1)


texts = {}
for rel, _ in EDITS:
    try:
        with open(root + '/' + rel, newline='') as f:
            raw = f.read()
    except OSError:
        fail("cannot read " + rel)
    txt = raw.replace('\r\n', '\n')
    mark = '// ---- dialogue log (ps2run_dialoglog_patch.py)\n'
    if rel.endswith('system.cpp') and mark in txt and FN_NEW not in txt:   # an earlier version of this patch: replace its function
        a = txt.index(mark)
        b = txt.index('\n}\n\n', a) + 4
        txt = txt[:a] + txt[b:]
    texts[rel] = (txt, '\r\n' in raw)
if all(new in texts[rel][0] for rel, edits in EDITS for _, new in edits):
    print("already patched")
    raise SystemExit
done = 0
out = {}
for rel, edits in EDITS:
    t, crlf = texts[rel]
    for old, new in edits:
        if new in t:
            continue
        if t.count(old) != 1:
            fail(rel + " does not look like the expected source (cannot find: " + old.strip().splitlines()[0][:70] + ")")
        t = t.replace(old, new)
        done += 1
    out[rel] = (t, crlf)
for rel, (t, crlf) in out.items():
    with open(root + '/' + rel, 'w', newline='') as f:
        f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d edits)" % done)
