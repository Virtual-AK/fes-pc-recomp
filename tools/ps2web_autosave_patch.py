"""Full-state autosave for the browser build. Patches host/web.cpp and web/shell.html
(run ps2web_cardbackup_patch.py first, the autosave reuses its storage helpers).
What it does:
- Every 2 minutes while the game runs, and 8 seconds after each in-game save, the whole machine state is saved in this
  browser (IndexedDB, compressed). The newest 3 of each kind are kept: timer, game save, manual.
- When the page opens and an autosave exists for this build, the start screen offers "Resume autosave from <time>"
  next to the normal start button. Resume puts the game back exactly where it was, in the middle of a battle or a walk.
- An Autosave button in the bottom bar lists the saved states with Resume (reloads the page and offers that one),
  Delete, and Save now.
- The memory card is not part of the state, so a resumed game uses the card as it is now. The card keeps its own
  backups (Backups button) and the autosave never changes it.
- A state only fits the build that made it. They are stored per build (the sizes of ps2web.wasm, .js and .data), so a
  rebuilt game does not offer old states. If a resume fails, that state is deleted and the page asks for a reload.
Usage (in the ps2-web-recomp folder): python3 ps2web_autosave_patch.py [host/web.cpp] [web/shell.html]
Safe to run twice. Rebuild afterwards (scripts/build_web.sh p3fes, or p3fesmod)
"""
import sys
cpp_path = sys.argv[1] if len(sys.argv) > 1 else 'host/web.cpp'
html_path = sys.argv[2] if len(sys.argv) > 2 else 'web/shell.html'
cpp = open(cpp_path).read()
html = open(html_path).read()
done_cpp = 'ps2web_save_state' in cpp
done_html = 'ps2-autosave' in html
if done_cpp and done_html:
    print("already patched"); raise SystemExit

# ---- host/web.cpp -----------------------------------------------------------------------------------------------
C_LOAD_OLD = """    if (g_state_url) {
        const double size = ps2web_url_size(g_state_url);
"""
C_LOAD_NEW = """    if (std::FILE *resume = std::fopen("/resume.state", "rb")) {
        std::fclose(resume);
        const bool resumed = ps2::load_state(std::string("/resume.state"));
        std::remove("/resume.state");
        if (!resumed) {
            std::fprintf(stderr, "[web] cannot load the autosave\\n");
            MAIN_THREAD_ASYNC_EM_ASM({ if (Module.ps2ResumeFailed) Module.ps2ResumeFailed(); });
            return nullptr;
        }
    } else if (g_state_url) {
        const double size = ps2web_url_size(g_state_url);
"""
C_EXPORT_OLD = 'extern "C" EMSCRIPTEN_KEEPALIVE int ps2web_rumble(int pad) { return ps2::pad_rumble(pad); }\n'
C_EXPORT_NEW = C_EXPORT_OLD + '\nextern "C" EMSCRIPTEN_KEEPALIVE void ps2web_save_state() { ps2::request_state_save(); }\n'

# ---- web/shell.html ---------------------------------------------------------------------------------------------
H_BTN_OLD = '  <button id="backups" type="button" title="Earlier versions of the memory card kept in this browser">Backups</button>\n'
H_BTN_NEW = H_BTN_OLD + '  <button id="autosave" type="button" title="Automatic saves of the whole game, to resume exactly where you were">Autosave</button>\n'

