#!/usr/bin/env python3
"""The model survey tool must find the RenderWare data after game-specific chunks with padding."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
sys.path.insert(0, HERE)
import p3fes_models as M
src = open(os.path.join(HERE, 'test_rmd_batch.py')).read().split('with tempfile')[0]
ns = {'__file__': os.path.join(HERE, 'test_rmd_batch.py')}
exec(compile(src, 'test_rmd_batch', 'exec'), ns)
m = ns['model']()
hdr, rw = m[:14], m[14:]
chunk = struct.pack('<III', 0xF0F000E0, 100, 0x40000000) + bytes(100)
cases = {'plain prefix': m, 'one long chunk + 2 pad': hdr + chunk + b'\0\0' + rw,
         'two chunks + 2 pad': hdr + chunk + b'\0\0' + chunk + rw}
ok = True
for name, data in cases.items():
    found = M.find_rw(data)
    good = found is not None
    print('  %-24s %s' % (name, 'found' if good else 'NOT FOUND'))
    ok &= good
print('ok   model survey finds RenderWare data after game-specific chunks' if ok else 'FAIL model survey')
sys.exit(0 if ok else 1)
