"""Browser controller panel. Patches web/shell.html (run ps2web_keyremap_patch.py first).
When a controller is connected, the Keys button becomes Controller and opens a panel that uses that controller's own
button names (PlayStation: Cross, Circle, Square, Triangle, Create, Options. Xbox: A, B, X, Y, View, Menu.
Nintendo: B, A, Y, X, Minus, Plus. Anything else: Bottom, Right, Left, Top button). Click a row, press the new button on
the controller, and it is used at once. The layout is saved in this browser for each controller type, so a DualSense and
an Xbox pad keep their own. The sticks follow the controller's sticks. A Keyboard keys button switches to the key panel.
While the panel waits for a button, the controller does not press anything in the game.
Usage (in the ps2-web-recomp folder): python3 ps2web_padremap_patch.py [web/shell.html]
Safe to run twice. Rebuild afterwards (scripts/build_web.sh p3fes, or p3fesmod)
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'web/shell.html'
s = open(p).read()
if 'ps2-pad-remap' in s:
    print("already patched"); raise SystemExit

PB_OLD = """const padButtons = [[0, 14], [1, 13], [2, 15], [3, 12], [4, 10], [5, 11], [6, 8], [7, 9], [8, 0], [9, 3], [10, 1], [11, 2],
                    [12, 4], [13, 6], [14, 7], [15, 5]];
"""
PB_NEW = """// ps2-pad-remap: controller button names and rebinding, saved for each controller type in this browser
// standard layout button index -> PS2 button bit
const padDefault = [[0, 14], [1, 13], [2, 15], [3, 12], [4, 10], [5, 11], [6, 8], [7, 9], [8, 0], [9, 3], [10, 1], [11, 2],
                    [12, 4], [13, 6], [14, 7], [15, 5]];
const PAD_ROWS = [[14, 'Cross (confirm)'], [13, 'Circle (cancel)'], [15, 'Square'], [12, 'Triangle'], [10, 'L1'], [11, 'R1'],
                  [8, 'L2'], [9, 'R2'], [1, 'L3'], [2, 'R3'], [3, 'Start'], [0, 'Select'],
                  [4, 'D-pad up'], [6, 'D-pad down'], [7, 'D-pad left'], [5, 'D-pad right']];
