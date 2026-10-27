# Essential mods (called Packed-In Mods before 0.40; launcher 0.29)

Mods > ESSENTIAL MODS lists community mods with an ON/OFF button each, and Mods > CHEATS lists two cheat sheets (off by default).
Nothing from these mods is in this repository: the launcher downloads each one from its author's GameBanana page onto your computer
(`C:\p3fes\packed\<mod>\` for the patch files, FILE MODS for the file mods), and the author is credited and linked on its row.

| Mod | Kind | How it works |
|---|---|---|
| Direct Commands | code (.pnach) | built into the shared mod build, live switch |
| Modern Persona Switch | code | same |
| Always Cut-In (the Always Cutins file) | code | same |
| Always Critical (the Always Critical file, a cheat in Mods > Cheats, off by default) | code | same build, switch bit 5; it shares the download of Always Cut-In (`source` / `match` / `exclude` in `packed_mods.json` pick the files by a word in the file name) |
| EXP Increase (a cheat, off by default; bundled: the patch text is in `packed_mods.json`, no download) | code | switch bit 22. Replaces the last five words of the battle EXP function (001fbf68 to 001fbf78): result x the number at 00007000, capped at 65535. The strength (3, 5 or 10) is written to 00007000 at start-up by `PS2_POKE` (`levels` / `level_addr` in `packed_mods.json`); the value kept in the patch is the default for a page that passes no poke |
| Spanish game program (hidden, made on the player's PC from the two discs, never shipped) | code | switch bit 23, `"follows": "spanish"`, `strict` (its start-up values apply only when it is on) and `weak` (where another mod changes the same word, the other wins). On while Settings > Language > TEXT LANGUAGE is SPANISH and the hidden file mod `spanishcore` exists; see docs/translation-spanish.md |
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


## Bundled cheats (0.39)

A registry entry with `"pnach"` holds its patch text itself; `p3fes_packed_build.py` writes it to `games/p3fesmod/bundled_<id>.pnach` and bakes it like a download. Entries with `"levels"` (value, label, 32-bit hex poke) get a strength picker in Mods > Cheats; the launcher keeps the choice in `packed.level` of its settings and adds `ADDR=VALUE` to `PS2_POKE` (PC window and page address) for every such cheat that is built in and on. The cells at 00007000 and 00007004 are in low memory, which the game and the runner never use (zero in every memory dump taken so far); the patch lines for them make the build add them as a small block of new memory.
Untested in the game when written (24 Oct 2026): both patches were checked against the boot program (all original words match) and through the patch tool (no clash), not played.

## One button (0.41)

`/api/packed/build` now starts `essentials_work()` in the launcher: (1) downloads each non-cheat mod that has a GameBanana number (the player's link, else `"gb"` in `packed_mods.json`) and is not there yet; (2) runs `p3fes_packed_build.py` if a code mod is not in the build; (3) when the PC window exists and its mod build is missing or older than the mods build, writes `_essentials_win.bat` next to the saves (`call vcvars64.bat` from the Build Tools that `vswhere` finds, then `call tools\p3fes_win_mod.bat`) and runs it with `cmd.exe`. All output goes to `~/.p3fes-essentials.log`; the page shows `auto` from `packed_state()` (busy, step, last line, what is left). Nothing about the game is shipped: the generated code is still made from the player's disc.

## Voice language (0.49)
The Japanese Dub (GameBanana 292547) is a hidden `files` entry (`undub`) of `packed_mods.json`: it has no row in Essential Mods, is not part of the one button (about 500 MB), and its file mod is hidden from FILE MODS and its page from BROWSE GAMEBANANA like the other built-in mods. Settings > Audio > VOICE LANGUAGE calls `/api/dub` with `lang` `ja` (downloads it the first time, then switches the file mod on) or `en` (switches it off). The mod uses the Aemulus layout (`DATA/SOUND/V*.AFS`, `BTL/...`), which the file-mod planner already maps (`DATA` means `DATA.CVM`); all 505 files fit the NTSC-U disc.
