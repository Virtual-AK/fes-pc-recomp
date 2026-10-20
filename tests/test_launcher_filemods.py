"""Loose-file mods in the launcher: add from a folder and a zip (with a wrapping folder and DATA-style names), toggle, remove."""
import os, sys, tempfile, zipfile, json
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools", "launcher"))
import p3fes_launcher as L
src = open(os.path.join(here, "test_modmap.py")).read()
exec(src[:src.index("with tempfile")])
with tempfile.TemporaryDirectory() as d:
    iso = os.path.join(d, "g.iso"); build(iso)
    saves = os.path.join(d, "p3fes", "saves"); os.makedirs(saves)
    L.find_iso = lambda: iso
    L.saves_dir = lambda: saves
    # folder mod, named TEST (the image says TEST.CVM), one fitting file and one not in the image
    f1 = os.path.join(d, "folder-mod", "TEST", "BTL.BIN.d"); os.makedirs(f1)
    open(os.path.join(f1, "a.bmd"), "wb").write(b"HELLO-MODDED-012")
    open(os.path.join(d, "folder-mod", "TEST", "nope.bin"), "wb").write(b"x")
    L.lm_add_work(os.path.join(d, "folder-mod"))
    st = L.lm_state()
    assert [m["id"] for m in st["list"]] == ["folder-mod"] and st["list"][0]["fit"] == 1 and st["list"][0]["total"] == 2, st
    ovl = os.path.join(d, "p3fes", "mods", "active.ovl")
    assert os.path.isfile(ovl) and b"HELLO-MODDED-012" in open(ovl, "rb").read()
    # zip mod wrapped in a folder, a bigger whole file (moves)
    z = os.path.join(d, "big.zip")
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("Big Mod 1.0/readme.txt", "hi")
        zf.writestr("Big Mod 1.0/test/BTL.BIN", b"BIGFILE!" * 1000)
    L.lm_add_work(z)
    st = L.lm_state()
    assert [m["id"] for m in st["list"]] == ["big", "folder-mod"] and st["list"][0]["fit"] == 1, st
    assert b"BIGFILE!" in open(ovl, "rb").read()
    # unsafe zip and no-game-folder zip are refused with a message
    bad = os.path.join(d, "bad.zip")
    with zipfile.ZipFile(bad, "w") as zf: zf.writestr("../evil.txt", "x")
    L.lm_add_work(bad); assert "unsafe" in L.lm_work["msg"], L.lm_work["msg"]
    no = os.path.join(d, "no.zip")
    with zipfile.ZipFile(no, "w") as zf: zf.writestr("stuff/readme.txt", "x")
    L.lm_add_work(no); assert "No game folders" in L.lm_work["msg"], L.lm_work["msg"]
    assert len(L.lm_state()["list"]) == 2
    # toggle off the big one: overlay keeps only the small change; remove the other: no overlay
    L.lm_change_work("big", False)
    assert b"BIGFILE!" not in open(ovl, "rb").read() and b"HELLO-MODDED-012" in open(ovl, "rb").read()
    L.lm_change_work("folder-mod", True)
    assert not os.path.exists(ovl) and not os.path.exists(os.path.join(d, "p3fes", "mods", "folder-mod"))
print("ok   launcher loose-file mods: add folder/zip, alias, wrapper folder, toggle, remove")

# .7z / .rar: found by content; a fake 7z tool stands in for 7-Zip
import stat
with tempfile.TemporaryDirectory() as d:
    a7 = os.path.join(d, "mod.7z"); open(a7, "wb").write(b"7z\xbc\xaf\x27\x1c" + b"\0" * 40)
    rr = os.path.join(d, "mod.rar"); open(rr, "wb").write(b"Rar!\x1a\x07\x00" + b"\0" * 40)
    junk = os.path.join(d, "x.7z"); open(junk, "wb").write(b"hello")
    old_path = os.environ["PATH"]
    os.environ["PATH"] = os.path.join(d, "empty")
    for arc in (a7, rr):
        try: L.lm_extract_archive(arc, os.path.join(d, "o")); raise SystemExit("expected a message")
        except ValueError as e: assert "p7zip-full" in str(e), e
    try: L.lm_extract_archive(junk, os.path.join(d, "o")); raise SystemExit("expected refusal")
    except ValueError as e: assert "not a .zip" in str(e)
    bindir = os.path.join(d, "bin"); os.makedirs(bindir)
    fake = os.path.join(bindir, "7z")
    open(fake, "w").write('#!/bin/sh\nout=""\nfor a in "$@"; do case "$a" in -o*) out="${a#-o}";; esac; done\nmkdir -p "$out/TEST"\necho hi > "$out/TEST/a.bin"\nif [ -n "$EVIL" ]; then ln -s /etc "$out/TEST/link"; fi\n')
    os.chmod(fake, 0o755)
    os.environ["PATH"] = bindir + os.pathsep + "/usr/bin:/bin"
    L.lm_extract_archive(a7, os.path.join(d, "o1")); assert os.path.isfile(os.path.join(d, "o1", "TEST", "a.bin"))
    os.environ["EVIL"] = "1"
    try: L.lm_extract_archive(rr, os.path.join(d, "o2")); raise SystemExit("expected unsafe refusal")
    except ValueError as e: assert "unsafe" in str(e)
    del os.environ["EVIL"]; os.environ["PATH"] = old_path
