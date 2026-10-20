# Launcher (first version)

An app window for the game, drawn to match the design in the launcher design spec. It is a small local server
(`tools/launcher/p3fes_launcher.py`) plus an Edge or Chrome window with no address bar, so nothing extra is installed.

## Start it
Double-click `tools\launcher\launch.bat` (after the installer has run once). Closing the window stops the launcher.
Or, in Ubuntu: `python3 tools/launcher/p3fes_launcher.py` (add `--no-window` and open `http://127.0.0.1:8630/` yourself).

## What works now
- **Home screen** in the game's blue, with the real state: Ready, Not Installed, Building (counts finished pieces), Wrong Disc (shows region, game ID and contents checks).
- **Disc check** reads only the `SYSTEM.CNF` line and the file size. A disc counts as wrong if the game ID is not `SLUS_216.21`, or the file is shorter than the disc says, or it cannot be read, or its file name contains "modded".
- **Play**: starts the browser server and opens Edge (or Chrome), or starts the PC window build if it exists. **Play in** switch: Browser or PC window (keys Q and E), remembered in `~/.p3fes-launcher.json`.
- Keyboard: arrows, Enter, Q and E, Esc. The mouse works too.

**PC window needs a display.** On WSL2 the launcher uses WSLg (and tries OpenGL on the card, which did not help on the first PC tested). On Windows 10 with WSL1 (no WSLg) start VcXsrv first, as in `windows-build.md` (display 0, Disable access control ticked). The launcher then sets `DISPLAY` and the SDL settings itself, and says so if no X server is found. This part is untested.

**Help** (getting started, default keys, troubleshooting, about with a copyable report) and **Settings**: *Controls* sets the PC window keys (click a row, press a key; saved in `~/.p3fes-keys.txt`; default K confirm, L cancel, same as the browser; a `keys.txt` in the game folder is ignored when started from the launcher), *Display* picks Edge, Chrome or the system default for the browser game, and its resolution (1x, 2x, 3x; default 3x, passed to the game as `?PS2_SCALE=`). *Memory Card* shows the shared card file (`C:\p3fes\saves\Mcd001.ps2`), how many backups are kept, and opens the folder; the browser game shares it after the installer has been run again (it updates the page, a few minutes). Controller and Autosave say "not connected yet": they live inside the browser game.

**Faster PC window:** see `better-window.md` (browser build resolution box, or WSL2 with WSLg for the graphics card).

## Not built yet
Starting setup from the window (the installer still runs in Ubuntu), choosing a disc from the window, a real "modified disc" check (needs a known-good checksum), file mods in the PC window, automatic detection of a finished Journey from the memory card, and a native Windows PC window (see `better-window.md`).

## Tested
Run on a real Windows 10 machine (Edge app window, Ubuntu on WSL1, later WSL2): home screen, settings and themes, saves, file mods (folder, zip, 7z, rar, merging and priority), portrait mods in the browser game, GameBanana browse and install. Not yet tested: a clean install on another person's PC, and GameBanana against pages with unusual file lists. Fonts load from Google Fonts when online and fall back to a plain font offline.

## Saves screen

Home > SAVES has three parts. AUTOSAVES says "not connected yet" (autosaves live inside the browser game and are untested across builds). MEMORY CARD shows the shared card file, when it was last saved, and an OPEN FOLDER button. BACKUPS lists the earlier copies in `saves\backups` (newest 10) with RESTORE and DELETE, each needing a second click to confirm. Restore refuses while the PC window is running, and keeps the card it replaces as a new backup.

### Autosaves in the launcher

The browser game now copies each autosave to `saves\autosaves\<build>` (and tells the launcher when one is deleted). The Autosaves screen lists them with RESUME (opens the browser game, then click "Resume autosave" on its start screen) and DELETE, and Home > RESUME opens the newest. Because they live in the folder, Edge and Chrome see the same ones. They only work with the build that made them; older ones are counted and ignored. Needs `ps2web_autosavesync_patch.py` (the installer applies it and updates the browser page, a few minutes). PC window autosaves are separate and untested.

## Setup from the launcher

On a computer with no game yet, Home shows SET UP. It opens the Setup screen with four steps: FIND YOUR DISC (a normal Windows file window, only a USA, unchanged disc is accepted), GET THE TOOLS and BUILD THE GAME (START SETUP runs `p3fes_install.sh` in its own window, where it may ask for the Ubuntu password once; the launcher shows the piece count and the last files compiled), then PLAY. If setup stops, CONTINUE SETUP picks up where it left off. Still needed before this works: Windows 10/11 with Ubuntu installed in WSL (see docs/install.md).

## Mods screen

