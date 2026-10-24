# Update log
Newest first. The launcher shows the same list under Extra > Update log (the source is `CHANGES` in `tools/launcher/ui/index.html`; keep the two in step).

## 0.35 · 23 Oct 2026 · Social Link screens in widescreen
- **FIXED** The widescreen Social Link part (`ws5`) no longer breaks the Tartarus entrance screen. It is now three parts (`ws5_slink` X-positions, `ws5a_hook`, `ws5e_cards2`); the hook in `ws5a_hook` narrowed every quad of the generic quad routine at 001140d0, which the Tartarus screen also uses. Its routine now reads the caller's return address (saved at 0x90(sp)) and narrows only for callers in the Social Link code (00130000-0013C000). Tested: Social Link screen and Tartarus entrance both correct. All three parts are on by default again. Needs the new `ws5a_hook.pnach`, `packed_mods.json`, then BUILD and `p3fes_win_mod.bat`.
- **NOTE** `ws3a_clock` and `ws3c_zoom` stay off for good: nothing visibly needs them.

## 0.34 · 23 Oct 2026 · File mods and widescreen in the browser
- **FIXED** Thin diagonal lines inside text (Load Data list, text boxes, transitions) are gone. New patch `ps2gpu_edgetie_patch.py`: at 2x/3x resolution the two triangles of a text quad both rejected samples that lay exactly on their shared diagonal; such a sample now goes to the top-left rule. Confirmed in the PC window. Rebuild the browser pages after applying it.
- **NEW** The browser game now gets the bigger-file pokes (Fast Start, Manual Skill Inheritance) as the page parameter `PS2_POKE`, and the file-mod overlay is used with the packed-in mods build too (before, it was only used with the normal build). Needs `p3fes_launcher.py` and the browser pages rebuilt (`scripts/build_web.sh p3fes`, then `p3fesmod`). Tested in the browser: Fast Start, Manual Skill Inheritance, widescreen and the line fix all work.
- **CHANGED** Widescreen parts `ws3a_clock`, `ws3c_zoom` and `ws5_slink` are off by default: they break the dark overlay of fades and the circle transition, the Dark Hour clock and the Tartarus entrance screen. `P3F_WS_ON=ws3a,ws5` switches them on for testing. Needs `packed_mods.json`.

## 0.33 · 23 Oct 2026 · Fast Start works, widescreen menus
- **FIXED** Fast Start works in the PC window (tested: the transfer and FES question screens are skipped). A `PS2_POKE` line in `~/.p3fes-window-env` is now added to the mod pokes instead of replacing them. Needs `p3fes_launcher.py`.
- **NEW** Widescreen menus, portraits and HUD (tested in the game; the final set of parts is in 0.34 and 0.35). The community file `94A82AAA.pnach` (about 184 code patches) is split into eleven part files (`ws1_core` to `ws11_zoom`, one per section of the file, plus the three converted routines `ws3a` to `ws3c`) in `packed\widescreen`; `ws7_title` and `ws8_font` are off by default. They are hidden code mods (switches 7 to 19) with no switch of their own: they are on when Settings > Widescreen is on. The file's conditional codes (apply only while the menu is open, and so on) are converted by hand in `ws3_detect`. Research: a line `P3F_WS_OFF=ws2,ws5` in `~/.p3fes-window-env` leaves those parts off without a rebuild. The one data line in it (the 3D field of view, `007cad1c`) is skipped because the PC window already sets that. Checked with all seven other code mods: no clashes. Then BUILD in Mods and `p3fes_win_mod.bat`.
- **FIXED** `p3fes_win_mod.bat` copied the game code from Ubuntu with `cp -u`, which skips files that are not newer. After a rebuild with a different unit layout, old unit files stayed next to the new header and the compile failed (`use of undeclared identifier 'unit_0005'`). The new `p3fes_win_copymod.sh` copies by content and removes files that no longer exist. Needs `p3fes_win_mod.bat` and `p3fes_win_copymod.sh` in `C:\p3fes`.

