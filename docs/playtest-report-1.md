# Playtest report 1: a fresh save, 28 October to 1 November 2026

The maintainer started a new game on 28 October and played about 20 hours over five days, from the first day to **9 July**, recording the play. This page says what held up, what broke, and what we do next. It is written from play notes; the recordings are still being reviewed, so the list will grow. Nothing here has been fixed yet.

Standing rules apply: this repository holds tools and documents only. Screenshots and recordings of the game stay on the tester's own PC.

## Setup used

| Part | State |
| --- | --- |
| Game | Persona 3 FES (USA), from the player's own disc, in the native PC window |
| Launcher | 0.56 |
| HD textures | on (High Quality Portraits, P3HD Enhanced Persona Artwork, and 85 pictures from the P3HD Widescreen pack; 851 pictures in the table) |
| Widescreen | on |
| Mods | Never Tired cheat on |
| Autosave | on |

## How far it got

From a new game to 9 July, past the first proper boss (around 10 May) and the Hierophant and Lovers bosses (9 July). No crash or lost save was reported in this stretch. The maintainer's summary was that the game is in a pretty good state.

## What worked well

- Menus, the shop, Status, the Persona list, Social Links and the Velvet Room read cleanly with the HD and widescreen pictures.
- Portraits are HD in nearly every scene, including Social Link dialogue.
- Battles, Tartarus floors and the boss fights played through.
- The Dialogue Log shows names for the Velvet Room lines (Igor and Elizabeth) and for Kenji after the 0.56 update. Ms. Toriumi's name has not been checked in play yet.

## Problems found

Each one is listed with what was seen, how often, what we suspect, and the next step. A suspicion is not a finding. Only problem 7 has been tested and fixed so far.

| # | What was seen | How often | What we suspect | Next step |
| --- | --- | --- | --- | --- |
| 1 | **Portraits clip into the environment.** The first case noticed was what looks like Yukari's portrait glitching into the dorm doorframe in cutscenes that include it. | Recurring, from time to time | A portrait or its widescreen background drawn in the wrong place or order, possibly tied to HD pictures or the widescreen patch | Match each case to a recording time; replay one with HD TEXTURES off |
| 2 | **Portraits show in the title menu** after choosing to go back to the title screen. | Seen, no count | Probably the same fault as 1: a leftover picture that is not cleared | Same test as 1 |
| 3 | **Battle backgrounds clip in and out** while a battle plays. | Seen, no count | Drawing order or a picture swapped while it is on screen | Pull frames from the recordings |
| 4 | **A character is stuck, with its walk animation visible when it should be off screen.** First seen right after the Hierophant and Lovers bosses on 9 July. | Once in this playtest; the same family of fault as the opening (see below) | The scene timing in the game's own code, not the HD pictures | Needs the clip; compare with [known-issues.md](known-issues.md) |
| 5 | **Frame rate dips or halts.** | From time to time | The maintainer suspects autosave. Not confirmed | Play an hour with autosave off and see if it stops |
| 6 | **One of Junpei's portraits is not HD.** | One found so far | A picture with no match in the HD table | Find it from a screenshot and add it, as with the 13 extra portraits |
| 7 | **The shower scene (P3CT008) had white bars** above and below the picture instead of the game's dark blue. Seen only with Simply Better FMVs on; with the pack off the bars were normal. | Every time that scene plays | The pack's bar-free version plus the LetterBoxBe-Gone size change. The exact reason is not known | **Fixed on 2 November 2026** by [p3fes_movie_bars.py](../tools/p3fes_movie_bars.py): the movie is padded back to 448 with dark blue bars and keeps its quality (see [hd-cutscenes.md](hd-cutscenes.md)). Not yet built into the launcher |
| 8 | **Some 3D Personas do not look fully clear**: Orpheus at the start of the game (9 April, Dark Hour) and Lucia when Fuuka joins (7 July). | Two cases noticed | Not known. They may be the effect itself or something we draw wrongly | Compare with the same scenes in the original game |
| 9 | **The battle background goes fully black** for a moment while the party's HUD and the boss stay on screen (seen in the Lovers fight). It also happens with Simply Better FMVs off, so it is not the movie pack. | Seen, no count | A battle background that is not drawn for a frame or two | Pull frames from the recordings, then look at how the runner draws the battle scene |
| 10 | **The battle menu looks less clear when playing on a keyboard.** The boxed key letter replaces the triangle in prompts such as RUSH. | One tester, keyboard only | Not known: it may be the prompt style and not the menu itself | Ask which part looks less clear; compare with a controller |
| 11 | **More to find** when the recordings are reviewed again. | Unknown | | Frames pulled from the recordings, in clips under 400 MB |

Problem 4 matches the open fault in [known-issues.md](known-issues.md), where characters stall in place or appear too early in the opening. That one is in the game code and not in any mod; this report suggests it also happens later in the game.

## A note on the Never Tired cheat

With Never Tired on, a character can never become Tired. That also blocks things that need the Tired status, such as the infirmary medicine on 24 April. This is expected, not a bug. If a guide asks you to do something that needs Tired, switch the cheat off for that day (Mods in the launcher), then switch it back on.

## Still untested

- The ending and the staff roll (the Spanish staff roll job titles are untested for the same reason).
- The battle tutorial texts in Spanish.
- Frame rates other than 60.
- Anything after 9 July.

## What happens next

1. Turn HD TEXTURES off and replay a scene that shows problems 1 or 2. This decides whether the cause is one of our pictures.
2. Play an hour with autosave off to test problem 5.
3. Review the recordings and add a time and scene to each problem.
4. Fix in order of how often it shows up and how much it spoils the game: the portrait problems first (1 to 3), then the missing HD portrait (6), then the stutter (5), then problem 4.
5. Then carry on from 9 July.

## How to help

Use Help > Bug report in the launcher. Say where in the game you were (the date, the scene or the menu), what you saw, and whether it happens every time. A screenshot helps. If you can, say whether it still happens with HD TEXTURES off in Settings > Display. Send the dialogue log (`saves\dialog_log.tsv`) if "Speaker N" names turn up that you can identify.
