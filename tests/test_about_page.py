"""About page: the main menu has ABOUT, its pictures exist as transparent PNGs, and the launcher serves PNG files."""
import os, re
here = os.path.dirname(os.path.abspath(__file__))
ui = os.path.join(here, "..", "tools", "launcher", "ui")
html = open(os.path.join(ui, "index.html")).read()
assert "'HELP','ABOUT']" in html and "open_('about')" in html and "about:{title:'ABOUT'" in html
for name in re.findall(r"'((?:virtualak|claude)-(?:avatar|signature)\.png)'", html):
    pass
names = ["virtualak-avatar.png", "virtualak-signature.png", "claude-avatar.png", "claude-signature.png"]
for n in names:
    assert n in html, n
    data = open(os.path.join(ui, "img", n), "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", n
    assert data[25] in (4, 6), n + " must have an alpha channel"   # colour type: grey+alpha or RGBA
    assert len(data) < 400_000, n + " is too big for a launcher page"
src = open(os.path.join(here, "..", "tools", "launcher", "p3fes_launcher.py")).read()
assert '"png": "image/png"' in src
assert "VirtualAK" in html and "Claude" in html
print("ok   About page: main menu entry, creator pictures (transparent PNGs) and PNG serving")
