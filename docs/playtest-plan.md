# Playtest plan: from the first scenes to a full playthrough

Status of the translated game (Persona 3 FES, NTSC-U, SLUS-21621) as of 16 October 2026, what is broken, and everything still to be tested. The aim of this stage: **find out what breaks, in what order, and write each break down well enough to fix it.** Nothing here needs coding skill; most tests are "do this, tell us what you saw".

Standing rules (same as everywhere in this project): the repo holds tools and documents only. Game pictures (screenshots, frame pictures, contact sheets), exported text, textures, models and disassembly stay on your own PC. You may send pictures to Claude in chat; they never go to GitHub. Numbers, addresses, function names and frame numbers are fine to share anywhere.

## 1. Where we are

Reached so far, all from the player's own disc, translated to PC code, with **0 unhandled system calls, 0 missing IOP functions and 0 new entry points** in the last three runs (60,000 frames, about 17 minutes of game time):

| Step | State |
| --- | --- |
| Boot, logos, title screen, main menu | works |
| New Game flow: advice pages, Yes/No boxes, difficulty, disclaimer | works |
| Opening movie and video decoder | works (picture; sound not checked) |
| Name entry (character grid, Del/OK/End, "Proceed?") | works |
| Second movie, then first 3D field scenes in the dormitory | runs |
| Dialogue boxes, portraits, choice boxes, time-of-day box, calendar | works |
| Walking, camera, character models, next-morning transition | runs |
| Cut to the city street (start of the walk to school) | runs |

## 2. Known faults

| # | Fault | Seen at | Notes |
| --- | --- | --- | --- |
| F1 | ~~Floors and some walls show coloured noise instead of their textures~~ **Fixed in the test runs (17 October 2026)** | field frames 51000 to 54600 | Cause: the runtime ignored the VIF1 MSKPATH3 command, so all texture uploads (PATH3) landed before the draws that needed them. `ps2run_fix_path3_mask.py` holds PATH3 data while masked and releases one packet per mask pulse; the corridor from the 50000 state now draws correctly with no leftover data. Still to do: re-check the whole run, and port the rule to the threaded window build (formats.md, sixth experiment). |
| F2 | ~~Large parts of rooms and corridors very dark or black~~ **Mostly fixed by the F1 fix (17 October 2026)** | was frames 47400 to 49200, 55800 | In the full 60,000-frame re-run the lobby (frames 44700 to 48900), corridor and room scenes are lit and textured. Three frames show only a blue-black screen with the clock box (49500, 56100 "Early Morning" title card, 59100): probably fades or title cards, to be checked with a finer frame step. |
| F3 | ~~Corrupted background on the title scene / main menu~~ **Fixed in the test runs (17 October 2026)** | was frames 1890 to 2430 | Same family as F1: the queue of PATH3 uploads built up because the end of a draw chain with the mask left off was treated as a one-packet pulse. `ps2run_fix_path3_mask.py` now releases the whole queue when a VIF1 chain finishes unmasked. The title screen, logo, "The Journey / The Answer" and the main menu now draw correctly (formats.md). |
| F4 | Sound | everywhere | Not implemented in the translated game yet. Decision pending: run the game's own IOP sound code (option A) or re-implement the sound layer (option B). See phase1-decisions.md 1.5. |
| F6 | `[sif] command 0x80000004 has no handler` is logged about twice per frame (129,740 times in 60,000 frames) | everywhere | An IOP-to-EE system command the runtime ignores. Harmless so far; find out what it carries (see formats.md). |
| F5 | Speed and pacing never measured | everywhere | Runs so far were headless and have no real-time target. |

## 3. What still has to be tested

Order is roughly the order of the game. "Scripted" means a `--press` run can check it and a contact sheet shows the result; "live" means a person plays with the window and reports.

### 3.1 Start of the game
- Finish the walk to school and the first classroom scenes (scripted, from frame 60000). Check that school interiors, the train/monorail, and the first lesson work.
- First time the player gets control in a field (live): walking, running, camera, the command/pause menu.
- Loading between areas (doors, stairs, leaving the dorm): does every transition finish? Time each one.
- Time of day and calendar changes (Late Night, Early Morning, afternoon, evening): lighting changes, the clock box, the day counter.

### 3.2 Field gameplay
- Talking to NPCs, choice boxes, phone and message screens.
- Shops: buy, sell, equipment list, item descriptions.
- Pause menu: items, equipment, Persona list, status, Social Links, quests/requests, save, system settings.
- Social Link events (portraits, choice scoring, rank-up screen).
- Part-time jobs and study/exam screens.
- Fixed-camera areas, moving-camera areas, indoors and outdoors; weather effects.

