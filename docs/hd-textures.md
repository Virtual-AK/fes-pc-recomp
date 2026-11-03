# HD textures (PC window)

Swaps the game's 2D pictures for the HD ones of community mods while you play. Works in the Windows PC window only.

## What is covered (0.56)
- **High Quality Portraits** (GameBanana): the character portraits in dialogue, the Command, Status and Social Link screens: 487 dialogue portraits (BUSTUP), 38 emotion pictures, 49 Social Link portraits and 12 menu pictures. 9 of the pack's 595 pictures have no match (three Aigis, two Junpei and one Igor picture whose disc textures are already taken by a better match, a faded copy of the protagonist, a Shinshoudo ghost picture and the Social Link static card); those stay in normal quality.
- **P3HD Enhanced Persona Artwork**: the Persona pictures (Persona compendium, party status): 180 pictures.
- **P3HD Widescreen** (GameBanana, folder name starts with `widescreen`): 85 pictures that are the game's own pictures in HD: 38 menu and UI pieces (shop, fusion and Social Link menus, number sheets, banners, arcana lists), 8 Emotion pictures (some the portraits pack lacks, such as Koromaru), 5 cut-in pictures, 2 Shuffle Time cards and 2 title-screen pictures. Its other pictures are not used yet: they were redrawn for the wide layout (party panel, field, most of the title and button prompt pictures), so they are not the same picture as the game's own and need a separate step.

Not covered yet: the navigator faces (no disc picture was found for them), the rest of the widescreen pack (the pictures redrawn for the wide layout), the sprites that come as PNG, the blinking sprites, and the 3D textures.

## Set up
1. Download the mods from GameBanana and put each mod folder in the `hdmods` folder next to the launcher (for example `hdmods\hq_portraits_11efb`, `hdmods\p3hd_enhanced_persona_artwork` and `hdmods\widescreen_e645d`). The folder names only need to start with `hq_portraits`, `p3hd_enhanced_persona_artwork` and `widescreen`.
2. Run `p3fes_install.sh` (it applies `ps2run_hdtex_patch.py` to `~/ps2-web-recomp`), then build both Windows programs: `build_win.bat game` and `p3fes_win_mod.bat`.
3. Settings > Display > HD TEXTURES > ON. The line under the buttons says how many HD pictures it found.
4. Press Play. The window log (`~/.p3fes-window.log`) has `[hdtex] N pictures in the table` (N is what your folders give) and one `loaded` line per picture used, then `used ...` lines that say where each HD picture was first drawn.

A picture appears in HD a moment after it is first needed (the HD file is decoded in the background); until then the original shows, so the first time a portrait appears it may switch once. To shorten that, the window remembers which pictures you use most in `hdtex.map.hot` (next to the map; one line per picture: hash and count) and decodes the top 24 when the game starts, so they are ready before a screen opens. Several pictures decode at once (up to three threads), and one the game is drawing with goes first. Preloads only fill free space and are the first to be dropped. The first session has nothing to preload; delete `hdtex.map.hot` to start over. Do not commit it. If a picture is drawn while it is still decoding, the window waits for it (at most 150 ms per frame, logged as `waited for ... (N ms)`) rather than showing the original for a few frames; if it takes longer, the original shows until it is ready (`drawn before it was ready`). When the game re-uploads a picture over one that is already HD, the HD copy is kept until the upload finishes (then it is adopted again if it is the same picture, dropped if not), but only for a picture the game has already re-sent to that same place at least once (a menu drawn again and again). A picture sent once is dropped as soon as anything is written over it, and any picture is dropped at once if something was drawn into its memory.

## How it works
- The game uploads each picture to the graphics chip's memory. The patch hashes every large upload (64-bit, over the pixels as the game uploads them) and looks the hash up in a list.
- The list (`tools/hdtex/hdtex-table-ntscu.tsv`, one line per picture: hash, size, how the HD picture is placed inside the original frame, which pack and file) was made by comparing every HD picture with every texture of the disc. It holds hashes and file names only, no game data.
- On a hit the HD file (DXT1/3/5 or BC7 .dds) is decoded on a worker thread, scaled down to at most 1024 pixels, and kept in a cache on the graphics card. When the game draws with that texture the shader reads the HD picture instead, with the stored scale and offset. A picture the game changes in memory afterwards is dropped, so it never shows a wrong one.
- The decoder is bit-exact against the mods' pictures (tested on all four formats).

## Settings (environment, Display settings do the same for normal use)
- `PS2_HDTEX=<map file>`: turn on; the launcher writes the map next to the p3fes folder (`hdtex.map`) and sets this.
- `PS2_HDTEX_MAX=<256..2048>`: biggest picture size kept (default 1024).
- `PS2_HDTEX_MB=<16..2048>`: graphics memory for HD pictures (default 192 MB, 47 pictures of 1024 x 1024 at once).

## If something looks wrong
- No `[hdtex]` line in the log: the PC window was built without the patch. A patch applied only to `winbuild` is overwritten by the next `build_win.bat`; apply it to `~/ps2-web-recomp` (the installer does).
- `no pictures`: the map is empty; check that the mod folders are in `hdmods` and the Display page shows a count.
- A menu or title picture shows for a moment over something that is not a menu (a gold lamp turns black or white for a frame or two, a floor flashes): the picture's index data matches a 3D texture, or the game uploads a 3D texture over the memory of a one-off picture. The log lines `used ... (texture at block ..., sent once)` and `dropped ...` name the picture; the cure is to take it out of `tools/hdtex/hdtex-table-ntscu.tsv` (one line). The swap compares only the index data, not the colour palette, so a flat or nearly flat 4-bit picture can match a model that is coloured by its palette. Left out on purpose for this reason: `Widescreen\UI\b3d82a2066fc2ede...` (floor flash in the Lovers fight), `Widescreen\TITLE\4d39dabedfe2a439...` (pure black), `Widescreen\UI\90138a0ebb5961c3...` and `...\90cb0705d6d4da5a...` (nearly black), and `Widescreen\UI\8f3afc0f4d213205...` and `...\aa3534e2a37f34e6...` (dark 4-bit panels that flashed black over the wall panels in the Hierophant room).
- Wrong or shifted picture: turn HD TEXTURES off, and tell us which screen (the placement of the Persona pictures was fitted by a computer).

## Tools
`p3fes_hdtex.py` (map builder), `p3fes_texhash.py` and `ps2run_texlog_patch.py` (research: log and check the hashes of the game's uploads). `tests/test_hdtex.py` checks the table, the map builder and the launcher switch.

## Button prompts in the battle menu
The wheel sheet, its icon sheet and the RUSH strip of the P3HD Widescreen pack show the PlayStation triangle. The HD swap finds a picture by what is in the game's sheet, so redrawing the button in the sheet would break the match. With HD textures on, the launcher therefore leaves those three sheets alone and `tools/p3fes_hdprompts.py` draws the key (or Xbox / Switch button) into a copy of each HD picture, kept in the `prompts/hd` folder next to the saves; the map uses these copies first. Your pack folders are never changed. Turning HD textures off redraws the button in the small sheets again.
