#!/usr/bin/env python3
"""A 16-byte filler ('npc_00') in front of a real entry must not be taken for a size-0 entry that hides the real one."""
import io, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
from p3fes_unpack import analyse_pak, Window
def entry(name, data):
    b = name.encode().ljust(252, b'\0') + struct.pack('<I', len(data)) + data
    return b + b'\0' * (-len(b) % 16)
fill = b'npc_00'.ljust(16, b'\0')
pak = (entry('f006_006.HBN', b'h' * 92) + fill + entry('f006_006.CMR', b'c' * 112) + fill + entry('f006_006.ENV', b'e' * 512)
       + entry('f020_002_init', b'') + entry('f006_106.ENV', b'e' * 512) + b'\0' * 256)
r = analyse_pak(Window(io.BytesIO(pak), 0, len(pak)))
assert r['ok'], r
got = [(n, l) for n, l in r['entries']]
assert got == [('f006_006.HBN', 92), ('f006_006.CMR', 112), ('f006_006.ENV', 512), ('f020_002_init', 0), ('f006_106.ENV', 512)], got
# a real empty entry at the very end of the data stays an entry
pak2 = entry('a.bin', b'x' * 16) + entry('empty_one', b'') + b'\0' * 256
r2 = analyse_pak(Window(io.BytesIO(pak2), 0, len(pak2)))
assert [(n, l) for n, l in r2['entries']] == [('a.bin', 16), ('empty_one', 0)], r2['entries']
print('ok   unpacker skips 16-byte fillers and keeps the real entry behind them')
