"""Share the browser game's autosaves with the launcher (so the launcher's Saves screen can list, resume and delete them,
and Edge and Chrome see the same ones). Patches web/shell.html. Run after ps2web_autosave_patch.py,
ps2web_autosaveopts_patch.py and ps2web_cardsync_patch.py.
What it does:
- every autosave is also sent to the launcher, which keeps it in C:\\p3fes\\saves\\autosaves (one folder per game build);
- every delete (by hand, or because of the "keep newest" setting) is sent too;
- when the page opens, autosaves the launcher has and this browser lacks are copied in, ones this browser has and the
  launcher lacks are sent up, and ones deleted in the launcher are deleted here;
- the page address can carry ?resume=<id> (the launcher's Resume button does this) so Start offers that autosave.
If the launcher is not running nothing changes. ?cardsync=off turns this off too.
Usage (in the ps2-web-recomp folder): python3 ps2web_autosavesync_patch.py [web/shell.html]
Then rebuild the browser game: scripts/build_web.sh p3fes
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'web/shell.html'
s = open(p).read()
if 'ps2-autosave-sync' in s:
    print("already patched"); raise SystemExit

ANCHOR = "const asReasons = {"
PUT_OLD = "    await asRun(db, 'readwrite', (store) => store.put({ id, key: asKey, reason, time: Date.now(), size: data.length, enc: packed.enc, bytes: packed.bytes }));\n"
PUT_NEW = ("    const rec = { id, key: asKey, reason, time: Date.now(), size: data.length, enc: packed.enc, bytes: packed.bytes };\n"
           "    await asRun(db, 'readwrite', (store) => store.put(rec));\n    asDiskPush(rec);\n")
KEEP_OLD = "    for (const old of same.slice(asOpts.keep - 1)) await asRun(db, 'readwrite', (store) => store.delete(old.id));\n"
KEEP_NEW = "    for (const old of same.slice(asOpts.keep - 1)) { await asRun(db, 'readwrite', (store) => store.delete(old.id)); asDiskDelete(old.id); }\n"
PRUNE_OLD = "      if (seen[e.reason] > asOpts.keep) await asRun(db, 'readwrite', (store) => store.delete(e.id));\n"
PRUNE_NEW = "      if (seen[e.reason] > asOpts.keep) { await asRun(db, 'readwrite', (store) => store.delete(e.id)); asDiskDelete(e.id); }\n"
DEL_OLD = "          await asRun(db, 'readwrite', (store) => store.delete(entry.id));\n"
DEL_NEW = "          await asRun(db, 'readwrite', (store) => store.delete(entry.id));\n          asDiskDelete(entry.id);\n"
KEY_OLD = "    asKey = await asBuildKey();\n"
KEY_NEW = "    asKey = await asBuildKey();\n    await asDiskSync().catch((e) => console.warn('autosave sync failed', e));\n"
WANT_OLD = "      const wanted = Number(sessionStorage.getItem('ps2-resume-id'));\n"
WANT_NEW = "      const wanted = Number(sessionStorage.getItem('ps2-resume-id')) || Number(new URLSearchParams(location.search).get('resume'));\n"
for name, old in (('anchor', ANCHOR), ('put', PUT_OLD), ('keep', KEEP_OLD), ('prune', PRUNE_OLD), ('delete', DEL_OLD), ('key', KEY_OLD), ('wanted', WANT_OLD)):
    if s.count(old) != 1:
        print("PATCH NOT APPLIED: expected text for '%s' not found exactly once (shell.html changed, or an earlier patch is missing)" % name)
        raise SystemExit(1)
if 'CS_URL' not in s:
    print("PATCH NOT APPLIED: run ps2web_cardsync_patch.py first")
    raise SystemExit(1)

BLOCK = r'''// ps2-autosave-sync: keep the launcher's copy of the autosaves in step with this browser (see tools/ps2web_autosavesync_patch.py)
const AD_BASE = CS_URL ? CS_URL.replace(/\/card$/, '/autosave') : '';
async function adFetch(path, opts) {
  if (!AD_BASE || csDown || asKey === 'default') return null;
  try { return await fetch(AD_BASE + path, opts); } catch (e) { return null; }
}
const adQ = () => '?key=' + encodeURIComponent(asKey);
async function asDiskPush(rec) {
  await adFetch('/' + rec.id + adQ() + '&reason=' + encodeURIComponent(rec.reason) + '&time=' + rec.time + '&size=' + rec.size + '&enc=' + rec.enc,
    { method: 'PUT', body: rec.bytes, headers: { 'Content-Type': 'application/octet-stream' } });
}
async function asDiskDelete(id) { await adFetch('/' + id + adQ(), { method: 'DELETE' }); }
async function asDiskSync() {
  const r = await adFetch(adQ() + '&announce=1', { cache: 'no-store' });
  if (!r || !r.ok) return;
  const info = await r.json();
  const db = await asOpen();
  try {
    const local = (await asRun(db, 'readonly', (store) => store.getAll())).filter((e) => e.key === asKey);
    const localIds = new Set(local.map((e) => e.id));
    const diskIds = new Set(info.items.map((e) => e.id));
    const gone = new Set(info.deleted);
    for (const e of local) if (gone.has(e.id)) await asRun(db, 'readwrite', (store) => store.delete(e.id));
    for (const it of info.items) {
      if (localIds.has(it.id) || gone.has(it.id)) continue;
      const g = await adFetch('/' + it.id + adQ(), { cache: 'no-store' });
      if (!g || !g.ok) continue;
      const bytes = new Uint8Array(await g.arrayBuffer());
      await asRun(db, 'readwrite', (store) => store.put({ id: it.id, key: asKey, reason: it.reason, time: it.time, size: it.size, enc: it.enc, bytes }));
    }
    for (const e of local) if (!diskIds.has(e.id) && !gone.has(e.id)) await asDiskPush(e);
  } finally {
    db.close();
  }
}
'''
s = (s.replace(ANCHOR, BLOCK + ANCHOR, 1).replace(PUT_OLD, PUT_NEW, 1).replace(KEEP_OLD, KEEP_NEW, 1).replace(PRUNE_OLD, PRUNE_NEW, 1)
      .replace(DEL_OLD, DEL_NEW, 1).replace(KEY_OLD, KEY_NEW, 1).replace(WANT_OLD, WANT_NEW, 1))
open(p, 'w').write(s)
print("patched (autosaves shared with the launcher folder)")
