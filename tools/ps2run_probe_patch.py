"""Probe tools for the PC window of PS2 Web Recomp: find where the game keeps things (see docs/fast-forward.md).

  F3 in the game window       writes "[mark] frame N" to the log (press it when a line of dialogue appears)
  F7 in the game window       writes the game's whole 32 MB memory to ramdump_NNN_fFRAME.bin in the folder the program runs in
  PS2_WATCH=addr,addr,...     logs "[watch] frame N addr: old -> new" to stderr whenever one of those 32-bit words changes
These are for research only: nothing changes in the game. Analyse dumps with p3fes_ramfind.py.

Run in the ps2-web-recomp folder:  python3 ps2run_probe_patch.py [folder]
(patches runtime/include/ps2/system.hpp, runtime/src/system.cpp, host/window.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'

HPP_OLD = 'void request_state_save();\n'
HPP_NEW = HPP_OLD + 'void request_ramdump();\n'
CPP_FN_OLD = 'void time_frames() {\n'
CPP_FN_NEW = r'''// ---- probe tools (ps2run_probe_patch.py)
std::atomic<bool> g_ramdump_req{false};

void probe_tick() {
    struct W { std::uint32_t addr, last; };
    static std::vector<W> watch;
    static bool init = false;
    static int dumps = 0;
    if (!init) {
        init = true;
        if (const char *e = std::getenv("PS2_WATCH")) {
            const std::string s = e;
            std::size_t pos = 0;
            while (pos < s.size()) {
                std::size_t end = s.find(',', pos);
                if (end == std::string::npos) end = s.size();
                const std::uint32_t a = static_cast<std::uint32_t>(std::strtoul(s.substr(pos, end - pos).c_str(), nullptr, 16));
                pos = end + 1;
                if (a + 4 <= kRamSize) {
                    W w{a, 0};
                    std::memcpy(&w.last, g_ram + a, 4);
                    watch.push_back(w);
                }
            }
            std::fprintf(stderr, "[watch] watching %zu addresses\n", watch.size());
        }
    }
    for (W &w : watch) {
        std::uint32_t cur;
        std::memcpy(&cur, g_ram + w.addr, 4);
        if (cur != w.last) {
            std::fprintf(stderr, "[watch] frame %llu %08x: %08x -> %08x\n", static_cast<unsigned long long>(g_frames), w.addr, w.last, cur);
            w.last = cur;
        }
    }
    if (g_ramdump_req.exchange(false)) {
        char name[96];
        std::snprintf(name, sizeof name, "ramdump_%03d_f%llu.bin", ++dumps, static_cast<unsigned long long>(g_frames));
        if (std::FILE *f = std::fopen(name, "wb")) {
            std::fwrite(g_ram, 1, kRamSize, f);
            std::fclose(f);
            std::fprintf(stderr, "[ramdump] wrote %s\n", name);
        } else {
            std::fprintf(stderr, "[ramdump] cannot write %s\n", name);
        }
    }
}

void time_frames() {
'''
CPP_REQ_OLD = 'bool present_frame() { return gs::present(); }\n'
CPP_REQ_NEW = 'void request_ramdump() { g_ramdump_req.store(true); }   // ps2run_probe_patch.py\n' + CPP_REQ_OLD
LEGACY_DEF = 'void request_ramdump() { g_ramdump_req.store(true); }\n\n'   # an earlier version put it in the private part, where the window cannot reach it
CPP_CALL_OLD = '    if (g_options.on_vblank) g_options.on_vblank();\n    iop::sio2::flush_cards();\n'
CPP_CALL_NEW = '    if (g_options.on_vblank) g_options.on_vblank();\n#ifndef __EMSCRIPTEN__\n    probe_tick();\n#endif\n    iop::sio2::flush_cards();\n'
WIN_OLD = '        if (e.type == SDL_KEYDOWN && e.key.keysym.scancode == SDL_SCANCODE_F11 && !e.key.repeat) {\n'
WIN_NEW = ('        if (e.type == SDL_KEYDOWN && e.key.keysym.scancode == SDL_SCANCODE_F7 && !e.key.repeat) {\n'
           '            std::fprintf(stderr, "[ramdump] requested\\n");\n            ps2::request_ramdump();\n        }\n' + WIN_OLD)
F7_LINE = '        if (e.type == SDL_KEYDOWN && e.key.keysym.scancode == SDL_SCANCODE_F7 && !e.key.repeat) {\n'
F3_NEW = ('        if (e.type == SDL_KEYDOWN && e.key.keysym.scancode == SDL_SCANCODE_F3 && !e.key.repeat)\n'
          '            std::fprintf(stderr, "[mark] frame %llu\\n", static_cast<unsigned long long>(ps2::frame_count()));\n' + F7_LINE)
EDITS = [('runtime/include/ps2/system.hpp', [(HPP_OLD, HPP_NEW)]),
         ('runtime/src/system.cpp', [(CPP_FN_OLD, CPP_FN_NEW), (CPP_CALL_OLD, CPP_CALL_NEW), (CPP_REQ_OLD, CPP_REQ_NEW)]),
         ('host/window.cpp', [(WIN_OLD, WIN_NEW), (F7_LINE, F3_NEW)])]


def fail(msg):
    print("PATCH NOT APPLIED:", msg)
    raise SystemExit(1)


texts = {}
for rel, _ in EDITS:
    try:
        with open(root + '/' + rel, newline='') as f:
            texts[rel] = f.read().replace('\r\n', '\n').replace(LEGACY_DEF, '')
    except OSError:
        fail("cannot read " + rel)
if all(new in texts[rel] for rel, edits in EDITS for _, new in edits):
    print("already patched")
    raise SystemExit
done = 0
out = {}
for rel, edits in EDITS:
    t = texts[rel]
    for old, new in edits:
        if new in t:
            continue
        if t.count(old) != 1:
            fail(rel + " does not look like the expected source")
        t = t.replace(old, new)
        done += 1
    out[rel] = t
for rel, t in out.items():
    with open(root + '/' + rel, 'rb') as f:
        crlf = b'\r\n' in f.read()
    with open(root + '/' + rel, 'w', newline='') as f:
        f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d edits)" % done)
