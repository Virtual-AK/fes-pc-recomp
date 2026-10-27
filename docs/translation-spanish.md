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

## The rest: the Spanish game program (0.53)

The translation also changes the game program (`SLUS_216.21`): the layout and text tables of the title screen, the battle command menu, status and results screens and item names. Those screens only work with that program (the original one freezes or stays black), so 0.53 turns the program's changes into a switchable Essential Mod.

- `p3fes_translate.py --program ORIG.iso PATCHED.iso OUT.pnach` compares the two programs word by word. Words in 0x100000-0x5B0000 and the new routines at 0x685BC0-0x685C80 are instructions (`patch=1`, switched with the mod); every other changed word is a value (`patch=0`, written at start-up while the mod is on). Values are never `patch=1`, because instruction words are baked into the patched program for good.
- Left out: the translation's own video subtitles (10 instruction words that point at its movie list, the new code from 0x7C8DA4 and the 12 KB block above 0x7C0000). This port draws its own subtitles (docs/subtitles.md). If an instruction jumps into new code that is not that one block, or the count of changes is far off (more than 40,000), the tool refuses: it is another version of the translation.
- Also left out: a table value that points into the translation's movie list (the 12 KB block at 0x9ACC80), e.g. the word at 0x5CE944. With it written, the game's own movie code read garbage and the window closed at once (first test, 26 Oct 2026: `missing code at 0x3C020086` through a callback slot at 0x78F760). `PROG_VERSION` in `p3fes_translate.py` is written into the patch file so the launcher makes it again after such a change.
- Also left out: the game's file table (about 13,800 changed words). The program keeps a table of its files (size, 0, start sector, two bytes, name; found by the names, `_table_region`) and reads files from those numbers. The translation's copy holds the numbers of its own disc, so taking it made the game read wrong sectors and load garbage over its own variables (second test: still `missing code at 0x3C020086`, ra 0x540E84, with the movie pointer already removed). Files that grew are moved and their table entries poked by the existing file-mod code (`table_pokes`), which stays the only thing that changes the table. If the table cannot be found (fewer than 1,000 entries) the tool refuses. The 0x7CA000-0x7CE000 words (layout floats, a few text pieces) are real data, only 0x7C0000-0x7CA000 (new video code) and everything from 0x7CE000 (movie list) are left out.
- Test results (26 Oct 2026, in game): the program mod alone works and makes the item names, Tactics, locations and the memory card screen Spanish. Laying the translation's extra files (`BATTLE/RESULT/*`, `SND_BENC/PANEL/*`, `MSG.TBL`, `AICALC*`, `OPED/*`) over the disc did not help: all together the window stays black; RESULT alone boots but the game never reaches the results screen after Shuffle Time; the others alone boot and change nothing visible. The likely reason is the file table: the translation's table has 24 more entries, the movies moved out, and most entries shifted, and the Spanish program was made for that layout. So the launcher no longer makes or lays these files (`spanishcore` is ignored). Still English: title screen, command wheel, Advantage / 1 More, results and status screens, skill names.
- The launcher (`es_core`) writes the result to `C:\p3fes\packed\spanishprog\esp_program.pnach` (hidden code mod `spanishprog`, switch bit 23, `"follows": "spanish"`, `strict` and `weak` in `packed_mods.json`) (the extra files `p3fes_translate.extract(..., core=True)` can still pull out are only for research).
- The program mod is on while TEXT LANGUAGE is SPANISH and its patch file exists. With ENGLISH nothing changes.
- Check done offline (real discs): 502 of 502 original-word comments match, no conflict with Direct Commands, Modern Persona Switch, Always Cut-In, Share Party Exp, Never Tired, Manual Skill Inheritance or the widescreen parts. Not yet tested in the game: the build, the new entry points (116 found; a "missing code at ..." stop would need an `extra_entries` line) and each screen.
- What the player does: press SPANISH once (or SET UP ESSENTIAL MODS if Spanish was set up before 0.53), wait for the rebuild, play. If it freezes, the launcher can go back by choosing ENGLISH, which switches the program off.

## The battle, title and result screens, and the prompts (0.54)

