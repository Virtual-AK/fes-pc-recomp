# Update log
Newest first. The launcher shows the same list under Help > Update log (the source is `CHANGES` in `tools/launcher/ui/index.html`; keep the two in step).

## 0.10 · 21 Oct 2026 · Add to Steam
- **NEW** Settings > Steam: add Persona 3 FES to your Steam library as a Non-Steam game, with the artwork you pick from SteamGridDB (capsule, wide, hero, logo, icon). Needs a free SteamGridDB key.
- **FIXED** GameBanana mod descriptions were cut off after a short while; the whole text now shows.
- **FIXED** On a GameBanana mod page the whole page now scrolls (and keeps its place), and the BACK TO THE LIST and INSTALL buttons stay in view at the bottom.
- **FIXED** Logo and icon artwork now load in Settings > Steam (they only accept some picture types).
- **FIXED** Typing in a box (volume, Steam key) is no longer wiped by the screen refreshing.

## 0.9 · 21 Oct 2026 · Moving static and a midnight teaser
- **FIXED** The update log no longer jumps back to the top while you scroll it.
- **IMPROVED** The static on the home screen TV now moves.
- **NEW** Play at midnight and the TV shows a short teaser for the next project instead of static.

## 0.8 · 21 Oct 2026 · Volume sliders
- **IMPROVED** Volume rows in Settings > Audio now have a slider you can drag, and a MUTE button that sets the row to 0 (UNMUTE puts it back).

## 0.7 · 21 Oct 2026 · Music and voice volume
- **IMPROVED** Settings > Audio now has separate Music and Voices sliders (instead of one shared slider), next to Master and Effects.

## 0.6 · 21 Oct 2026 · Effects volume
- **NEW** Settings > Audio: separate volume for sound effects, and for music and voices together (they share one channel in the game for now).

## 0.5 · 21 Oct 2026 · Audio settings
- **NEW** Settings > Audio: master volume for the PC window, 0 to 100 percent. Use the buttons or type any value.

## 0.4 · 21 Oct 2026 · Speedrun clock
- **NEW** Speedrun clock for the PC window (Settings > Speedrun): real time in the top left corner, saved as you play so Resume carries on. F6 pauses, F7 sets it to zero.

## 0.3 · 20 Oct 2026 · Log, mouse and a calmer start
- **NEW** Log screen on Home: every line of dialogue the PC window shows, with the speaker and an icon. A crossed speaker means no voice. Click a speaker icon to hear the line again.
- **NEW** Mouse camera in the PC window, like the browser game: click the picture, move the mouse sideways to turn the camera. Esc gives the mouse back.
- **NEW** The PC window opens maximized, filling the screen like this launcher.
- **NEW** The launcher closes as soon as the game starts. Turn it off in Settings > Launcher.
- **NEW** This update log (Help > Update log).
- **IMPROVED** Direct Commands is now a switch (Mods > Direct Commands), on by default: Play uses it whenever it is built, in the browser and in the PC window. The PC window version is built once with tools\p3fes_win_mod.bat.
- **NEW** A small TV on the home screen. Just a hint of what comes later; it does nothing yet.

## 0.2 · 14 to 19 Oct 2026 · The native Windows PC window
- **NEW** A native Windows PC window: no Ubuntu display program, about 60 frames per second on a graphics card.
- **NEW** Resolution setting that applies to the PC window (1x, 2x or 3x).
- **NEW** Widescreen option for the PC window (Settings > Display). The 3D view is widened; menus and the HUD stay 4:3 for now.
- **NEW** Fast-forward: Tab speeds the game up and Tab again turns it off (the sound is muted while it is on).
- **NEW** PC window autosave and resume, shared memory card with the browser game.
- **NEW** One-step Windows setup for friends (first version).
- **NEW** Key and controller settings; keys like PCSX2 (WASD, TFGH, IJKL).
- **NEW** About page with the creators and the project.
- **IMPROVED** The PC window no longer needs a display program to be started first.

## 0.1 · earlier · The launcher itself
- **NEW** Home screen in the game's own style, with the real state: Ready, Not installed, Building, Wrong disc.
- **NEW** Play in the browser or in a PC window, one switch.
- **NEW** Saves screen: autosaves, the shared memory card and backups.
- **NEW** Mods: file mods (folders, zip, 7z and rar, merged with a priority order), portrait mods, GameBanana browsing and install, direct commands.
- **NEW** Ten colour themes, and the Twelve theme for finishing The Journey.
- **NEW** Help with getting started, controls, troubleshooting and a copyable report.
