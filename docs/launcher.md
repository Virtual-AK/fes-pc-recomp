# Launcher (first version)

An app window for the game, drawn to match the design in the launcher design spec. It is a small local server
(`tools/launcher/p3fes_launcher.py`) plus an Edge or Chrome window with no address bar, so nothing extra is installed.

## Start it
Double-click `tools\launcher\launch.bat` (after the installer has run once). Closing the window stops the launcher. The window is maximized right after it opens (a short PowerShell step finds the window titled Launcher and maximizes it, because Edge and Chrome remember the last size and ignore start flags); the interface scales to fit any size.
Or, in Ubuntu: `python3 tools/launcher/p3fes_launcher.py` (add `--no-window` and open `http://127.0.0.1:8630/` yourself).

## What works now
- **Home screen** in the game's blue, with the real state: Ready, Not Installed, Building (counts finished pieces), Wrong Disc (shows region, game ID and contents checks).
- **Disc check** reads only the `SYSTEM.CNF` line and the file size. A disc counts as wrong if the game ID is not `SLUS_216.21`, or the file is shorter than the disc says, or it cannot be read, or its file name contains "modded".
- **Play**: starts the browser server and opens Edge (or Chrome), or starts the PC window build if it exists. **Play in** switch: Browser or PC window (keys Q and E), remembered in `~/.p3fes-launcher.json`.
- Keyboard: arrows, Enter, Q and E, Esc. The mouse works too.

**PC window needs a display.** On WSL2 the launcher uses WSLg (and tries OpenGL on the card, which did not help on the first PC tested). On Windows 10 with WSL1 (no WSLg) start VcXsrv first, as in `windows-build.md` (display 0, Disable access control ticked). The launcher then sets `DISPLAY` and the SDL settings itself, and says so if no X server is found. This part is untested.

**About** (main menu, last item): the creators (VirtualAK and Claude, each with an avatar and signature picture from `ui/img`) and a short description of the project with its credits (PS2 Web Recomp by snuri00, SDL2, wgpu-native). **Help** (getting started, default keys, troubleshooting, version with a copyable report) and **Settings**: *Controls* sets the PC window keys (click a row, press a key; saved in `~/.p3fes-keys.txt`; default K confirm, L cancel, same as the browser; a `keys.txt` in the game folder is ignored when started from the launcher), *Display* picks Edge, Chrome or the system default for the browser game, and its resolution (1x, 2x, 3x; default 3x, passed to the game as `?PS2_SCALE=`). *Memory Card* shows the shared card file (`C:\p3fes\saves\Mcd001.ps2`), how many backups are kept, and opens the folder; the browser game shares it after the installer has been run again (it updates the page, a few minutes). Controller says "in the browser game" (no panel for the PC window yet). *Autosave* sets the PC window's autosave: how often (off to 30 minutes), whether to also save after each in-game save, and how many to keep; it applies the next time the PC window starts. The browser game keeps its own Autosave panel.

**Native Windows PC window:** when `C:\p3fes\winbuild\build\ps2run.exe` exists (or the path in `P3F_WINEXE`), PC WINDOW starts it instead of the Ubuntu one: no XLaunch, about 60 fps on the first test PC. The launcher copies the boot file next to it, passes the shared memory card and the key file, and prefers a disc image on a Windows drive (`C:\p3fes\*.iso`) for speed. Log: `~/.p3fes-window.log`. File mods (Mods > File mods) are passed to it as `--overlay` when `C:\p3fes\mods\active.ovl` exists and the build knows the switch (`ps2run_overlay_patch.py`); an older build starts without them and the launcher says so.

**Faster PC window:** see `better-window.md` (browser build resolution box, or WSL2 with WSLg for the graphics card).

## Not built yet
Starting setup from the window (the installer still runs in Ubuntu), choosing a disc from the window, a real "modified disc" check (needs a known-good checksum), automatic detection of a finished Journey from the memory card, and building the Windows PC window from inside the launcher (it only starts one that was built by hand, see `windows-native-plan.md`).

## Tested
Run on a real Windows 10 machine (Edge app window, Ubuntu on WSL1, later WSL2): home screen, settings and themes, saves, file mods (folder, zip, 7z, rar, merging and priority), portrait mods in the browser game, GameBanana browse and install. Not yet tested: a clean install on another person's PC, and GameBanana against pages with unusual file lists. Fonts load from Google Fonts when online and fall back to a plain font offline.

