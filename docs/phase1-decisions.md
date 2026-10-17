# Phase 1 decisions: what we need to settle, and how

This is a decision memo for the five open questions in [section 1 of the Phase 0 list](phase0-todo.md). It has no results yet; it says what each choice means, what it costs, and the first investigation that would settle it. Where something is a guess, it says so.

## What we already know (from the executable)

- One MIPS R5900 program, `SLUS_216.21`, loaded at 0x00100000 to 0x009ACC80 (about 9 MB), no symbol table. No sign of overlays or code loaded later, so probably all game code is in this file.
- Sony SDK libraries and CRI middleware (file system, ADX audio, SFD video) built in early 2005.
- About 15 IOP modules (programs for the PS2's second processor) loaded from the disc.
- The game's scripts (`.BF`) call a table of 213 game functions, so a lot of game logic is data, not code.

## 1.1 Recompile or decompile?

| | Static recompilation | Decompilation |
| --- | --- | --- |
| What it is | A tool translates the R5900 machine code into C++, which is compiled for PC. A runtime stands in for the PS2's hardware. | People rewrite the game's code as readable source, function by function, until it matches. |
| Cost | The tool and the runtime are the work; the game's code is translated in bulk. | Roughly a person-year or more for a game this size; progress is slow and very manual. |
| Result | Runs the original code; modding by replacing files and patching. Fast to a first result. | Clean source, easy to change, fully portable. |
| Risk | The tool must handle everything the game does (VU code, self-modifying tricks, odd library calls). | Never finishes if the community loses interest. |

Reading: static recompilation is the realistic first path, and a decompilation can grow on top of it later, one function at a time. There is an open-source project of this kind, PS2Recomp by ran-j, which turns PS2 programs into C++; as of early 2026 press coverage it was experimental and still in early days ([Time Extension](https://www.timeextension.com/news/2026/01/native-pc-ports-of-ps2-games-could-be-on-the-way-thanks-to-new-recompilation-experiment)). We have not tried it on this game.

First investigation: read what PS2Recomp supports today, then run our executable through it as a prototype and list what fails. Success is not a running game; it is a list of the first ten problems.

## 1.2 The vector units (VU0, VU1)

The PS2 has two small vector processors with their own programs ("microcode"). Games use VU1 for most 3D drawing and VU0 for maths. A recompiler that only handles the main CPU leaves these out.

What we need to know: how many different VU programs the game has, how big they are, and whether the game uses VU0 inline in its CPU code (fast, hard to translate) or only as separate programs.

Result of the first scan (see formats.md): VU0 macro mode is used heavily (5,938 instructions in 716 places), the code uploads microcode through VIF and DMA (VU memory is written directly in only 12 places), and there are about 170 different VU1 programs (172 of 181 uploads differ, 677 KB), some in families of near-copies. Consequence for the decision: treat the microcode as data to be run or translated automatically by the runtime, not by hand; the open choice is interpreter first (simple, slower) versus translating the programs ahead of time (faster, more work).

Original plan for the first investigation: add a scan to `p3fes_exe_scan.py` that finds VU program uploads in the executable (the data blocks sent to VU memory) and counts the distinct programs and their sizes. If there are a handful of small programs, translating them by hand or by a second tool is realistic. If there are dozens of large ones, graphics is the long pole of the whole project.

## 1.3 CVFS/ROFS file calls

We already read every archive format. What is open is how the game asks for files: through the CRI file system calls (`cvFsOpen`, `ROFS_Open`, ...). The runtime must answer those calls from the player's own disc image or a mod folder.

Choice: replace the CRI calls with our own file functions (clean, needs each call understood), or emulate the lower layer (the disc driver) and keep CRI's code running (less to understand, more to emulate).

Result of the first scan (see formats.md): the game asks by path through a central request function (0x00100D80, 218 callers) on top of a CRI `cvFs` device layer that can register new devices. Proposal: serve files at the `cvFs` device level. Read in the second pass: `cvFsOpen(path, mode, option)` finds a device by name and calls the device's function table (open at +16, read request at +32), so the clean replacement point is the roughly 25 public `cvFs*` functions. Still to check: whether anything calls the Sony `sceCd*` read functions directly.

Original plan: list every CRI file function the executable calls and what arguments it passes (a directory, a name, a number?). If the game asks by name, a replacement is simple.

## 1.4 Frame pacing

The game is built for a fixed 60 Hz (NTSC) refresh. To raise the frame rate safely we must know whether game speed is tied to frames, and where the main loop waits for the screen.

Result of the first scan (see formats.md, `p3fes_pacing.py`, run on the real executable): the game does not wait for the screen in a polling loop each frame. A **vertical-blank interrupt handler** (0x004D47F0, registered at 0x004D6470 together with two DMA-end handlers at 0x004D4350) flips the display buffers once a "drawing finished" flag is set, and a small counter against a target byte holds a minimum number of refreshes per drawn frame (the usual 60 / 30 frame mode switch). The program contains no read of the CPU cycle counter, no 1/60 or 1/30 constants, and the EE timers appear only in two small groups (a stopwatch near 0x00197030 to 0x00199140 and the CRI library at 0x0050E000). Reading: **game time advances per frame, not by a clock.** For a native build that means a fixed-step loop at the console's 59.94 Hz tick, with the display flip as the sync point; a higher frame rate must be done by interpolating drawing, not by running the game logic faster. Still unproven: that nothing reads the real-time clock for gameplay, which only a run can show.

Original plan, for reference: find the call that waits for the vertical sync (a Sony graphics library function, so it has a known name pattern) and the main loop around it, then check whether game time advances per frame or by a clock. Our script-function table already names a few timing functions to start from.

## 1.5 IOP modules

The IOP modules do sound, memory card, controller, disc and video decode work on the second processor. A native build replaces each of them with PC code.

Result of the first scan (see formats.md): the game loads 14 modules by name, 5 for input and saves (PADMAN, SIO2MAN, SIO2D, DBCMAN, MC2_S1) and 9 for sound (LIBSD, SDRDRV, MODHSYN, MODMSIN, MODSESQ, SKSOUND, SKHSYNTH, SKSESQ, CRI_ADXI). Input and saves are small: replace the EE-side controller and memory-card calls with host input and save files. Sound is the large piece, and it is a real choice: (A) re-implement the sound API on the host (sound effects from the `.hd`/`.bd`/`.sq` files we already decode, ADX streams decoded on the host, a software mixer for the SPU2 voices), or (B) run the original modules by emulating the IOP processor and the SPU2 chip (exact behaviour, a lot more machinery). Open: `IOPRP310.IMG`, which bundles the base IOP modules.

Result of the IOP image scan (formats.md): the reboot image (`IOPRP310.IMG`, same set as the older 300) holds only the 17 standard Sony system modules; five system libraries (intrman, dmacman, heaplib, secrman, vblank) come from the console's ROM. The sound choice therefore reads: **A. run the original sound modules** (needs an IOP processor interpreter, those five libraries and an SPU2 sound-chip model; the game's sound behaviour is then exact), or **B. re-implement the sound layer** (needs the EE-to-IOP command protocol of the nine sound modules understood; more work in reading, no processor emulation). Not decided; the next evidence is a real run, which shows how many sound commands the game actually sends.

Original plan: list the modules on the disc, name what each does, and mark which ones the game calls into (sound and memory card most likely). Most can be replaced by thin PC code; the sound driver is the one to look at closely.

## What already exists (research, October 2026)

Read from public pages only; nothing below was run or verified by us. Claims are the authors' own.

- **PS2Recomp** (ran-j, GPL-3.0): a static recompiler that turns a PS2 ELF into C++ for PC. Early 2026 coverage described it as experimental with no playable games; it listed the R5900 instruction set with 128-bit instructions, VU0 macro mode, relocations and overlays, function stubbing and instruction patches through a TOML config, and said the graphics chip needed an external implementation and VU1 support was limited ([Time Extension](https://www.timeextension.com/news/2026/01/native-pc-ports-of-ps2-games-could-be-on-the-way-thanks-to-new-recompilation-experiment), [Gigazine](https://www.gigazine.net/gsc_news/en/20260130-ps2recomp)). A later video title suggests it has since run a game; we have not checked.
- **PS2 Web Recomp** (snuri00, MIT, repository created recently, 113 commits, 1 star): the same method, aimed at the browser. Its README claims: the game's EE code is translated to C++ and compiled to WebAssembly (`eerecomp`); the EE operating system is reimplemented; the IOP runs the game's own `.IRX` modules on an R3000 interpreter with the IOP kernel reimplemented; VU1 microprograms are compiled ahead of time or translated when first met; the GS is rebuilt on WebGPU compute shaders; the SPU2 and MPEG-2 movie decoding are reimplemented. Two games are said to run: Gran Turismo 4 (PAL) from boot through menus and races, and God of War II from menus into combat, with the author's own speed figures and a demo video as the only evidence. The README says another game "will most likely stop at a system call or an IOP library function nobody implemented yet", asks users to bring their own disc image, and asks that generated code is not published ([repository](https://github.com/snuri00/ps2-web-recomp)).

What this changes, if the claims hold: the approach we are weighing has been shown to work end to end by someone else; their choices (run the original IOP modules on an interpreter, translate VU1 programs automatically, GS on a modern GPU API) are answers to 1.2 and 1.5 that we can compare with our own measurements; and a prototype for 1.1 does not have to start from nothing. What it does not change: our game is different, so the first run will stop somewhere, and the useful result is where.

Result of the prototype (see formats.md): their recompiler translated our executable in 1.7 seconds (1,187,301 instructions, 9,446 functions, 0 rejected) and the generated C++ passes a syntax check with zero errors. The first real problems will come from running it, which needs the disc image and a GPU.

Proposed prototype for 1.1 (done as far as the executable goes): build their recompiler on a machine with the tools they list, run it on our `SLUS_216.21`, and write down the first problems. Keep everything it generates out of the repository.

## Suggested order

1. 1.1, as a prototype (it tells us what the rest of the list really costs).
2. 1.2, because it decides how big the graphics phase is.
3. 1.3 and 1.5 together (both are about replacing a layer).
4. 1.4 last (it only matters once something runs).

Nothing in this memo is decided yet. Each investigation ends with its result written into [formats.md](formats.md) and a status change in the Phase 0 list.
