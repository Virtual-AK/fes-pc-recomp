"""Screenshots: file-name checks, listing, deletion, helper script text and the Extra panel wiring."""
import os, sys, tempfile, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "launcher"))
import p3fes_launcher as L

d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "thumbs"))
L.shots_dir = lambda: d
good = "P3FES_2026-10-21_12-30-05.png"
for n in (good, "P3FES_2026-10-21_12-30-06_2.png"):
    open(os.path.join(d, n), "wb").write(b"\x89PNG")
    open(os.path.join(d, "thumbs", n[:-4] + ".jpg"), "wb").write(b"\xff\xd8")
open(os.path.join(d, "secret.png"), "wb").write(b"x")

assert L.SHOT_RE.match(good)
for bad in ("../x.png", "secret.png", "P3FES_2026-10-21_12-30-05.png/../../x", "", None, "P3FES_x.png"):
    assert not L.SHOT_RE.match(bad or ""), bad
    assert L.shots_file(bad) is None and not L.shots_delete(bad)
names = [e["name"] for e in L.shots_list()]
assert sorted(names) == sorted([good, "P3FES_2026-10-21_12-30-06_2.png"]), names
assert L.shots_file(good)[1] == "image/png" and L.shots_file(good, thumb=True)[1] == "image/jpeg"
assert L.shots_delete(good) and not os.path.exists(os.path.join(d, good)) and not os.path.exists(os.path.join(d, "thumbs", good[:-4] + ".jpg"))
assert os.path.exists(os.path.join(d, "secret.png"))
print("ok  names, listing, delete stay inside the screenshots folder")

# clear: removes every screenshot and its small picture, leaves other files alone, counts what it removed
assert L.shots_clear() == 1 and not [e for e in L.shots_list()]
assert not os.listdir(os.path.join(d, "thumbs")) and os.path.exists(os.path.join(d, "secret.png"))
assert L.shots_clear() == 0
print("ok  clear all removes only the launcher's screenshots")

assert L.shots_settings({}) == {"on": True, "key": "F9", "sound": True}
assert L.shots_settings({"screenshot_key": "Delete"})["key"] == "F9"
assert L.shots_settings({"screenshots_on": False, "screenshot_key": "F10"})["key"] == "F10"
print("ok  settings defaults and key whitelist")

ps = L.SHOT_PS1
assert ps.count('@"') == 1 and ps.count('\n"@') == 1, "here-string markers"
cs = ps.split('@"\n', 1)[1].split('\n"@', 1)[0]
assert "$" not in cs, "PowerShell would expand $ inside the C# here-string"
assert cs.count("{") == cs.count("}") and cs.count("(") == cs.count(")")
for k in L.SHOT_KEYS:
    assert hasattr(__import__("enum").Enum, "__members__") and re.match(r"^[A-Za-z0-9]+$", k)
assert "void Capture(" not in cs, "clashes with Control.Capture"
assert "RegisterHotKey" in cs and "CopyFromScreen" in cs and "P3FES_ShotHelper" in cs and "@DIR@" in ps
print("ok  helper script is balanced and has no PowerShell expansion traps")

ui = open(os.path.join(os.path.dirname(__file__), "..", "tools", "launcher", "ui", "index.html")).read()
assert "'SCREENSHOTS'" in ui and "msel===3)return shPanel()" in ui and "shgrid" in ui
print("ok  Extra menu has the SCREENSHOTS panel")

# bug report links: mail goes to the maintainer's address, carries the version and the report, nothing from disc or saves
mailto, gmail = L.bug_mail_urls()
assert mailto.startswith("mailto:kingbackup1876@gmail.com?subject=") and "&body=" in mailto and len(mailto) < 1800
assert gmail.startswith("https://mail.google.com/mail/?view=cm") and "to=kingbackup1876%40gmail.com" in gmail
assert L.LAUNCHER_VERSION in mailto and "report" in mailto.lower() and " " not in mailto and "\n" not in mailto
print("ok  bug report links hold the address, the version and the report")
