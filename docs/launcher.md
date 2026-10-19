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

**PC window needs a display.** On Windows 10 with WSL1 (no WSLg) start VcXsrv first, as in `windows-build.md` (display 0, Disable access control ticked). The launcher then sets `DISPLAY` and the SDL settings itself, and says so if no X server is found. This part is untested.

**Help** (getting started, default keys, troubleshooting, about with a copyable report) and **Settings**: *Controls* sets the PC window keys (click a row, press a key; saved in `~/.p3fes-keys.txt`; default K confirm, L cancel, same as the browser; a `keys.txt` in the game folder is ignored when started from the launcher), *Display* picks Edge, Chrome or the system default for the browser game, and its resolution (1x, 2x, 3x; default 3x, passed to the game as `?PS2_SCALE=`). Controller, Autosave and Memory Card say "not connected yet": they live inside the browser game until saves are shared.

**Faster PC window:** see `better-window.md` (browser build resolution box, or WSL2 with WSLg for the graphics card).

## Not built yet
Resume, Mods, Saves (the buttons say so), the pink and Reload themes, shared saves between browser and PC window, starting setup from the window (the installer still runs in Ubuntu), choosing a disc from the window, and a real "modified disc" check (needs a known-good checksum).

## Untested
Not yet run on a real Windows machine. Check that `launch.bat` opens the window, that Edge or Chrome is chosen for the game (not Firefox), and that Play opens the game. Fonts load from Google Fonts when online and fall back to a plain font offline.
