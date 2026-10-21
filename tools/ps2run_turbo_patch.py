"""Turbo (fast forward) for the PC window of PS2 Web Recomp (see docs/fast-forward.md).

Press Tab in the game window to turn turbo on, press it again to turn it off. While on, the frame limiter is off (the game
runs as fast as the computer can, only every 4th frame is drawn) and sound is muted; the window title shows [TURBO]. It speeds up everything, not only
dialogue. Stopping at choices needs the game's own state (a later step).

Run in the ps2-web-recomp folder:  python3 ps2run_turbo_patch.py [folder]
(patches host/window.cpp, runtime/include/ps2/system.hpp, runtime/src/system.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'

PACE_OLD = 'constexpr Uint32 kAudioBytesPerMs = 48 * 4;\n\nvoid pace() {\n'
PACE_NEW = ('constexpr Uint32 kAudioBytesPerMs = 48 * 4;\n\n'
            'void pace() {\n    if (g_turbo) {\n        g_last = 0;\n        return;\n    }\n')
POLL_OLD = 'void poll() {\n    SDL_Event e;\n'
POLL_NEW = 'bool g_turbo = false;   // ps2run_turbo_patch.py: Tab toggles\n\n' + POLL_OLD
AUD_OLD = 'void queue_audio(const std::int16_t *samples, std::size_t frames) {\n'
AUD_NEW = AUD_OLD + '    if (g_turbo) return;\n'
TITLE_OLD = '    SDL_SetWindowTitle(g_window, title);\n'
TITLE_NEW = ('    if (g_turbo) {\n        const std::string t2 = std::string("[TURBO] ") + title;\n'
             '        SDL_SetWindowTitle(g_window, t2.c_str());\n    } else {\n        SDL_SetWindowTitle(g_window, title);\n    }\n')
VB_OLD = '    poll();\n    present();\n    pace();\n'
VB_NEW = ('    poll();\n    static unsigned turbo_n = 0;\n'
          '    if (!g_turbo || (++turbo_n & 3u) == 0) present();   // turbo shows every 4th frame: presenting is a sync point\n'
          '    pace();\n')
KEY_OLD = '            if (log_keys) std::fprintf(stderr, "[key] scancode %d (%s)\\n", static_cast<int>(k), SDL_GetScancodeName(k));\n'
KEY_BLOCK = ('            if (k == SDL_SCANCODE_TAB) {\n                g_turbo = !g_turbo;\n%s'
             '                std::fprintf(stderr, "[turbo] %%s\\n", g_turbo ? "on" : "off");\n            }\n')
KEY_LEGACY = KEY_OLD + KEY_BLOCK % ''          # an earlier version of this patch
KEY_NEW = KEY_OLD + KEY_BLOCK % '                ps2::set_turbo(g_turbo);\n'
HPP_OLD = 'void post_present();\n'
HPP_NEW = HPP_OLD + 'void set_turbo(bool on);\n'
SYS_OLD = 'void post_present() { gs::post_present(); }\n'
SYS_NEW = ('static std::atomic<bool> g_turbo_on{false};\n'
           'void set_turbo(bool on) { g_turbo_on.store(on); }\n'
           '// ps2run_turbo_patch.py: in turbo only every 4th frame is handed to the drawing thread (the game waits for it to show frames)\n'
           'void post_present() {\n    static unsigned n = 0;\n    if (g_turbo_on.load() && (++n & 3u) != 0) return;\n    gs::post_present();\n}\n')
EDITS = [('host/window.cpp', [(POLL_OLD, POLL_NEW), (VB_OLD, VB_NEW), (PACE_OLD, PACE_NEW), (AUD_OLD, AUD_NEW), (TITLE_OLD, TITLE_NEW), (KEY_OLD, KEY_NEW)]),
         ('runtime/include/ps2/system.hpp', [(HPP_OLD, HPP_NEW)]),
         ('runtime/src/system.cpp', [(SYS_OLD, SYS_NEW)])]


def fail(msg):
    print("PATCH NOT APPLIED:", msg)
    raise SystemExit(1)


texts, crlfs = {}, {}
for rel, _ in EDITS:
    try:
        with open(root + '/' + rel, newline='') as f:
            t = f.read()
    except OSError:
        fail("cannot read " + rel)
    crlfs[rel] = '\r\n' in t
    texts[rel] = t.replace('\r\n', '\n').replace(KEY_LEGACY, KEY_NEW)
if all(new in texts[rel] for rel, edits in EDITS for _, new in edits):
    print("already patched")
    raise SystemExit
done = 0
for rel, edits in EDITS:
    t = texts[rel]
    for old, new in edits:
        if new in t:
            continue
        if t.count(old) != 1:
            fail(rel + " does not look like the expected source (cannot find: " + old.strip().splitlines()[0][:70] + ")")
        t = t.replace(old, new)
        done += 1
    texts[rel] = t
for rel, t in texts.items():
    with open(root + '/' + rel, 'w', newline='') as f:
        f.write(t.replace('\n', '\r\n') if crlfs[rel] else t)
print("patched (%d edits)" % done)