The translation's own copies of these files cannot be laid over the disc (they move things around for the translation's program). Instead the original file is kept byte for byte and only the parts that hold Spanish text or Spanish art are replaced, without changing any size or layout. `tools/p3fes_spanish_battle.py` (original disc + Spanish copy -> a mod folder):
- `BATTLE/MSG.TBL`: skill, passive and item names (in the name slots, only up to the "MSG1" header; writing past it corrupted the message pointer table and blanked the All-Out Attack "Atacar" label), the All-Out Attack prompt and every battle message that fits its slot (133 of 285); `BATTLE/AICALC.TBL`, `AICALC_F.TBL`: boss and enemy lines (139 of 220).
- `SND_BENC/PANEL/*BP_ALL.BIN`, `BATTLE/PANEL/BS_INIT.BIN`, `BATTLE/RESULT/BR_*.BIN`, `BRP_BASE.BIN`, `BRP_SYSMSG.BMD`, `BR_LEVEL.BIN` and the fusion room's `FCL_COMBINE.PAK` copies: pictures one texture at a time (only where the size is the same; a few sprite rectangles are widened, `GEOMETRY`) and message files re-fitted (`fit_bmd`: messages matched by name, a few shortened by hand in `BMD_SHORT`, padded to the exact original size).
- `DATA.CVM/OPED/OP_TITLE.BIN`: the title menu is one sprite (`DATA/AGS_I_TITLE_SPR01.SPR`); the translation's is smaller (it drops the Japanese descriptions) so it is written at the start of the old one's room and the rest is zeroed.
- Left out on purpose: `BP_TUTORIAL.BIN` and `SFL_BASE.BIN` messages from the battle screens layer (a freeze after Shuffle Time was suspected earlier; it does not freeze, and Shuffle Time is Spanish through the translation itself, tested 26 Oct 2026), the "Reflect" picture (texture size differs). The staff roll (`ED_SR.BIN`, `ED_SR_F.BIN`) is made from the original: the translation's own version has bigger fonts and a longer script that do not fit the container, so only the job titles are replaced in the original script (`tools/p3fes_spanish_staff.py`): same lines, same layout, same size, plain letters because the original fonts have no accents, some abbreviations. Names stay. Not seen in game (it only plays after the ending).
- Long lines: boss/enemy lines (`AICALC*.TBL`) and battle messages (`MSG.TBL`) whose Spanish was longer than the English slot use a hand-shortened wording from `tools/p3fes_spanish_text.py` (165 lines; they have to fit the old slot because the game walks from message to message by the size field). Two sets of accented letters exist (help lines and dialogue); the module picks the right one.
- Tactics: the game program mod used to write Spanish pointers into the Tactics table; Direct Commands moves that table by one slot, so "Act Freely" stayed English. The program patch now writes the Spanish names over the English strings (16 bytes apart; "Ir por caídos" and "Asig. objetivo" are shortened to fit) and leaves the pointers alone (`PROG_TACTICS`, `PROG_VERSION` 4).

Button prompts follow the same rule: the translation replaces many of the pictures the Button Prompts mod redraws (menus, shops, Velvet Room, save/load, Shuffle Time), and a translation has priority, so the PlayStation buttons came back. `tools/p3fes_spanish_prompts.py` finds the icons in the Spanish copies of those pictures (searching with the original's icon cut-outs, `scan(..., template_root=...)`) and redraws them with the current style, keys and buttons; only files the translation really changes are written.

In the launcher (`es_layers_sync`, called after setting up Spanish, after every change of Button Prompts and before every Play) these become two hidden file mods, `spanishbattle` (top priority) and `spanishprompts`, made on the player's PC and kept in `C:\p3fes\mods`. `lm_rebuild` always puts them above every other mod and applies them only while the Spanish mod is on. They are made again when the prompts' style, keys or controller (AUTO), the original disc or the Spanish copy change (a signature in `C:\p3fes\prompts\es_layers.json`); the Spanish pictures are read out of the Spanish disc once into `C:\p3fes\prompts\src_es` (about 110 MB) and the icon search is kept in `hits_es.json`. Tested in game (26 Oct 2026, keyboard) as hand-made test mods first: every screen above showed the right prompts and Spanish text.

Known gaps: textures whose size differs in the Spanish file (some shop and save/load rectangles) are searched again by picture, so check them; the prompts for Start/Select, L2/R2 and the Square STATUS prompt are the same open items as in English.

The start-up logo screen (OP_LOGO.BIN) gets the translation's CRI/ADX logo picture, the one with the translators' credits. It has the same size as the original, so it is swapped in place.
