import io, os, sys, tempfile, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
import p3fes_launcher as L

assert L.update_repo_ok('someone/persona3-pc') and not L.update_repo_ok('someone') and not L.update_repo_ok('a/b/c') and not L.update_repo_ok('a b/c')
assert L.ver_tuple('0.21') > L.ver_tuple('0.9') and L.ver_tuple('1.0') > L.ver_tuple('0.99') and not L.ver_tuple('0.21') > L.ver_tuple('0.21')
assert L.update_parse_version('x = 1\nLAUNCHER_VERSION = "3.4"\n') == '3.4' and L.update_parse_version('nothing') == ''

def make(py, extra=None):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        z.writestr('repo-main/README.md', 'x')
        if py is not None:
            z.writestr('repo-main/tools/launcher/p3fes_launcher.py', py)
        z.writestr('repo-main/tools/launcher/ui/index.html', '<html>new</html>')
        z.writestr('repo-main/tools/launcher/ui/img/a.png', b'PNG')
        z.writestr('repo-main/tools/other.py', 'not wanted')
        z.writestr('repo-main/tools/launcher/ui/../../../../evil.txt', 'bad')
        for k, v in (extra or {}).items():
            z.writestr(k, v)
    return b.getvalue()

d = tempfile.mkdtemp(); bk = tempfile.mkdtemp()
os.makedirs(os.path.join(d, 'ui'))
open(os.path.join(d, 'p3fes_launcher.py'), 'w').write('LAUNCHER_VERSION = "0.1"\n')
open(os.path.join(d, 'ui', 'index.html'), 'w').write('<html>old</html>')
ver, n = L.update_apply(make('LAUNCHER_VERSION = "9.9"\nprint(1)\n'), d, bk, '0.1')
assert ver == '9.9' and n == 3, (ver, n)
assert 'LAUNCHER_VERSION = "9.9"' in open(os.path.join(d, 'p3fes_launcher.py')).read()
assert open(os.path.join(d, 'ui', 'index.html')).read() == '<html>new</html>' and os.path.isfile(os.path.join(d, 'ui', 'img', 'a.png'))
assert not os.path.exists(os.path.join(d, 'other.py')) and not os.path.exists(os.path.join(d, '..', 'evil.txt')) and not os.path.exists(os.path.join(d, 'evil.txt'))
assert open(os.path.join(bk, '0.1', 'p3fes_launcher.py')).read() == 'LAUNCHER_VERSION = "0.1"\n' and open(os.path.join(bk, '0.1', 'ui', 'index.html')).read() == '<html>old</html>'
# a broken or incomplete download changes nothing
before = open(os.path.join(d, 'p3fes_launcher.py')).read()
for bad in (make('def broken(:\n'), make(None), make('print(1)\n')):
    try:
        L.update_apply(bad, d, bk, '9.9')
        raise SystemExit('should refuse')
    except (ValueError, SyntaxError):
        pass
assert open(os.path.join(d, 'p3fes_launcher.py')).read() == before and open(os.path.join(d, 'ui', 'index.html')).read() == '<html>new</html>'
# check: reads the version from the repository file
L.load_cfg = lambda: {'update_repo': 'o/n'}
L.update_http = lambda url, limit: b'LAUNCHER_VERSION = "99.0"\n'
c = L.update_check()
assert c['ok'] and c['newer'] and c['latest'] == '99.0' and c['branch'] == 'main'
L.update_http = lambda url, limit: b'LAUNCHER_VERSION = "0.0"\n'
assert not L.update_check()['newer']
L.load_cfg = lambda: {}
assert L.update_check()['configured'] is False
print('ok update: version compare, safe install of launcher files only, backup, broken downloads refused')
