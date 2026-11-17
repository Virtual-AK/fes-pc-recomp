"""HD textures: a portrait no longer drops to the original (or flickers between the two) while a small texture is sent over the same memory right after it.

What went wrong: the game sends a portrait, draws it, and a moment later sends a small sprite (for example 32x32) to the same place in video memory. Before a
write is queued, the draws already waiting that read the same memory are flushed (queue_pre -> batch_conflict -> flush_batch), which is when the HD picture is
put into those draws. But the HD code noted "this memory was written" one line BEFORE that flush, so the draw was checked against a write that came after
it, the picture counted as overwritten, and the portrait was drawn from the original for that frame - every frame while the sprite kept arriving (Mitsuru
after her father's scene, Junpei at the beach house).

Fix: note the write after queue_pre. A draw is then checked against the memory as it was when the draw happened.

Run in the ps2-web-recomp folder:  python3 ps2run_hdtex_noteorder_patch.py [folder]
(patches runtime/src/gs/gpu/gpu.cpp; idempotent; refuses unknown source; needs ps2run_hdtex_patch.py applied)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
TAG = 'ps2run_hdtex_noteorder_patch.py'
GPU = 'runtime/src/gs/gpu/gpu.cpp'

OLD = '''    hd_note_write(op.range);   // ps2run_hdtex_patch.py
    queue_pre(op);
'''
NEW = '''    queue_pre(op);   // draws waiting on this memory are flushed in here, and must still see the picture as it was
    hd_note_write(op.range);   // ps2run_hdtex_patch.py, after queue_pre (''' + TAG + ''')
'''

try:
    with open(root + '/' + GPU, newline='') as f:
        raw = f.read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + GPU)
    raise SystemExit(1)
crlf = '\r\n' in raw
t = raw.replace('\r\n', '\n')
if NEW in t:
    print("already patched")
    raise SystemExit
if t.count(OLD) != 1:
    print("PATCH NOT APPLIED: " + GPU + " does not look like the expected source (hd_note_write / queue_pre in queue_upload)")
    raise SystemExit(1)
t = t.replace(OLD, NEW)
with open(root + '/' + GPU, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (1 edit)")