Home > MODS lists Direct Commands (PLAY WITH THIS MOD when the `p3fesmod` build exists; it uses the browser or PC window as set on Home, and the shared memory card), the FEMC protagonist (in development) and the Reload style pack (concept), and ADD A MOD. ADD A MOD opens a file window for a `.pnach`, and checks it against the program on your disc with `p3fes_pnach_apply.py` (how many lines apply, whether the original-code notes match). Building the checked mod from the launcher is not done yet: see docs/mods.md.

## Mods > File mods
For mods that replace game files (text, images, sounds), the kind found on GameBanana. Press ADD A FOLDER or ADD A ZIP. The launcher unpacks the mod into `C:\p3fes\mods`, finds the game folders in it (DATA, BTL, ... even inside a wrapping folder), checks every file against your disc and says how many fit. Each mod can be switched ON or OFF and removed. The enabled ones are merged (a later mod wins for the same file) into `C:\p3fes\mods\active.ovl`, which the browser game's server lays over your disc when you press Play. Your disc is never changed. Files that are bigger than the original are moved to the end of the image automatically; a bigger file inside an archive (.PAC/.BIN) is skipped and listed. The PC window does not use file mods yet. It needs the one-time server update (Setup > GET THE TOOLS, or `bash p3fes_install.sh --patches-only`).

### Archives for file mods
ADD A ZIP / 7Z / RAR accepts .zip (opened by Python), .7z and .rar (opened with 7-Zip, unrar or bsdtar when installed; p7zip-full is already part of the installer, rar needs `sudo apt install p7zip-rar`). The type is read from the file's first bytes, not its name. After unpacking, links and paths that leave the folder are refused, and the unpacked size is capped at 4 GB.

### Merging mods (Aemulus-style)
- Order: the list shows the highest priority on top. A new mod goes on top; the ▲ button raises a mod one place. Where two mods change the same thing, the one higher in the list wins.
- A mod that ships a whole container (a `.BIN`, `.PAK` or `.PAC` of the same size and layout as the disc's) is split into the entries that differ from the disc, so another mod can change other entries of the same container and both apply. If the layout differs, the whole file is used as before.
- Overlapping writes (a whole file from one mod, a single entry from another) are resolved byte by byte in priority order before the overlay is written (`flatten` in `p3fes_modmap.py`).
- The "files fit" count counts changed entries for a whole container, so it can be larger than the number of files in the mod.
- Not done: merging text tables (`.tbl`) and scripts (`.bf`, `.bmd`) line by line, which needs format-specific tools.

### Mods > Browse GameBanana
Lists the Persona 3 FES mods on GameBanana (game id 8502, public API `gamebanana.com/apiv11`) with NEWEST / MOST LIKED / MOST VIEWED, SEARCH (name, author or type), PREV / NEXT and REFRESH. PREVIEW opens the mod's page in the launcher first: its pictures, description (as plain text), version, and every file it offers (file names, sizes, notes) with the supported ones (`.zip`, `.7z`, `.rar`) selectable. Nothing is downloaded until INSTALL SELECTED FILE is pressed. That downloads the chosen file (max 2 GB) straight from gamebanana.com and runs it through the normal FILE MODS add flow, so it appears there and can be turned on, off, raised in priority or removed. The list is read from the site when the screen opens and cached in memory for 15 minutes; nothing is stored or shipped by us. Downloads only follow addresses on gamebanana.com. Mods that only ship other file types (an .xdelta, an .exe, an ISO) are reported and not added. Not verified against the live API from the build machine: if the list shows an error, send the message shown.

### Themes
Settings > THEME switches the launcher between BLUE (the original), PINK and RELOAD (electric cyan, colours only, nothing taken from the game). The choice is kept in the launcher settings file and applied on start. Colours live in `:root[data-theme=...]` blocks at the top of `ui/index.html`, so another theme is one more block plus its name in `/api/theme` and the THEME panel. The FEMC protagonist mod is meant to switch to PINK when it ships.

Six themes in all: BLUE, PINK, RELOAD, MOON (indigo and gold), DAWN (cream and peach) and SEAL (white and ice blue). All are always available; a "finished The Journey" unlock was dropped. DAWN and SEAL are light themes: they use `--fg` for text on the light background, and selected menu items stay white on the dark bar. Idea on hold: detecting a finished Journey from the memory card (needs a card from before and after the ending to find the flag).


## More themes and the Journey unlock

Settings > Theme now has Daybreak, Horizon, Ceremony and Eclipse. Twelve (green, Dark Hour) and a gold "THE JOURNEY · COMPLETE" badge on the home screen unlock with the "I FINISHED THE JOURNEY" button, on the player's honour. Automatic detection from the memory card is on hold until before/after card copies are available.
