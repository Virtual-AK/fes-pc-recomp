"""Add an F6 "save the game state now" key to the game window of PS2 Web Recomp.

Press F6 (or V) in the window and the exact machine state is written to live_1.state, live_2.state ... in the folder
you started the game from (never overwriting an older one). Such a state can be replayed again and again without the
window with:  build/native-p3fes/ps2run games/p3fes/disc/SLUS_216.21 --disc games/p3fes/disc.iso --load-state live_1.state ...
which lets a short glitch be repeated exactly and traced. The state files are game data: they stay on your PC.
Run in the ps2-web-recomp folder: python3 ps2run_window_savestate_patch.py
(patches runtime/include/ps2/system.hpp, runtime/src/system.cpp and host/window.cpp; idempotent; refuses unknown source)
Rebuild afterwards: ninja -C build/native-p3fes ps2run
"""
import sys

FILES = ('runtime/include/ps2/system.hpp', 'runtime/src/system.cpp', 'host/window.cpp')
root = sys.argv[1] if len(sys.argv) > 1 else '.'
texts = {}
for f in FILES:
    try:
        texts[f] = open(root + '/' + f).read()
    except OSError:
        print("PATCH NOT APPLIED: cannot read", f); raise SystemExit(1)
hpp, cpp, win = (texts[f] for f in FILES)

if 'request_state_save' in hpp and 'request_state_save' in cpp and 'request_state_save' in win:
    print("already patched"); raise SystemExit

HPP_OLD = 'bool save_state(const std::string &path);\n'
HPP_NEW = HPP_OLD + 'void request_state_save();\n'
CPP_VAR_OLD = 'bool g_state_request = false;\n'
CPP_VAR_NEW = CPP_VAR_OLD + 'std::atomic<bool> g_live_state_request{false};\nint g_live_state_n = 0;\n'
CPP_VB_OLD = '    if (g_options.save_state_frame && g_frames == g_options.save_state_frame) g_state_request = true;\n'
CPP_VB_NEW = CPP_VB_OLD + """    if (g_live_state_request.exchange(false)) {
        std::string name;
        do name = "live_" + std::to_string(++g_live_state_n) + ".state"; while (std::ifstream(name).good());
        g_options.save_state_path = name;
        g_state_request = true;
    }
"""
CPP_FN_OLD = 'bool load_state(const std::uint8_t *data, std::size_t size) {\n'
CPP_FN_NEW = 'void request_state_save() { g_live_state_request.store(true); }\n\n' + CPP_FN_OLD
WIN_OLD = '            if (k == SDL_SCANCODE_F12 || k == SDL_SCANCODE_F9 || k == SDL_SCANCODE_F8 || k == SDL_SCANCODE_C) {\n'
WIN_NEW = """            if (k == SDL_SCANCODE_F6 || k == SDL_SCANCODE_V) {
                std::fprintf(stderr, "[state] save requested\\n");
                ps2::request_state_save();
            }
""" + WIN_OLD

for what, text, old in (('system.hpp', hpp, HPP_OLD), ('g_state_request', cpp, CPP_VAR_OLD), ('vblank', cpp, CPP_VB_OLD),
                        ('load_state', cpp, CPP_FN_OLD), ('window keys (apply ps2run_window_capture_patch.py first)', win, WIN_OLD)):
    if text.count(old) != 1:
        print("PATCH NOT APPLIED:", what); raise SystemExit(1)
if '<atomic>' not in cpp or '<fstream>' not in cpp:
    print("PATCH NOT APPLIED: includes"); raise SystemExit(1)

hpp = hpp.replace(HPP_OLD, HPP_NEW, 1)
cpp = cpp.replace(CPP_VAR_OLD, CPP_VAR_NEW, 1).replace(CPP_VB_OLD, CPP_VB_NEW, 1).replace(CPP_FN_OLD, CPP_FN_NEW, 1)
win = win.replace(WIN_OLD, WIN_NEW, 1)
for f, t in zip(FILES, (hpp, cpp, win)):
    open(root + '/' + f, 'w').write(t)
print("patched (F6 saves the state)")
