# Achievements plan (research, 25 Oct 2026)

**Status: parked, marked for last.** It would take a long time to set up and was put off on purpose. Do the other roadmap items first.

Two routes were looked at. RetroAchievements itself is probably closed to us (their rules exclude recompilations from standalone sets; the emulator route needs admin approval). The alternative is **our own local achievement system**: a list of conditions checked against game memory every frame, an unlock popup drawn in the PC window, unlocks saved next to the saves, an Achievements screen in the launcher. Ideas can follow the kinds of milestones the RetroAchievements set uses (bosses, Social Links, Compendium), but we write our own names and conditions and find the memory addresses ourselves, because their set is community-authored under their site's terms and we have not checked whether it may be reused. A first batch of 15 to 20 achievements is realistic; all 170 would be a long project. Suggested first prototype when this is picked up: one achievement (a Social Link rank) that unlocks with a popup and saves.

The research on RetroAchievements follows.

Goal: unlock the existing Persona 3 FES achievements while playing in the PC window (and maybe the browser build). Nothing is built yet.

## What the RetroAchievements rules say
- **Standalone route is closed to us.** The standalone-support page says: "Decompilations, recompilations, and other unofficial ports are not eligible for standalone sets." Standalone also needs a RetroAchievements Developer to propose it.
- **Emulator route is the only candidate.** Our PC window runs the player's own unmodified disc image on a PS2 runtime (the recompiled game code works on a full PS2 memory image), so it can be argued to be an emulator-style host. Whether the admins accept that is **their** decision; we should ask before building much (RAdmin / the RetroAchievements Discord or forum).
- **Hardcore rules** (needed for hardcore points; casual has no such limits): no cheats, rewind, slowdown, frame advance, save-state loading, resume (a resumed session drops to casual), memory editors/debuggers, scripted input. Widescreen-style quality-of-life patches are exempt. Rich presence and leaderboards must stay on.
- Our PC window has save states (F6), autosave and resume, fast-forward (Tab), cheats and mods, so a first version would be **casual (softcore) only**, with hardcore a later step that switches those off.

## The existing set
- Shin Megami Tensei: Persona 3 FES (PlayStation 2), retroachievements.org/game/2657: 170 achievements, 1,475 points. Easy mode is blocked; many need New Game / New Game+. Subsets exist (Orpheus Only, Heart Items). The set was written against PS2 emulators, so its memory addresses are the real PS2 main-memory addresses.
- Not checked yet: which disc hashes it accepts (we need the NTSC-U SLUS-21621 one), and any note about mods.

## How the integration would work (rcheevos, C library, MIT licence)
- Use `rc_client`: `rc_client_create(read_memory, server_call)`, log in with the player's own account (username + token, stored on their computer, never in the repository), `rc_client_begin_identify_and_load_game` (PS2 hash = system config + main program, so file mods that do not touch the program leave it unchanged; translation / widescreen code patches need checking), `rc_client_do_frame` once per frame, `rc_client_reset` on reset, an event handler for unlock / progress / leaderboard popups.
- rcheevos does no networking: the host sends the HTTP requests (the PC runner needs a small HTTPS client, e.g. libcurl, or the launcher can do it).
- The read-memory callback reads the runner's emulated main memory (we already do this for pokes, the dialogue log and the speedrun clock).
- Must be identified honestly (own user agent, not pretending to be PCSX2).
- Unlock popups: draw in the window (we already have an overlay for the Log box) and add a launcher login screen.

## Open questions / next steps
1. Ask RAdmin whether a static-recompilation PC window can be approved as an emulator (and what they want to see). This decides everything else. A working casual-mode prototype helps the case.
2. Confirm the accepted disc hash(es) and whether mods (Fast Start, undub, prompts, widescreen) are allowed in hardcore.
3. Prototype: rcheevos in the PC runner, memory read, one achievement unlocking locally (no server) to prove the memory map.
4. Launcher: login (token only stored locally), on/off, Casual/Hardcore switch (hardcore turns off save states, resume, fast-forward, cheats).
5. Browser build: separate question (WebAssembly build of rcheevos + HTTP from the page); do the PC window first.

Sources: docs.retroachievements.org (standalone-support, hardcore-compliance-requirements), rcheevos README and rc_client.h, retroachievements.org/game/2657.
