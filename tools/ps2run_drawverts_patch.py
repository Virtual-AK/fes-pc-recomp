"""Draw vertex log for the PC window of PS2 Web Recomp (a diagnostic; it changes nothing on screen). Needs ps2run_drawlog_patch.py applied first.

With PS2_DRAWLOG_VERTS=1 set (in ~/.p3fes-window-env) and the PS2_DRAWLOG flag file in place, every flat 2D piece (a sprite drawn as one or two right-angled
triangles, 8 to 300 px wide and 8 to 150 px high, so 3D models and full-screen fades are skipped) is also written to the log as one "[dv]" line while the flag file exists: shape, tex0, then each vertex as
(screen x, screen y, u, v, s, t) in the game's 640-wide screen pixels. At most 60000 are written per run.
Use it to see exactly where the game puts things, e.g. the moons and the dates on the calendar screen:  touch the flag file while that screen is
up, wait two seconds, delete it, then copy ~/.p3fes-window.log somewhere.

Run in the ps2-web-recomp folder:  python3 ps2run_drawverts_patch.py [folder]
(patches runtime/src/gs/gpu/gpu.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
TAG = 'ps2run_drawverts_patch.py'
GPU = 'runtime/src/gs/gpu/gpu.cpp'

OLD = '    if (!g_dl_on) return;\n    char key[300];\n'
OLD2 = '    if (!g_dl_on) return;\n    char key[300];\n'
NEW = r'''    if (!g_dl_on) return;
    {  // %TAG%
        static int dv_n = 0;
        static const bool dv = std::getenv("PS2_DRAWLOG_VERTS") != nullptr;
        if (dv && dv_n < 60000 && count >= 3 && count <= 6) {
            float mnx = 1e9f, mxx = -1e9f, mny = 1e9f, mxy = -1e9f;
            for (int i = 0; i < count; ++i) {
                const float px = static_cast<float>(v[i].x) / 16.0f, py = static_cast<float>(v[i].y) / 16.0f;
                mnx = std::min(mnx, px); mxx = std::max(mxx, px); mny = std::min(mny, py); mxy = std::max(mxy, py);
            }
            bool flat = true;  // every vertex sits on a corner of the bounding box: a right-angled piece of a sprite
            for (int i = 0; i < count; ++i) {
                const float px = static_cast<float>(v[i].x) / 16.0f, py = static_cast<float>(v[i].y) / 16.0f;
                if (!((std::fabs(px - mnx) < 0.1f || std::fabs(px - mxx) < 0.1f) && (std::fabs(py - mny) < 0.1f || std::fabs(py - mxy) < 0.1f))) flat = false;
            }
            if (!flat || mxx - mnx < 8.0f || mxx - mnx > 300.0f || mxy - mny < 8.0f || mxy - mny > 150.0f) goto dv_skip;
            ++dv_n;
            const int ofx = static_cast<int>(c.xyoffset & 0xFFFFu), ofy = static_cast<int>((c.xyoffset >> 32) & 0xFFFFu);
            std::fprintf(stderr, "[dv] p%u tex0=%llx n=%d", prim, static_cast<unsigned long long>(c.tex0), count);
            for (int i = 0; i < count; ++i)
                std::fprintf(stderr, " (%.2f,%.2f u%.1f v%.1f s%.4f t%.4f)", (static_cast<float>(v[i].x) - static_cast<float>(ofx)) / 16.0f,
                             (static_cast<float>(v[i].y) - static_cast<float>(ofy)) / 16.0f, static_cast<float>(v[i].u) / 16.0f,
                             static_cast<float>(v[i].v) / 16.0f, static_cast<double>(v[i].s), static_cast<double>(v[i].t));
            std::fprintf(stderr, "\n");
        }
        dv_skip:;
    }
    char key[300];
'''.replace('%TAG%', TAG)

try:
    with open(root + '/' + GPU, newline='') as f:
        raw = f.read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + GPU)
    raise SystemExit(1)
crlf = '\r\n' in raw
t = raw.replace('\r\n', '\n')
if TAG in t:   # an older version of this patch is in: take its block out and put this one in
    i = t.index('    {  // ' + TAG)
    j = t.index('    char key[300];\n', i)
    t = t[:i] + t[j:]
    t = t.replace('    char key[300];\n', '    if (!g_dl_on) return;\n    char key[300];\n', 1) if False else t
    t = t.replace(OLD2, OLD, 1)
if 'ps2run_drawlog_patch.py' not in t or t.count(OLD) != 1:
    print("PATCH NOT APPLIED: apply ps2run_drawlog_patch.py first (or " + GPU + " does not look like the expected source)")
    raise SystemExit(1)
t = t.replace(OLD, NEW)
with open(root + '/' + GPU, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched")