H_ANCHOR = "document.getElementById('backups').addEventListener('click', bkShow);\n"
H_JS = r"""// ps2-autosave: save the whole machine state every 2 minutes and let Start resume from it
const AS_DB = 'ps2-autosave', AS_STORE = 'states', AS_EVERY = 120000, AS_KEEP = 3;
let asKey = 'default', asBusy = false, asSoonTimer = 0;
const asSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
function asOpen() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(AS_DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(AS_STORE, { keyPath: 'id' });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
function asRun(db, mode, fn) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(AS_STORE, mode);
    const req = fn(tx.objectStore(AS_STORE));
    tx.oncomplete = () => resolve(req && req.result);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}
async function asAll() {
  const db = await asOpen();
  const all = (await asRun(db, 'readonly', (store) => store.getAll())) || [];
  db.close();
  return all.filter((e) => e.key === asKey).sort((a, b) => b.id - a.id);
}
async function asBuildKey() {
  const parts = [];
  for (const name of ['ps2web.wasm', 'ps2web.js', 'ps2web.data']) {
    try {
      const r = await fetch(name, { method: 'HEAD', cache: 'no-store' });
      parts.push(r.ok ? (r.headers.get('content-length') || '?') : '-');
    } catch (e) { parts.push('-'); }
  }
  return parts.join('/');
}
function asFiles() {
  try { return FS.readdir('/').filter((f) => /^live_\d+\.state$/.test(f)); } catch (e) { return []; }
}
// a finished state file is long and ends with the 8 bytes 'end' + zeros (the last section tag)
function asComplete(path) {
  try {
    const size = FS.stat(path).size;
    if (size < 1048576) return false;
    const tail = new Uint8Array(8);
    const stream = FS.open(path, 'r');
    FS.read(stream, tail, 0, 8, size - 8);
    FS.close(stream);
    return String.fromCharCode(...tail.subarray(0, 3)) === 'end' && tail.subarray(3).every((b) => b === 0);
  } catch (e) { return false; }
}
async function asSave(reason) {
  if (asBusy || !Module.running || !Module._ps2web_save_state) return false;
  asBusy = true;
  let name = '';
  try {
    const before = new Set(asFiles());
    Module._ps2web_save_state();
    let complete = false;
    for (let i = 0; i < 150 && !complete; i++) {
      await asSleep(200);
      const fresh = asFiles().filter((f) => !before.has(f));
      if (!fresh.length) continue;
      name = fresh[0];
      complete = asComplete('/' + name);
    }
    if (!name || !complete) throw new Error('the game did not finish writing a state');
    const data = FS.readFile('/' + name);
    try { FS.unlink('/' + name); } catch (e) { /* keep going */ }
    name = '';
    const packed = await bkPack(data);
    const db = await asOpen();
    let id = Date.now();
    const all = await asRun(db, 'readonly', (store) => store.getAll());
    for (const e of all) if (e.id >= id) id = e.id + 1;
    await asRun(db, 'readwrite', (store) => store.put({ id, key: asKey, reason, time: Date.now(), size: data.length, enc: packed.enc, bytes: packed.bytes }));
    const same = all.filter((e) => e.key === asKey && e.reason === reason).sort((a, b) => b.id - a.id);
    for (const old of same.slice(AS_KEEP - 1)) await asRun(db, 'readwrite', (store) => store.delete(old.id));
    db.close();
    note('Autosaved');
    return true;
  } catch (e) {
    console.warn('autosave failed', e);
    if (name) { try { FS.unlink('/' + name); } catch (e2) { /* nothing */ } }
    return false;
  } finally {
    asBusy = false;
  }
}
function asSoon() {
  clearTimeout(asSoonTimer);
  asSoonTimer = setTimeout(() => asSave('game save'), 8000);
}
setInterval(() => asSave('timer'), AS_EVERY);
const asReasons = { timer: 'every 2 minutes', 'game save': 'after a game save', manual: 'saved by you' };
async function asOfferResume(start) {
  try {
    asKey = await asBuildKey();
    const all = await asAll();
    if (!all.length) return;
    let entry = all[0];
    try {
      const wanted = Number(sessionStorage.getItem('ps2-resume-id'));
      sessionStorage.removeItem('ps2-resume-id');
      if (wanted) entry = all.find((e) => e.id === wanted) || entry;
    } catch (e) { /* storage not available */ }
    const btn = document.createElement('button');
    btn.id = 'resume';
    btn.textContent = 'Resume autosave from ' + new Date(entry.time).toLocaleString();
    start.textContent = 'Start from the title screen';
    start.parentNode.insertBefore(btn, start);
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      btn.textContent = 'Loading the autosave…';
      try {
        FS.writeFile('/resume.state', await bkUnpack(entry));
        Module.resumeId = entry.id;
      } catch (e) {
        console.warn('autosave could not be read', e);
        btn.textContent = 'This autosave could not be read';
        return;
      }
      start.click();
    });
  } catch (e) {
    console.warn('autosave not available', e);
  }
}
async function asResumeFailed() {
  try {
    const db = await asOpen();
    if (Module.resumeId) await asRun(db, 'readwrite', (store) => store.delete(Module.resumeId));
    db.close();
  } catch (e) { /* nothing */ }
  statusEl.textContent = 'That autosave could not be loaded, so it was deleted. Reload the page to start again.';
}
async function asShow() {
  const old = document.getElementById('as-panel');
  if (old) old.remove();
  const box = document.createElement('div');
  box.id = 'as-panel';
  box.style.cssText = 'position:fixed;inset:0;z-index:50;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center';
  const card = document.createElement('div');
  card.style.cssText = 'background:#1b2438;color:#fff;padding:16px 20px;border-radius:8px;max-width:560px;width:92%;max-height:80vh;overflow:auto;font:14px system-ui,sans-serif';
  box.appendChild(card);
  const close = () => { box.remove(); document.removeEventListener('keydown', onKey); };
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  document.addEventListener('keydown', onKey);
  box.addEventListener('click', (e) => { if (e.target === box) close(); });
  const title = document.createElement('div');
  title.textContent = 'Autosaves';
  title.style.cssText = 'font-size:16px;font-weight:600;margin-bottom:4px';
  const help = document.createElement('div');
  help.textContent = 'The whole game is saved every 2 minutes and after each in-game save, in this browser. Resume reloads the page and offers that save on the start screen. The memory card is not part of an autosave.';
  help.style.cssText = 'opacity:.75;margin-bottom:10px';
  const list = document.createElement('div');
  const bar = document.createElement('div');
  bar.style.cssText = 'display:flex;gap:8px;margin-top:12px';
  const now = document.createElement('button');
  now.textContent = 'Save now';
  const shut = document.createElement('button');
  shut.textContent = 'Close';
  shut.addEventListener('click', close);
  bar.append(now, shut);
  card.append(title, help, list, bar);
  document.body.appendChild(box);
  async function fill() {
    list.textContent = '';
    let all = [];
    try { all = await asAll(); } catch (e) { list.textContent = 'Browser storage is not available.'; return; }
    if (!all.length) { list.textContent = 'No autosaves yet for this version of the game.'; return; }
    for (const entry of all) {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;gap:8px;align-items:center;padding:6px 0;border-top:1px solid #33425f';
      const label = document.createElement('span');
      label.style.cssText = 'flex:1';
      label.textContent = new Date(entry.time).toLocaleString() + ' (' + (asReasons[entry.reason] || entry.reason) + ', ' + (entry.bytes.length / 1048576).toFixed(1) + ' MB)';
      const resume = document.createElement('button');
      resume.textContent = 'Resume';
      resume.addEventListener('click', () => {
        if (!confirm('Reload the page and resume from this autosave? Anything since your last in-game save is only kept if you resume from a newer autosave.')) return;
        try { sessionStorage.setItem('ps2-resume-id', String(entry.id)); } catch (e) { /* newest is offered instead */ }
        location.reload();
      });
      const del = document.createElement('button');
      del.textContent = 'Delete';
      del.addEventListener('click', async () => {
        try {
          const db = await asOpen();
          await asRun(db, 'readwrite', (store) => store.delete(entry.id));
          db.close();
        } catch (e) { note('Could not delete: ' + e.message); }
        fill();
      });
      row.append(label, resume, del);
      list.appendChild(row);
    }
  }
  now.addEventListener('click', async () => {
    now.disabled = true;
    const ok = await asSave('manual');
    now.disabled = false;
    if (!ok) note('Could not save right now');
    fill();
  });
  fill();
}
document.getElementById('autosave').addEventListener('click', asShow);
"""