print("ok   launcher opens .7z/.rar through 7-Zip, refuses links, explains when 7-Zip is missing")

assert L.lm_kind(os.path.dirname(os.path.abspath(__file__))) == "FOLDER"
with tempfile.TemporaryDirectory() as d:
    for nm, b, want in (("a.bin", b"PK\3\4", "ZIP"), ("b.bin", b"7z\xbc\xaf\x27\x1c", "7Z"), ("c.bin", b"Rar!\x1a\x07", "RAR")):
        open(os.path.join(d, nm), "wb").write(b); assert L.lm_kind(os.path.join(d, nm)) == want
print("ok   launcher tells folder, zip, 7z and rar apart")

# merging: one mod ships a whole container, another changes a single entry of it; both survive, the higher one wins on overlap
with tempfile.TemporaryDirectory() as d:
    iso = os.path.join(d, "g.iso"); build(iso)
    saves = os.path.join(d, "p3fes", "saves"); os.makedirs(saves)
    L.find_iso = lambda: iso; L.saves_dir = lambda: saves
    whole = os.path.join(d, "whole", "TEST"); os.makedirs(whole)
    open(os.path.join(whole, "BTL.BIN"), "wb").write(pak([("a.bmd", b"WHOLE-MOD-A-0123"), ("b.bin", b"x" * 40)]))
    one = os.path.join(d, "one", "TEST", "BTL.BIN.d"); os.makedirs(one)
    open(os.path.join(one, "b.bin"), "wb").write(b"B" * 40)
    L.lm_add_work(os.path.join(d, "whole")); L.lm_add_work(os.path.join(d, "one"))
    assert [m["id"] for m in L.lm_load()] == ["one", "whole"]          # newest on top
    ovl = open(os.path.join(d, "p3fes", "mods", "active.ovl"), "rb").read()
    assert b"WHOLE-MOD-A-0123" in ovl and b"B" * 40 in ovl and b"HELLO-WORLD-0123" not in ovl
    # overlapping changes to b.bin: whole mod changes it too, the one on top wins
    open(os.path.join(whole, "BTL.BIN"), "wb").write(b"")             # (the stored copy is in the mod folder, rewrite it there)
    wf = os.path.join(d, "p3fes", "mods", "whole", "files")
    stored = [os.path.join(dp, f) for dp, _d, fs in os.walk(wf) for f in fs if f == "BTL.BIN"][0]
    open(stored, "wb").write(pak([("a.bmd", b"WHOLE-MOD-A-0123"), ("b.bin", b"W" * 40)]))
    L.lm_change_work("one", False)                                      # toggle off then on to rebuild
    L.lm_change_work("one", False)
    ovl = open(os.path.join(d, "p3fes", "mods", "active.ovl"), "rb").read()
    assert b"B" * 40 in ovl and b"W" * 40 not in ovl, "the mod on top should win"
    L.lm_change_work("one", False, up=False)
    lst = L.lm_load(); L.lm_change_work("whole", False, up=True)         # whole moves above one
    assert [m["id"] for m in L.lm_load()] == ["whole", "one"]
    ovl = open(os.path.join(d, "p3fes", "mods", "active.ovl"), "rb").read()
    assert b"W" * 40 in ovl and b"B" * 40 not in ovl
print("ok   launcher merges a whole-container mod with a single-entry mod, priority decides overlaps")


def test_twelve_theme_needs_journey_unlock():
    import p3fes_launcher as L
    assert "twelve" in L.THEMES_ALL and "horizon" in L.THEMES_ALL
    assert L.theme_now({"theme": "twelve"}) == "blue"
    assert L.theme_now({"theme": "twelve", "journey": True}) == "twelve"
    assert L.theme_now({"theme": "eclipse"}) == "eclipse"
