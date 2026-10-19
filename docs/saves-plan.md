# Saves: where each build keeps them, and a plan to share them

Found by reading the PS2 Web Recomp source and our patches (19 October 2026). Not yet tested on a real machine.

## Where things are today

| What | Browser build | PC window |
|---|---|---|
| Memory card (game saves) | `/memcard/Mcd001.ps2` in the **browser's own storage** (IndexedDB), so Edge and Chrome each have their own card, and a different address (port) would too | A plain file, only if the runner is started with `--memcard file.ps2`. **With no `--memcard` there is no card at all** |
| Card format | 8,650,752 bytes, starts "Sony PS2 Memory Card Format" | The same format and size (`sio2.cpp`) |
| Autosave states | IndexedDB, per build (sizes of the wasm, js and data files), compressed | `--save-state` / `--load-state` files, and F6 in the window |
| Card backups | IndexedDB (Backups button) | none |

So the memory card is the same file format on both sides and can be shared. Autosave states come from the same runtime code (`save_state`), but each is tied to its build, and a browser state may not load in the PC window (different compiler, threads and JIT). That needs a real test before promising it.

## Done now (launcher 0.2)
The launcher starts the PC window with `--memcard`, using `C:\p3fes\saves\Mcd001.ps2` (or `~/p3fes-saves` if that folder does not exist). Before this the PC window had no card, so in-game saving could not work from the launcher.

## Plan to share the card
1. **One file on disk** is the master: `C:\p3fes\saves\Mcd001.ps2`. The PC window already uses it.
2. **Browser build reads and writes the same file** through the launcher's server: a small patch to `web/shell.html` that, on start, fetches the card from the server and writes it into the browser's card folder, and, on every card save (the existing `ps2CardSaved` hook), sends it back. The launcher server (not `scripts/serve.py`, which only accepts VU1 uploads) serves `GET` and `PUT /card`, and keeps the last 10 copies as backups on disk.
3. **Rule for the first start:** if the browser has a card and the disk file does not, copy the browser card to disk; if both exist and differ, ask which to keep (never silently overwrite).
4. **Saves screen** lists the card file, its backups and, later, autosaves.
5. **Autosaves:** decide after testing whether a browser state loads in the PC window. If not, keep them per build and say so on screen.

## Open
- Does the game accept a card made on the other side (should; same format)? Test: save in the browser, open in the PC window.
- Two windows open at once would overwrite each other's card. The launcher should refuse to start the second one.
- A browser opened at a different address or in another browser keeps its old card in its own storage; the first-start rule above handles it.
