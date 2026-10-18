import os, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools"))
import p3fes_primsum as ps
T = """[prim] f10 type=5 iip=1 tme=0 fge=0 abe=1 fst=0 ctx=1 tbp=0 psm=0 tw=0 th=0 tcc=0 tfx=0 alpha=42 test=30000 clamp=0 frame=8C0000 zbuf=1 ofx=32768 ofy=32768
[prim]   v0 x=33000 y=33000 z=1 rgba=FF000080 s=0 t=0 q=1 u=0 v=0
[prim]   v1 x=34000 y=33000 z=1 rgba=FF000080 s=0 t=0 q=1 u=0 v=0
[prim]   v2 x=34000 y=34600 z=1 rgba=FF000080 s=0 t=0 q=1 u=0 v=0
[prim] f10 type=6 iip=0 tme=1 fge=0 abe=0 fst=0 ctx=0 tbp=1180 psm=0 tw=10 th=9 tcc=1 tfx=0 alpha=44 test=1 clamp=0 frame=0 zbuf=1 ofx=32768 ofy=32768
[prim]   v0 x=32768 y=32768 z=0 rgba=80808080 s=0 t=0 q=1 u=0 v=0
[prim]   v1 x=43008 y=40960 z=0 rgba=80808080 s=1 t=1 q=1 u=0 v=0
"""
prims = ps.parse(T.splitlines())
assert len(prims) == 2 and len(prims[0]['v']) == 3 and prims[1]['tme'] == 1
b = ps.box(prims[0])
assert abs(b[0] - (33000 - 32768) / 16.0) < 1e-9 and abs(b[3] - (34600 - 32768) / 16.0) < 1e-9
rows = ps.select(prims, tme='0')
assert len(rows) == 1 and rows[0][1]['alpha'] == '42'
rows = ps.select(prims, tme='any')
assert rows[0][1]['tme'] == 1  # the big textured quad sorts first
assert ps.select(prims, min_area=1e9) == []
assert prims[0]['abe'] == 1 and prims[0]['iip'] == 1 and prims[1]['abe'] == 0
import io, contextlib
tmp = os.path.join(here, "_prim_tmp.txt"); open(tmp, "w").write(T)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    ps.main([tmp, "--detail", "0"])
os.remove(tmp)
assert "corner 2: screen" in buf.getvalue() and "abe=1" in buf.getvalue()
buf = io.StringIO()
open(tmp, "w").write(T)
with contextlib.redirect_stdout(buf):
    ps.main([tmp, "--range", "0,2"])
os.remove(tmp)
assert buf.getvalue().count("#") == 2 and "tbp=1180" in buf.getvalue() and "zmsk=0" in buf.getvalue(), buf.getvalue()
assert prims[1]['tbp'] == '1180'
buf = io.StringIO()
open(tmp, "w").write(T)
with contextlib.redirect_stdout(buf):
    ps.main([tmp, "--hist"])
os.remove(tmp)
out = buf.getvalue()
assert "2 shapes" in out and "type=6 tme=1" in out and "type=5 tme=0" in out and out.index("type=6") < out.index("type=5"), out
print("ok   primsum parses a prim trace, removes the offset and sorts shapes by box area")
