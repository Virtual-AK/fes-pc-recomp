"""File mods for the PC window of PS2 Web Recomp: lay a mod overlay (.ovl from p3fes_modmap.py overlay) over the disc image
while the game reads it, the same idea as the browser server's --overlay (ps2web_serveovl_patch.py). The disc image is never
changed, and a mod needs no copy of the disc.

New switch for ps2run:  --overlay mods.ovl
Reads that touch a listed position get the mod's bytes, everything else comes from the untouched image. Mods that move a
bigger file to the end of the disc make the disc as seen by the game longer. Without the switch nothing changes.
The launcher passes --overlay when C:\\p3fes\\mods\\active.ovl exists.

Run in the ps2-web-recomp folder:  python3 ps2run_overlay_patch.py [folder]
(patches runtime/include/ps2/disc.hpp, runtime/src/disc.cpp, runtime/include/ps2/system.hpp, runtime/src/system.cpp,
host/main.cpp; idempotent; refuses unknown source). Rebuild afterwards.
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'

DISC_HPP_OLD = 'bool open(const std::string &path);\n'
DISC_HPP_NEW = '// Lay a mod overlay (P3OVL001 file) over the disc image; call before open(path).\nbool set_overlay(const std::string &path);\n' + DISC_HPP_OLD

DISC_VAR_OLD = 'std::map<std::string, Entry> g_index;\n'
DISC_VAR_NEW = DISC_VAR_OLD + r'''
// ---- mod overlay (ps2run_overlay_patch.py)
struct OvlEntry {
    std::uint64_t off;
    std::uint32_t len;
    std::uint64_t at;   // position of the bytes inside the .ovl file
};
std::vector<OvlEntry> g_ovl;
std::FILE *g_ovl_file = nullptr;
std::uint64_t g_ovl_end = 0;

void seek_to(std::FILE *f, std::uint64_t pos) {
#if defined(_WIN32)
    _fseeki64(f, static_cast<long long>(pos), SEEK_SET);
#else
    fseeko(f, static_cast<off_t>(pos), SEEK_SET);
#endif
}

std::uint64_t tell_pos(std::FILE *f) {
#if defined(_WIN32)
    return static_cast<std::uint64_t>(_ftelli64(f));
#else
    return static_cast<std::uint64_t>(ftello(f));
#endif
}
'''

DISC_OPEN_OLD = '''    std::FILE *file = g_file;
    return open(path, size, [file](std::uint64_t offset, void *out, std::size_t bytes) {
'''
DISC_OPEN_NEW = '''    std::FILE *file = g_file;
    if (!g_ovl.empty()) {
        const std::uint64_t real = size, total = std::max(size, g_ovl_end);
        return open(path, total, [file, real, total](std::uint64_t offset, void *out, std::size_t bytes) -> std::size_t {
            if (offset >= total) return 0;
            const std::size_t n = static_cast<std::size_t>(std::min<std::uint64_t>(bytes, total - offset));
            auto *dst = static_cast<std::uint8_t *>(out);
            std::memset(dst, 0, n);
            if (offset < real) {
                seek_to(file, offset);
                std::fread(dst, 1, static_cast<std::size_t>(std::min<std::uint64_t>(n, real - offset)), file);
            }
            for (const OvlEntry &e : g_ovl) {
                const std::uint64_t lo = std::max(e.off, offset), hi = std::min<std::uint64_t>(e.off + e.len, offset + n);
                if (lo < hi) {
                    seek_to(g_ovl_file, e.at + (lo - e.off));
                    std::fread(dst + (lo - offset), 1, static_cast<std::size_t>(hi - lo), g_ovl_file);
                }
            }
            return n;
        });
    }
    return open(path, size, [file](std::uint64_t offset, void *out, std::size_t bytes) {
'''

DISC_FN_OLD = 'bool open(const std::string &path) {\n'
DISC_FN_NEW = r'''bool set_overlay(const std::string &path) {
    std::FILE *f = std::fopen(path.c_str(), "rb");
    if (!f) return false;
    char magic[8];
    std::uint32_t n = 0;
    if (std::fread(magic, 1, 8, f) != 8 || std::memcmp(magic, "P3OVL001", 8) != 0 || std::fread(&n, 4, 1, f) != 1) {
        std::fclose(f);
        return false;
    }
    std::vector<OvlEntry> entries;
    std::uint64_t end = 0;
    for (std::uint32_t i = 0; i < n; ++i) {
        OvlEntry e{};
        if (std::fread(&e.off, 8, 1, f) != 1 || std::fread(&e.len, 4, 1, f) != 1) {
            std::fclose(f);
            return false;
        }
        e.at = tell_pos(f);
        seek_to(f, e.at + e.len);
        end = std::max(end, e.off + e.len);
        entries.push_back(e);
    }
    if (g_ovl_file) std::fclose(g_ovl_file);
    g_ovl_file = f;
    g_ovl = std::move(entries);
    g_ovl_end = end;
    std::fprintf(stderr, "[disc] mod overlay %s: %zu parts\n", path.c_str(), g_ovl.size());
    return true;
}

''' + DISC_FN_OLD

SYS_HPP_OLD = '    std::string save_state_path;\n'
SYS_HPP_NEW = '    std::string overlay_path;\n' + SYS_HPP_OLD

SYS_CPP_OLD = '    if (!g_options.disc_path.empty() && !disc::open(g_options.disc_path))\n'
SYS_CPP_NEW = ('    if (!g_options.overlay_path.empty() && !disc::set_overlay(g_options.overlay_path))\n'
               '        std::fprintf(stderr, "[ee] cannot use the mod overlay %s (the disc is used as it is)\\n", g_options.overlay_path.c_str());\n' + SYS_CPP_OLD)

MAIN_OLD = '        else if (a == "--memcard" && i + 1 < argc) ps2::g_options.memcard_path = argv[++i];\n'
MAIN_NEW = MAIN_OLD + '        else if (a == "--overlay" && i + 1 < argc) ps2::g_options.overlay_path = argv[++i];\n'

MAIN_USE_OLD = '[--disc image.iso] [--memcard card.ps2] [--pal | --ntsc]'
MAIN_USE_NEW = '[--disc image.iso] [--memcard card.ps2] [--overlay mods.ovl] [--pal | --ntsc]'

EDITS = [
    ('runtime/include/ps2/disc.hpp', [(DISC_HPP_OLD, DISC_HPP_NEW)]),
    ('runtime/src/disc.cpp', [(DISC_VAR_OLD, DISC_VAR_NEW), (DISC_OPEN_OLD, DISC_OPEN_NEW), (DISC_FN_OLD, DISC_FN_NEW)]),
    ('runtime/include/ps2/system.hpp', [(SYS_HPP_OLD, SYS_HPP_NEW)]),
    ('runtime/src/system.cpp', [(SYS_CPP_OLD, SYS_CPP_NEW)]),
    ('host/main.cpp', [(MAIN_OLD, MAIN_NEW), (MAIN_USE_OLD, MAIN_USE_NEW)]),
]


def fail(msg):
    print("PATCH NOT APPLIED:", msg)
    raise SystemExit(1)


texts = {}
for rel, _ in EDITS:
    try:
        with open(root + '/' + rel, newline='') as f:
            texts[rel] = f.read()
    except OSError:
        fail("cannot read " + rel)

if all(new in texts[rel] for rel, edits in EDITS for _, new in edits):
    print("already patched")
    raise SystemExit

done = 0
out = {}
for rel, edits in EDITS:
    t = texts[rel]
    crlf = '\r\n' in t
    if crlf:
        t = t.replace('\r\n', '\n')
    for old, new in edits:
        if new in t:
            continue
        if t.count(old) != 1:
            fail(rel + " does not look like the expected source")
        t = t.replace(old, new)
        done += 1
    out[rel] = t.replace('\n', '\r\n') if crlf else t
for rel, t in out.items():
    with open(root + '/' + rel, 'w', newline='') as f:
        f.write(t)
print("patched (%d edits)" % done)
