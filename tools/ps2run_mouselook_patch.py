"""Mouse look and a full-screen start for the PC window of PS2 Web Recomp (host/window.cpp).

Mouse look, the same as the browser build: click the game picture to capture the mouse (Esc or switching to another window gives it back).
Moving the mouse sideways drives the right stick and also taps L1 / R1 (the buttons Persona 3 uses to turn the camera in Tartarus):
left = L1, right = R1. Gamepad and keyboard keep working at the same time.
Start: the window opens maximized (it fills the screen but keeps its title bar, like the launcher). Set PS2_NO_MAXIMIZE=1 to keep the
small window (a line in ~/.p3fes-window-env). F11 still toggles real full screen.

Run in the ps2-web-recomp folder:  python3 ps2run_mouselook_patch.py [folder]
(idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
REL = 'host/window.cpp'

FN_OLD = 'void poll_port(int port) {\n'
FN_NEW = r'''// ---- mouse look (ps2run_mouselook_patch.py)
int g_mouse_dx = 0;
int g_mouse_dir = 0;
Uint32 g_mouse_until = 0;

void mouse_look_apply(std::uint8_t &rx, std::uint16_t &pressed) {
    const Uint32 now = SDL_GetTicks();
    const int dx = g_mouse_dx;
    g_mouse_dx = 0;
    if (dx) {
        int v = 128 + dx * 6;
        v = v < 1 ? 1 : (v > 255 ? 255 : v);
        rx = static_cast<std::uint8_t>(v);
        if (dx >= 2 || dx <= -2) {
            g_mouse_dir = dx < 0 ? -1 : 1;
            g_mouse_until = now + 80;
        }
    }
    if (now < g_mouse_until) pressed |= (g_mouse_dir < 0 ? kL1 : kR1);
}

''' + FN_OLD
CALL_OLD = '    rumble(port);\n    static std::uint64_t last[2]'
CALL_NEW = '    if (port == 0) mouse_look_apply(rx, pressed);   // ps2run_mouselook_patch.py\n' + CALL_OLD
EV_OLD = '        if (e.type == SDL_CONTROLLERDEVICEADDED) open_pad(e.cdevice.which);\n'
EV_NEW = r'''        // mouse look (ps2run_mouselook_patch.py)
        if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT && !SDL_GetRelativeMouseMode()) SDL_SetRelativeMouseMode(SDL_TRUE);
        if (e.type == SDL_MOUSEMOTION && SDL_GetRelativeMouseMode()) g_mouse_dx += e.motion.xrel;
        if (e.type == SDL_KEYDOWN && e.key.keysym.scancode == SDL_SCANCODE_ESCAPE && SDL_GetRelativeMouseMode()) SDL_SetRelativeMouseMode(SDL_FALSE);
        if (e.type == SDL_WINDOWEVENT && e.window.event == SDL_WINDOWEVENT_FOCUS_LOST && SDL_GetRelativeMouseMode()) SDL_SetRelativeMouseMode(SDL_FALSE);
''' + EV_OLD
MAX_OLD = '    SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "linear");\n'
MAX_NEW = '    if (!fullscreen && !std::getenv("PS2_NO_MAXIMIZE")) SDL_MaximizeWindow(g_window);   // ps2run_mouselook_patch.py\n' + MAX_OLD
EDITS = [(FN_OLD, FN_NEW), (CALL_OLD, CALL_NEW), (EV_OLD, EV_NEW), (MAX_OLD, MAX_NEW)]


def fail(msg):
    print("PATCH NOT APPLIED:", msg)
    raise SystemExit(1)


try:
    with open(root + '/' + REL, newline='') as f:
        t = f.read()
except OSError:
    fail("cannot read " + REL)
crlf = '\r\n' in t
t = t.replace('\r\n', '\n')
if all(new in t for _, new in EDITS):
    print("already patched")
    raise SystemExit
done = 0
for old, new in EDITS:
    if new in t:
        continue
    if t.count(old) != 1:
        fail(REL + " does not look like the expected source (cannot find: " + old.strip().splitlines()[0][:70] + ")")
    t = t.replace(old, new)
    done += 1
with open(root + '/' + REL, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d edits)" % done)