## 0.32 · 23 Oct 2026 · Bigger mod files (PC window)
- **FIXED** Manual Skill Inheritance now works in full (tested: choose-skills list, SKILL HELP panel, fusion). Its fusion menu file is bigger than the original, and the game reads files from its own table of sizes and start sectors, not from the directory. The launcher now writes the new size and sector for the PC window (`mods\active.pokes`, passed as `PS2_POKE`), puts moved files in the unused space at the end of the disc volume, and raises the size the CVM and its directory record state so the game accepts the new place. Needs `p3fes_launcher.py`, `p3fes_modmap.py`, `ps2run_poke_patch.py`, `p3fes_install.sh`, then `p3fes_win_mod.bat`. Browser game: not yet.
- **NOTE** `p3fes_install.sh --patches-only` must not be run on a tree that is already patched (it re-applies patches). Run it without the option; it remembers what it applied.

## 0.31 · 22 Oct 2026 · Manual Skill Inheritance fixed
- **FIXED** Manual Skill Inheritance took the wrong download (the Portable 4:3 one) and ignored the code patch in the FES one. Now it picks the FES zip, adds its patch to the build (switch 6) and lays its game files over the disc, all under one ON/OFF. Remove the old one, press DOWNLOAD again, press BUILD, then run `tools\p3fes_win_mod.bat`.

## 0.30 · 22 Oct 2026 · Always Critical is a cheat
- **IMPROVED** Always Cut-In now only does the cut-ins. The Always Critical part (every attack is a critical hit) is its own switch under Mods > CHEATS, off by default. Both still come from the same GameBanana download. Press BUILD once, then run `tools\p3fes_win_mod.bat` once for the PC window.

## 0.29 · 21 Oct 2026 · Packed-in mods
- **NEW** Mods > PACKED-IN MODS: Direct Commands, Modern Persona Switch, Always Cut-In, Share Party Experience, Never Tired, Fast Start and Manual Skill Inheritance, each with an ON/OFF button, its author credited and linked, and a DOWNLOAD button that fetches it from GameBanana onto your computer. Nothing from the mods is in our project.
- **NEW** Code mods share ONE extra build of the game with a live switch each: press BUILD once after adding one, then turn mods on and off without rebuilding. The translator keeps the original and the patched version of every changed instruction and picks one while the game runs.
- **NEW** Mods > CHEATS: the Classroom and Social Link cheat sheets, off by default.
- **NEW** `p3fes_pnach_apply.py` understands `extended` patch lines and several mods at once; `p3fes_packed_build.py` builds them. Run the installer once more (Setup > GET THE TOOLS), then press BUILD.
- **IMPROVED** Direct Commands is now one of the switches (it keeps working from the old build until the first BUILD). The PC window build must be redone with `tools\p3fes_win_mod.bat` after a BUILD; the launcher tells you.

## 0.28 · 21 Oct 2026 · Settings wording
- **IMPROVED** Settings no longer say PC window only for the speedrun clock, volumes and widescreen, which now work in the browser game too. The Autosave and Controls screens point to the buttons on the browser game page.

## 0.27 · 21 Oct 2026 · Instant music
- **IMPROVED** Launcher music comes back within a few seconds of closing the browser game (the game page now tells the launcher when it opens and closes). Run the installer once more to rebuild the browser pages.

## 0.26 · 21 Oct 2026 · Browser turbo
- **NEW** Turbo (fast forward) in the browser game: press Tab to turn it on, Tab again to turn it off. The frame limiter is off, only every 4th frame is drawn, sound is muted and a TURBO badge shows. Run the installer once more to rebuild the browser pages.

## 0.25 · 21 Oct 2026 · Browser catches up
- **NEW** The browser game now has the speedrun clock (Settings > Speedrun): top left of the page, F6 pauses, F7 resets, kept between sessions.
- **NEW** Widescreen (Settings > Widescreen) and the Master, Music, Voices and Effects volumes now apply to the browser game too. Run the installer once more to rebuild the browser page.
- **NOTE** Still PC window only: fast-forward on Tab.

## 0.24 · 21 Oct 2026 · Screenshots
- **NEW** Press one key (F9 by default) while the game is in front and it saves a screenshot of the game window. No Snipping Tool needed.
- **NEW** Extra > SCREENSHOTS shows them as a gallery with a large view, next and previous, delete, and a button that opens the folder (C:\p3fes\screenshots).
- **NEW** Choose the key (F8, F9, F10, F12, Print Screen or Insert), turn the click sound off, or turn the feature off.
- **FIXED** Launcher music no longer stays silent after you close the browser game.

