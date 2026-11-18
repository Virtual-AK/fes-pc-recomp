"""Calendar moons: the moons that run backwards (the mirrored ones, waning phases such as 16 to 22 July) were drawn about 2.5 pixels (original
screen pixels) left of their dates and weekdays, while the unmirrored ones (waxing) line up. The game's own positions for the moon, the weekday and
the date are identical, and the moon picture is read one to one, so this moves the picture the other way by 2.5 texels for the 256x128 4-bit
moon picture only, when its coordinate runs backwards. Patches runtime/src/gs/gpu/gs.wgsl. Needs ps2gpu_flipfix_patch.py applied first.
Usage (in the ps2-web-recomp folder): python3 ps2gpu_moonfix_patch.py [runtime/src/gs/gpu/gs.wgsl]
Safe to run twice (also replaces the first version of this patch). Rebuild both builds afterwards.
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gpu/gs.wgsl'
K = '2.5'
s = open(p, newline='').read()
nl = '\r\n' in s
t = s.replace('\r\n', '\n')
if 'moon_shift' in t:
    print("already patched"); raise SystemExit
# the first version of this patch left the moon picture out of the flipped-tile step; put that step back
OLD1 = ("            // moon_fix: not for the 256x128 4-bit picture of the calendar moons\n"
        "            if (has(s, F_TME) && !(s.tw == 8u && s.th == 7u && s.tpsm == 0x14u)) {")
NEW1 = "            if (has(s, F_TME)) {"
if OLD1 in t:
    t = t.replace(OLD1, NEW1, 1)
ANCHOR = ("                }\n            }\n            at = Attr(c.x, c.y, c.z, c.w, t.x, t.y, t.z, t.w,")
INSERT = ("                }\n"
          "                // moon_shift: the mirrored calendar moons (256x128 4-bit picture) are moved " + K + " texels so they line up with their dates\n"
          "                if (s.tw == 8u && s.th == 7u && s.tpsm == 0x14u && gu < 0.0) {\n"
          "                    if (has(s, F_FST)) {\n"
          "                        t.x = t.x + 16.0 * " + K + ";\n"
          "                    } else {\n"
          "                        t.x = t.x + t.z * " + K + " / f32(1u << s.tw);\n"
          "                    }\n"
          "                }\n"
          "            }\n"
          "            at = Attr(c.x, c.y, c.z, c.w, t.x, t.y, t.z, t.w,")
if 'flip_fix' not in t or t.count(ANCHOR) != 1:
    print("PATCH NOT APPLIED: the flipped-tile step was not found (apply ps2gpu_flipfix_patch.py first)"); raise SystemExit(1)
t = t.replace(ANCHOR, INSERT, 1)
open(p, 'w', newline='').write(t.replace('\n', '\r\n') if nl else t)
print("patched (the mirrored calendar moons are moved %s texels)" % K)
