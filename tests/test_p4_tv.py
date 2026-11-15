"""0.59: the home-screen TV says WORK IN PROGRESS and opens the Persona 4 project page."""
import os, sys
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(root, 'tools', 'launcher'))
import p3fes_launcher as L
h = open(os.path.join(root, 'tools', 'launcher', 'ui', 'index.html')).read()
assert "['WORK IN','PROGRESS']" in h and 'data-act="p4tv"' in h and "a==='p4tv'" in h and "/api/p4/open" in h
assert L.P4_URL == 'https://github.com/Virtual-AK/p4-pc-recomp'
seen = []
L.win_open = lambda url, app=False, prefer=None, size=None: seen.append((url, prefer)) or 'msedge'
r = L.open_p4_page(); assert r['ok'] and seen[0][0] == L.P4_URL, (r, seen)
L.win_open = lambda *a, **k: None
r = L.open_p4_page(); assert not r['ok'] and L.P4_URL in r['msg']
print('ok p4 tv')
