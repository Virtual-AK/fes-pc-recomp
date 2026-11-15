"""HD textures: stop an old HD portrait from being drawn onto a different picture (the one-frame pink wash over floors/backgrounds).

What went wrong: a remembered HD picture is kept alive while "the game is re-sending a picture over this one's memory" (hd_refreshing). That test only asked
whether ANY upload in progress overlapped the remembered picture's memory. When the game uploaded some other portrait overlapping part of an old portrait's
rotating slot, a different texture that really sat at the old portrait's base block (a 512x512 scene overlay) was drawn with the old HD portrait for that
frame, so the floor flashed pink-brown every few seconds.

Fix: the exemption only applies when the upload in progress starts at the same base block as the remembered picture (a re-send to the same place).

Run in the ps2-web-recomp folder:  python3 ps2run_hdtex_staleres_patch.py [folder]
(patches runtime/src/gs/gpu/gpu.cpp; idempotent; refuses unknown source; needs ps2run_hdtex_patch.py applied)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
TAG = 'ps2run_hdtex_staleres_patch.py'
GPU = 'runtime/src/gs/gpu/gpu.cpp'

EDITS = [
    ('bool hd_refreshing(const Range &rg) {\n    const Image &im = g_image;\n    if (!im.active || !im.rrw) return false;\n',
     'bool hd_refreshing(const Range &rg, std::uint32_t base) {\n    const Image &im = g_image;\n    if (!im.active || !im.rrw) return false;\n'
     '    if (im.dbp != base) return false;   // a re-send of the same picture goes to the same place; anything else is a different picture (' + TAG + ')\n'),
    ('!(r.again > 0 && hd_refreshing(r.range))',
     '!(r.again > 0 && hd_refreshing(r.range, it->first))'),
]

try:
    with open(root + '/' + GPU, newline='') as f:
        raw = f.read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + GPU)
    raise SystemExit(1)
crlf = '\r\n' in raw
t = raw.replace('\r\n', '\n')
todo = [(old, new) for old, new in EDITS if new not in t]      # an edit that is already in is skipped, so a half-patched file is finished
if not todo:
    print("already patched")
    raise SystemExit
for old, _ in todo:
    if t.count(old) != 1:
        print("PATCH NOT APPLIED: " + GPU + " does not look like the expected source (" + old.strip().split('\n')[0][:60] + ")")
        raise SystemExit(1)
for old, new in todo:
    t = t.replace(old, new)
with open(root + '/' + GPU, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d edits)" % len(todo))
