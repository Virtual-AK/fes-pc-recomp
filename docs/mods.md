# Using PCSX2-style code patches (.pnach) in the recompiled game

A `.pnach` file rewrites game code while the game runs on PCSX2. Our game is recompiled ahead of time, so the same
rewrite at run time has no effect. Instead the patch is written into a copy of the boot program (`SLUS_216.21`) and
the game is recompiled from that copy. The original disc and program are never changed, and the patch files stay on
your computer (they belong to their authors and are not part of this repository).

1. `python3 tools/p3fes_pnach_apply.py games/p3fes/disc/SLUS_216.21 mod.pnach -o games/p3fesmod/core.elf --entries games/p3fesmod/entries_new.txt`
   writes the patched program and lists the code entry points the patch adds. Check the line "original-word checks":
   every mismatch means the program or patch is for a different version.
2. Put the earlier entry points (`games/p3fes/entries.txt`) and the new ones into `games/p3fesmod/entries.txt`, link the
   disc image into `games/p3fesmod/disc.iso`, and run `scripts/port.sh p3fesmod games/p3fes/disc.iso --no-explore`.
   `port.sh` uses `core.elf` in the game folder in place of the program on the disc.
3. Play it with the same commands as the unmodified game, with `p3fesmod` in place of `p3fes`.

Patches that replace files (text, textures) are not covered by this: they need either an edited disc image (an
`.xdelta` file applied to your own image) or a mod-folder feature in the runner, which does not exist yet.

## Troubleshooting: "missing code at 0x........" crash

If the modded game stops with `[ee] stopped ... missing code at 0xADDR (ra 0xCALLER)`, the
recompiler never translated the code at `ADDR`. This happens when a mod's added code is reached
through a function pointer or `jalr`, so `p3fes_pnach_apply.py` could not see the call.

Fix: append `ADDR` (six hex digits, one per line) to `games/<mod>/entries.txt`, delete
`generated/<mod>` and `build/native-<mod>`, and rerun `scripts/port.sh`.

Notes from the Direct Commands mod:
- Only one extra entry (`69ac94`) was needed beyond the ones the tool printed.
- Do not mark every instruction in the cave as an entry point. Branches inside one routine then
  point into a different generated routine and the build fails with "undeclared label".
- Always delete `generated/<mod>` before rebuilding after changing `entries.txt`. Stale generated
  files from an earlier run cause "undeclared identifier unit_XXXX" errors.
