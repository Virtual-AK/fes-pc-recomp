"""Autosave for the PC window of PS2 Web Recomp (the same idea as the browser autosave, see docs/autosave.md).

New switches for ps2run:
  --autosave DIR         turn autosaving on; states are written to DIR as <kind>_<YYYYMMDD-HHMMSS>.state
  --autosave-every MIN   minutes between timed saves (default 2, 0 = off)
  --autosave-keep N      keep the newest N of each kind (default 3)
  --autosave-card 0|1    also save 8 seconds after each in-game save (default 1)
  --load-state FILE      already exists: resume from a state
Kinds: timer (every N minutes), card (after an in-game save), manual (F5 in the window).
A state is written to <name>.state.part first and renamed when complete, so a crash never leaves a half file.
Old files beyond the newest N of their kind are deleted. A state only fits the build that made it: the launcher keeps
each build's states in its own folder.

Run in the ps2-web-recomp folder AFTER ps2run_window_savestate_patch.py:  python3 ps2run_autosave_patch.py [folder]
(patches runtime/include/ps2/system.hpp, runtime/src/system.cpp, host/main.cpp, host/window.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'

HPP_OPT_OLD = '    std::uint64_t save_state_frame = 0;\n};\n'
HPP_OPT_NEW = ('    std::uint64_t save_state_frame = 0;\n'
               '    std::string autosave_dir;\n'
               '    double autosave_minutes = 2.0;\n'
               '    int autosave_keep = 3;\n'
               '    bool autosave_card = true;\n};\n')
HPP_FN_OLD = 'void request_state_save();\n'
HPP_FN_NEW = HPP_FN_OLD + 'void request_autosave_now();\nvoid note_card_saved();\n'

CPP_INC_OLD = '#include <chrono>\n'
CPP_INC_NEW = '#include <chrono>\n#include <ctime>\n#include <filesystem>\n#include <functional>\n#include <vector>\n'

CPP_VAR_OLD = 'int g_live_state_n = 0;\n'
CPP_VAR_NEW = CPP_VAR_OLD + r'''
// ---- autosave (ps2run_autosave_patch.py)
std::atomic<bool> g_as_manual{false}, g_as_card_saved{false};
std::chrono::steady_clock::time_point g_as_last, g_as_card_due;
bool g_as_started = false, g_as_card_wait = false;
std::string g_as_final;

#ifndef __EMSCRIPTEN__
std::string as_stamp() {
    const std::time_t t = std::time(nullptr);
    std::tm tm{};
#ifdef _WIN32
    localtime_s(&tm, &t);
#else
    localtime_r(&t, &tm);
#endif
    char buf[32];
    std::strftime(buf, sizeof buf, "%Y%m%d-%H%M%S", &tm);
    return buf;
}

void as_prune(const std::string &dir, const std::string &kind) {
    namespace fs = std::filesystem;
    std::error_code ec;
    std::vector<std::string> names;
    for (const auto &e : fs::directory_iterator(dir, ec)) {
        const std::string n = e.path().filename().string();
        if (n.size() > kind.size() + 7 && n.compare(0, kind.size() + 1, kind + "_") == 0 && n.compare(n.size() - 6, 6, ".state") == 0) names.push_back(n);
    }
    std::sort(names.begin(), names.end(), std::greater<>());
    for (std::size_t i = static_cast<std::size_t>(std::max(1, g_options.autosave_keep)); i < names.size(); ++i) fs::remove(fs::path(dir) / names[i], ec);
}

void as_request(const char *kind) {
    namespace fs = std::filesystem;
    std::error_code ec;
    fs::create_directories(g_options.autosave_dir, ec);
    g_as_final = (fs::path(g_options.autosave_dir) / (std::string(kind) + "_" + as_stamp() + ".state")).string();
    g_options.save_state_path = g_as_final + ".part";
    g_state_request = true;
}

void as_tick() {
    if (g_options.autosave_dir.empty() || g_state_request) return;
    const auto t = std::chrono::steady_clock::now();
    if (!g_as_started) {
        g_as_started = true;
        g_as_last = t;
    }
    if (g_as_card_saved.exchange(false) && g_options.autosave_card) {
        g_as_card_wait = true;
        g_as_card_due = t + std::chrono::seconds(8);
    }
    if (g_as_manual.exchange(false)) {
        g_as_last = t;
        as_request("manual");
        return;
    }
    if (g_as_card_wait && t >= g_as_card_due) {
        g_as_card_wait = false;
        g_as_last = t;
        as_request("card");
        return;
    }
    if (g_options.autosave_minutes > 0 && std::chrono::duration<double>(t - g_as_last).count() >= g_options.autosave_minutes * 60.0) {
        g_as_last = t;
        as_request("timer");
    }
}

void as_finish() {
    if (g_as_final.empty()) return;
    namespace fs = std::filesystem;
    std::error_code ec;
    const std::string final_path = g_as_final, part = g_as_final + ".part";
    g_as_final.clear();
    if (!fs::exists(part, ec)) return;   // a live (F6) save took this frame's request
    fs::rename(part, final_path, ec);
    if (ec) {
        std::fprintf(stderr, "[autosave] cannot finish %s: %s\n", final_path.c_str(), ec.message().c_str());
        fs::remove(part, ec);
        return;
    }
    const std::string name = fs::path(final_path).filename().string();
    as_prune(g_options.autosave_dir, name.substr(0, name.find('_')));
}
#endif
'''

CPP_VB_OLD = '    if (g_live_state_request.exchange(false)) {\n        std::string name;\n'
CPP_VB_NEW = '#ifndef __EMSCRIPTEN__\n    as_tick();\n#endif\n' + CPP_VB_OLD

CPP_PUB_OLD = 'void request_state_save() { g_live_state_request.store(true); }\n'
CPP_PUB_NEW = CPP_PUB_OLD + 'void request_autosave_now() { g_as_manual.store(true); }\nvoid note_card_saved() { g_as_card_saved.store(true); }\n'

CPP_RUN_OLD = '            g_state_request = false;\n            save_state(g_options.save_state_path);\n'
CPP_RUN_NEW = CPP_RUN_OLD + '#ifndef __EMSCRIPTEN__\n            as_finish();\n#endif\n'

MAIN_USE_OLD = '"              [--save-state frame:file] [--load-state file]\\n");'
MAIN_USE_NEW = ('"              [--save-state frame:file] [--load-state file]\\n"\n'
                '            "              [--autosave dir] [--autosave-every minutes] [--autosave-keep n] [--autosave-card 0|1]\\n");')
MAIN_ARG_OLD = '        else if (a == "--load-state" && i + 1 < argc) load_path = argv[++i];\n'
MAIN_ARG_NEW = ('        else if (a == "--autosave" && i + 1 < argc) ps2::g_options.autosave_dir = argv[++i];\n'
                '        else if (a == "--autosave-every" && i + 1 < argc) ps2::g_options.autosave_minutes = std::strtod(argv[++i], nullptr);\n'
                '        else if (a == "--autosave-keep" && i + 1 < argc) ps2::g_options.autosave_keep = std::atoi(argv[++i]);\n'
                '        else if (a == "--autosave-card" && i + 1 < argc) ps2::g_options.autosave_card = std::atoi(argv[++i]) != 0;\n'
                + MAIN_ARG_OLD)
MAIN_HOOK_OLD = '#ifdef PS2_WINDOW\n    if (window && !open_window(fullscreen)) return 1;\n'
MAIN_HOOK_NEW = ('    if (!ps2::g_options.autosave_dir.empty()) ps2::g_options.on_memcard_saved = [] { ps2::note_card_saved(); };\n'
                 + MAIN_HOOK_OLD)

WIN_OLD = '            if (k == SDL_SCANCODE_F12 || k == SDL_SCANCODE_F9 || k == SDL_SCANCODE_F8 || k == SDL_SCANCODE_C) {\n'
WIN_NEW = ('            if (k == SDL_SCANCODE_F5) {\n'
           '                std::fprintf(stderr, "[autosave] save now requested\\n");\n'
           '                ps2::request_autosave_now();\n'
           '            }\n' + WIN_OLD)

EDITS = [
    ('runtime/include/ps2/system.hpp', [(HPP_OPT_OLD, HPP_OPT_NEW), (HPP_FN_OLD, HPP_FN_NEW)]),
    ('runtime/src/system.cpp', [(CPP_INC_OLD, CPP_INC_NEW), (CPP_VAR_OLD, CPP_VAR_NEW), (CPP_VB_OLD, CPP_VB_NEW),
                                (CPP_PUB_OLD, CPP_PUB_NEW), (CPP_RUN_OLD, CPP_RUN_NEW)]),
    ('host/main.cpp', [(MAIN_USE_OLD, MAIN_USE_NEW), (MAIN_ARG_OLD, MAIN_ARG_NEW), (MAIN_HOOK_OLD, MAIN_HOOK_NEW)]),
    ('host/window.cpp', [(WIN_OLD, WIN_NEW)]),
]


def fail(msg):
    print("PATCH NOT APPLIED:", msg)
    raise SystemExit(1)


texts = {}
for rel, _ in EDITS:
    try:
        with open(root + '/' + rel, newline='') as f:
            texts[rel] = f.read()
    except OSError:
        fail("cannot read " + rel)

if all(new in texts[rel] for rel, edits in EDITS for _, new in edits):
    print("already patched")
    raise SystemExit

if 'request_state_save' not in texts['runtime/include/ps2/system.hpp']:
    fail("apply ps2run_window_savestate_patch.py first")

done = 0
out = {}
for rel, edits in EDITS:
    t = texts[rel]
    crlf = '\r\n' in t
    if crlf:
        t = t.replace('\r\n', '\n')
    for old, new in edits:
        if new in t:
            continue
        if t.count(old) != 1:
            fail(rel + " does not look like the expected source")
        t = t.replace(old, new)
        done += 1
    out[rel] = t.replace('\n', '\r\n') if crlf else t
for rel, t in out.items():
    with open(root + '/' + rel, 'w', newline='') as f:
        f.write(t)
print("patched (%d edits)" % done)
