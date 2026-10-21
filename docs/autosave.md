# Autosave (browser build)

`python3 tools/ps2web_autosave_patch.py host/web.cpp web/shell.html` (after `ps2web_cardbackup_patch.py`), then rebuild
the web build (`scripts/build_web.sh <game>`).

What it does:

- Every 2 minutes while the game runs, and 8 seconds after each in-game save, the whole machine state is saved in the
  browser (IndexedDB, compressed). The newest 3 of each kind are kept: every 2 minutes, after a game save, and saved by
  you with **Save now**.
- When the page opens and an autosave exists for this build, the start screen offers **Resume autosave from <time>**
  next to the normal start button (renamed **Start from the title screen**). Resume puts the game back exactly where it
  was, for example in the middle of a battle.
- The **Autosave** button in the bottom bar lists the saves, with Resume (reloads the page and offers that one on the
  start screen), Delete, and Save now.

## Settings

`python3 tools/ps2web_autosaveopts_patch.py web/shell.html` (after `ps2web_autosave_patch.py`), then rebuild.
The Autosave panel gets a settings block, kept in the browser:

- **Save automatically:** Off, every minute, 2, 5, 10, 15 or 30 minutes (default every 2 minutes).
- **Also save after each in-game save:** on or off (default on).
- **Keep the newest of each kind:** 1, 3, 5 or 10 (default 3). Lowering it deletes the extra saves at once, which frees
  browser storage.

**Save now** always works, even with automatic saving turned off.

Things to know:

- The memory card is not part of an autosave. A resumed game uses the card as it is now; the card has its own backups
  (Backups button).
- A state only fits the build that made it. They are stored per build, identified by the sizes of `ps2web.wasm`,
  `ps2web.js` and `ps2web.data`, so a rebuilt game does not offer old states. If a resume fails, that state is deleted
  and the page asks for a reload.
- Saving happens at a frame boundary in the game's own thread (the same request as F6 in the PC window), so it is safe at
  any moment, with a short hitch while the state is written. The page waits for the file to end with the state's closing
  marker before it stores it.
- States are stored in the browser only. They contain game data, so they never belong in the repository or in a bug report.

## PC window

`python3 tools/ps2run_autosave_patch.py` in the project folder, after `ps2run_window_savestate_patch.py` (the installer does this), then rebuild the PC window. The launcher starts it with these switches, so nothing else is needed:

- `--autosave DIR`: turns autosaving on. States are written to `DIR` as `timer_<date>-<time>.state` (every N minutes), `card_...` (8 seconds after each in-game save) and `manual_...` (F5 in the window). A state is written as `.part` and renamed when complete, so a crash never leaves a half file.
- `--autosave-every MIN` (default 2, 0 = off), `--autosave-keep N` (default 3 of each kind), `--autosave-card 0|1`.
- `--load-state FILE` (already there) resumes from one.

The launcher keeps each build of `ps2run.exe` in its own folder, `C:\p3fes\saves\pc-autosaves\<build>`, because a state only fits the build that made it. After a rebuild the old states are listed as "from an older build" and cannot be resumed.

In the launcher: **Saves, Autosaves** has a PC WINDOW tab with Resume and Delete; **Resume** on the main menu resumes the newest PC autosave when the PC window is the chosen version (the E key); **Settings, Autosave** sets the interval, the number kept and the after-game-save switch (applies the next time the PC window starts).

Things to know:
- The memory card is not part of a state; a resumed game uses the card as it is now (same as the browser).
- A save writes the whole machine to disk in one go on the emulation thread: expect a short hitch each time, and tens of MB per file.
- Browser states and PC window states are separate and cannot be loaded into each other.
- Tested on a real PC (20 October 2026): timer saves, F5 saves, the Saves list and Resume all work.
