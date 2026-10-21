"""Widescreen for the PC window of PS2 Web Recomp (see docs/widescreen.md).

Two parts, both switched on by environment variables (the launcher sets them from its Widescreen setting):
  PS2_ASPECT=16:9            the picture is shown at 16:9 instead of 4:3 (stretches the game's own picture to the window)
  PS2_PATCH=ADDR=VAL/EXPECT;ADDR=VAL   32-bit values (hex) written into the game's memory every frame; with /EXPECT a value
                             is only written when the game still holds EXPECT there (so a wrong address is never poisoned)
The runner prints "[widescreen] ..." lines to stderr (the launcher keeps them in ~/.p3fes-window.log).
Only DATA patches work this way. Patches that change the game's code (most of the community .pnach) cannot, because the
game's code is converted ahead of time; see docs/widescreen.md.

Run in the ps2-web-recomp folder:  python3 ps2run_widescreen_patch.py [folder]
(patches runtime/src/gs/gpu/gpu.cpp and runtime/src/system.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'

GPU_VAR_OLD = 'std::uint32_t g_scale = 1, g_copy_words = 1u << 20, g_field_words = 1u << 19;\n'
GPU_VAR_NEW = GPU_VAR_OLD + 'float g_aspect = 4.0f / 3.0f;   // ps2run_widescreen_patch.py\n'
GPU_V1_OLD = '        const float vw = std::min(w, h * 4.0f / 3.0f), vh = vw * 3.0f / 4.0f;\n'
GPU_V1_NEW = '        const float vw = std::min(w, h * g_aspect), vh = vw / g_aspect;\n'
GPU_V2_OLD = '    const float vw = std::min(sw, sh * 4.0f / 3.0f), vh = vw * 3.0f / 4.0f;\n'
GPU_V2_NEW = '    const float vw = std::min(sw, sh * g_aspect), vh = vw / g_aspect;\n'
GPU_ENV_OLD = '    if (const char *scale = std::getenv("PS2_SCALE")) g_scale ='
GPU_ENV_NEW = r'''    if (const char *asp = std::getenv("PS2_ASPECT")) {
        float a = 0.0f, b = 0.0f;
        if (std::sscanf(asp, "%f:%f", &a, &b) == 2 && a > 0.0f && b > 0.0f) g_aspect = std::clamp(a / b, 1.0f, 3.0f);
        else if (std::sscanf(asp, "%f", &a) == 1) g_aspect = std::clamp(a, 1.0f, 3.0f);
        std::fprintf(stderr, "[widescreen] picture aspect %.4f\n", g_aspect);
    }
''' + GPU_ENV_OLD

SYS_INC_OLD = '#include <algorithm>\n'
SYS_INC_NEW = '#include <algorithm>\n#include <cstdlib>\n#include <cstring>\n'
SYS_FN_OLD = 'void vblank() {\n'
SYS_FN_NEW = r'''// ---- widescreen data patches (ps2run_widescreen_patch.py)
void ws_apply() {
    struct P { std::uint32_t addr, val, expect; bool has_expect, done, warned; };
    static std::vector<P> list;
    static bool init = false;
    if (!init) {
        init = true;
        if (const char *e = std::getenv("PS2_PATCH")) {
            std::string s = e;
            std::size_t pos = 0;
            while (pos < s.size()) {
                std::size_t end = s.find(';', pos);
                if (end == std::string::npos) end = s.size();
                const std::string item = s.substr(pos, end - pos);
                pos = end + 1;
                const std::size_t eq = item.find('=');
                if (eq == std::string::npos) continue;
                P p{};
                p.addr = static_cast<std::uint32_t>(std::strtoul(item.c_str(), nullptr, 16));
                p.val = static_cast<std::uint32_t>(std::strtoul(item.c_str() + eq + 1, nullptr, 16));
                const std::size_t sl = item.find('/', eq);
                if (sl != std::string::npos) {
                    p.has_expect = true;
                    p.expect = static_cast<std::uint32_t>(std::strtoul(item.c_str() + sl + 1, nullptr, 16));
                }
                if (p.addr + 4 <= kRamSize) list.push_back(p);
            }
        }
    }
    for (P &p : list) {
        std::uint32_t cur;
        std::memcpy(&cur, g_ram + p.addr, 4);
        if (cur == p.val) {
            if (!p.done) std::fprintf(stderr, "[widescreen] %08x already holds %08x\n", p.addr, cur);
            p.done = true;
        } else if (!p.has_expect || cur == p.expect) {
            std::memcpy(g_ram + p.addr, &p.val, 4);
            if (!p.done) std::fprintf(stderr, "[widescreen] %08x: %08x -> %08x\n", p.addr, cur, p.val);
            p.done = true;
        } else if (!p.warned) {
            p.warned = true;
            std::fprintf(stderr, "[widescreen] %08x holds %08x, expected %08x: left alone\n", p.addr, cur, p.expect);
        }
    }
}

void vblank() {
'''
SYS_CALL_OLD = '    apply_presses();\n    if (g_options.on_vblank) g_options.on_vblank();\n'
SYS_CALL_NEW = '    apply_presses();\n#ifndef __EMSCRIPTEN__\n    ws_apply();\n#endif\n    if (g_options.on_vblank) g_options.on_vblank();\n'

EDITS = [
    ('runtime/src/gs/gpu/gpu.cpp', [(GPU_VAR_OLD, GPU_VAR_NEW), (GPU_V1_OLD, GPU_V1_NEW), (GPU_V2_OLD, GPU_V2_NEW), (GPU_ENV_OLD, GPU_ENV_NEW)]),
    ('runtime/src/system.cpp', [(SYS_INC_OLD, SYS_INC_NEW), (SYS_FN_OLD, SYS_FN_NEW), (SYS_CALL_OLD, SYS_CALL_NEW)]),
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

if all(new in texts[rel].replace('\r\n', '\n') for rel, edits in EDITS for _, new in edits):
    print("already patched")
    raise SystemExit

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
