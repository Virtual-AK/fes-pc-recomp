"""Browser key remapping. Patches web/shell.html (run ps2web_controls_patch.py first).
Adds a Keys button next to Backups. In the panel, click a row, press the new key, and it is saved in this browser
(local storage) and used at once. Reset puts the PCSX2-style defaults back. Esc closes the panel, and ` stays
fullscreen. If you give a key that another row uses, that other row becomes unbound.
Usage (in the ps2-web-recomp folder): python3 ps2web_keyremap_patch.py [web/shell.html]
Safe to run twice. Rebuild afterwards (scripts/build_web.sh p3fes)
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'web/shell.html'
s = open(p).read()
if 'ps2-key-remap' in s:
    print("already patched"); raise SystemExit

BTN_OLD = '  <button id="backups" type="button" title="Earlier versions of the memory card kept in this browser">Backups</button>\n'
BTN_NEW = BTN_OLD + '  <button id="keys" type="button" title="Change the keyboard keys">Keys</button>\n'

K_OLD = """const keyMap = { ArrowUp: 4, ArrowRight: 5, ArrowDown: 6, ArrowLeft: 7, KeyI: 12, KeyL: 13, KeyK: 14, KeyJ: 15,
                 KeyQ: 10, KeyE: 11, Digit1: 8, Digit3: 9, Digit2: 1, Digit4: 2, Enter: 3, Backspace: 0 };
