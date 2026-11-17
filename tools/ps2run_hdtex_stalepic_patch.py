"""HD textures: a title picture no longer shows on top of the textures of the next scene (the one-frame green rug and green props after loading a save).

What went wrong: the title screen sends its pictures (the green moon, PRESS ANY BUTTON, the F box) again and again to about 30 different places in video
memory, so after the title many places still hold a remembered HD picture. A remembered picture is kept while "the game is re-sending a picture over
this one's memory" (hd_refreshing), and that test accepted any upload that started at the same place, even a small piece of the next scene's textures.
While that upload was in progress, props drawn from that place (the lounge rug, the papers on the counter) were drawn with the HD moon: a mottled green
flash for about two frames.

Fix: (1) the exemption only holds for an upload that covers exactly the same memory as the remembered picture (a real re-send of the same picture);
(2) when a different picture has finished arriving at a place, the remembered picture there is forgotten at once.

Run in the ps2-web-recomp folder:  python3 ps2run_hdtex_stalepic_patch.py [folder]
(patches runtime/src/gs/gpu/gpu.cpp; idempotent; refuses unknown source; needs ps2run_hdtex_patch.py and ps2run_hdtex_staleres_patch.py applied)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
TAG = 'ps2run_hdtex_stalepic_patch.py'
GPU = 'runtime/src/gs/gpu/gpu.cpp'

OLD1 = '        g_hd_seen.erase(im.dbp);   // something else was sent here: whatever was re-sent before is not coming back\n'
NEW1 = '        g_hd_res.erase(im.dbp);   // a different picture finished arriving here: the remembered one is gone (' + TAG + ')\n' + OLD1
OLD2 = '    if (!(rg.lo < u.hi && u.lo < rg.hi)) return false;\n'
NEW2 = OLD2 + '    if (u.lo != rg.lo || u.hi != rg.hi) return false;   // only a re-send of the very same place counts (' + TAG + ')\n'
EDITS = [(OLD1, NEW1), (OLD2, NEW2)]

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
        print("PATCH NOT APPLIED: unknown source (expected text found %d times)" % t.count(old))
        raise SystemExit(1)
if 'hd_refreshing(const Range &rg, std::uint32_t base)' not in t:
    print("PATCH NOT APPLIED: ps2run_hdtex_staleres_patch.py is not applied")
    raise SystemExit(1)
for old, new in todo:
    t = t.replace(old, new)
with open(root + '/' + GPU, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d edits)" % len(todo))
