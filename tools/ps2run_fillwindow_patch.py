"""Widescreen fills the window: when the window is close to the picture's shape (a windowed 16:9 picture in a window that is a few percent wider or taller,
with the title bar and borders taken off), the picture is stretched to fill the whole client area instead of leaving thin black bars. A window that is
very different from the picture (a 21:9 monitor, a tall window) keeps the bars so the picture is not stretched far.

Run in the ps2-web-recomp folder:  python3 ps2run_fillwindow_patch.py [folder]
(patches runtime/src/gs/gpu/gpu.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
TAG = 'ps2run_fillwindow_patch.py'
GPU = 'runtime/src/gs/gpu/gpu.cpp'

HELP_OLD = 'float g_aspect = 4.0f / 3.0f;   // ps2run_widescreen_patch.py\n'
HELP_NEW = HELP_OLD + '''// ''' + TAG + ''': the shape of the picture on screen. A wide picture (16:9) is stretched to fill a window that is within 15% of its shape.
inline void present_size(float w, float h, float &vw, float &vh) {
    vw = std::min(w, h * g_aspect);
    vh = vw / g_aspect;
    if (g_aspect > 1.5f && w > 0.0f && h > 0.0f) {
        const float win = w / h;
        if (win > g_aspect * 0.85f && win < g_aspect * 1.15f) {
            vw = w;
            vh = h;
        }
    }
}
'''
V1_OLD = '        const float vw = std::min(w, h * g_aspect), vh = vw / g_aspect;\n'
V1_NEW = '        float vw, vh;\n        present_size(w, h, vw, vh);   // ' + TAG + '\n'
V2_OLD = '    const float vw = std::min(sw, sh * g_aspect), vh = vw / g_aspect;\n'
V2_NEW = '    float vw, vh;\n    present_size(sw, sh, vw, vh);   // ' + TAG + '\n'
EDITS = [(HELP_OLD, HELP_NEW), (V1_OLD, V1_NEW), (V2_OLD, V2_NEW)]

try:
    with open(root + '/' + GPU, newline='') as f:
        raw = f.read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + GPU)
    raise SystemExit(1)
crlf = '\r\n' in raw
t = raw.replace('\r\n', '\n')
todo = [(o, n) for o, n in EDITS if n not in t]
if not todo:
    print("already patched")
    raise SystemExit
for o, _ in todo:
    if t.count(o) != 1:
        print("PATCH NOT APPLIED: unknown source (expected text found %d times)" % t.count(o))
        raise SystemExit(1)
for o, n in todo:
    t = t.replace(o, n)
with open(root + '/' + GPU, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d edits)" % len(todo))