## Saves screen

Home > SAVES has three parts. AUTOSAVES has a PC WINDOW tab and a BROWSER tab (the PC tab only when the Windows PC window is built); each lists the saves with RESUME and DELETE. MEMORY CARD shows the shared card file, when it was last saved, and an OPEN FOLDER button. BACKUPS lists the earlier copies in `saves\backups` (newest 10) with RESTORE and DELETE, each needing a second click to confirm. Restore refuses while the PC window is running, and keeps the card it replaces as a new backup.

### Autosaves in the launcher

The browser game now copies each autosave to `saves\autosaves\<build>` (and tells the launcher when one is deleted). The Autosaves screen lists them with RESUME (opens the browser game, then click "Resume autosave" on its start screen) and DELETE, and Home > RESUME opens the newest. Because they live in the folder, Edge and Chrome see the same ones. They only work with the build that made them; older ones are counted and ignored. Needs `ps2web_autosavesync_patch.py` (the installer applies it and updates the browser page, a few minutes). PC window autosaves (`ps2run_autosave_patch.py`, see `autosave.md`) are separate from the browser ones: Home > RESUME resumes the newest of whichever version is chosen with Q or E. Tested on a real PC (20 October 2026): saving, listing and resuming all work.

## Setup from the launcher

On a computer with no game yet, Home shows SET UP. It opens the Setup screen with four steps: FIND YOUR DISC (a normal Windows file window, only a USA, unchanged disc is accepted), GET THE TOOLS and BUILD THE GAME (START SETUP runs `p3fes_install.sh` in its own window, where it may ask for the Ubuntu password once; the launcher shows the piece count and the last files compiled), then PLAY. If setup stops, CONTINUE SETUP picks up where it left off. Still needed before this works: Windows 10/11 with Ubuntu installed in WSL (see docs/install.md).

## Mods screen

Home > MODS lists Direct Commands (PLAY WITH THIS MOD when the `p3fesmod` build exists; it uses the browser or PC window as set on Home, and the shared memory card), the FEMC protagonist (in development) and the Reload style pack (concept), and ADD A MOD. ADD A MOD opens a file window for a `.pnach`, and checks it against the program on your disc with `p3fes_pnach_apply.py` (how many lines apply, whether the original-code notes match). Building the checked mod from the launcher is not done yet: see docs/mods.md.

## Mods > File mods
For mods that replace game files (text, images, sounds), the kind found on GameBanana. Press ADD A FOLDER or ADD A ZIP. The launcher unpacks the mod into `C:\p3fes\mods`, finds the game folders in it (DATA, BTL, ... even inside a wrapping folder), checks every file against your disc and says how many fit. Each mod can be switched ON or OFF and removed. The enabled ones are merged (a later mod wins for the same file) into `C:\p3fes\mods\active.ovl`, which the browser game's server lays over your disc when you press Play. Your disc is never changed. Files that are bigger than the original are moved to the end of the image automatically; a bigger file inside an archive (.PAC/.BIN) is skipped and listed. The PC window does not use file mods yet. It needs the one-time server update (Setup > GET THE TOOLS, or `bash p3fes_install.sh`).

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

## Log screen
Home > LOG lists every line of dialogue the PC window has shown, newest last, grouped by play session. Each line has the speaker's name
and an icon: a speaker for a line that has a voice, a crossed speaker for one that has none (narration, most townspeople). Click a
speaker icon to hear that line again; the clip is read from your own disc and decoded on the spot, nothing is stored. CLEAR LOG empties
the list. It needs the PC window built with `ps2run_dialoglog_patch.py` (the installer applies it); the log is written to
`saves\dialog_log.tsv`. Speakers the launcher does not know yet show as "Speaker N". See [log-plan.md](log-plan.md) for how it works.

## Close on Play, update log and the TV (0.3)
- **Close the launcher on Play:** by default the launcher window closes as soon as the game starts, for the browser and the PC window. Turn it off
  in Settings > Launcher (the choice is remembered). For the browser game the launcher's background server keeps running for up to 30 minutes
  after the last save so the memory card and autosaves stay in sync; opening the launcher again just opens a window onto it.
