import os, re
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
h = open(root + '/tools/launcher/ui/index.html').read()
md = open(root + '/docs/changelog.md').read()
ui = re.findall(r"\{v:'([^']+)',d:'", h)
doc = re.findall(r"^## ([0-9.]+) ", md, re.M)
assert ui and ui == doc, (ui, doc)
src = open(root + '/tools/launcher/p3fes_launcher.py').read()
assert ('LAUNCHER_VERSION = "%s"' % ui[0]) in src, 'newest changelog version must be the launcher version'
n_ui = len(re.findall(r"'(?:NEW|IMPROVED|FIXED)  ", h))
n_doc = len(re.findall(r"^- \*\*(?:NEW|IMPROVED|FIXED)\*\*", md, re.M))
assert n_ui == n_doc, (n_ui, n_doc)
print('ok changelog: launcher list, docs/changelog.md and the version agree (%d entries)' % n_ui)
