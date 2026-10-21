# Plan: loose-file mods ("mod folder") for the recompiled game

Most Persona 3 FES mods are not code patches. They are loose files laid out like the extracted CVM archives (a file from
`DATA.CVM/INIT/` goes in `DATA/INIT/` in the mod), and mod tools such as Aemulus apply them either through a PCSX2 HostFS
code patch or by rebuilding the CVMs and the disc image. (Source: the ShrineFox
[P3 FES PS2 mod support page](https://docs.shrinefox.com/getting-started/persona-3-fes-ps2-mod-support).) Our `.pnach`
route (docs/mods.md) covers only the code patches. This note is what it takes to cover the loose files.

## What I found in the runner (ps2-web-recomp, tested version)
- Every disc read goes through one function, `disc::read(sector, count, out)` in `runtime/src/disc.cpp`. The four callers
  (`cdvd.cpp` file reads and sector reads, `cdvdfsv.cpp` reads to EE and IOP memory) all use it.
- The runner only indexes the outer disc file system (`disc::find`). Files inside the CVMs are found by the game itself,
  which reads the CVM's own directory and asks for absolute sectors.
- So the runner never sees a file name for CVM contents. It sees sectors.

## Proposed design: a sector overlay
1. At start the runner (or the launcher, before start) reads the CVM directories (we already parse them in
   `p3fes_cvm.py`) and, for each file in the mod folder, works out the absolute start sector and size of the file it replaces.
2. It builds an overlay: a list of "sectors N to M come from this mod file instead".
3. `disc::read` applies the overlay on top of the normal read. The disc image is never changed or copied.
4. A replacement file larger than the original does not fit in place. The overlay then serves it from extra sectors
   placed after the end of the image, and also patches the CVM directory sector so the game is told the new start and size.
   This is the part to test first: it only works if the game does not check sector ranges. Replacements the same size or
   smaller work in place.
5. Several mods: later ones win for the same file. The launcher lists them in order.

## What it does not cover
- Mods that merge into game tables (Aemulus merges `.bf`, `.bmd`, `.pac` contents). The first version replaces whole files only.
- Code patches: still `.pnach`, still a separate build.
- Streaming music and movies in `BGM.CVM` and the outer files: same overlay works, but a big replacement means a big file.

## Steps
1. Prototype in the runner with one same-size replacement (for example a text or texture file), confirm it shows in game.
2. Test a larger replacement (the relocation case).
3. Launcher: Mods > Add a mod accepts a folder or zip, lists files it will replace, checks each against the CVM directory.
4. GameBanana browsing, after the above (check their terms and the P3 FES section first).

Needs: someone to build and test on a real install (the build takes about 10 minutes), and a small mod to try.

## Result of the first test (19 October 2026)
- `tools/p3fes_modmap.py` found every file of a text-edit mod on the real USA disc (115 files, all the same size as the originals, in the big archives and inside containers) and `apply` wrote a modified copy of the image.
- The browser game, run from that copy, showed the changed menu text in classroom 2-F ("MOD" for "Yes" at a student's question, "MOD WORKS!!" for "Don't enter" at the men's room). So the mapping is right and the game takes in-place replacements without any other change.
- Things learned: (1) a resumed autosave never shows a mod, because it brings back the game's memory including the old script text: start from Load Game; (2) the first guess at which script held those two prompts was wrong, so a whole-folder change was the quick way to find them; (3) text such as the "Classroom 2-F" label is not in the extracted text at all.
- Not yet tried: a replacement larger than the original (step 2 above), the overlay in the runner (so no 4.5 GB copy is needed), and non-text files (textures, models, music).

## Result of the relocation test (19 October 2026)
- `p3fes_modmap.py movetest` moved 8,589 whole files (407 MB, each under 256 KB) to the end of a copy of the USA image and pointed their directory entries there. The browser game ran normally from that copy (Load Game, walking, menus). So the game follows a moved directory entry and does not check that a file lies inside its archive's range.
- This means a whole file bigger than the original can be supported. Files inside containers (.PAC/.BIN) still cannot grow; that needs the container rebuilt.
- Next: a real bigger-than-original file, then the runner overlay.

## Overlay without a runner change (19 October 2026)
- The browser game reads the disc over HTTP from `scripts/serve.py`, so the overlay is applied there. `tools/ps2web_serveovl_patch.py` adds `--overlay mods.ovl` to serve.py: reads that touch a listed position get the mod's bytes, the rest comes from the untouched image, and moved files make the served disc longer. No C++ change, no rebuild; the patch is part of the installer.
- The launcher passes `--overlay` when `C:\p3fes\mods\active.ovl` exists (and restarts the server when it changes).
- The PC window (ps2run) still reads the image file directly; it needs a small change in the runner's disc reader to apply the same file (not done).
- Tested on the real disc: the relocation test as an overlay (`movetest -o active.ovl`, 400 MB, no image copy) played normally through the launcher's Play in browser.
- Launcher: Mods > FILE MODS adds a folder or zip, finds the game folders (DATA, BTL... with or without `.CVM`, inside a wrapper folder), reports how many files fit, and keeps ON/OFF/REMOVE state in `mods/mods.json`; the enabled mods are merged into `mods/active.ovl` (tests/test_launcher_filemods.py).
- Mod-manager layout (found with the first real mod, a portrait pack for `BTL/SND_BENC/PANEL/AGS2_BP_ALL/data/AGS2_i_b_face03/AGS_i_b_face03a.tmx`): a container is a folder without its extension (`AGS2_BP_ALL` for `AGS2_BP_ALL.BIN`), the entry path follows (`data/...`), and a `.SPR` entry is a folder holding its textures. A `.SPR` starts `01 00 00 00 00 00 00 00 "SPR0"` and holds `.TMX` textures back to back (`TMX0` 8 bytes into each); modmap finds them by scanning and names them by the letter the mod gives them (`...a.tmx` is the first, `...b.tmx` the second). That letter rule is a guess from this one mod: test in game. Textures keep their size, so they are replaced in place.
- Growing files inside containers (needed by the portrait mod: its textures are 65,600 bytes, the originals 17,472, i.e. 32-bit instead of 8-bit with palette, same 128x128 size): when any file inside a container grows, modmap rebuilds the whole container from the original plus every edit to it (all enabled mods together), using `p3fes_patch.py`'s container reader (entries sit at an alignment; if the container does not show which, the smallest fitting one is used), and moves the container to the end of the image like any bigger whole file. Textures inside a `.SPR`: the sprite file is rebuilt with the textures at their new places and any header value that pointed at a texture start/end or at the file size (minus 4) is moved to match. Unverified in game: whether the game accepts the bigger container and the rebuilt `.SPR`.

## Result of the portrait mod tests (19 October 2026)
- Red-portraits test mod (made from the disc itself with `p3fes_modmap.py tint`): same-size textures inside `.SPR` inside `BP_ALL.BIN` etc. show in game (all portraits red). So the targeting, the `.SPR` texture search and in-place writes are right.
- The same test made 16 bytes bigger (archive rebuilt and moved to the end of the image): portraits stayed normal. The server's read logs (`active.ovl.log`, `.reads.log`; `p3fes_modmap.py reads`) show why: at battle load the game reads the three `BP_ALL` archives from their ORIGINAL positions, although the directory entries were changed (the moved copies were only touched once, earlier). So the game gets file positions from somewhere other than the directory records we patch for these archives, and relocating (whole files or rebuilt archives) does not reach it. In-place writes always work.
- So files must fit where they are. For the portrait mod (32-bit 128x128 textures, 65,600 bytes; the originals are 8-bit with a 256-colour palette, 17,472 bytes) modmap now converts such a texture to the original's 8-bit form (the original's header, a 256-colour palette made from the mod's colours by median cut, one index per pixel; palette order read off the original) and writes it in place. The relocation code is kept but only used when a file cannot be converted; it is unproven.
- First real result: the portrait mod's art shows in the battle HUD after the 256-colour conversion. A first version (plain median cut per pixel) left a dotted fringe on the soft outlines; the colour reduction now works on distinct colours weighted by frequency, with alpha snapped to steps of 8, transparent pixels given the outline colour, and one k-means step (synthetic portrait test: error 20 -> 4). Still open: the 22 menu portraits of the same mod in `DATA.CVM/CAMP/PTYPNL.PAK` have Japanese file names inside the archive and are skipped.

## Status after the portrait mod (2026-10)
- Works in game: in-place replacement, including 32-bit textures reduced to the original's 8-bit form (battle portraits and menu portraits, 76 of 76 files).
- Entry names: container entries with Japanese names match on their ASCII part; SPR entries named `X_SPR.SPR` match mod folders called `X`; the a/b texture letter is found even when a Japanese tail follows it.
- Quantizer: alpha under 12 becomes fully transparent, faint edge pixels share one colour, alpha steps of 16 on the soft edge. Remaining speckle is the 256-colour limit.
- Still unproven in game: relocating a file or rebuilding a container (the game ignores moved BP_ALL archives). Used only when a file cannot be converted.
- Since added in the launcher: 7z/rar, Aemulus-style merges with priority, GameBanana browsing. File mods in the PC window (ps2run): `tools/ps2run_overlay_patch.py` adds `--overlay mods.ovl` to the runner's disc reader (`disc.cpp`): same .ovl file, same rules (listed positions come from the mod, the rest from the untouched image, moved files make the disc longer). Checked with a small test program on a synthetic disc and overlay (a change inside a sector, one beyond the end of the image, one at a sector edge); the launcher passes it when `active.ovl` exists. **Tested on a real PC (20 October 2026):** the in-battle portraits mod (76 files) shows up in the PC window and the launcher reports that file mods are on. The launcher asks `ps2run.exe` for its usage text to know whether the build supports `--overlay` (searching the file for the switch missed it). PC autosaves are kept per build only, not per mod set, so resuming a state made before a mod change loads old data already in memory.
