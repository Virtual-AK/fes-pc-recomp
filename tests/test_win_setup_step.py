"""0.58: the launcher starts p3fes_win_setup.bat (PC window build) from the Setup screen."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
import p3fes_launcher as L

d = tempfile.mkdtemp(); L.DIR = d; L.WINCWD = d
web = os.path.join(d, 'build', 'web-' + L.NAME); os.makedirs(web)
calls = []
class P:
    def __init__(s, cmd, **k): calls.append(cmd)
L.subprocess.Popen = P
L.to_win = lambda p: 'C:\\x\\' + os.path.basename(p)
L.win_exe = lambda: None
L.win_setup_running = lambda: False
r = L.start_win_setup(); assert not r['ok'] and 'game build' in r['msg'], r      # browser build not done yet
open(os.path.join(web, 'ps2web.html'), 'w').write('x')
assert L.win_setup_script() and L.win_setup_script().endswith('p3fes_win_setup.bat')
r = L.start_win_setup(); assert r['ok'], r
assert calls[-1][:3] == ['cmd.exe', '/c', 'start'] and calls[-1][3] == L.WIN_SETUP_TITLE and calls[-1][4].endswith('p3fes_win_setup.bat'), calls
n = len(calls); L.win_setup_running = lambda: True
r = L.start_win_setup(); assert not r['ok'] and len(calls) == n
L.win_setup_running = lambda: False; L.win_exe = lambda: '/x/ps2run.exe'
r = L.start_win_setup(); assert not r['ok'] and 'already built' in r['msg']
assert 'title ' + L.WIN_SETUP_TITLE in open(os.path.join(os.path.dirname(L.win_setup_script()), 'p3fes_win_setup.bat')).read()
print('ok')
