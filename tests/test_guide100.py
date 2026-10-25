"""Built-in 100% guide (0.38): data file is sane, ids are unique and safe, endpoint stores ticks."""
import os, re, sys, json, subprocess, shutil, tempfile
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ui = root + "/tools/launcher/ui/"
srv = open(root + "/tools/launcher/p3fes_launcher.py").read()
html = open(ui + "index.html").read()
assert "guide100.js" in html and "g1Open" in html and "g100" in html and '"/api/guide100"' in srv
node = shutil.which("node")
if node:
    js = open(ui + "guide100.js").read() + "\nconsole.log(JSON.stringify(window.G100));"
    r = subprocess.run([node, "-e", "global.window={};" + js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[:400]
    G = json.loads(r.stdout)
    ids = []
    for c in G["chapters"]:
        for l in c.get("links", []):
            ids += [l["id"], l["id"] + "-p"]
        for i in c.get("items", []):
            ids.append(i["id"])
    assert len(ids) == len(set(ids)), "duplicate ids"
    assert all(re.match(r"^[a-z0-9._-]{1,40}$", x) for x in ids), [x for x in ids if not re.match(r"^[a-z0-9._-]{1,40}$", x)]
    ch = {c["id"]: c for c in G["chapters"]}
    assert len(ch["links"]["links"]) == 22 and len(ch["requests"]["items"]) == 99
    print("ok   100%% guide data: %d chapters, %d tick boxes, 22 links, 99 requests" % (len(G["chapters"]), len(ids)))
else:
    print("ok   100% guide data: node missing, not parsed")
sys.path.insert(0, root + "/tools/launcher")
import importlib.util
spec = importlib.util.spec_from_file_location("l", root + "/tools/launcher/p3fes_launcher.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.GUIDE100_FILE = os.path.join(tempfile.mkdtemp(), "g.json")
assert m.guide100_apply({}) == []
assert m.guide100_apply({"id": "sl-fool", "on": True}) == ["sl-fool"]
assert m.guide100_apply({"id": "../x", "on": True}) == ["sl-fool"]
assert m.guide100_apply({"id": "rq-01", "on": True}) == ["rq-01", "sl-fool"]
assert m.guide100_apply({"id": "sl-fool", "on": False}) == ["rq-01"]
assert m.guide100_apply({"reset": True}) == [] and m.guide100_load() == []
print("ok   guide100 endpoint logic stores, validates and resets ticks")
