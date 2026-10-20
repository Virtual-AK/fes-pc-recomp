"""Share the memory card between the browser game and the launcher (and so the PC window).

The launcher keeps one card file on disk (C:\\p3fes\\saves\\Mcd001.ps2) and serves it at http://127.0.0.1:8630/card.
This patch makes web/shell.html:
  - at start, compare the browser's card with the disk card: copy the disk card in if the browser has none, copy the
    browser card out if the disk has none, and ask which to keep if they differ (the one not kept is backed up);
  - after every in-game save, send the card to the disk file.
If the launcher is not running nothing changes: the browser keeps using its own storage. Add ?cardsync=off to the page
address to turn it off, or ?cardsync=PORT if the launcher uses another port.
Usage (in the ps2-web-recomp folder, after ps2web_cardbackup_patch.py): python3 ps2web_cardsync_patch.py [web/shell.html]
Then rebuild the browser game: scripts/build_web.sh p3fes
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'web/shell.html'
s = open(p).read()
if 'ps2-card-sync' in s:
    print("already patched"); raise SystemExit

ANCHOR = "const importInput = document.getElementById('import-file');\n"
SYNC_OLD = """        FS.syncfs(true, (err) => {
          if (err) console.warn('memory card: could not read browser storage', err);
          Module.removeRunDependency('card');
        });
"""
SYNC_NEW = """        FS.syncfs(true, (err) => {
          if (err) console.warn('memory card: could not read browser storage', err);
          syncDiskCardAtStart().catch((e) => console.warn('memory card: disk sync failed', e)).finally(() => Module.removeRunDependency('card'));
        });
"""
SAVED_OLD = "  ps2CardSaved: () => storeCard(),\n"
SAVED_NEW = "  ps2CardSaved: () => { storeCard(); pushDiskCard(); },\n"
for name, old in (('anchor', ANCHOR), ('start', SYNC_OLD), ('saved', SAVED_OLD)):
    if s.count(old) != 1:
        print("PATCH NOT APPLIED: expected text for '%s' not found exactly once (shell.html changed?)" % name)
        raise SystemExit(1)

BLOCK = r'''// ps2-card-sync: share the memory card with the launcher's file on disk (see tools/ps2web_cardsync_patch.py)
const CS_PORT = new URLSearchParams(location.search).get('cardsync') || '8630';
const CS_URL = CS_PORT === 'off' ? '' : 'http://127.0.0.1:' + CS_PORT + '/card';
let csDown = false;
function csValid(d) { return !!d && d.length === CARD_BYTES && new TextDecoder().decode(d.subarray(0, 28)) === 'Sony PS2 Memory Card Format '; }
function csLocal() { try { const d = FS.readFile(CARD_FILE); return csValid(d) ? d : null; } catch (e) { return null; } }
function csSame(a, b) { if (a.length !== b.length) return false; for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false; return true; }
async function csFetch() {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 2500);
  try {
    const r = await fetch(CS_URL, { cache: 'no-store', signal: ctl.signal });
    if (r.status !== 200) return { status: r.status };
    return { status: 200, data: new Uint8Array(await r.arrayBuffer()) };
  } catch (e) {
    return { status: 0 };
  } finally {
    clearTimeout(t);
  }
}
async function pushDiskCard() {
  if (!CS_URL || csDown) return;
  const d = csLocal();
  if (!d) return;
  try {
    const r = await fetch(CS_URL, { method: 'PUT', body: d, headers: { 'Content-Type': 'application/octet-stream' } });
    if (r.status === 409) note('Card not saved to the launcher folder: the PC window is running. Close it first.');
    else if (!r.ok) note('Card not saved to the launcher folder (' + r.status + ')');
  } catch (e) { /* launcher not running: the browser keeps its own copy */ }
}
async function syncDiskCardAtStart() {
  if (!CS_URL) return;
  const disk = await csFetch();
  if (disk.status === 0) { csDown = true; return; }
  const local = csLocal();
  const store = () => new Promise((res) => FS.syncfs(false, () => res()));
  if (disk.status === 200 && csValid(disk.data)) {
    if (!local) { FS.writeFile(CARD_FILE, disk.data); await store(); console.log('memory card: loaded from the launcher folder'); return; }
    if (csSame(local, disk.data)) return;
    const useDisk = confirm('The memory card in the launcher folder (shared with the PC window) is different from the one in this browser.\n\n' +
      'OK = use the launcher folder card. This browser\'s card is kept under Backups.\n' +
      'Cancel = keep this browser\'s card and copy it to the launcher folder. The old file there is kept as a backup.');
    if (useDisk) {
      if (typeof backupCard === 'function') { backupCard('before launcher card'); if (typeof bkChain !== 'undefined') await bkChain; }
      FS.writeFile(CARD_FILE, disk.data);
      await store();
    } else {
      await pushDiskCard();
    }
    return;
  }
  if (disk.status === 404 && local) await pushDiskCard();
}
'''
s = s.replace(ANCHOR, BLOCK + ANCHOR, 1).replace(SYNC_OLD, SYNC_NEW, 1).replace(SAVED_OLD, SAVED_NEW, 1)
open(p, 'w').write(s)
print("patched (memory card shared with the launcher folder)")
