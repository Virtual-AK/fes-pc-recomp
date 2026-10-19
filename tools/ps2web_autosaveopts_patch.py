"""Autosave settings for the browser build. Patches web/shell.html (run ps2web_autosave_patch.py first).
Adds a settings block at the top of the Autosave panel:
- Save automatically: Off, every minute, 2, 5, 10, 15 or 30 minutes (default every 2 minutes, as before).
- Also after each in-game save: on or off (default on).
- Keep the newest 1, 3, 5 or 10 saves of each kind (default 3). Lowering it deletes the extra saves at once.
Save now always works, even with automatic saving off. The choices are kept in this browser (local storage).
Usage (in the ps2-web-recomp folder): python3 ps2web_autosaveopts_patch.py [web/shell.html]
Safe to run twice. Rebuild afterwards (scripts/build_web.sh p3fes, or p3fesmod)
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'web/shell.html'
s = open(p).read()
if 'ps2-autosave-options' in s:
    print("already patched"); raise SystemExit

C_OLD = "const AS_DB = 'ps2-autosave', AS_STORE = 'states', AS_EVERY = 120000, AS_KEEP = 3;\n"
C_NEW = r"""const AS_DB = 'ps2-autosave', AS_STORE = 'states';
// ps2-autosave-options: how often to save, whether to save after a game save, and how many saves to keep
const AS_CHOICES = [[0, 'Off'], [60000, 'Every minute'], [120000, 'Every 2 minutes'], [300000, 'Every 5 minutes'],
                    [600000, 'Every 10 minutes'], [900000, 'Every 15 minutes'], [1800000, 'Every 30 minutes']];
const AS_KEEPS = [1, 3, 5, 10];
const AS_OPTS_STORE = 'ps2-autosave-options';
const asOpts = { every: 120000, afterSave: true, keep: 3 };
try {
  const saved = JSON.parse(localStorage.getItem(AS_OPTS_STORE) || '{}') || {};
  if (AS_CHOICES.some((c) => c[0] === saved.every)) asOpts.every = saved.every;
  if (typeof saved.afterSave === 'boolean') asOpts.afterSave = saved.afterSave;
  if (AS_KEEPS.includes(saved.keep)) asOpts.keep = saved.keep;
} catch (e) { /* storage not available: defaults */ }
function asStoreOpts() {
  try { localStorage.setItem(AS_OPTS_STORE, JSON.stringify(asOpts)); } catch (e) { /* not saved */ }
}
"""

K_OLD = "    for (const old of same.slice(AS_KEEP - 1)) await asRun(db, 'readwrite', (store) => store.delete(old.id));\n"
K_NEW = "    for (const old of same.slice(asOpts.keep - 1)) await asRun(db, 'readwrite', (store) => store.delete(old.id));\n"

S_OLD = "function asSoon() {\n  clearTimeout(asSoonTimer);\n"
S_NEW = "function asSoon() {\n  if (!asOpts.afterSave) return;\n  clearTimeout(asSoonTimer);\n"

T_OLD = "setInterval(() => asSave('timer'), AS_EVERY);\n"
T_NEW = r"""let asTimer = 0;
function asSchedule() {
  clearInterval(asTimer);
  asTimer = asOpts.every ? setInterval(() => asSave('timer'), asOpts.every) : 0;
}
asSchedule();
async function asPrune() {
  try {
    const db = await asOpen();
    const all = (await asRun(db, 'readonly', (store) => store.getAll())).filter((e) => e.key === asKey).sort((a, b) => b.id - a.id);
    const seen = {};
    for (const e of all) {
      seen[e.reason] = (seen[e.reason] || 0) + 1;
      if (seen[e.reason] > asOpts.keep) await asRun(db, 'readwrite', (store) => store.delete(e.id));
    }
    db.close();
  } catch (e) { /* nothing to prune */ }
}
"""

U_OLD = "  card.append(title, help, list, bar);\n  document.body.appendChild(box);\n  async function fill() {\n"
U_NEW = r"""  card.append(title, help, list, bar);
  const opts = document.createElement('div');
  opts.style.cssText = 'display:grid;grid-template-columns:1fr auto;gap:6px 12px;align-items:center;margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid #33425f';
  const addRow = (text, control) => {
    const label = document.createElement('span');
    label.textContent = text;
    opts.append(label, control);
  };
  const every = document.createElement('select');
  for (const [ms, text] of AS_CHOICES) {
    const o = document.createElement('option');
    o.value = String(ms);
    o.textContent = text;
    every.appendChild(o);
  }
  every.value = String(asOpts.every);
  const after = document.createElement('input');
  after.type = 'checkbox';
  after.checked = asOpts.afterSave;
  const keep = document.createElement('select');
  for (const n of AS_KEEPS) {
    const o = document.createElement('option');
    o.value = String(n);
    o.textContent = String(n);
    keep.appendChild(o);
  }
  keep.value = String(asOpts.keep);
  addRow('Save automatically', every);
  addRow('Also save after each in-game save', after);
  addRow('Keep the newest of each kind', keep);
  const state = document.createElement('div');
  state.style.cssText = 'grid-column:1 / -1;opacity:.75';
  const showState = () => {
    state.textContent = asOpts.every || asOpts.afterSave ? '' : 'Automatic saving is off. Save now still works.';
  };
  showState();
  opts.appendChild(state);
  every.addEventListener('change', () => { asOpts.every = Number(every.value); asStoreOpts(); asSchedule(); showState(); });
  after.addEventListener('change', () => { asOpts.afterSave = after.checked; asStoreOpts(); if (!asOpts.afterSave) clearTimeout(asSoonTimer); showState(); });
  keep.addEventListener('change', async () => { asOpts.keep = Number(keep.value); asStoreOpts(); await asPrune(); fill(); });
  card.insertBefore(opts, list);
  document.body.appendChild(box);
  async function fill() {
"""

H_OLD = "help.textContent = 'The whole game is saved every 2 minutes and after each in-game save, in this browser. Resume reloads the page and offers that save on the start screen. The memory card is not part of an autosave.';"
H_NEW = "help.textContent = 'The whole game is saved in this browser, on the schedule below. Resume reloads the page and offers that save on the start screen. The memory card is not part of an autosave.';"

for o in [C_OLD, K_OLD, S_OLD, T_OLD, U_OLD, H_OLD]:
    if s.count(o) != 1:
        print("PATCH NOT APPLIED: web/shell.html does not look like the expected source (run ps2web_autosave_patch.py first)")
        raise SystemExit(1)
s = (s.replace(C_OLD, C_NEW, 1).replace(K_OLD, K_NEW, 1).replace(S_OLD, S_NEW, 1).replace(T_OLD, T_NEW, 1)
      .replace(U_OLD, U_NEW, 1).replace(H_OLD, H_NEW, 1))
open(p, 'w').write(s)
print("patched (autosave settings: interval, after a game save, how many to keep)")
