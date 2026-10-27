import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import p3fes_spanish_staff as S


def script(lines, table=0x100):
    text = b"\x00".join(lines) + b"\x00\x00\x00\x00"
    layout = bytes([3, 40, 2, 1, 4, 1, 3, 16])
    off = 0x1c + table + len(text)
    head = struct.pack("<7I", 504, off, len(layout), 227, 0x1c, table, off - table)
    return head + bytes([8] * table) + text + layout


for table in (0x100, 0x120):
    old = script([b"art director", b"\tKatsura Hashino", b"", b"composer", b"\tShoji Meguro", b"\t\tzenina"], table)
    new = S.translate(old)
    h = struct.unpack_from("<7I", new, 0)
    assert h[1] == 0x1c + table + len(new[0x1c + table:h[1]]) and h[6] == h[1] - table and h[2] == 8 and h[0] == 504
    text = new[0x1c + table:h[1]].split(b"\x00")
    assert text[:5] == [b"director de arte", b"\tKatsura Hashino", b"", b"compositor", b"\tShoji Meguro"], text
    assert b"\t\tzenina" in text                                   # names and handles are never touched
    assert new[h[1]:] == old[struct.unpack_from("<I", old, 4)[0]:]  # the layout part is carried over as it was
    assert S.translate(new) == new                                 # already Spanish: nothing changes
try:
    S.translate(b"\x00" * 64)
    raise SystemExit("a wrong file was accepted")
except ValueError:
    pass
# every wording uses only letters the original font has (plain ASCII) and no title is empty
for k, v in S.ROLES.items():
    assert v.strip() and all(ord(c) < 0x7f for c in v), (k, v)
print("ok   Spanish staff roll: titles replaced, layout kept, names untouched")
