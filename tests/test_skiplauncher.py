"""Skip the launcher (0.37): setting is stored and sent in the state; the page has the countdown and the Turbo patches are gone."""
import os, re
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
srv = open(root + "/tools/launcher/p3fes_launcher.py").read()
html = open(root + "/tools/launcher/ui/index.html").read()
assert '"/api/skiplauncher"' in srv and '"skip_launcher": bool(cfg.get("skip_launcher"))' in srv
assert "skipStart" in html and "sk:1" in html and "SKIP THE LAUNCHER" in html and "menu" in html[html.index("function skipStart"):html.index("function skipStart") + 600]
assert not os.path.exists(root + "/tools/ps2run_turbo_patch.py") and not os.path.exists(root + "/tools/ps2web_turbo_patch.py")
assert "turbo" not in open(root + "/tools/p3fes_install.sh").read().lower()
print("ok   skip-the-launcher setting and countdown are wired; Turbo patches removed from the installer")
