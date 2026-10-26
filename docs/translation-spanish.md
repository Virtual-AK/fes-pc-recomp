# Spanish text (launcher 0.50)

Settings > Audio > TEXT LANGUAGE: ENGLISH or SPANISH. Built 25 Oct 2026 from the community translation of Persona 3 FES by IlDucci, TraduSquare, Tio Victor and their team (v1.1b, NTSC-U and PAL).

## What the translation is

A patcher program (about 80 MB, Windows) that writes a new copy of the disc, named like the original with [T-Esp] added. It cannot be shipped by us and its authors ask not to share patched images, so the player makes the copy with their own disc and the launcher takes the files it needs from it (`tools/p3fes_translate.py`). Nothing of the translation is in this repository.

Compared with the USA disc (25 Oct 2026): three things differ.
- `DATA.CVM`: 1,373 files changed, 24 added (the subtitled videos, `SFD/P3CT*.STR`, which are not in the original image and are skipped), about 527 MB.
- `BTL.CVM`: 252 files changed, about 71 MB.
- The game program `SLUS_216.21`: about 71,000 bytes edited in about 186 places and a new 12 KB block (the translation's on-the-fly video subtitles and its text handling). This port is recompiled from the original program, so these changes are not used.

## What works (tested in game, PC window)

With the 1,387 files below, the game boots and plays: field and event dialogue with accents and the n with a tilde (the translation's own fonts, `DATA.CVM/FONT/FONT0-2.FNT`, are what make the letters show; without them accented letters appear as Japanese characters), the pause menu, Social Links, load and save screens, the Dark Hour clock, skill and item descriptions in battle, Shuffle Time, the support lines of the navigator, and battles that finish.

## What stays English, and why

Found by putting the files back in groups until the game booted (black screen = the game waits for a file it cannot read):
- Battle core files in `BTL.CVM`: `BATTLE/MSG.TBL`, `BATTLE/AICALC*.TBL`, `BATTLE/PANEL/BS_INIT.BIN`, `SND_BENC/PANEL/*BP_ALL.BIN`. Any of these gives a black screen at startup. They are loaded when the game starts and their size or layout changed with the translation's program.
- `BTL.CVM/BATTLE/RESULT/*`: the game freezes on the winner's pose and never shows the results screen.
- `BTL.CVM/BATTLE/CUTIN/*` (213 effect files): never tested in game; left out as they hold no text.
- `DATA.CVM/OPED/*` (title screen) and `DATA.CVM/SFD/*` (videos): not tested; left out as the title and videos need the translation's program.

So the battle command menu (Skill, Persona, Item, Tactics), the results screen, the title screen and the video subtitles are English.

## Choosing the files

`p3fes_translate.keep()`: everything that changed in `DATA.CVM` except `SFD/` and `OPED/`, plus 22 named files of `BTL.CVM` (`BTL_KEEP`). The test `tests/test_translate.py` uses a small made-up disc. The same list was checked against the real files: it gives exactly the 1,387 files that were played.

## Using it with other mods

Spanish and the Japanese Dub are both file mods; where they change the same file the one higher in the priority order wins (not tested together). The translation's own readme says the full patched disc is not compatible with existing mods; ours only borrows the data files, and Manual Skill Inheritance, Direct Commands and the others still apply (not yet tested together with Spanish).

## If we want the rest

The full translation needs its game program. That means recompiling a second copy of the game from the Spanish program (like a mod variant) and keeping the Essential Mods in step with it. Not planned for now.
