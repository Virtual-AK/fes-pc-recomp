"""Browser game tells the launcher when it is open and when it closes. Patches web/shell.html.
Every 5 seconds the page asks the launcher (the cardsync port in the page address) /gamebeat?s=1, and when the page is closed or left
it sends /gamebeat?s=0. The launcher uses this to pause its music while the game is open and bring it back the moment the game closes.
Usage (in the ps2-web-recomp folder): python3 ps2web_gamebeat_patch.py [web/shell.html]
Safe to run twice. Rebuild afterwards (scripts/build_web.sh p3fes)
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'web/shell.html'
s = open(p, newline='').read()
if 'ps2-gamebeat' in s:
    print("already patched"); raise SystemExit
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')
OLD = '{{{ SCRIPT }}}\n'
NEW = """<script>
// ps2-gamebeat: tell the launcher this game page is open (every 5 s) and when it closes
(function () {
  const port = new URLSearchParams(location.search).get('cardsync');
  if (!port) return;
  const url = (s) => 'http://127.0.0.1:' + port + '/gamebeat?s=' + s;
  const send = (s) => { try { fetch(url(s), { mode: 'no-cors', keepalive: true, cache: 'no-store' }).catch(() => {}); } catch (e) {} };
  send(1);
  setInterval(() => send(1), 5000);
  window.addEventListener('pagehide', () => send(0));
})();
</script>
""" + OLD
if s.count(OLD) != 1:
    print("PATCH NOT APPLIED: web/shell.html does not look like the expected source"); raise SystemExit(1)
s = s.replace(OLD, NEW)
open(p, 'w', newline='').write(s.replace('\n', '\r\n') if crlf else s)
print("patched (1 edit)")
