"""scripts/port.sh passes the mod switch table to the translator when the game folder has one.
If games/<name>/variants.txt and games/<name>/vanilla.elf exist, the translator gets --variants/--vanilla (see ps2recomp_modswitch_patch.py).
Usage (in the ps2-web-recomp folder): python3 ps2port_modswitch_patch.py [scripts/port.sh]
Safe to run twice.
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'scripts/port.sh'
s = open(p, newline='').read()
if 'ps2-modswitch' in s:
    print("already patched"); raise SystemExit
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')
OLD = 'translate() { "$tools/eerecomp" "$elf" --entries "$game/entries.txt" "${modules[@]}" --out "$generated" | tail -1; }\n'
NEW = """# ps2-modswitch: mods with live on/off switches (games/<name>/variants.txt, written by tools/p3fes_pnach_apply.py)
variants=()
if [ -f "$game/variants.txt" ] && [ -f "$game/vanilla.elf" ]; then variants=(--variants "$game/variants.txt" --vanilla "$game/vanilla.elf"); fi
translate() { "$tools/eerecomp" "$elf" --entries "$game/entries.txt" "${modules[@]}" "${variants[@]}" --out "$generated" | tail -1; }
"""
if s.count(OLD) != 1:
    print("PATCH NOT APPLIED: scripts/port.sh does not look like the expected source"); raise SystemExit(1)
open(p, 'w', newline='').write((s.replace(OLD, NEW)).replace('\n', '\r\n') if crlf else s.replace(OLD, NEW))
print("patched (1 edit)")