H_CARD_OLD = "        else backupCard('game save');\n"
H_CARD_NEW = "        else { backupCard('game save'); asSoon(); }\n"
H_INIT_OLD = "    start.disabled = false;\n    start.textContent = 'Start';\n"
H_INIT_NEW = H_INIT_OLD + "    asOfferResume(start);\n"
H_MOD_OLD = "  ps2CardSaved: () => storeCard(),\n"
H_MOD_NEW = H_MOD_OLD + "  ps2ResumeFailed: () => asResumeFailed(),\n"

problems = []
if not done_cpp:
    for o in [C_LOAD_OLD, C_EXPORT_OLD]:
        if cpp.count(o) != 1:
            problems.append(cpp_path)
            break
if not done_html:
    if 'ps2-card-backups' not in html:
        problems.append(html_path + " (run ps2web_cardbackup_patch.py first)")
    else:
        for o in [H_BTN_OLD, H_ANCHOR, H_CARD_OLD, H_INIT_OLD, H_MOD_OLD]:
            if html.count(o) != 1:
                problems.append(html_path)
                break
if problems:
    print("PATCH NOT APPLIED: " + ", ".join(problems) + " does not look like the expected source")
    raise SystemExit(1)
if not done_cpp:
    cpp = cpp.replace(C_LOAD_OLD, C_LOAD_NEW, 1).replace(C_EXPORT_OLD, C_EXPORT_NEW, 1)
    open(cpp_path, 'w').write(cpp)
if not done_html:
    html = (html.replace(H_BTN_OLD, H_BTN_NEW, 1).replace(H_ANCHOR, H_ANCHOR + H_JS, 1).replace(H_CARD_OLD, H_CARD_NEW, 1)
                .replace(H_INIT_OLD, H_INIT_NEW, 1).replace(H_MOD_OLD, H_MOD_NEW, 1))
    open(html_path, 'w').write(html)
print("patched (autosave of the whole game state, Resume on the start screen, Autosave button)")
