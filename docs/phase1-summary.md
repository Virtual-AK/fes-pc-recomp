# Phase 1 summary: what is settled, what needs a real run, first build milestone

Status: first pass of all five questions is done (October 2026). Details and addresses are in `formats.md`; options in `phase1-decisions.md`. Everything below comes from reading the executable and the disc files, not from running the game.

## Settled (from reading)

| Question | Answer |
|---|---|
| 1.1 Recompile or decompile | **Recompile.** An existing MIT-licensed recompiler (`eerecomp`) translated our executable in 1.7 s (1,187,301 instructions, 9,446 functions, 0 rejected) into 297 C++ units, and all of them compile and link with 0 errors. Decompiling to readable source is not needed to get a playable port. |
| 1.2 Vector units | Heavy VU0 macro-mode use in game code and about 170 different VU1 programs (172 of 181 uploads differ). They need either translation or an interpreter; the recompiler's runtime already has a VU path to be tested. |
| 1.3 File access | One request function (`0x00100D80`) over the CRI `cvFs` device layer. Plan: host versions of the `cvFs` functions serve files from the player's own disc image. |
| 1.4 Frame pacing | VBlank interrupt handler flips display buffers; a counter/target pair limits frames per refresh; no clock reads in game logic. Game time is counted in frames: run a fixed-step loop at 59.94 Hz and raise the displayed frame rate by interpolating drawing only. |
| 1.5 IOP modules | 14 modules loaded by name: 5 for input and saves (small, replace with host input and save files), 9 for sound (the large piece, still a choice between re-implementing and running the original modules). |

## Needs a real run (cannot be answered by reading)

- Which of the 55 system calls without a named case in the runtime are actually reached.
- Whether the VU1 programs and graphics packets draw correctly through the runtime's graphics path.
- Whether anything reads the real-time clock for gameplay, and what sets the frame-limit target byte to values other than 0.
- Whether the CRI audio and video code reads the disc directly with `sceCd*` calls instead of through `cvFs`.
- Sound: pick between re-implementing the sound driver and running the original IOP modules. Open `IOPRP310.IMG` first (not yet opened).

## First run result (16 October 2026)

The translated game was built and run on a Windows PC (through WSL2): it ran 3,600 frames with no unhandled system call, no missing IOP function and no new code found, and the runtime loaded all 14 IOP modules, so the sound question leans to option A (run the original modules). On screen it reached the publisher logo, the opening video, the title screen, the main menu and the Load Data screen within 3,600 frames; the menu background shows corrupted texture patches (a drawing fault). Driving it through New Game it then reached the opening movie after 16,000 frames with no unhandled system call and no missing IOP function at all. Next: past the opening into the first playable field, then battles. Details in `formats.md`.

## First build milestone (proposal)

"Boots to the first logo on a PC." Steps:
1. Build the existing runtime and the generated code on Windows, through WSL2 (step-by-step in [windows-build.md](windows-build.md); the tools it needs are git, CMake, Ninja, a C++20 compiler, Python 3, 7-Zip, SDL2 and wgpu-native, which the script fetches). This is the biggest step for a non-programmer; a volunteer with C++ experience should own it.
2. Run with a disc image supplied by the player; log the first unimplemented system call or IOP function it stops at (the runtime's own README says this is where other games stop).
3. Implement that one thing, repeat. Each stop is a small, testable task, which suits the planned Discord testers ("play it, break it, report how").

## Rules that stay

- The repository holds tools and documentation only; generated code, extracted data and disc contents never go in.
- The player supplies their own disc dump.

## Fifth run (16 October 2026, updated 17 October)

The translated game now reaches the first 3D scenes in the dormitory (dialogue, choices, time-of-day box, walking, next morning), 60,000 frames from the first boot. Known faults: coloured noise on floors and walls, very dark scenes, one corrupted menu background. The floor noise has a strong lead: the runtime ignores the MSKPATH3 command that interleaves the game's texture uploads with its draws (formats.md, fifth experiment); not yet confirmed. See formats.md for details.

Next stage: see [playtest-plan.md](playtest-plan.md).