- **Update log:** Extra > Update log lists what changed in each version (same text as [changelog.md](changelog.md)).
- **TV icon:** a small static TV with "To be continued" on the home screen. It does nothing; it is a teaser for what comes after this project.

## Direct Commands switch (0.3)
*Since 0.29 Direct Commands is one of the packed-in mods: see [packed-mods.md](packed-mods.md). Mods > PACKED-IN MODS replaces Mods > Direct Commands.*

Mods > Direct Commands is now a switch, on by default. While it is on, Play (and Resume in the PC window) starts the Direct Commands build of the
game whenever it is built for the way you are playing, otherwise the normal game, with a note saying so. The browser version comes from the
mod build in Ubuntu. The PC window version is a second build of the Windows program: run `tools\p3fes_win_mod.bat` once from the
"x64 Native Tools Command Prompt for VS 2022" (it copies only the mod's generated game code, shares the recorded graphics code with the normal
build and compiles into `C:\p3fes\winbuild\build-mod`). The launcher finds it by itself. A browser Resume always uses the normal build, and PC window
autosaves are kept separately per build, so a state is never loaded into the wrong one.

## Speedrun clock (0.4)
Settings > Speedrun switches on a clock in the top left corner of the PC window (real time, H:MM:SS.cc, off by default). The game draws through
the graphics card, so the clock is a small see-through, click-through window that sits over the picture and follows the game window (moved,
resized, maximized, full screen); it hides when the game window is minimized. OBS: Display Capture shows it, some Window Capture modes do not.
The time is saved once a second in `C:\p3fes\saves\speedrun_clock.txt` and read back at start, so a run continues through Resume.
In the game window F6 pauses and continues, F7 sets it back to zero (Settings > Speedrun > Reset also does it, for the next start).
The clock starts counting when the window opens (the game does not tell us where a New Game begins); press F7 at the moment your run starts.
Browser game (0.25): the same clock, drawn over the page (`tools/ps2web_speedrun_patch.py`, page address `?speedrun=1`). It starts when the page opens, is kept in the browser's local storage, and uses the same F6 / F7 keys. Settings > Speedrun > Reset zeroes it the next time the browser game opens.

## Audio (0.5)
Settings > Audio sets the master volume of the PC window (0 to 100 percent: type any value and press Enter or SET, or use minus and plus in steps of 5; default 100). It applies when the game
starts (`PS2_VOL_MASTER`, handled by `tools/ps2run_audio_patch.py` in the sound chip mixer).
Separate Music / Voices / Effects volumes need the game's sounds told apart. The same patch has a research switch: put `PS2_AUDIO_PROBE=1` in
`~/.p3fes-window-env`, play, and `~/.p3fes-window.log` gets one `[audio]` line per second with the loudness of each sound chip's streamed input and
of each of its voices. Playing music only, then a voice line, then an effect shows which carries what.

## Effects and stream volume (0.6)
Settings > Audio now has three rows: Master, Effects and Music and voices (type 0 to 100 and press Enter, or minus / plus in steps of 5).
From the audio probe: the music arrives through the first sound chip's streamed input, sound effects are ordinary sound voices on both chips.
So `PS2_VOL_FX` scales the sound voices and `PS2_VOL_STREAM` the streamed input (`tools/ps2run_audio2_patch.py`, applied after `ps2run_audio_patch.py`).
Voice lines are probably in the streamed input too, mixed with the music before the sound chip sees them. The probe (`PS2_AUDIO_PROBE=1`) now also logs
`[adma]` lines with the memory areas the stream is read from; if music and voices come from different areas they can be split into two sliders.

## Music and voice volume (0.7)
The audio probe showed that music and voice lines are mixed into one stream before the sound chip, so Settings > Audio now turns them down where
they can be told apart: on the disc. Music is the ADX files in BGM.CVM, voice lines are the ADX clips in the SOUND/V*.AFS archives in DATA.CVM. Every ADX
block starts with a 16-bit scale and the decoded sound is proportional to it, so `tools/ps2run_audiosrc_patch.py` multiplies it by `PS2_VOL_MUSIC` /
`PS2_VOL_VOICE` (0 to 100) as the disc is read. At 100 nothing is touched. Four rows now: Master, Music, Voices, Effects. If a sound is on the wrong
slider (for example a battle voice that follows Effects or Music), tell us which one; the probe (`PS2_AUDIO_PROBE=1`) and the disc log show where it comes from.