const PAD_DPAD = ['D-pad up', 'D-pad down', 'D-pad left', 'D-pad right'];
const PAD_NAMES = {
  ps: ['Cross', 'Circle', 'Square', 'Triangle', 'L1', 'R1', 'L2', 'R2', 'Create', 'Options', 'L3 (stick press)', 'R3 (stick press)'],
  xbox: ['A', 'B', 'X', 'Y', 'LB', 'RB', 'LT', 'RT', 'View', 'Menu', 'Left stick press', 'Right stick press'],
  nintendo: ['B', 'A', 'Y', 'X', 'L', 'R', 'ZL', 'ZR', 'Minus', 'Plus', 'Left stick press', 'Right stick press'],
  other: ['Bottom button', 'Right button', 'Left button', 'Top button', 'L1', 'R1', 'L2', 'R2', 'Select', 'Start', 'L3', 'R3'],
};
const PAD_TITLES = { ps: 'PlayStation controller', xbox: 'Xbox controller', nintendo: 'Nintendo controller', other: 'Controller' };
function padFamily(id) {
  const t = String(id || '').toLowerCase();
  if (/057e|nintendo|pro controller|joy-con|switch/.test(t)) return 'nintendo';
  if (/xbox|045e|xinput|microsoft/.test(t)) return 'xbox';
  if (/dualsense|dualshock|playstation|054c|sony|wireless controller/.test(t)) return 'ps';
  return 'other';
}
function padName(family, index) {
  const names = PAD_NAMES[family];
  if (index < 0) return 'not set';
  if (index < names.length) return names[index];
  if (index < 16) return PAD_DPAD[index - 12];
  return 'Button ' + index;
}
const PAD_STORE = 'ps2-padmap';
let padSaved = {};
try { padSaved = JSON.parse(localStorage.getItem(PAD_STORE) || '{}') || {}; } catch (e) { padSaved = {}; }
const padCache = {};
let padCapturing = false;
function padBinding(family) {
  const b = {};
  for (const [i, bit] of padDefault) b[bit] = i;
  const sv = padSaved[family];
  if (sv) for (const bit of Object.keys(b)) if (typeof sv[bit] === 'number') b[bit] = sv[bit];
  return b;
}
function padEntries(gamepad) {
  const family = padFamily(gamepad.id);
  if (!padCache[family]) {
    const b = padBinding(family);
    padCache[family] = Object.keys(b).filter((bit) => b[bit] >= 0).map((bit) => [b[bit], Number(bit)]);
  }
  return padCache[family];
}
function padFirst() {
  const list = navigator.getGamepads ? navigator.getGamepads() : [];
  for (const g of list) if (g && g.connected) return g;
  return null;
}
function padButtonLabel() {
  const el = document.getElementById('keys');
  if (el) el.textContent = padFirst() ? 'Controller' : 'Keys';
}
window.addEventListener('gamepadconnected', padButtonLabel);
window.addEventListener('gamepaddisconnected', () => setTimeout(padButtonLabel, 0));
padButtonLabel();
function padShow() {
  const pad = padFirst();
  if (!pad) { keyShowKeyboard(); return; }
  if (document.getElementById('key-panel')) return;
  keys.clear();
  const family = padFamily(pad.id);
  const box = document.createElement('div');
  box.id = 'key-panel';
  box.style.cssText = 'position:fixed;inset:0;z-index:50;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center';
  const card = document.createElement('div');
  card.style.cssText = 'background:#1b2438;color:#fff;padding:16px 20px;border-radius:8px;max-width:520px;width:92%;max-height:85vh;overflow:auto;font:14px system-ui,sans-serif';
  box.appendChild(card);
  const title = document.createElement('div');
  title.textContent = PAD_TITLES[family];
  title.style.cssText = 'font-size:16px;font-weight:600;margin-bottom:2px';
  const sub = document.createElement('div');
  sub.textContent = pad.id.replace(/\\s*\\(.*$/, '');
  sub.style.cssText = 'opacity:.6;margin-bottom:6px;font-size:12px';
  const help = document.createElement('div');
  help.textContent = 'Click a row, then press the new button on the controller. Esc cancels. The sticks follow the controller sticks. Saved in this browser for this type of controller.';
  help.style.cssText = 'opacity:.75;margin-bottom:10px';
  const list = document.createElement('div');
  const note = document.createElement('div');
  note.style.cssText = 'min-height:18px;margin-top:8px;color:#ffd479';
  const bar = document.createElement('div');
  bar.style.cssText = 'display:flex;gap:8px;margin-top:12px';
  const reset = document.createElement('button');
  reset.textContent = 'Reset to defaults';
  const swap = document.createElement('button');
  swap.textContent = 'Keyboard keys';
  const shut = document.createElement('button');
  shut.textContent = 'Close';
  bar.append(reset, swap, shut);
  card.append(title, sub, help, list, note, bar);
  let waiting = -1, armed = false, timer = 0;
  const bits = () => padBinding(family);
  const save = (b) => {
    padSaved[family] = b;
    try { localStorage.setItem(PAD_STORE, JSON.stringify(padSaved)); } catch (e) { /* not saved */ }
    delete padCache[family];
  };
  const fill = () => {
    list.textContent = '';
    const b = bits();
    for (const [bit, label] of PAD_ROWS) {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;gap:8px;align-items:center;padding:4px 0;border-top:1px solid #33425f';
      const name = document.createElement('span');
      name.style.cssText = 'flex:1';
      name.textContent = label;
      const btn = document.createElement('button');
      btn.style.cssText = 'min-width:150px';
      btn.textContent = waiting === bit ? 'press a button…' : padName(family, b[bit]);
      btn.addEventListener('click', () => { waiting = bit; armed = false; note.textContent = ''; padCapturing = true; fill(); });
      row.append(name, btn);
      list.appendChild(row);
    }
  };
  const close = () => {
    clearInterval(timer);
    padCapturing = false;
    box.remove();
    window.removeEventListener('keydown', onKey, true);
  };
  const onKey = (e) => {
    e.preventDefault();
    e.stopImmediatePropagation();
    if (e.repeat || e.code !== 'Escape') return;
    if (waiting >= 0) { waiting = -1; padCapturing = false; note.textContent = ''; fill(); } else close();
  };
  window.addEventListener('keydown', onKey, true);
  timer = setInterval(() => {
    if (waiting < 0) return;
    const g = padFirst();
    if (!g) return;
    let hit = -1, any = false;
    for (let i = 0; i < Math.min(g.buttons.length, 16); i++) {
      const down = g.buttons[i].pressed || g.buttons[i].value > 0.5;
      if (down) { any = true; if (hit < 0) hit = i; }
    }
    if (!armed) { if (!any) armed = true; return; }
    if (hit < 0) return;
    const b = bits();
    let freed = '';
    for (const [bit, label] of PAD_ROWS) if (bit !== waiting && b[bit] === hit) { b[bit] = -1; freed = label; }
    b[waiting] = hit;
    note.textContent = freed ? padName(family, hit) + ' was used by ' + freed + ', which is now not set.' : '';
    waiting = -1;
    padCapturing = false;
    save(b);
    fill();
  }, 40);
  reset.addEventListener('click', () => {
    delete padSaved[family];
    try { localStorage.setItem(PAD_STORE, JSON.stringify(padSaved)); } catch (e) { /* not saved */ }
    delete padCache[family];
    waiting = -1; padCapturing = false; note.textContent = 'Defaults restored.';
    fill();
  });
  swap.addEventListener('click', () => { close(); keyShowKeyboard(); });
  shut.addEventListener('click', close);
  box.addEventListener('click', (e) => { if (e.target === box) close(); });
  fill();
  document.body.appendChild(box);
}
"""

PL_OLD = """  if (gamepad) {
    for (const [index, bit] of padButtons) {
"""
PL_NEW = """  if (gamepad && !padCapturing) {
    for (const [index, bit] of padEntries(gamepad)) {
"""

KS_OLD = "function keyShow() {\n"
KS_NEW = "function keyShowKeyboard() {\n"
CL_OLD = "document.getElementById('keys').addEventListener('click', (e) => { e.target.blur(); keyShow(); });"
CL_NEW = "document.getElementById('keys').addEventListener('click', (e) => { e.target.blur(); padShow(); });"
BAR_OLD = "  bar.append(reset, shut);\n  card.append(title, help, list, bar);\n"
BAR_NEW = """  bar.append(reset, shut);
  if (typeof padFirst === 'function' && padFirst()) {
    const toPad = document.createElement('button');
    toPad.textContent = 'Controller';
    toPad.addEventListener('click', () => { close(); padShow(); });
    bar.insertBefore(toPad, shut);
  }
  card.append(title, help, list, bar);
"""
for o in [PB_OLD, PL_OLD, KS_OLD, CL_OLD, BAR_OLD]:
    if s.count(o) != 1:
        print("PATCH NOT APPLIED: web/shell.html does not look like the expected source (run ps2web_keyremap_patch.py first)")
        raise SystemExit(1)
s = (s.replace(PB_OLD, PB_NEW, 1).replace(PL_OLD, PL_NEW, 1).replace(KS_OLD, KS_NEW, 1)
      .replace(CL_OLD, CL_NEW, 1).replace(BAR_OLD, BAR_NEW, 1))
open(p, 'w').write(s)
print("patched (controller panel with PlayStation, Xbox and Nintendo button names)")
