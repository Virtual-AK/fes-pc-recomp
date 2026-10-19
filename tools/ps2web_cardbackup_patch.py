"""Memory card backups for the browser build. Every time the memory card changes (an in-game save), and once when the page
starts, the page keeps a compressed copy in the browser's storage (the last 10 different versions). A new "Backups" button in
the bar lists them with Restore and Download, so an overwritten save can be brought back. Restoring first backs up the card
that is being replaced. Patches web/shell.html. The copies live in the same browser storage as the card itself, so use
"Export card" or Download for a copy outside the browser.
Usage (in the ps2-web-recomp folder): python3 ps2web_cardbackup_patch.py [web/shell.html]
Safe to run twice. Rebuild afterwards: scripts/build_web.sh p3fes
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'web/shell.html'
s = open(p).read()
if 'ps2-card-backups' in s:
    print("already patched"); raise SystemExit
BUTTON_OLD = '  <button id="import-card" type="button" title="Put a .ps2 memory card file in slot 1">Import card</button>\n'
BUTTON_NEW = BUTTON_OLD + '  <button id="backups" type="button" title="Earlier versions of the memory card kept in this browser">Backups</button>\n'
STORE_OLD = "        if (err) console.warn('memory card: could not write browser storage', err);\n"
STORE_NEW = STORE_OLD + "        else backupCard('game save');\n"
INIT_OLD = "  onRuntimeInitialized: () => {\n"
INIT_NEW = INIT_OLD + "    if (!Module.noCard) setTimeout(() => backupCard('page start'), 1500);\n"
BLOCK_ANCHOR = "const statsEl = document.getElementById('stats');\n"
BLOCK = r'''// ps2-card-backups: keep the last versions of the memory card in browser storage
const BK_DB = 'ps2-card-backups', BK_STORE = 'backups', BK_KEEP = 10;
function bkOpen() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(BK_DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(BK_STORE, { keyPath: 'id' });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
function bkRun(db, mode, fn) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(BK_STORE, mode);
    const req = fn(tx.objectStore(BK_STORE));
    tx.oncomplete = () => resolve(req && req.result);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}
async function bkAll(db) {
  const all = (await bkRun(db, 'readonly', (store) => store.getAll())) || [];
  return all.sort((a, b) => b.id - a.id);
}
async function bkPack(data) {
  if (typeof CompressionStream === 'undefined') return { enc: 'raw', bytes: data };
  const stream = new Blob([data]).stream().pipeThrough(new CompressionStream('gzip'));
  return { enc: 'gzip', bytes: new Uint8Array(await new Response(stream).arrayBuffer()) };
}
async function bkUnpack(entry) {
  if (entry.enc !== 'gzip') return entry.bytes;
  const stream = new Blob([entry.bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}
async function bkHash(data) {
  try {
    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', data));
    return Array.from(digest, (b) => b.toString(16).padStart(2, '0')).join('');
  } catch (e) {
    let h = 2166136261;
    for (let i = 0; i < data.length; i += 7) h = Math.imul(h ^ data[i], 16777619);
    return 'f' + (h >>> 0).toString(16) + '-' + data.length;
  }
}
async function bkDoBackup(reason) {
  let data = null;
  try { data = FS.readFile(CARD_FILE); } catch (e) {}
  if (!data || data.length !== CARD_BYTES) return;
  if (new TextDecoder().decode(data.subarray(0, 28)) !== 'Sony PS2 Memory Card Format ') return;
  const hash = await bkHash(data);
  const db = await bkOpen();
  const all = await bkAll(db);
  if (all.length && all[0].hash === hash) return;
  const packed = await bkPack(data);
  let id = Date.now();
  if (all.length && id <= all[0].id) id = all[0].id + 1;
  await bkRun(db, 'readwrite', (store) => store.put({ id, hash, reason, size: data.length, enc: packed.enc, bytes: packed.bytes }));
  for (const old of all.slice(BK_KEEP - 1)) await bkRun(db, 'readwrite', (store) => store.delete(old.id));
}
let bkChain = Promise.resolve();
function backupCard(reason) {
  bkChain = bkChain.then(() => bkDoBackup(reason)).catch((e) => console.warn('memory card backup failed', e));
  return bkChain;
}
const bkReasons = { 'game save': 'game save', 'page start': 'page start', 'before restore': 'before a restore', 'before import': 'before an import' };
async function bkShow() {
  const old = document.getElementById('bk-panel');
  if (old) old.remove();
  const box = document.createElement('div');
  box.id = 'bk-panel';
  box.style.cssText = 'position:fixed;inset:0;z-index:50;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center';
  const card = document.createElement('div');
  card.style.cssText = 'background:#1b2438;color:#fff;padding:16px 20px;border-radius:8px;max-width:520px;width:92%;max-height:80vh;overflow:auto;font:14px system-ui,sans-serif';
  box.appendChild(card);
  const close = () => { box.remove(); document.removeEventListener('keydown', onKey); };
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  document.addEventListener('keydown', onKey);
  box.addEventListener('click', (e) => { if (e.target === box) close(); });
  const title = document.createElement('div');
  title.textContent = 'Memory card backups';
  title.style.cssText = 'font-size:16px;font-weight:600;margin-bottom:4px';
  card.appendChild(title);
  const help = document.createElement('div');
  help.textContent = 'The last ' + BK_KEEP + ' different versions of the card, kept in this browser. Use Download to keep a copy outside it.';
  help.style.cssText = 'opacity:.75;margin-bottom:10px';
  card.appendChild(help);
  const list = document.createElement('div');
  card.appendChild(list);
  const bar = document.createElement('div');
  bar.style.cssText = 'display:flex;gap:8px;margin-top:12px';
  const now = document.createElement('button');
  now.textContent = 'Back up now';
  const shut = document.createElement('button');
  shut.textContent = 'Close';
  shut.addEventListener('click', close);
  bar.append(now, shut);
  card.appendChild(bar);
  document.body.appendChild(box);
  async function fill() {
    list.textContent = '';
    let all = [];
    try { all = await bkAll(await bkOpen()); } catch (e) { list.textContent = 'Browser storage is not available.'; return; }
    if (!all.length) { list.textContent = 'No backups yet. One is made each time the game saves.'; return; }
    for (const entry of all) {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;gap:8px;align-items:center;padding:6px 0;border-top:1px solid #33425f';
      const label = document.createElement('span');
      label.style.cssText = 'flex:1';
      label.textContent = new Date(entry.id).toLocaleString() + ' (' + (bkReasons[entry.reason] || entry.reason) + ')';
      const restore = document.createElement('button');
      restore.textContent = 'Restore';
      restore.addEventListener('click', async () => {
        if (!confirm('Replace the memory card in slot 1 with this backup? The current card is backed up first, and the page reloads to use it.')) return;
        try {
          const data = await bkUnpack(entry);
          await backupCard('before restore');
          FS.writeFile(CARD_FILE, data);
        } catch (e) {
          note('Restore failed: ' + e.message);
          return;
        }
        storeCard(() => location.reload());
      });
      const save = document.createElement('button');
      save.textContent = 'Download';
      save.addEventListener('click', async () => {
        const data = await bkUnpack(entry);
        const link = document.createElement('a');
        link.href = URL.createObjectURL(new Blob([data], { type: 'application/octet-stream' }));
        link.download = 'Mcd001-' + new Date(entry.id).toISOString().replace(/[:.]/g, '-') + '.ps2';
        link.click();
        setTimeout(() => URL.revokeObjectURL(link.href), 10000);
      });
      row.append(label, restore, save);
      list.appendChild(row);
    }
  }
  now.addEventListener('click', async () => { await backupCard('game save'); await fill(); note('Backup checked'); });
  fill();
}
document.getElementById('backups').addEventListener('click', bkShow);
'''
IMPORT_OLD = "  if (!confirm('Replace the memory card in slot 1 with ' + file.name + '? The page reloads to use it.')) return;\n  try {\n    FS.writeFile(CARD_FILE, data);"
IMPORT_NEW = "  if (!confirm('Replace the memory card in slot 1 with ' + file.name + '? The page reloads to use it.')) return;\n  await backupCard('before import');\n  try {\n    FS.writeFile(CARD_FILE, data);"
for o in [BUTTON_OLD, STORE_OLD, INIT_OLD, BLOCK_ANCHOR, IMPORT_OLD]:
    if s.count(o) != 1:
        print("PATCH NOT APPLIED: shell.html does not look like the expected source"); raise SystemExit(1)
s = s.replace(BUTTON_OLD, BUTTON_NEW, 1).replace(STORE_OLD, STORE_NEW, 1).replace(INIT_OLD, INIT_NEW, 1)
s = s.replace(IMPORT_OLD, IMPORT_NEW, 1).replace(BLOCK_ANCHOR, BLOCK + BLOCK_ANCHOR, 1)
open(p, 'w').write(s)
print("patched (Backups button keeps the last 10 versions of the memory card)")
