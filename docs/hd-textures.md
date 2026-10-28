# HD textures (PC window)

Swaps the game's 2D pictures for the HD ones of community mods while you play. Works in the Windows PC window only.

## What is covered (0.56)
- **High Quality Portraits** (GameBanana): the character portraits in dialogue, the Command, Status and Social Link screens: 487 dialogue portraits (BUSTUP), 38 emotion pictures, 49 Social Link portraits and 12 menu pictures. 9 of the pack's 595 pictures have no match (three Aigis, two Junpei and one Igor picture whose disc textures are already taken by a better match, a faded copy of the protagonist, a Shinshoudo ghost picture and the Social Link static card); those stay in normal quality.
- **P3HD Enhanced Persona Artwork**: the Persona pictures (Persona compendium, party status): 180 pictures.

Not covered yet: the navigator faces (no disc picture was found for them), the widescreen pack, the sprites that come as PNG, the blinking sprites, and the 3D textures.

## Set up
1. Download the mods from GameBanana and put each mod folder in the `hdmods` folder next to the launcher (for example `hdmods\hq_portraits_11efb` and `hdmods\p3hd_enhanced_persona_artwork`). The folder names only need to start with `hq_portraits` and `p3hd_enhanced_persona_artwork`.
2. Run `p3fes_install.sh` (it applies `ps2run_hdtex_patch.py` to `~/ps2-web-recomp`), then build both Windows programs: `build_win.bat game` and `p3fes_win_mod.bat`.
3. Settings > Display > HD TEXTURES > ON. The line under the buttons says how many HD pictures it found.
4. Press Play. The window log (`~/.p3fes-window.log`) has `[hdtex] 665 pictures in the table` and one `loaded` line per picture used.

A picture appears in HD a moment after it is first needed (the HD file is decoded in the background); until then the original shows, so the first time a portrait appears it may switch once. To shorten that, the window remembers which pictures you use most in `hdtex.map.hot` (next to the map; one line per picture: hash and count) and decodes the top 24 when the game starts, so they are ready before a screen opens. Several pictures decode at once (up to three threads), and one the game is drawing with goes first. Preloads only fill free space and are the first to be dropped. The first session has nothing to preload; delete `hdtex.map.hot` to start over. Do not commit it. If a picture is drawn while it is still decoding, the window waits for it (at most 150 ms per frame, logged as `waited for ... (N ms)`) rather than showing the original for a few frames; if it takes longer, the original shows until it is ready (`drawn before it was ready`). When the game re-uploads a picture over one that is already HD, the HD copy is kept until the upload finishes (then it is adopted again if it is the same picture, dropped if not); a picture is dropped at once if anything was drawn into its memory.

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
- Wrong or shifted picture: turn HD TEXTURES off, and tell us which screen (the placement of the Persona pictures was fitted by a computer).

## Tools
`p3fes_hdtex.py` (map builder), `p3fes_texhash.py` and `ps2run_texlog_patch.py` (research: log and check the hashes of the game's uploads). `tests/test_hdtex.py` checks the table, the map builder and the launcher switch.
