"""Memory card screens say "your PC" instead of "PlayStation 2" / "PS2" (Checking memory card (8MB) (for your PC)..., No memory card (for your PC) inserted in
MEMORY CARD slot 1, and the saving, loading and formatting messages).

The game keeps these messages as plain text in its own program (the main executable, NTSC-U). The window and the browser build load that program into memory
when the game starts, so the patch rewrites the ten lines there once, at the first frame. A line is only changed when memory holds exactly the original text
(so another program version or a translation that already changed the line is left alone). Every new line is no longer than the old one, so nothing else moves.

Run in the ps2-web-recomp folder:  python3 ps2run_pctext_patch.py [folder]
(patches runtime/src/system.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
TAG = 'ps2run_pctext_patch.py'
SYS = 'runtime/src/system.cpp'

TABLE = r'''
    {0x6b33f0, "No memory card (for PS2)", 24, "No memory card (for your PC)", 32},
    {0x6b3440, "The memory card (for PS2) in", 28, "Memory card (for your PC) in", 32},
    {0x6b34b0, "Formatting memory card (for PS2)", 32, "Formatting memory card (for your PC)", 48},
    {0x6b3520, "(for PS2) or controller, or reset/", 34, "(for your PC) or controller, or reset/", 48},
    {0x6b3640, "memory card (for PS2) in", 24, "memory card (for your PC) in", 32},
    {0x6b3750, "(for PS2) in MEMORY CARD", 24, "(for your PC) in MEMORY CARD", 32},
    {0x6b3780, "(for PS2) or controller, or", 27, "(for your PC) or controller, or", 32},
    {0x6b3880, "(for PlayStation\x82\xce\x80\x92)...", 24, "(for your PC)...", 32},
    {0x6b38c0, "a memory card (for PS2) with", 28, "a memory card for your PC with", 32},
    {0x6b3b50, "(for PS2) in MEMORY CARD slot 1.", 32, "(for your PC) in MEMORY CARD slot 1.", 48},
'''

HELP = '''// ps2run_pctext_patch.py: the memory card messages name the PC, not the PlayStation 2 (address in game memory, original text and its length, new text).
struct PcText { std::uint32_t addr; const char *old_text; std::uint32_t old_len; const char *new_text; std::uint32_t room; };   // room: bytes the line may use (up to the next text), with its end byte
const PcText kPcText[] = {
@TABLE@};

void pc_text_apply() {
    static bool done = false;
    if (done) return;
    done = true;
    for (const PcText &p : kPcText) {
        if (p.addr + p.old_len + 1 > kRamSize) continue;
        if (std::memcmp(g_ram + p.addr, p.old_text, p.old_len) != 0) continue;   // not the original text: leave it
        const std::size_t n = std::strlen(p.new_text);
        if (n + 1 > p.room) continue;
        std::memcpy(g_ram + p.addr, p.new_text, n);
        std::memset(g_ram + p.addr + n, 0, std::max<std::size_t>(p.old_len, n + 1) - n);
    }
}

'''.replace('@TABLE@', TABLE.strip('\n') + '\n')

A_OLD = '// ---- widescreen data patches (ps2run_widescreen_patch.py)\nvoid ws_apply() {\n'
A_NEW = HELP + A_OLD + '    pc_text_apply();   // ' + TAG + '\n'
EDITS = [(A_OLD, A_NEW)]

try:
    with open(root + '/' + SYS, newline='') as f:
        raw = f.read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + SYS)
    raise SystemExit(1)
crlf = '\r\n' in raw
t = raw.replace('\r\n', '\n')
if 'pc_text_apply();   // ' + TAG in t:
    print("already patched")
    raise SystemExit
if t.count(A_OLD) != 1:
    print("PATCH NOT APPLIED: unknown source (expected text found %d times)" % t.count(A_OLD))
    raise SystemExit(1)
t = t.replace(A_OLD, A_NEW)
with open(root + '/' + SYS, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (1 edit)")
