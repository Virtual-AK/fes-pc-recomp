"""GameBanana browsing in the launcher: list, sort, search, paging, and installing a mod through the normal add flow (the network is faked)."""
import os, sys, tempfile, zipfile, threading, http.server, functools, json
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools", "launcher"))
import p3fes_launcher as L
src = open(os.path.join(here, "test_modmap.py")).read()
exec(src[:src.index("with tempfile")])

# host check
assert L.gb_host_ok("https://gamebanana.com/dl/1") and L.gb_host_ok("https://files.gamebanana.com/x")
assert not L.gb_host_ok("http://gamebanana.com/x") and not L.gb_host_ok("https://evilgamebanana.com/x") and not L.gb_host_ok("https://gamebanana.com.evil.io/x")

recs = [{"_idRow": 100 + i, "_sName": "Mod %d" % i, "_aSubmitter": {"_sName": "Author%d" % (i % 3)}, "_nLikeCount": i * 2, "_nViewCount": 1000 - i,
         "_tsDateAdded": 5000 + i, "_aRootCategory": {"_sName": "Skins"}} for i in range(14)]
calls = []
def fake_get(url, timeout=25):
    calls.append(url)
    if "/Mod/Index" in url:
        assert "Generic_Game%5D=8502" in url
        return {"_aRecords": recs, "_aMetadata": {"_nRecordCount": 14, "_bIsComplete": True}}
    raise AssertionError(url)
L.gb_get = fake_get
v = L.gb_view("", "new", 0, True)
assert v["ok"] and v["total"] == 14 and v["pages"] == 3 and [m["id"] for m in v["mods"]] == [113, 112, 111, 110, 109, 108], v
assert [m["id"] for m in L.gb_view("", "liked", 0)["mods"]][0] == 113
assert L.gb_view("", "viewed", 0)["mods"][0]["id"] == 100
s = L.gb_view("author1", "new", 0); assert s["total"] == 5 and all(m["by"] == "Author1" for m in s["mods"])
assert L.gb_view("", "new", 99)["page"] == 2
n = len(calls); L.gb_view("", "new", 1); assert len(calls) == n          # cached
def boom(url, timeout=25): raise OSError("offline")
L.gb_get = boom
e = L.gb_view("", "new", 0, True)
assert e["ok"] is False or e["total"] == 0 or e["err"], e
L.gb_cache["mods"] = []; e = L.gb_view("", "new", 0, True); assert not e["ok"] and "offline" in e["err"] and e["mods"] == []

# install: a local server stands in for gamebanana.com
with tempfile.TemporaryDirectory() as d:
    iso = os.path.join(d, "g.iso"); build(iso)
    saves = os.path.join(d, "p3fes", "saves"); os.makedirs(saves)
    L.find_iso = lambda: iso; L.saves_dir = lambda: saves
    web = os.path.join(d, "web"); os.makedirs(web)
    with zipfile.ZipFile(os.path.join(web, "mod.zip"), "w") as zf:
        zf.writestr("Cool Skin/test/BTL.BIN.d/a.bmd", b"HELLO-MODDED-012")
    open(os.path.join(web, "tool.exe"), "wb").write(b"MZ")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=web))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    L.gb_host_ok = lambda url: True
    def info(url, timeout=25):
        if url.endswith("/Mod/7/ProfilePage"):
            return {"_sName": "Cool Skin!", "_aFiles": [{"_sFile": "readme.txt", "_sDownloadUrl": base + "/x"}, {"_idRow": 71, "_sFile": "mod.zip", "_nFilesize": 300, "_sDownloadUrl": base + "/mod.zip"}]}
        if url.endswith("/Mod/8/ProfilePage"):
            return {"_sName": "A tool", "_aFiles": [{"_sFile": "tool.exe", "_sDownloadUrl": base + "/tool.exe"}]}
        if url.endswith("/Mod/9/ProfilePage"):
            return {"_sName": "Huge", "_aFiles": [{"_sFile": "big.zip", "_nFilesize": 3 * 1024 ** 3, "_sDownloadUrl": base + "/mod.zip"}]}
        raise AssertionError(url)
    L.gb_get = info
    # the preview: description cleaned to text, pictures only from gamebanana, files marked installable or not
    def pv(url, timeout=25):
        d = info(url) if not url.endswith("/Mod/5/ProfilePage") else {
            "_sName": "Preview me", "_sVersion": "1.2", "_aSubmitter": {"_sName": "Auth"}, "_nLikeCount": 3, "_nViewCount": 9,
            "_sText": "<p>Hello <b>world</b></p><script>bad()</script><ul><li>one</li><li>two</li></ul>",
            "_aPreviewMedia": {"_aImages": [{"_sBaseUrl": "https://images.gamebanana.com/img/ss/mods", "_sFile": "a.png", "_sFile530": "530-a.png"}, {"_sBaseUrl": "https://evil.example.com/x", "_sFile": "b.png"}]},
            "_aFiles": [{"_idRow": 1, "_sFile": "a.7z", "_nFilesize": 2048, "_sDescription": "Main", "_sDownloadUrl": "https://gamebanana.com/dl/1"}, {"_idRow": 2, "_sFile": "b.xdelta", "_nFilesize": 5, "_sDownloadUrl": "https://gamebanana.com/dl/2"}]}
        return d
    L.gb_get = pv
    real_ok = L.gb_host_ok
    L.gb_host_ok = lambda u: u.startswith("https://images.gamebanana.com") or u.startswith("https://gamebanana.com")
    v = L.gb_mod(5)
    assert v["name"] == "Preview me" and v["version"] == "1.2" and "Hello world" in v["desc"] and "bad()" not in v["desc"] and "one" in v["desc"], v
    assert v["images"] == ["https://images.gamebanana.com/img/ss/mods/530-a.png"], v["images"]
    assert [(f["id"], f["ok"]) for f in v["files"]] == [(1, True), (2, False)], v["files"]
    L.gb_host_ok = lambda url: True
    L.gb_get = info
    L.lm_work["busy"] = True; L.gb_install_work(7, 999); assert "no longer listed" in L.lm_work["msg"], L.lm_work["msg"]
    L.lm_work["busy"] = True; L.gb_install_work(7, 71)
    st = L.lm_state()
    assert [m["id"] for m in st["list"]] == ["cool-skin"] and st["list"][0]["kind"] == "ZIP" and st["list"][0]["fit"] == 1, st
    assert "Added (ZIP)" in st["msg"] and not st["busy"], st
    assert b"HELLO-MODDED-012" in open(os.path.join(d, "p3fes", "mods", "active.ovl"), "rb").read()
    assert not os.path.exists(os.path.join(d, "p3fes", "mods", "_dl"))
    L.lm_work["busy"] = True; L.gb_install_work(8); assert "no .zip, .7z or .rar" in L.lm_work["msg"] and ".exe" in L.lm_work["msg"], L.lm_work["msg"]
    L.lm_work["busy"] = True; L.gb_install_work(9); assert "over 2 GB" in L.lm_work["msg"]
    assert len(L.lm_state()["list"]) == 1 and not L.lm_work["busy"]
    srv.shutdown()
print("ok   launcher GameBanana: list, sort, search, paging, host checks, install through the add flow")
