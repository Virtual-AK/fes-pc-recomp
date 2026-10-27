import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import p3fes_spanish_text as T

# every wording encodes, in both letter sets, and decodes back to itself
for k, t in T.SHORT_TEXT.items():
    for kind in ("help", "dlg"):
        assert T.decode(T.encode(t, kind), kind) == t, (kind, t)
# a line shortened by hand keeps the control bytes of its message
en = b"\xf2\x07\x81\x01Missed!\n"
es = b"\xf2\x07\x81\x01\x7fEl ataque ha fallado!\n"
assert T.shorter(en, es, b"jyokyohelp_AVOID_PLAYER") == b"\xf2\x07\x81\x01\x7fFallo!\n"
# dialogue uses the other set of letters
en = b"\xf3I\x06\x01Why am I sensing two entities...?\nIt doesn't make sense!\n\xf2G\x0b\x01\xf1\x04"
es = b"\xf3I\x06\x01\x81`Por qu\x82\x0c percibo a dos entidades...?\n\x7fNo tiene sentido!\n\xf2G\x0b\x01\xf1\x04"
r = T.shorter(en, es, b"MSG_0049")
assert r.startswith(b"\xf3I\x06\x01\x81`Por qu\x82\x0c percibo dos") and r.endswith(b"\n\xf2G\x0b\x01\xf1\x04"), r
# a line with no wording, or Spanish with other control bytes, gives nothing
assert T.shorter(b"\xf2\x07\x81\x01Unknown!\n", b"\xf2\x07\x81\x01\x7fDesconocido!\n", b"jyokyohelp_X") is None
assert T.shorter(en, b"\xf3K\x06\x01hola\n", b"MSG_0049") is None
print("ok   Spanish shortened lines: encode, letter sets, control bytes kept")
