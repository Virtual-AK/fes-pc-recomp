# Packed-in mods (launcher 0.29)

Mods > PACKED-IN MODS lists community mods with an ON/OFF button each, and Mods > CHEATS lists two cheat sheets (off by default).
Nothing from these mods is in this repository: the launcher downloads each one from its author's GameBanana page onto your computer
(`C:\p3fes\packed\<mod>\` for the patch files, FILE MODS for the file mods), and the author is credited and linked on its row.

| Mod | Kind | How it works |
|---|---|---|
| Direct Commands | code (.pnach) | built into the shared mod build, live switch |
| Modern Persona Switch | code | same |
| Always Cut-In (the Always Cutins file) | code | same |
| Always Critical (the Always Critical file, a cheat in Mods > Cheats, off by default) | code | same build, switch bit 5; it shares the download of Always Cut-In (`source` / `match` / `exclude` in `packed_mods.json` pick the files by a word in the file name) |
| Share Party Experience | code | same |
| Never Tired | code | same |
| Fast Start, Manual Skill Inheritance | game files | ordinary FILE MODS, instant on/off |
| Classroom Cheat Sheet, Social Link Cheat Sheet | game files | ordinary FILE MODS, in Mods > Cheats, off by default |

## Using it
1. On each row press DOWNLOAD. The first time, paste the mod's GameBanana page address (`https://gamebanana.com/mods/123456`); the launcher
   remembers it. (For a code mod you can also press FOLDER and drop its `.pnach` files in.)
2. Code mods only: press BUILD once. It makes ONE extra copy of the game that contains all downloaded code mods (about as long as the first
   game build, in Ubuntu, in the background). Run the installer once first (Setup > GET THE TOOLS) so the project has the mod switch patch.
3. Windows PC window only: after BUILD run `tools\p3fes_win_mod.bat` once, as before. Until then the PC window starts the normal game.
4. Turn mods ON or OFF on their rows, then press Play. No rebuild is needed to change what is on. With nothing on, Play starts the normal game.
   Add or remove a code mod later: press BUILD again.

## How the live switches work
A `.pnach` rewrites game code while the game runs on PCSX2. Our game is translated to C++ ahead of time, so the patches go into a copy of the
boot program instead, and the translator (`eerecomp --variants`) keeps **both** versions of every instruction a mod changes. While the
game runs, each changed place checks one number, `PS2_MODS` (bit k set = mod k on), and runs the matching version. A mod that is off costs one
test at the few places it hooks. Code that mods add in free memory (code caves) is always present but never reached while its mod is off.
Changes to data, and `patch=0` lines (such as "expand executable memory"), are written into memory at start-up when their mod is on.

- `tools/p3fes_pnach_apply.py --mod NAME:BIT=a.pnach[,b.pnach] ... --variants variants.txt` makes the program copy and the switch table. It
  understands `word`, `short`, `byte` and `extended` lines (`0xxxxxxx` = byte, `1xxxxxxx` = halfword, `2xxxxxxx` = word). Two mods that change the
  same instruction in different ways are refused (it names the place); in our six mods there are no such conflicts.
- `tools/ps2recomp_modswitch_patch.py` and `tools/ps2port_modswitch_patch.py` add the switches to the translator and `scripts/port.sh`.
- `tools/p3fes_packed_build.py` does the whole build (the launcher's BUILD button runs it; log in `~/.p3fes-packed-build.log`).
- The launcher passes `PS2_MODS` to the browser page (page address) and to the PC window (environment). An older build made before this
  (Direct Commands only, always on) keeps working until the first BUILD.

## Limits
- A code mod needs a BUILD before its switch exists; the row says NOT BUILT IN YET until then.
- If a mod's code is reached in a way the translator cannot see, the game stops with "missing code at 0x...": see "Troubleshooting" in
  [mods.md](mods.md) (Direct Commands needed one extra entry, `69ac94`, which the build adds by itself).
- Mods can only be used together if they do not change the same instruction. The tool checks this when it builds.
- The cheat sheets and Fast Start are game-file mods: their rows download the archive from GameBanana and add it to FILE MODS; the launcher
  has not seen those files yet, so whether each one fits the disc is shown on its row after the download.
