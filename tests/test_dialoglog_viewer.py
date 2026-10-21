import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
import p3fes_launcher as L
f = tempfile.mktemp()
open(f, 'w').write('100\t12\t2\tMSG_000\t0\tHi\\nthere\\n\n110\t-1\t1\tMSG_035\t0\t> narration\\n\n120\t3\t-1\tB\t0\tNo voice\\n\nbad line\n5\t8\t4\tC\t1\tNew session\\n\n')
r = L.dialog_log_entries(f)
e = r['entries']
assert [x['voiced'] for x in e] == [True, False, False, True], e      # narration pages carry a clip number but are not voiced
assert [x['sess'] for x in e] == [0, 0, 0, 1], e                        # frame number going back down = new play session
assert e[0]['t'] == 'Hi\nthere\n'
assert L.dialog_log_entries(f + 'x')['have_file'] is False
assert L.dialog_log_clear(f) and L.dialog_log_entries(f)['entries'] == []
print('ok dialogue log reading: voiced rule, sessions, missing file, clear')
