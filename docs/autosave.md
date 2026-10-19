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
