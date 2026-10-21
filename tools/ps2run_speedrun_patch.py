"""Speedrun clock for the PC window of PS2 Web Recomp (host/window.cpp, Windows only).

With the environment variable PS2_SPEEDRUN=<file> (the launcher sets it from Settings > Speedrun) the window shows a clock in the top left
corner of the game picture: H:MM:SS.cc, real time. The clock is a small transparent window that sits on top of the game window (the game
draws through the graphics card, so it cannot be painted into the picture itself); it is click-through and follows the window when it is
moved, resized, maximized or full screen. It hides with the game window. A display or game capture in OBS shows it; some "window capture" modes do not.
The elapsed time is saved to <file> once a second and read back at start, so closing the game and pressing Resume carries on from where the
clock stopped. Keys (game window focused): F6 pauses / continues, F7 sets the clock back to 0:00:00.00.

Run in the ps2-web-recomp folder:  python3 ps2run_speedrun_patch.py [folder]
(idempotent; refuses unknown source; independent of the other window.cpp patches)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
REL = 'host/window.cpp'

DECL_OLD = 'namespace {\n'
DECL_NEW = DECL_OLD + 'void speedrun_tick();   // ps2run_speedrun_patch.py\n'
FN_OLD = 'void show_pixels(const std::uint32_t *rgba, std::uint32_t w, std::uint32_t h) {\n'
FN_NEW = r'''// ---- speedrun clock (ps2run_speedrun_patch.py)
#ifdef _WIN32
HWND g_sr_wnd = nullptr;
HFONT g_sr_font = nullptr;
int g_sr_font_h = 0;
char g_sr_text[40] = "0:00:00.00";

LRESULT CALLBACK sr_proc(HWND h, UINT m, WPARAM w, LPARAM l) {
    if (m == WM_PAINT) {
        PAINTSTRUCT ps;
        HDC dc = BeginPaint(h, &ps);
        RECT rc;
        GetClientRect(h, &rc);
        HBRUSH bg = CreateSolidBrush(RGB(255, 0, 255));
        FillRect(dc, &rc, bg);
        DeleteObject(bg);
        SetBkMode(dc, TRANSPARENT);
        HGDIOBJ old = SelectObject(dc, g_sr_font);
        const int n = static_cast<int>(std::strlen(g_sr_text));
        SetTextColor(dc, RGB(0, 0, 0));
        for (int dx = -2; dx <= 2; dx += 2)
            for (int dy = -2; dy <= 2; dy += 2)
                if (dx || dy) TextOutA(dc, 3 + dx, 3 + dy, g_sr_text, n);
        SetTextColor(dc, RGB(255, 255, 255));
        TextOutA(dc, 3, 3, g_sr_text, n);
        SelectObject(dc, old);
        EndPaint(h, &ps);
        return 0;
    }
    if (m == WM_ERASEBKGND) return 1;
    if (m == WM_NCHITTEST) return HTTRANSPARENT;
    if (m == WM_MOUSEACTIVATE) return MA_NOACTIVATE;
    return DefWindowProcA(h, m, w, l);
}
#endif

void speedrun_tick() {
#ifdef _WIN32
    static bool init = false, on = false, paused = false, f6 = false, f7 = false;
    static std::uint64_t ms = 0;
    static Uint32 last = 0, saved = 0;
    static std::string path;
    static HWND owner = nullptr;
    auto save = [&] {
        if (std::FILE *f = std::fopen(path.c_str(), "wb")) {
            std::fprintf(f, "%llu\n", static_cast<unsigned long long>(ms));
            std::fclose(f);
        }
    };
    if (!init) {
        init = true;
        const char *e = std::getenv("PS2_SPEEDRUN");
        if (!e || !*e || !g_window) return;
        path = e;
        if (std::FILE *f = std::fopen(path.c_str(), "rb")) {
            unsigned long long v = 0;
            if (std::fscanf(f, "%llu", &v) == 1) ms = v;
            std::fclose(f);
        }
        SDL_SysWMinfo info;
        SDL_VERSION(&info.version);
        if (!SDL_GetWindowWMInfo(g_window, &info) || info.subsystem != SDL_SYSWM_WINDOWS) return;
        owner = info.info.win.window;
        WNDCLASSA wc = {};
        wc.lpfnWndProc = sr_proc;
        wc.hInstance = GetModuleHandleA(nullptr);
        wc.lpszClassName = "ps2run_speedrun_clock";
        RegisterClassA(&wc);
        g_sr_wnd = CreateWindowExA(WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, wc.lpszClassName, "", WS_POPUP, 0, 0, 10, 10, owner,
                                   nullptr, wc.hInstance, nullptr);
        if (!g_sr_wnd) return;
        SetLayeredWindowAttributes(g_sr_wnd, RGB(255, 0, 255), 0, LWA_COLORKEY);
        on = true;
        last = saved = SDL_GetTicks();
        std::fprintf(stderr, "[speedrun] clock on, file %s, starts at %llu ms\n", path.c_str(), static_cast<unsigned long long>(ms));
    }
    if (!on) return;
    const Uint32 now = SDL_GetTicks();
    if (!paused) ms += now - last;
    last = now;
    if (SDL_GetKeyboardFocus() == g_window) {
        const Uint8 *k = SDL_GetKeyboardState(nullptr);
        if (k[SDL_SCANCODE_F6] && !f6) { paused = !paused; save(); }
        if (k[SDL_SCANCODE_F7] && !f7) { ms = 0; save(); }
        f6 = k[SDL_SCANCODE_F6] != 0;
        f7 = k[SDL_SCANCODE_F7] != 0;
    }
    if (now - saved >= 1000) {
        saved = now;
        save();
    }
    if (IsIconic(owner) || !IsWindowVisible(owner)) {
        ShowWindow(g_sr_wnd, SW_HIDE);
        return;
    }
    RECT rc;
    GetClientRect(owner, &rc);
    POINT p = {0, 0};
    ClientToScreen(owner, &p);
    int fh = (rc.bottom - rc.top) / 20;
    if (fh < 18) fh = 18;
    if (fh != g_sr_font_h) {
        if (g_sr_font) DeleteObject(g_sr_font);
        g_sr_font = CreateFontA(-fh, 0, 0, 0, FW_BOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, NONANTIALIASED_QUALITY, FIXED_PITCH | FF_MODERN, "Consolas");
        g_sr_font_h = fh;
    }
    const unsigned long long t = ms;
    char text[40];
    std::snprintf(text, sizeof text, "%llu:%02llu:%02llu.%02llu%s", t / 3600000, t / 60000 % 60, t / 1000 % 60, t / 10 % 100, paused ? " II" : "");
    const bool changed = std::strcmp(text, g_sr_text) != 0;
    std::strcpy(g_sr_text, text);
    SetWindowPos(g_sr_wnd, nullptr, p.x + fh / 2, p.y + fh / 2, fh * 8, fh * 3 / 2 + 6, SWP_NOACTIVATE | SWP_NOZORDER | SWP_SHOWWINDOW);
    if (changed) InvalidateRect(g_sr_wnd, nullptr, FALSE);
#endif
}

''' + FN_OLD
CALL_OLD = '    poll_port(0);\n    poll_port(1);\n}\n'
CALL_NEW = '    poll_port(0);\n    poll_port(1);\n    speedrun_tick();   // ps2run_speedrun_patch.py\n}\n'
EDITS = [(DECL_OLD, DECL_NEW), (FN_OLD, FN_NEW), (CALL_OLD, CALL_NEW)]


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