## 0.23 · 21 Oct 2026 · Launcher music
- **NEW** Launcher music: an original, laid-back loop (electric piano, bass, drums and a short lead line) that plays while the launcher is open. Nothing is taken from the game.
- **NEW** Settings > Audio has a LAUNCHER slider with a number box and MUTE like the others. Press M anywhere to mute or unmute it.
- **IMPROVED** The music stops by itself while a game is running.

## 0.22 · 21 Oct 2026 · Update source set
- **IMPROVED** Help > Version now checks the project's own GitHub repository by default (Virtual-AK/fes-pc-recomp). You can still change the source there.

## 0.21 · 21 Oct 2026 · Updates from the launcher
- **NEW** Help > Version checks whether you have the latest launcher and can update it with one button. Enter the project's GitHub address (owner/name) once. The old files are backed up first.

## 0.20 · 21 Oct 2026 · Guides: class answers and fusion shortcut
- **NEW** Guides > School answers now lists Pop Quiz dates and answers from the Shin Megami Tensei Persona Wiki.
- **IMPROVED** The Fusion Calculator opens straight on the Persona 3 FES page.

## 0.19 · 21 Oct 2026 · Guide fixes
- **FIXED** School answers no longer lists pages from other games. When the wiki has no page for class answers, buttons offer the same search on GameFAQs or the web in a window.

## 0.18 · 21 Oct 2026 · Guides: fusion calculator and topic fixes
- **NEW** Guides > Fusion lists the Persona 3 FES Fusion Calculator (Megaten Fusion Tool, made by the community) and opens it inside the launcher. Needs internet.
- **IMPROVED** Tactics and Shuffle Time now sit under Tartarus instead of Daily planner. The Persona 3 game page no longer shows up in results.
- **IMPROVED** School answers searches several ways and looks for pages about exams and class questions; if the wiki has none it says so.

## 0.17 · 21 Oct 2026 · Tighter guide topics
- **IMPROVED** Guide topic buttons now rank by page name and category, drop loose matches when enough on-topic pages exist, and leave out songs, albums and merchandise.

## 0.16 · 21 Oct 2026 · Better guide results and pictures
- **FIXED** Pictures now show on guide pages.
- **IMPROVED** Guide results leave out the manga, live action, stage plays, anthologies and other games, and put pages whose names match your topic first.

## 0.15 · 21 Oct 2026 · Guide pages and results
- **FIXED** Guide pages are now drawn directly in the launcher (they came up blank before).
- **IMPROVED** Guide searches leave out Portable, Reload, The Night Before, the stage play and other non-FES pages. Each result shows what the wiki filed it under.

## 0.14 · 21 Oct 2026 · Guide fixes
- **FIXED** The list of guide results and of saved pages no longer jumps back to the top while you scroll.
- **IMPROVED** Guide searches now only list Persona 3 pages (not Persona 4, 5 and other games).
- **FIXED** Guide pages that showed up blank.

## 0.13 · 21 Oct 2026 · Guides you can save
- **IMPROVED** Extra > Guides now searches the Megami Tensei Wiki right inside the launcher and shows the pages there. SAVE OFFLINE keeps a page on your computer so you can read it without internet.
- **IMPROVED** GameFAQs and web search open in their own window (those sites do not allow being shown inside the launcher).

## 0.12 · 21 Oct 2026 · Guides inside the launcher
- **IMPROVED** Extra > Guides now shows the wiki, GameFAQs and web search pages right inside the launcher (plain pages, no ads or scripts). OPEN IN A WINDOW still gives you the full site.
- **FIXED** The moon in the Golden theme is now easy to see.

## 0.11 · 21 Oct 2026 · Guides, Extra and the Golden theme
- **NEW** Extra > Guides: look up enemies and bosses, social link answers, the daily planner, school answers, fusion or Tartarus on the Megami Tensei wiki, GameFAQs or the web, in a window next to the launcher. Or search for anything you like.
- **NEW** Golden theme (yellow and black with TV lines), the launcher look for the next project. Settings > Theme.
- **NEW** About > Playtesters and Bug reporters (placeholders for now).
- **IMPROVED** The Log menu is now called Extra, and the Update log moved there from Help.

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
- **NEW** This update log (Extra > Update log).
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

### Turbo fix
- PC window Turbo no longer skips drawing frames (that could freeze the picture for good). It now runs at double speed on a timer (unlimited speed froze voiced scenes) and still mutes sound. Re-run the installer (Setup > GET THE TOOLS) and rebuild the PC window.