const stickKeys = new Set(['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyT', 'KeyF', 'KeyG', 'KeyH']);
"""
K_NEW = """// ps2-key-remap: rebindable keyboard layout, saved in this browser
// each row: id, name in the panel, default key, button bit (or the stick axis and value)
const KEY_ROWS = [
  ['up', 'D-pad up', 'ArrowUp', 4], ['down', 'D-pad down', 'ArrowDown', 6],
  ['left', 'D-pad left', 'ArrowLeft', 7], ['right', 'D-pad right', 'ArrowRight', 5],
  ['cross', 'Cross (confirm)', 'KeyK', 14], ['circle', 'Circle (cancel)', 'KeyL', 13],
  ['square', 'Square', 'KeyJ', 15], ['triangle', 'Triangle', 'KeyI', 12],
  ['l1', 'L1', 'KeyQ', 10], ['r1', 'R1', 'KeyE', 11], ['l2', 'L2', 'Digit1', 8], ['r2', 'R2', 'Digit3', 9],
  ['l3', 'L3', 'Digit2', 1], ['r3', 'R3', 'Digit4', 2], ['start', 'Start', 'Enter', 3], ['select', 'Select', 'Backspace', 0],
  ['lup', 'Left stick up', 'KeyW', ['ly', 0]], ['ldown', 'Left stick down', 'KeyS', ['ly', 255]],
  ['lleft', 'Left stick left', 'KeyA', ['lx', 0]], ['lright', 'Left stick right', 'KeyD', ['lx', 255]],
  ['rup', 'Right stick up', 'KeyT', ['ry', 0]], ['rdown', 'Right stick down', 'KeyG', ['ry', 255]],
  ['rleft', 'Right stick left', 'KeyF', ['rx', 0]], ['rright', 'Right stick right', 'KeyH', ['rx', 255]],
];
const KEY_STORE = 'ps2-keymap';
const KEY_RESERVED = new Set(['Backquote', 'Escape']);
let keyBinds = {};
function keyLoad() {
  keyBinds = {};
  for (const r of KEY_ROWS) keyBinds[r[0]] = r[2];
  try {
    const saved = JSON.parse(localStorage.getItem(KEY_STORE) || '{}');
    for (const r of KEY_ROWS) if (typeof saved[r[0]] === 'string') keyBinds[r[0]] = saved[r[0]];
  } catch (e) { /* storage not available: defaults */ }
}
function keySave() {
  try { localStorage.setItem(KEY_STORE, JSON.stringify(keyBinds)); } catch (e) { /* not saved */ }
}
let keyMap = {}, stickMap = {};
function keyRebuild() {
  keyMap = {}; stickMap = {};
  for (const r of KEY_ROWS) {
    const code = keyBinds[r[0]];
    if (!code) continue;
    if (typeof r[3] === 'number') keyMap[code] = r[3]; else stickMap[code] = r[3];
  }
  keys.clear();
}
keyLoad();
keyRebuild();
function keyLabel(code) {
  if (!code) return 'not set';
  const names = { ArrowUp: 'Up arrow', ArrowDown: 'Down arrow', ArrowLeft: 'Left arrow', ArrowRight: 'Right arrow',
                  Enter: 'Enter', Backspace: 'Backspace', Space: 'Space', ShiftLeft: 'Left Shift', ShiftRight: 'Right Shift',
                  ControlLeft: 'Left Ctrl', ControlRight: 'Right Ctrl', AltLeft: 'Left Alt', AltRight: 'Right Alt', Tab: 'Tab' };
  if (names[code]) return names[code];
  if (code.startsWith('Key')) return code.slice(3);
  if (code.startsWith('Digit')) return code.slice(5);
  if (code.startsWith('Numpad')) return 'Numpad ' + code.slice(6);
  return code;
}
function keyShow() {
  if (document.getElementById('key-panel')) return;
  keys.clear();
  const box = document.createElement('div');
  box.id = 'key-panel';
  box.style.cssText = 'position:fixed;inset:0;z-index:50;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center';
  const card = document.createElement('div');
  card.style.cssText = 'background:#1b2438;color:#fff;padding:16px 20px;border-radius:8px;max-width:520px;width:92%;max-height:85vh;overflow:auto;font:14px system-ui,sans-serif';
  box.appendChild(card);
  const title = document.createElement('div');
  title.textContent = 'Keyboard keys';
  title.style.cssText = 'font-size:16px;font-weight:600;margin-bottom:4px';
  const help = document.createElement('div');
  help.textContent = 'Click a row, then press the new key. Esc cancels. The ` key is always fullscreen. Saved in this browser.';
  help.style.cssText = 'opacity:.75;margin-bottom:10px';
  const list = document.createElement('div');
  const bar = document.createElement('div');
  bar.style.cssText = 'display:flex;gap:8px;margin-top:12px';
  const reset = document.createElement('button');
  reset.textContent = 'Reset to defaults';
  const shut = document.createElement('button');
  shut.textContent = 'Close';
  bar.append(reset, shut);
  card.append(title, help, list, bar);
  let waiting = null;
  const note = document.createElement('div');
  note.style.cssText = 'min-height:18px;margin-top:8px;color:#ffd479';
  card.insertBefore(note, bar);
  const fill = () => {
    list.textContent = '';
    for (const r of KEY_ROWS) {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;gap:8px;align-items:center;padding:4px 0;border-top:1px solid #33425f';
      const label = document.createElement('span');
      label.style.cssText = 'flex:1';
      label.textContent = r[1];
      const b = document.createElement('button');
      b.style.cssText = 'min-width:130px';
      b.textContent = waiting === r[0] ? 'press a key…' : keyLabel(keyBinds[r[0]]);
      b.addEventListener('click', () => { waiting = r[0]; note.textContent = ''; fill(); });
      row.append(label, b);
      list.appendChild(row);
    }
  };
  const close = () => { box.remove(); window.removeEventListener('keydown', onKey, true); };
  const onKey = (e) => {
    e.preventDefault();
    e.stopImmediatePropagation();
    if (e.repeat) return;
    if (e.code === 'Escape') {
      if (waiting) { waiting = null; note.textContent = ''; fill(); } else close();
      return;
    }
    if (!waiting) return;
    if (KEY_RESERVED.has(e.code)) { note.textContent = keyLabel(e.code) + ' is reserved. Pick another key.'; return; }
    let freed = '';
    for (const r of KEY_ROWS) if (r[0] !== waiting && keyBinds[r[0]] === e.code) { keyBinds[r[0]] = ''; freed = r[1]; }
    keyBinds[waiting] = e.code;
    note.textContent = freed ? keyLabel(e.code) + ' was used by ' + freed + ', which is now not set.' : '';
    waiting = null;
    keySave();
    keyRebuild();
    fill();
  };
  window.addEventListener('keydown', onKey, true);
  reset.addEventListener('click', () => {
    for (const r of KEY_ROWS) keyBinds[r[0]] = r[2];
    waiting = null; note.textContent = 'Defaults restored.';
    keySave(); keyRebuild(); fill();
  });
  shut.addEventListener('click', close);
  box.addEventListener('click', (e) => { if (e.target === box) close(); });
  fill();
  document.body.appendChild(box);
}
document.getElementById('keys').addEventListener('click', (e) => { e.target.blur(); keyShow(); });
"""

H_OLD = "window.addEventListener('keydown', (e) => { if (e.code in keyMap || stickKeys.has(e.code)) { keys.add(e.code); e.preventDefault(); } });"
H_NEW = "window.addEventListener('keydown', (e) => { if (e.code in keyMap || e.code in stickMap) { keys.add(e.code); e.preventDefault(); } });"

S_OLD = """    if (keys.has('KeyA')) lx = 0;
    if (keys.has('KeyD')) lx = 255;
    if (keys.has('KeyW')) ly = 0;
    if (keys.has('KeyS')) ly = 255;
    if (keys.has('KeyF')) rx = 0;
    if (keys.has('KeyH')) rx = 255;
    if (keys.has('KeyT')) ry = 0;
    if (keys.has('KeyG')) ry = 255;
"""
S_NEW = """    for (const k of keys) {
      const st = stickMap[k];
      if (!st) continue;
      if (st[0] === 'lx') lx = st[1]; else if (st[0] === 'ly') ly = st[1];
      else if (st[0] === 'rx') rx = st[1]; else ry = st[1];
    }
"""
for o in [BTN_OLD, K_OLD, H_OLD, S_OLD]:
    if s.count(o) != 1:
        print("PATCH NOT APPLIED: web/shell.html does not look like the expected source (run ps2web_cardbackup_patch.py and ps2web_controls_patch.py first)")
        raise SystemExit(1)
s = s.replace(BTN_OLD, BTN_NEW, 1).replace(K_OLD, K_NEW, 1).replace(H_OLD, H_NEW, 1).replace(S_OLD, S_NEW, 1)
open(p, 'w').write(s)
print("patched (Keys button: click a row, press a key)")
