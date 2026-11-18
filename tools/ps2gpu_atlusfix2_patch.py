"""Second part of the ATLUS logo fix (ps2gpu_atlusfix_patch.py): after Return to Title Screen (Back to Title in the System Menu) the game copies the logo
to a different place in graphics memory (it changes from run to run), but reads it the same way as at boot, 4 pages before the picture, so the same two
strokes are there: the one under the A (column 233, rows 232 to 239) and the one under the U (columns 378 and 379, rows 256 to 263). Each is read as
the black beside it. The copy is recognised by its shape (1024 x 512, 4-bit, row pitch 16, not the boot place). The Sofdec / ADX splash screen has the
same shape (at 0x2F40) and is left alone. Patches runtime/src/gs/gpu/gs.wgsl. Needs ps2gpu_atlusfix_patch.py applied first. Replaces the earlier
versions of this patch.
Usage (in the ps2-web-recomp folder): python3 ps2gpu_atlusfix2_patch.py [runtime/src/gs/gpu/gs.wgsl]
Safe to run twice. Rebuild both builds afterwards.
"""
import sys, re
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/gs/gpu/gs.wgsl'
s = open(p, newline='').read()
nl = '\r\n' in s
t = s.replace('\r\n', '\n')
NEWCOND = "    if (s.tbw == 16u && s.tw == 10u && s.th == 9u && s.tpsm == 0x14u && s.tbp != 0x2F60u && s.tbp != 0x2F40u) {\n"
OLDCOND = "    if (s.tbp == 0x37E0u && s.tw == 10u && s.tpsm == 0x14u) {\n"
ORIG = "    if (s.tbp == 0x2F60u && s.tw == 10u && s.tpsm == 0x14u) {\n"
V1 = "    if ((s.tbp == 0x2F60u || s.tbp == 0x37E0u) && s.tw == 10u && s.tpsm == 0x14u) {\n"
END = "        if ((x == 378u || x == 379u) && y >= 256u && y <= 263u) {\n            x = 377u;\n        }\n    }\n"
BLOCK = ("    // atlus_fix2: the same two strokes in the logo's second place (after Return to Title Screen), read the same way as at boot\n"
         + NEWCOND
         + "        if (x == 233u && y >= 232u && y <= 239u) {\n            x = 232u;\n        }\n"
         + "        if ((x == 378u || x == 379u) && y >= 256u && y <= 263u) {\n            x = 377u;\n        }\n"
         + "    }\n")
if NEWCOND in t:
    print("already patched"); raise SystemExit
# remove any earlier version of this patch's block (it is always right after the boot block)
t = re.sub(r"    // atlus_fix2:.*?\n    if \(s\.tbw == 16u.*?\n    \}\n", "", t, flags=re.S)
t = t.replace(OLDCOND, ORIG, 1) if OLDCOND in t else t
if V1 in t:
    t = t.replace(V1, ORIG, 1)
if ORIG not in t or t.count(END) != 1:
    print("PATCH NOT APPLIED: the ATLUS fix was not found (apply ps2gpu_atlusfix_patch.py first)"); raise SystemExit(1)
t = t.replace(END, END + BLOCK, 1)
open(p, 'w', newline='').write(t.replace('\n', '\r\n') if nl else t)
print("patched (the ATLUS logo fix also covers the logo after Return to Title Screen)")