## Volume sliders (0.8)
Each row in Settings > Audio has a slider (drag it; the number box follows while dragging and the value is saved when you let go), the number box
(type and press Enter), minus / plus buttons (steps of 5) and a MUTE button. MUTE sets the row to 0 and remembers the old value; the same button, now
UNMUTE, puts it back (100 if the launcher was restarted in between).

## Update log scroll, moving static, midnight teaser (0.9)
The launcher redraws its screens every few seconds, which put the update log back at the top; it now keeps its scroll position. The TV on the home screen
is one canvas that lives outside those redraws, so its static keeps moving. Midnight: while a game is running (the PC window, or the browser game's server)
the launcher asks Windows for the time once a minute (`midnight_watch` in `p3fes_launcher.py`) and, if it is in the 00:00 hour, remembers the date in its settings
file (`midnight_play`). The TV then shows a short text teaser (about 10 seconds, looping) instead of static: while the launcher is open in the 00:00 hour with
a game running, and until 03:00 on a date that was recorded. The label under the TV changes to MIDNIGHT CHANNEL. The teaser is only text drawn by the launcher, no game art.
To preview it at any time, add `?midnight=1` to the launcher's address (open http://127.0.0.1:8630/?midnight=1 in a browser).

## Add to Steam (0.10)
Settings > Steam adds Persona 3 FES to your Steam library as a Non-Steam game, with artwork you choose from SteamGridDB, the way some other emulator launchers do.
- You need a free SteamGridDB API key (steamgriddb.com, sign in, Preferences, API). It is saved in the launcher's settings file in your Ubuntu home folder (plain text), and only sent to steamgriddb.com.
- The launcher finds the game on SteamGridDB (Persona 3 FES), then shows the artwork people have made in five groups: capsule (600x900), wide capsule (920x430), hero, logo and icon. Click one picture in each group you want (click again to unpick); LOAD MORE fetches more. Thumbnails come straight from SteamGridDB, nothing from the game is used.
- ADD TO STEAM writes the shortcut and downloads the chosen pictures into your Steam folder (`userdata/<account>/config`, `shortcuts.vdf` and `grid`) for the account that signed in most recently. Steam must be closed completely first, because it rewrites that file when it quits. A copy of the old file is kept next to it as `shortcuts.vdf.p3fes-backup`.
- The shortcut starts `launch.bat` (next to `p3fes_launcher.py`), so Steam opens the launcher and you press Play there. Adding again replaces the shortcut and artwork. REMOVE FROM STEAM takes out the shortcut and the artwork this launcher added.
- Only links on steamgriddb.com are downloaded. Code: `steam_*`, `shortcuts_*`, `vdf_*` and `sgdb_get` in `p3fes_launcher.py`; test: `tests/test_steam.py`. Not yet tried against the real SteamGridDB service or Steam (only against a pretend Steam folder).

## Guides, Extra and the Golden theme (0.11)
- **Extra** is the old Log menu: Dialogue log, Update log (moved from Help) and Guides.
- **Extra > Guides** (reworked in 0.13): the launcher searches the Megami Tensei Wiki (Fandom) through its public MediaWiki API from the launcher page itself, so your own browser makes the request, and shows the page text in a viewer drawn inside the launcher (scripts, styles, classes and link addresses are removed; wiki links stay in the viewer; searches leave out Portable, Reload and other non-FES pages by title and category). SAVE OFFLINE writes the cleaned page to `~/.p3fes-guides/` in your Ubuntu home folder; saved pages open without internet (pictures need internet). Wiki text is CC BY-SA 3.0, so every page shows that notice and the page address (authors are in the page history). GameFAQs and web search cannot be shown inside the launcher (GameFAQs authors keep their copyright, and both sites refuse the launcher), so they open in a separate window from the typed search. Code: `gd*` functions in `index.html`, `guide_*` in `p3fes_launcher.py`; test: `tests/test_guides.py`. Not yet tried against the live wiki from here.
- Since 0.20 the School answers topic also lists *Pop Quiz dates and answers* from the Shin Megami Tensei Persona Wiki (`WIKIS` in `index.html` lists the two wikis; saved pages remember which wiki they came from). The Fusion Calculator opens at `https://aqiu384.github.io/megaten-fusion-tool/p3f/personas`.
- **About** now has Playtesters and Bug reporters pages. They are placeholders: edit the text in `index.html` (search for `PLAYTESTERS`) when there are names to list.
- **Golden theme:** yellow and black with diagonal and TV-line overlays, only colours and CSS (no game art). Settings > Theme > GOLDEN. It is the starting point for the Persona 4 launcher look.

## Updating the launcher (0.21)
Help > Version has an UPDATES box. The default source is `Virtual-AK/fes-pc-recomp` (`DEFAULT_UPDATE_REPO`); another `owner/name` can be entered and is saved as `update_repo` in the launcher settings file. The launcher then reads `LAUNCHER_VERSION` from `tools/launcher/p3fes_launcher.py` on the repository's `main` branch (or `master`) and says whether you are up to date. UPDATE NOW downloads the branch as a zip from GitHub and replaces only `p3fes_launcher.py` and the `ui` folder next to the running launcher.
- Before anything is replaced the download is checked (it must hold a launcher file that compiles and has a version), the old files are copied to `~/.p3fes-launcher-backup/<old version>/`, and the `.py` is written last. If anything fails, nothing is changed.
- RESTART THE LAUNCHER restarts the server in place and reloads the window. If that does not work, close the launcher and open it again.
- It updates the launcher only. The game build, the PC window, patches and tools are not touched.
- Updating means running whatever is on that branch, so only point it at a repository you control. Code: `update_*` in `p3fes_launcher.py`; test: `tests/test_update.py` (the download itself has not been tried against GitHub from here).

## Launcher music (0.23)
`tools/launcher/ui/music.js` makes an original 16-bar loop live in the browser's audio engine: electric piano (FM), bass, a soft pad, a short lead line, swung drums and finger snaps, at 86 BPM in B minor. It uses no audio files, no samples and nothing from the game or its soundtrack (the game's music is the player's own disc data and is never copied here).
- Starts after the first click or key press (browsers do not allow sound before that). Settings > Audio > LAUNCHER sets the level (default 70) with slider, number box and MUTE; the **M** key mutes and unmutes from any screen. It pauses while a game is running or the launcher window is hidden.
- To change the music, edit the chords (`PROG`, `C`), the lead line (`LEAD`), the tempo (`BPM`) or the drum patterns in `music.js`. `LM.build(ctx)` also works with an `OfflineAudioContext`, which is how the loop was rendered and checked (levels, balance, timing); it has not been listened to by its author, so tune it by ear. Test: `tests/test_music.py`.

## Screenshots (0.24)
Press one key (F9 by default) with the game in front and the launcher saves the game window as `P3FES_YYYY-MM-DD_HH-MM-SS.png` in `C:\p3fes\screenshots` (a small picture for the gallery goes in `thumbs`). Extra > SCREENSHOTS shows the gallery, a large view with newer/older, delete (asks twice) and OPEN FOLDER. The key (F8, F9, F10, F12, Print Screen, Insert), the click sound and the whole feature can be changed there.

How it works: the launcher writes a small PowerShell helper (`.helper.ps1`) into the screenshots folder and starts it hidden. The helper registers the key with Windows, reads `.helper.cfg` for changes and quits by itself when the launcher stops writing `.alive`. Only the launcher's own file names are served or deleted (`P3FES_...png`).

Limits: it works while the launcher is running (it keeps running while the PC window is open). It copies what is on screen, so a game in exclusive fullscreen may give a black picture; use the windowed mode. Screenshots stay on the player's PC and are never part of the repo.

## Browser build catches up (0.25)
The launcher adds the PC window's settings to the browser game's address: widescreen (`PS2_ASPECT`, `PS2_PATCH`), the four volumes (only when below 100) and the speedrun clock. The browser build shares the graphics and sound code with the PC window, so these work there once the browser page is rebuilt (run `p3fes_install.sh` again; it notices the new patches `ps2run_widescreen_web_patch.py` and `ps2web_speedrun_patch.py`). Fast-forward on Tab came to the browser in 0.26. Still PC window only: the research switches.
