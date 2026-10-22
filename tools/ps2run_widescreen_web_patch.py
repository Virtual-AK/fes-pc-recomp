"""Widescreen field-of-view data patch for the BROWSER build (runtime/src/system.cpp).
ps2run_widescreen_patch.py compiled the data patch (the 3D view's field of view) only for the PC window. The picture aspect (PS2_ASPECT)
already works in the browser because it is in the shared graphics code; this patch lets the data patch (PS2_PATCH) run there too.
The launcher passes both as page parameters when Settings > Widescreen is on.
Run in the ps2-web-recomp folder (after ps2run_widescreen_patch.py):  python3 ps2run_widescreen_web_patch.py [folder]
(idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
REL = 'runtime/src/system.cpp'
OLD = '#ifndef __EMSCRIPTEN__\n    ws_apply();\n#endif\n'
NEW = '    ws_apply();   // ps2run_widescreen_web_patch.py: also in the browser build\n'

try:
    with open(root + '/' + REL, newline='') as f:
        t = f.read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + REL)
    raise SystemExit(1)
crlf = '\r\n' in t
t = t.replace('\r\n', '\n')
if NEW in t:
    print("already patched")
    raise SystemExit
if t.count(OLD) != 1:
    print("PATCH NOT APPLIED: " + REL + " does not look like the expected source (apply ps2run_widescreen_patch.py first)")
    raise SystemExit(1)
t = t.replace(OLD, NEW)
with open(root + '/' + REL, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (1 edit)")
