"""Speedrun clock for the BROWSER build. Patches web/shell.html.
With ?speedrun=1 in the page address (the launcher adds it when Settings > Speedrun is on) a clock shows in the top left of the page:
H:MM:SS.cc, real time, white with a black outline. It starts when the page opens and is saved in this browser once a second, so closing
the game and pressing Resume carries on from where it stopped. ?srzero=1 (the launcher adds it once after Settings > Speedrun > Reset)
sets it to zero. Keys: F6 pauses / continues, F7 sets it to 0:00:00.00. It sits over the picture, also in fullscreen.
Usage (in the ps2-web-recomp folder): python3 ps2web_speedrun_patch.py [web/shell.html]
Safe to run twice. Rebuild afterwards (scripts/build_web.sh p3fes)
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'web/shell.html'
s = open(p, newline='').read()
if 'ps2-speedrun' in s:
    print("already patched"); raise SystemExit
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')

CSS_OLD = '</style>\n'
CSS_NEW = """  /* ps2-speedrun */
  #srclock { position: fixed; left: 12px; top: 8px; z-index: 40; pointer-events: none; font: 700 30px/1 ui-monospace, Consolas, monospace;
             color: #fff; text-shadow: -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000, 0 0 6px #000; }
  #srclock[hidden] { display: none; }
""" + CSS_OLD
DIV_OLD = '<div id="stage"><canvas id="canvas" tabindex="0"></canvas></div>\n'
DIV_NEW = DIV_OLD + '<div id="srclock" hidden>0:00:00.00</div>\n'
JS_OLD = '{{{ SCRIPT }}}\n'
JS_NEW = """<script>
// ps2-speedrun: real-time clock over the picture, kept in this browser's local storage
(function () {
  const q = new URLSearchParams(location.search);
  const el = document.getElementById('srclock');
  if (!el || q.get('speedrun') !== '1') return;
  const KEY = 'ps2-speedrun-ms';
  let ms = 0, paused = false, last = performance.now(), saved = 0;
  try { ms = q.get('srzero') === '1' ? 0 : (Number(localStorage.getItem(KEY)) || 0); } catch (e) {}
  const fmt = (t) => {
    const cs = Math.floor(t / 10) % 100, s = Math.floor(t / 1000) % 60, m = Math.floor(t / 60000) % 60, h = Math.floor(t / 3600000);
    return h + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0') + '.' + String(cs).padStart(2, '0');
  };
  function save() { try { localStorage.setItem(KEY, String(Math.round(ms))); } catch (e) {} }
  function tick(now) {
    if (!paused) ms += now - last;
    last = now;
    el.textContent = fmt(ms);
    if (now - saved > 1000) { saved = now; save(); }
    requestAnimationFrame(tick);
  }
  el.hidden = false;
  save();
  requestAnimationFrame((n) => { last = n; tick(n); });
  window.addEventListener('keydown', (e) => {
    if (e.repeat || (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT'))) return;
    if (e.code === 'F6') { paused = !paused; e.preventDefault(); }
    else if (e.code === 'F7') { ms = 0; save(); e.preventDefault(); }
  });
  window.addEventListener('pagehide', save);
})();
</script>
""" + JS_OLD
for old in (CSS_OLD, DIV_OLD, JS_OLD):
    if s.count(old) != 1:
        print("PATCH NOT APPLIED: web/shell.html does not look like the expected source"); raise SystemExit(1)
s = s.replace(CSS_OLD, CSS_NEW).replace(DIV_OLD, DIV_NEW).replace(JS_OLD, JS_NEW)
open(p, 'w', newline='').write(s.replace('\n', '\r\n') if crlf else s)
print("patched (3 edits)")
