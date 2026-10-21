import json, os, struct, sys, tempfile, zlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
import p3fes_launcher as L

# the binary shortcut list: parse / write round trip, add, add again (replaces), remove
entry = L.shortcut_entry(123 | 0x80000000, '"C:\\p3fes\\launcher\\launch.bat"', 'C:\\p3fes\\launcher', '')
empty = L.vdf_dump([(0, 'shortcuts', [])])
assert empty == b'\x00shortcuts\x00\x08\x08', empty
one = L.shortcuts_add(b'', entry)
assert L.vdf_dump(L.vdf_parse(one)[0]) == one
assert b'Persona 3 FES' in one and one.count(b'AppName') == 1
again = L.shortcuts_add(one, entry)
assert again == one, 'adding twice must replace, not duplicate'
# another program's shortcut stays, and ours is numbered after it
other = [(2, 'appid', 5), (1, 'AppName', 'Other game'), (1, 'Exe', '"x.exe"')]
base = L.vdf_dump([(0, 'shortcuts', [(0, '0', other)])])
both = L.shortcuts_add(base, entry)
root = L.vdf_parse(both)[0]
sc = root[0][2]
assert [k for _, k, _ in sc] == ['0', '1'] and sc[0][2] == other
gone, app_id = L.shortcuts_remove(both)
assert L.vdf_parse(gone)[0][0][2] == [(0, '0', other)] and app_id == 123 | 0x80000000
# the number Steam files artwork under: crc32 of exe + name with the top bit set
assert L.steam_app_id('"a"', 'b') == (zlib.crc32(b'"a"b') & 0xFFFFFFFF) | 0x80000000

# adding to a pretend Steam folder
d = tempfile.mkdtemp()
root_dir = os.path.join(d, 'Steam')
os.makedirs(os.path.join(root_dir, 'userdata', '42', 'config'))
os.makedirs(os.path.join(root_dir, 'userdata', '7', 'config'))
os.makedirs(os.path.join(root_dir, 'config'))
open(os.path.join(root_dir, 'config', 'loginusers.vdf'), 'w').write('"users"\n{\n "76561197960265770"\n {\n  "MostRecent"  "1"\n }\n}\n')   # account 42
L.steam_root = lambda: root_dir
L.steam_running = lambda: True
L.to_win = lambda p: 'C:\\p3fes\\launcher\\launch.bat' if p.endswith('launch.bat') else 'C:\\fake\\' + os.path.basename(p)
L.CFG = os.path.join(d, 'cfg.json')
assert L.steam_users(root_dir)[0][0] == 42
r = L.steam_add({'portrait': 'https://cdn2.steamgriddb.com/grid/a.png'})
assert not r['ok'] and 'Close Steam' in r['msg']
L.steam_running = lambda: False
fetched = []
L.steam_download = lambda url, dest: (fetched.append(url), open(dest, 'wb').write(b'img'))
r = L.steam_add({'portrait': 'https://cdn2.steamgriddb.com/grid/a.png', 'wide': 'https://cdn2.steamgriddb.com/grid/b.jpg',
                 'hero': 'https://cdn2.steamgriddb.com/hero/h.png', 'logo': 'https://cdn2.steamgriddb.com/logo/l.png',
                 'icon': 'https://cdn2.steamgriddb.com/icon/i.png', 'evil': 'https://example.com/x.png'})
assert r['ok'], r
exe, start = L.steam_launch_target()
app_id = L.steam_app_id(exe, 'Persona 3 FES')
grid = os.path.join(root_dir, 'userdata', '42', 'config', 'grid')
names = sorted(os.listdir(grid))
assert names == sorted(['%dp.png' % app_id, '%d.jpg' % app_id, '%d_hero.png' % app_id, '%d_logo.png' % app_id, '%d_icon.png' % app_id]), names
data = open(os.path.join(root_dir, 'userdata', '42', 'config', 'shortcuts.vdf'), 'rb').read()
assert b'Persona 3 FES' in data and b'launch.bat' in data
# a link to some other site is refused
r2 = L.steam_add({'portrait': 'https://example.com/a.png'})
assert 'portrait' in r2['msg'] and 'Could not download' in r2['msg']
assert L.steam_state()['added'] is True
# removing takes the shortcut and its artwork, keeps a backup
r = L.steam_remove()
assert r['ok'] and not os.listdir(grid)
assert os.path.exists(os.path.join(root_dir, 'userdata', '42', 'config', 'shortcuts.vdf.p3fes-backup'))
assert b'Persona 3 FES' not in open(os.path.join(root_dir, 'userdata', '42', 'config', 'shortcuts.vdf'), 'rb').read()

# SteamGridDB calls: parameters and the filtering of the answer
seen = []
def fake(path, params=None, key=None):
    seen.append((path, params))
    return {'data': [{'id': 1, 'url': 'https://cdn2.steamgriddb.com/grid/1.png', 'thumb': 'https://cdn2.steamgriddb.com/thumb/1.png', 'width': 600, 'height': 900, 'style': 'alternate', 'author': {'name': 'x'}},
                     {'id': 2, 'url': 'https://cdn2.steamgriddb.com/grid/2.png', 'nsfw': True}]}
L.sgdb_get = fake
json.dump({'steamgriddb_key': 'k', 'steamgriddb_game': 99}, open(L.CFG, 'w'))
class FakeH(L.H):
    def __init__(self): self.out = None
    def send(self, code, obj): self.out = obj
import io
h = FakeH(); h.path = '/api/steam/art'; h.headers = {'Content-Length': '0'}
h.rfile = io.BytesIO(json.dumps({'kind': 'portrait', 'page': 0}).encode())
h.headers = {'Content-Length': str(len(json.dumps({'kind': 'portrait', 'page': 0})))}
h.do_POST()
assert h.out['ok'] and len(h.out['items']) == 1, h.out
assert seen[-1][0] == '/grids/game/99' and seen[-1][1]['dimensions'] == '600x900' and 'image/png' in seen[-1][1]['mimes'], seen
for kind, mime in (('logo', 'image/png'), ('icon', 'image/png,image/vnd.microsoft.icon'), ('hero', 'image/png,image/jpeg')):
    body = json.dumps({'kind': kind, 'page': 0})
    h = FakeH(); h.path = '/api/steam/art'; h.headers = {'Content-Length': str(len(body))}; h.rfile = io.BytesIO(body.encode()); h.do_POST()
    assert seen[-1][1]['mimes'] == mime, (kind, seen[-1])
print('ok steam: shortcut file round trip, add/replace/remove, artwork file names, refuses other sites, SteamGridDB request shape')