### 3.3 The Dark Hour, Tartarus and battle
- The Dark Hour transition (green screen, coffins, the shadow stage) and the first Tartarus entry.
- Floor generation (random layouts): enter several floors; check that none hangs.
- Battle start, command menu, attacks, guard, items, Persona summon animations (every Persona that has its own), Evoker, critical hits, "One More", All-Out Attack, level up, victory screen, game over.
- Boss fights and their special effects.
- Elevator / floor-select screen, return to the lobby, Velvet Room.
- Fusion, Fusion Spells, compendium, requests from Elizabeth (and the extra FES content).
- The Answer (second scenario) is a separate disc area: test the title screen entry "The Answer", its menu and its first scenes.

### 3.4 Movies and cutscenes
- Every pre-rendered movie: opening, story movies, the ones in Tartarus, the ending (picture, timing, end of movie returns to the game).
- In-engine cutscenes with the camera moving.
- Skipping scenes with the buttons.

### 3.5 Sound (after the A/B decision)
- Background music in menus, field, battle, Tartarus; loops and fade-outs.
- Sound effects: menu clicks, footsteps, battle hits, summons.
- Voices in battle and story scenes.
- Movie audio and its sync with the picture.

### 3.6 Input
- Keyboard keys and gamepad mapping: which key is which PlayStation button, the sticks, shoulder buttons, Start/Select. Write down anything that does not respond.
- Rumble (nice to have, later).
- Pressing buttons during loading and fades: nothing should hang.

### 3.7 Saving and loading
- Memory card: save at a save point or the Velvet Room, quit, start again, load. Is the save file written, and does it come back?
- Several slots; overwriting; "Continue the game?" from the title.
- Transfer data / Journey and Answer save linkage ("Transfer your data?").

### 3.8 Stability and speed
- A long session (an hour or more): does it crash, hang, or slow down? Note memory use from Task Manager if it grows.
- Frame rate and game speed: is it a steady 60 per second (game time equals real time, per the pacing notes in phase1-summary.md)?
- Window size, full screen, resizing, alt-tab.
- Browser build (see windows-build.md): same checks, plus loading time.

### 3.9 Disc reading
- Every file the game asks for is found. Any "missing" or "not found" line in the log is a bug to report.
- Streaming files (movies, voice, music) read without stutter.

### 3.10 Drawing details (once F1 to F3 are understood)
- Transparency (fog, glass, shadows), blur and glow effects, screen fades, the "Dark Hour" colour wash.
- Text in every box: no missing letters, no wrong spacing.
- Menu backgrounds, the loading screens, the status screens with portraits.

## 4. How to run a test

- **Scripted run (headless):** `scripts/port.sh p3fes ~/p3fes.iso --native-only --frames N` with `--press frame:button` lines, then `python3 p3fes_contact.py games/p3fes/shots -o sheet --from-frame F --step 2` and `grep -cE "unhandled|missing" games/p3fes/explore.log`. Details in windows-build.md.
- **Live run:** `build/native-p3fes/ps2run games/p3fes/disc/SLUS_216.21 --disc games/p3fes/disc.iso --window`.

## 5. How to report a break

Send one message per break with:
1. **Where**: area and what you were doing (for example "dorm lobby, 7 April, after talking to Yukari").
2. **When**: frame number from a sheet, or minutes into the live run.
3. **What happened**: hang, crash, wrong picture, wrong sound, wrong behaviour.
4. **What you expected.**
5. **A picture** if it is visual (to Claude, in chat only).
6. **Numbers**: the grep count, any last lines of the log, and the ones that start with `[sys]`, `[iop]` or `[ee]`.

## 6. Order of work

1. Understand F1 to F3 (drawing faults), since they affect every scene.
2. Finish the first day and reach the first control point (3.1).
3. Reach the first Tartarus and the first battle (3.3).
4. Decide and start sound (F4, 3.5).
5. Save and load (3.7).
6. Speed, input and long sessions (3.6, 3.8).
7. Sweep movies, shops, Social Links, the rest of 3.2 to 3.4.
8. The Answer.

When a section is done, tick it here and add one line saying what broke and how it was fixed.

## 7. Results so far from scripted runs (17 October 2026)

Scripted runs from the saved states reached the school (shoe-locker tour, main lobby, first-floor hallway, Nurse's Office door prompt) with no visible graphics fault. Free-roam navigation by blind button scripts is slow and cannot tell a locked door from a fault (the character stopped at a corner at frames 108400 to 112000). Next steps for 3.1 and 3.2: a person walks the school in the window build and reports where the character cannot move and where the game stops responding.

Window build, first run (17 October 2026): works through VcXsrv on WSL1 (see windows-build.md) with `PS2_NO_VU_THREAD=1`: 24.6 fps in software drawing, lobby correct. With the VU thread on it crashed (queue shared by two threads); fixed in the last step of `ps2run_fix_path3_mask.py`, to be re-run in the window.

Window play, 17 October 2026: lobby, classroom, Dark Hour command room and saving all worked; speed 21 to 26 fps; open fault: brief stretching at the bottom left during short cut-in portraits (to be captured with F12). Loading the save back is not tested yet.
