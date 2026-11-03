"""Draw log for the PC window of PS2 Web Recomp (a diagnostic; it changes nothing on screen).

With PS2_DRAWLOG=<file> set, the window looks every half second for that file. While it exists, the window counts every kind of draw the game sends
(shape, test/blend/texture settings, picture format) and, when the file is deleted again, writes a table of them to the log (stderr, "[drawlog]" lines).
Use it to see how something odd is being drawn:  create the file while the odd thing is on screen, wait two seconds, delete the file.

  PS2_DRAWLOG=C:\\p3fes\\drawlog.on      (in ~/.p3fes-window-env; create the file in WSL with: touch /mnt/c/p3fes/drawlog.on)

Run in the ps2-web-recomp folder:  python3 ps2run_drawlog_patch.py [folder]
(patches runtime/src/gs/gpu/gpu.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
TAG = 'ps2run_drawlog_patch.py'
GPU = 'runtime/src/gs/gpu/gpu.cpp'

CODE = r'''
// ---- draw log (%TAG%) ----
struct DrawLogRow {
    std::uint64_t attr, test, alpha, tex0, tex1, frame, zbuf, texa, clamp;
    std::uint32_t prim, pabe, hits, verts, amin, amax;
};
std::unordered_map<std::string, DrawLogRow> g_dl_rows;
bool g_dl_on = false;
std::uint32_t g_dl_tick = 0;
const char *g_dl_file = nullptr;
bool g_dl_checked = false;

void drawlog(const State &st, std::uint64_t attr, std::uint32_t prim, const Context &c, const Vertex *v, int count) {
    if (!g_dl_checked) {
        g_dl_checked = true;
        g_dl_file = std::getenv("PS2_DRAWLOG");
        if (g_dl_file) std::fprintf(stderr, "[drawlog] watching %s\n", g_dl_file);
    }
    if (!g_dl_file) return;
    if ((++g_dl_tick & 255u) == 0) {
        FILE *f = std::fopen(g_dl_file, "rb");
        const bool exists = f != nullptr;
        if (f) std::fclose(f);
        if (exists && !g_dl_on) {
            g_dl_on = true;
            g_dl_rows.clear();
            std::fprintf(stderr, "[drawlog] start\n");
        } else if (!exists && g_dl_on) {
            g_dl_on = false;
            std::fprintf(stderr, "[drawlog] %zu kinds of draw (prim attr test alpha tex0 tex1 frame zbuf texa clamp pabe | hits vertices alpha-min alpha-max)\n", g_dl_rows.size());
            for (const auto &kv : g_dl_rows) {
                const DrawLogRow &r = kv.second;
                std::fprintf(stderr, "[drawlog] p%u attr=%llx test=%llx alpha=%llx tex0=%llx tex1=%llx frame=%llx zbuf=%llx texa=%llx clamp=%llx pabe=%u | %u %u %u %u\n",
                             r.prim, static_cast<unsigned long long>(r.attr), static_cast<unsigned long long>(r.test), static_cast<unsigned long long>(r.alpha),
                             static_cast<unsigned long long>(r.tex0), static_cast<unsigned long long>(r.tex1), static_cast<unsigned long long>(r.frame),
                             static_cast<unsigned long long>(r.zbuf), static_cast<unsigned long long>(r.texa), static_cast<unsigned long long>(r.clamp), r.pabe,
                             r.hits, r.verts, r.amin, r.amax);
            }
            std::fprintf(stderr, "[drawlog] end\n");
        }
    }
    if (!g_dl_on) return;
    char key[300];
    std::snprintf(key, sizeof key, "%u/%llx/%llx/%llx/%llx/%llx/%llx/%llx/%llx/%llx/%u", prim, static_cast<unsigned long long>(attr),
                  static_cast<unsigned long long>(c.test), static_cast<unsigned long long>(c.alpha), static_cast<unsigned long long>(c.tex0),
                  static_cast<unsigned long long>(c.tex1), static_cast<unsigned long long>(c.frame), static_cast<unsigned long long>(c.zbuf),
                  static_cast<unsigned long long>(st.texa), static_cast<unsigned long long>(c.clamp), static_cast<unsigned>(st.pabe & 1u));
    DrawLogRow &r = g_dl_rows[key];
    if (r.hits == 0) {
        r.attr = attr; r.test = c.test; r.alpha = c.alpha; r.tex0 = c.tex0; r.tex1 = c.tex1; r.frame = c.frame; r.zbuf = c.zbuf;
        r.texa = st.texa; r.clamp = c.clamp; r.prim = prim; r.pabe = static_cast<std::uint32_t>(st.pabe & 1u); r.amin = 255; r.amax = 0;
    }
    ++r.hits;
    r.verts += static_cast<std::uint32_t>(count);
    for (int i = 0; i < count; ++i) {
        r.amin = std::min<std::uint32_t>(r.amin, v[i].a);
        r.amax = std::max<std::uint32_t>(r.amax, v[i].a);
    }
}
// ---- end draw log ----

'''.replace('%TAG%', TAG)

EDITS = [
    ('#include <deque>\n', '#include <deque>\n#include <string>  // ' + TAG + '\n'),
    ('void draw(const State &st, const Vertex *v, int count) {\n',
     CODE + 'void draw(const State &st, const Vertex *v, int count) {\n'),
    ('    const Context &c = st.ctx[(attr >> 9) & 1u];\n    SetupCache &cache = g_setup_cache;\n',
     '    const Context &c = st.ctx[(attr >> 9) & 1u];\n    drawlog(st, attr, prim, c, v, count);  // ' + TAG + '\n    SetupCache &cache = g_setup_cache;\n'),
]

try:
    with open(root + '/' + GPU, newline='') as f:
        raw = f.read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + GPU)
    raise SystemExit(1)
crlf = '\r\n' in raw
t = raw.replace('\r\n', '\n')
if TAG in t:
    print("already patched")
    raise SystemExit
for old, _ in EDITS:
    if t.count(old) != 1:
        print("PATCH NOT APPLIED: " + GPU + " does not look like the expected source")
        raise SystemExit(1)
for old, new in EDITS:
    t = t.replace(old, new)
with open(root + '/' + GPU, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d edits)" % len(EDITS))
