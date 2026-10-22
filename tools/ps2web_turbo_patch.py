"""Turbo (fast forward) for the BROWSER build: press Tab in the game page to turn it on, press it again to turn it off.
Same idea as the PC window (ps2run_turbo_patch.py, which must be applied first because it provides ps2::set_turbo): the frame limiter is off,
only every 4th frame is drawn, and sound is muted while turbo is on. A TURBO badge shows at the top right of the page.
Patches host/web.cpp and web/shell.html. Run in the ps2-web-recomp folder:  python3 ps2web_turbo_patch.py [folder]
(idempotent; refuses unknown source; rebuild afterwards with scripts/build_web.sh p3fes)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'

PUSH_OLD = 'void push_audio(const std::int16_t *samples, std::size_t frames) {\n'
PUSH_NEW = ('std::atomic<bool> g_turbo{false};   // ps2web_turbo_patch.py: Tab in the page toggles\n\n' + PUSH_OLD +
            '    if (g_turbo.load()) return;   // turbo is silent\n')
PACE_OLD = 'void pace() {\n    ps2::post_present();\n'
PACE_NEW = PACE_OLD + '    if (g_turbo.load()) {   // no frame limiter in turbo\n        g_next_frame = 0.0;\n        return;\n    }\n'
EXP_OLD = 'extern "C" EMSCRIPTEN_KEEPALIVE int ps2web_rumble(int pad) { return ps2::pad_rumble(pad); }\n'
EXP_NEW = EXP_OLD + 'extern "C" EMSCRIPTEN_KEEPALIVE void ps2web_set_turbo(int on) {\n    g_turbo.store(on != 0);\n    ps2::set_turbo(on != 0);\n}\n'
CPP = ('host/web.cpp', [(PUSH_OLD, PUSH_NEW), (PACE_OLD, PACE_NEW), (EXP_OLD, EXP_NEW)])

JS_OLD = '{{{ SCRIPT }}}\n'
JS_NEW = """<script>
// ps2-turbo: Tab toggles fast forward (no frame limiter, every 4th frame drawn, silent)
(function () {
  let on = false, badge = null;
  window.addEventListener('keydown', (e) => {
    if (e.code !== 'Tab' || e.repeat || e.altKey || e.ctrlKey || e.metaKey) return;
    const t = e.target && e.target.tagName;
    if (t === 'INPUT' || t === 'SELECT' || t === 'TEXTAREA') return;
    if (typeof Module === 'undefined' || !Module.running || !Module._ps2web_set_turbo) return;
    e.preventDefault();
    on = !on;
    Module._ps2web_set_turbo(on ? 1 : 0);
    if (!badge) {
      badge = document.createElement('div');
      badge.textContent = 'TURBO \\u25B6\\u25B6';
      badge.style.cssText = 'position:fixed;right:14px;top:8px;z-index:40;pointer-events:none;font:700 22px/1 system-ui,sans-serif;color:#ffd24a;text-shadow:-2px -2px 0 #000,2px -2px 0 #000,-2px 2px 0 #000,2px 2px 0 #000';
      document.body.appendChild(badge);
    }
    badge.hidden = !on;
  }, true);
})();
</script>
""" + JS_OLD
HTML = ('web/shell.html', [(JS_OLD, JS_NEW)])


def fail(msg):
    print("PATCH NOT APPLIED:", msg)
    raise SystemExit(1)


texts = {}
for rel in ['host/web.cpp', 'web/shell.html', 'runtime/include/ps2/system.hpp']:
    try:
        with open(root + '/' + rel, newline='') as f:
            texts[rel] = f.read()
    except OSError:
        fail("cannot read " + rel)
if 'set_turbo' not in texts['runtime/include/ps2/system.hpp']:
    fail("apply ps2run_turbo_patch.py first")
if 'ps2-turbo' in texts['web/shell.html'] and 'ps2web_set_turbo' in texts['host/web.cpp']:
    print("already patched")
    raise SystemExit
out, done = {}, 0
for rel, edits in (CPP, HTML):
    t = texts[rel]
    crlf = '\r\n' in t
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
