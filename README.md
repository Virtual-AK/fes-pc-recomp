# ps2-native-tools

A community effort to run a PlayStation 2 role-playing game (Persona 3 FES, NTSC-U, serial SLUS-21621) natively on PC and in the browser, with no emulator. The goals are higher resolutions, higher frame rates and easy mod support.

**Status: research and tooling.** Nothing here runs the game yet. The tools read, unpack, convert and (for text) edit and repack the game's data from your own disc, and the file formats are documented.

<!-- progress:start -->
**Overall progress: about 77%** (rough estimate by the maintainers; the game already starts and plays in the browser and in a PC window, and most of what is left is testing and polish)

`███████████████░░░░░` 77%

| Phase | Progress | |
| --- | --- | --- |
| 0. Research and tooling | `█████████████████░░░` | 85% |
| 1. Pick the approach, prototype | `████████████████████` | 100% |
| 2. Runtime layer (files, audio, video, input, saves) | `██████████████████░░` | 90% |
| 3. Graphics (GS and vector units to a modern API) | `█████████████████░░░` | 85% |
| 4. Playable desktop build, QA | `████░░░░░░░░░░░░░░░░` | 20% |
| 5. Browser build and mod tooling | `████████████████░░░░` | 80% |

Phase 0 is about 85%: disc, archives, textures, audio, sound effects, text, models, animations and field geometry are done; scripts, effect data, field tables and the remaining model chunks are partly understood. Phases 1 to 3 work end to end: the game is recompiled and runs from the player's own disc with graphics, sound, movies, input and saves, and the opening, town and first dungeon floors have been played through. Phase 4 (testing the whole game) has only just started, and phase 5 has the browser build with card backups, autosave, key and controller settings, and a first mod route (patch files baked into a separate recompiled copy), and a one-command installer ([docs/install.md](docs/install.md)) tried on a fresh copy (browser build, title screen to the first Tartarus floor); the PC window from a fresh install is still untested. Since then the launcher gained loose-file mods (folders, zip, 7z and rar, merged Aemulus-style with a priority order), browsing and previewing GameBanana mods before installing, battle and menu portrait mods, and ten colour themes, one of them (Twelve) unlocked by saying you finished The Journey (automatic detection from the memory card is on hold until before and after card copies exist). The PC window is still slow: about 25 fps through VcXsrv on WSL1, and no better on WSL2 with WSLg, because Ubuntu has no Vulkan driver for the graphics card there (see [docs/better-window.md](docs/better-window.md)). The next step for it is a native Windows build, to be scoped first; the browser build runs at 60 fps meanwhile. The percentages are a guide, not a promise. See [docs/roadmap.md](docs/roadmap.md).
<!-- progress:end -->

| Area | State |
| --- | --- |
| Disc, archives, containers | Read and unpacked. |
| Textures | Converted to PNG. |
| Voice audio (`.ADX`, `.AFS`) | Converted to WAV. |
| Sound effects (`.SE` banks) | Samples decode to WAV; the sequences (`.sq`) render to audio (timing, pitch, envelopes and pan not exact yet). |
| Game text | Extract, edit, repack, patch into a disc copy that plays. |
| 3D models | All 3,766 models export to glTF with skeletons, skin weights and animations (checked in Blender on a character, an NPC, a Persona, a boss, a weapon, a facility piece, a field object and an effect model). |
| Effect data (`.BED`) | Structure and parameter-block headers read; the parameter fields are not decoded. |
| Field (map) data | All 819 field `.RWS` files export to `.obj` with textures. The `n*.bin` tables are calendars (dates and entries, checked on 107 files); `.FBN` records are placements (position and rotation). Script calls `field_357(F, id)` return an object handle that `field_358` places in a slot; whether the id is tied to the calendar is not settled (see [docs/formats.md](docs/formats.md)). `.HBN` and `h*.bin` are not decoded. |
| Scripts (`.BF`) | Layout, instruction set and the table of the 213 game functions the scripts call are known ([docs/script-functions.md](docs/script-functions.md)); what each function does is not decoded yet. The dialogue inside scripts extracts and repacks like other text. |

The next phases need developers; see [How to help](#how-to-help).

## Ground rules
- **Bring your own disc.** Everyone uses their own legally owned dump. This repository contains no game code, assets, BIOS files, disc images or extracted files, and never will. Please do not attach any of those to issues or pull requests.
- **Tools and documentation only.** The tools read your disc image and write files on your own computer. Keep what they produce private.
- **Independent project.** It is not affiliated with or endorsed by the game's publisher or developer, so we avoid their names and logos in the project branding. The game's name appears only where needed to say what the tools work with.
- Nothing here is legal advice. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full rules.

## What works today
All tools need only Python 3.8 or later (no extra packages). Test them without a disc: `python tests/run_tests.py`. Every tool prints `--help`.

**Look at a disc**
| Tool | What it does |
| --- | --- |
| `p3fes_inspect.py` | Checks a disc image: region, serial, boot executable, hashes and file list. `--compare OTHER_ISO` lists the differences between two images. |
| `p3fes_cvm.py` | Opens the CVM archives on the disc and reports their file types, sizes and folders. |
| `p3fes_unpack.py` | Extracts all files from your disc into a folder, and with `--containers` splits the container files into the files inside. |

**Pictures and sound**
| Tool | What it does |
| --- | --- |
| `p3fes_tmx.py` | Converts the `.TMX` textures from the extracted folder to `.PNG`, with an optional browsable gallery page. |
| `p3fes_audio.py` | Splits the `.AFS` voice archives and converts `.ADX` audio to `.WAV`. |
| `p3fes_bed.py` | Sound effects: `banks` decodes the `.SE` banks to `.WAV`; `seq` renders their sequences to `.WAV` (flat `seq_wav` folder); other commands write survey reports. |

**Text (editing works)**
| Tool | What it does |
| --- | --- |
| `p3fes_text.py` | `extract` writes the game's message text (the `.BMD` files and the dialogue inside `.BF` scripts) to editable text files; `repack` builds modified files from your edits; `diag` reports (numbers only) why a file cannot be rebuilt. |
| `p3fes_textfind.py` | Searches the extracted text for a word or phrase and shows the file, message and line of each match. |
| `p3fes_textcodes.py` | Counts the control codes (the `{F1 05}` style tokens) in the extracted text, with examples. |
| `p3fes_patch.py` | Writes changed files (from a folder laid out like the extracted one) into a COPY of the disc image, then verifies the copy. In-place only: files must fit their existing space. Use `--dry-run` first. |

**3D models**
| Tool | What it does |
| --- | --- |
| `p3fes_rmd.py` | `export` writes one model (`.RMD`) as `.obj` and `.mtl` with its textures as PNG; `batch` does a whole folder and writes a report of what failed and why; `info` lists what is inside; `textures` writes only the textures; `skeleton` shows the bones, skin weights and animation headers (a diagnostic). `gltf` writes mesh, skeleton, skin weights and the animations for Blender `batch --gltf` does a whole folder. `export` writes a static T-pose. |

**Research tools** (for people working on formats; most users never need these)
| Tool | What it does |
| --- | --- |
| `p3fes_exe_scan.py` | Scans the boot executable for library versions, device paths, file-name patterns and library function names. |
| `p3fes_formats.py` | Surveys how the main file types are built: containers, AFS, ADX, SFD, and header samples for every other type. |
| `p3fes_models.py` | Surveys the `.RMD` files: header patterns, chunk lists, strings. `--tree` and `--hex` look inside one file. |
| `p3fes_bmd.py` | Shows the structure (and optional hex dump) of one `.BMD` message file. |
| `p3fes_fx.py` | Surveys the `.BED` effect files: `survey`, `nodes` (element types and examples), `fields` (every parameter word per type), `show` and `dump` for one file. |
| `p3fes_field.py` | Surveys the field (map) data: `survey` (file types, sizes, first numbers), `names` (entry names in the field packs), `words` (every word position of the small field files), `check` (size rules of `.FBN`/`.HBN`), `fbn` (all `.FBN` records), `dump` (one small file as words) `split` (splits the `.FPC` containers into folders; needs `p3fes_unpack.py` beside it) `rws` (lists and decodes the textures in the `.RWS` files; needs `p3fes_rmd.py` beside it) `nbin` and `ncal` (the calendar tables), and `ncodes`, `fbnlink`, `objids`, `objdata`, `objwhere`, `calcalls`, `datecheck`, `hbn`, `hbnlink`, `hbnmap`, `hbnprops`, `slotcalls`, `calls312`, `warpcalls`, `variantargs`, `variantcalls`, `fbnvariants`, `fbnmap`, `fbnobj`, `callprocs`, `doorwhere`, `hbinrecs`, `eventvariants`, `fbndump`, `fbnchars`, `hbinprocs`, `entrycount`, `hbnobj`, `entrywhere`, `doornorec`, `hbinw5`, `emptyfiles`, `pakscan` and `treediff` (check script object ids against model file names, the calendar and the small field files) and `fields` (writes every field's models as `.obj` and its textures as `.png`, with a report of anything odd; needs the `split` folders and `p3fes_rmd.py`). |
| `p3fes_filecalls.py` | `scan` finds the file-related strings in the boot executable and the functions that load them and how often they are called (names, addresses and counts only). |
| `p3fes_iop.py` | `scan` lists the IOP modules (`.IRX`) on the disc and in the executable: names, sizes, and the libraries each exports and imports. |
| `p3fes_pacing.py` | `scan` finds how the executable keeps time: system call wrappers, vertical-sync and timer hardware use, interrupt handlers, loops around sync calls, frame-time constants. |
| `p3fes_iopimg.py` | `scan` lists the files inside the IOP reboot image (`IOPRP310.IMG`): module names, versions, sizes, the libraries each exports and imports. |
| `p3fes_contact.py` | Makes contact sheets (PNG) from the test run's frame pictures, so many frames can be viewed or sent as one image. |
| `p3fes_primsum.py` | Reads a `PS2_TRACE_PRIM` file and lists the biggest shapes with their real screen boxes, blend and colour. Numbers only. |
| `p3fes_primdiff.py` | Compares two `PS2_TRACE_PRIM` files (for example PC runner vs browser) shape by shape, ignoring frame numbers; shows the first difference. |
| `p3fes_wavstat.py` | Summarises a WAV written by `PS2_DUMP_AUDIO`: length, peak, loudness per second, silent seconds. Numbers only. |
| `p3fes_ppm2png.py` | Turns raw `.ppm` pictures (frames, texture dumps) into `.png` files Windows can open. Pictures stay on your PC. |
| `ps2run_trace_patch.py` | Adds an opt-in texture and transfer trace (`PS2_TRACE_TEX=from,to`) to the PS2 Web Recomp graphics source, tagged with frame numbers; for finding the cause of picture faults. Steps 2 to 5 below build on it and are run in order in the same folder. |
| `ps2run_trace_patch2.py` | Second trace step: bytes each GS upload really received, and how many were non-zero. |
| `ps2run_trace_patch3.py` | Third trace step: `PS2_DUMP_TEX=frame,folder` writes each texture set in that frame as a grey picture of its palette indices (local use only). |
| `ps2run_trace_patch4.py` | Fourth trace step: also writes each dumped texture in real colour (local use only). |
| `ps2run_trace_patch5.py` | Fifth trace step: `PS2_TRACE_M3=1` prints each MSKPATH3 command and each GIF transfer with its path, to see how uploads and draws interleave. |
| `ps2run_trace_patch6.py` | Opt-in trace `PS2_TRACE_PRIM=from,to`: one line per shape the GS draws in those frames (type, texture, blend, and every corner's position, colour and picture coordinates, plus the screen offset ofx/ofy and the global switches PRMODECONT, COLCLAMP, PABE, FBA, SCISSOR). Numbers only. Running it again upgrades an older patched tree. |
| `ps2run_trace_patch7.py` | Opt-in trace `PS2_TRACE_VIF=from,to`: one line per VIF UNPACK (format, mask, cycle, mode, address, count) and per VU program start in those frames. Numbers only. |
| `ps2run_trace_patch8.py` | Opt-in trace `PS2_TRACE_VUMEM=from,to,ADDR,QWORDS,RUN`: dumps the VU1 input data (as hex and floats) at the start of one run of the VU1 program at ADDR. Numbers only. Needs patch 7. |
| `ps2run_trace_patch9.py` | Opt-in `PS2_DUMP_TEXDRAW=frame,folder`: writes each 4-bit/8-bit texture as it looks at its first draw in that frame (run with `PS2_GS=cpu`) and prints a numbers-only summary line (how many indices are non-zero, palette start). Needs patch 6. Pictures stay on your PC. |
| `ps2run_trace_patch10.py` | Opt-in `PS2_SKIP_PRIM=frame,mode,value`: leaves out one class of shapes (by drawing setup, textured or not, blending, shape type, untextured shapes of one type (flat), depth-write on or off (zmsk), or texture base) in a single frame, so a frame picture shows which class causes a visual fault. Needs patch 6. |
| `ps2run_trace_patch11.py` | Opt-in trace `PS2_TRACE_XGK=from,to,RRGGBBAA`: prints the first three VU1-to-GS packets in those frames that contain a colour with those bytes, every quadword in hex, match marked. Numbers only. |
| `ps2run_trace_patch12.py` | Opt-in trace `PS2_TRACE_VULQ=from,to,LO,HI,RRGGBBAA` (with `PS2_VU_INTERPRET=1`): follows the VU1 loads and stores that touch data-memory quadwords LO..HI and prints them (pc, register, value, offset, the four words) for the packet that contains that colour. Numbers only. |
| `ps2run_vif_v2zero_patch.py` | Fix for the cut-in panel glitch: a VIF UNPACK with two values per entry (V2) now writes 0 into the third and fourth lane instead of repeating the first two (the repeat gave the first corner of each panel bad texture coordinates and colour). `PS2_VIF_V2REPEAT=1` restores the old behaviour, `PS2_VIF_V2KEEP=1` leaves the two lanes untouched, for comparing. |
| `ps2run_nodraw_patch.py` | Speed test switch `PS2_NODRAW=1`: the GS draws nothing, so `PS2_TIME` shows the cost of everything except drawing. Timing only. |
| `ps2run_primcount_patch.py` | `PS2_TRACE_PRIMCOUNT=1` prints one line per frame with the number of shapes (all, and those drawn to the screen buffer), to find heavy frames cheaply. |
| `ps2run_vudump_patch.py` | `PS2_DUMP_VU1=FRAME,ADDRESS` saves the VU1 program, its memory before and after, and its registers for one packet, so the program can be read offline (game data: keep local). |
| `ps2run_vubranch_patch.py` | Fix for the half-drawn cut-in portraits, part 1: in the VU interpreter a conditional branch right after an integer instruction sees the OLD register value, as on the real chip (`PS2_VU_BRANCHNEW=1` switches it off for comparing). |
| `ps2web_vubranch_patch.py` | The same fix for the browser's VU compiler (`runtime/src/vu_jit.cpp`). |
| `ps2web_controls_patch.py` | Browser keys like PCSX2's default (WASD left stick, TFGH right stick, IJKL face buttons, Q/E shoulders, 1/2/3/4 for L2/L3/R2/R3) plus mouse look: click the picture, move the mouse sideways to turn the camera. |
| `ps2web_cardbackup_patch.py` | Memory card backups for the browser build: the page keeps the last 10 versions of the card (each in-game save, and once at page start) with a Backups button to restore or download one. Restoring backs up the card it replaces. |
| `ps2run_controls_patch.py` | The same PCSX2-style keys for the PC runner window (WASD left stick, TFGH right stick, IJKL face buttons, Q/E shoulders, 1/2/3/4 for L2/L3/R2/R3). No mouse look in the window yet. |
| `ps2web_keyremap_patch.py` | Key remapping for the browser build: a Keys button opens a panel, click a row and press the new key. Saved in the browser, with Reset to defaults. See `docs/controls.md`. |
| `ps2run_keyremap_patch.py` | Key remapping for the PC runner window from a `keys.txt` file (`cross = Z` style lines, SDL key names). See `docs/controls.md`. |
| `ps2web_padremap_patch.py` | Controller panel for the browser build: with a controller connected the Keys button shows that controller's own button names (PlayStation, Xbox or Nintendo) and lets you rebind its buttons, saved per controller type. See `docs/controls.md`. |
| `ps2run_sifquiet_patch.py` | Prints the harmless `[sif] command 0x........ has no handler` message once per command number instead of every time, for both the PC runner and the browser build. |
| `ps2web_autosave_patch.py` | Full-state autosave for the browser build: the whole game is saved every 2 minutes and after each in-game save, and the start screen offers Resume to continue exactly where you were. An Autosave button lists, resumes and deletes the saves. See `docs/autosave.md`. |
| `ps2web_autosaveopts_patch.py` | Autosave settings for the browser build: turn automatic saving off or pick the interval (1 to 30 minutes), turn off saving after each in-game save, and choose how many saves to keep. See `docs/autosave.md`. |
| `p3fes_install.sh` | One-command install for newcomers (Ubuntu on Windows or Linux): installs packages, downloads the tested version of PS2 Web Recomp, applies every patch in order, builds from your own disc and writes `play.sh`. See [docs/install.md](docs/install.md). |
| `ps2run_tricenter_patch.py` | Opt-in test (`PS2_TRI_CENTER=1`, CPU drawing route): triangle textures are read at pixel centres, like the real chip, to test the dashed outlines on the Tartarus minimap tiles. |
| `ps2run_flipfix_patch.py` | Opt-in test (`PS2_TRI_FLIPFIX=1`, CPU drawing route, use with `PS2_TRI_CENTER=1`): flipped minimap tiles are moved one texel so they line up with unflipped ones. |
| `p3fes_pnach_apply.py` | Bakes a PCSX2 `.pnach` code patch (such as a gameplay mod) into a copy of the boot program for recompiling, checks it against the original words named in the patch's comments, and lists the new code entry points. See [docs/mods.md](docs/mods.md). |
| `ps2gpu_flipfix_patch.py` | Fix for the misaligned tiles on the Tartarus minimap: in the graphics-card route (browser build and PC window) flipped tiles are moved one texel so they line up. Apply `ps2gpu_tricenter_patch.py` first, then rebuild both builds. |
| `ps2gs_uploadclamp_patch.py` | Fix for the line of coloured specks along the bottom edge of the anime movies: texture clamping now stops at the area the game really uploaded (both drawing routes). `PS2_NO_UPLOADCLAMP=1` turns it off for comparing. Rebuild both builds after applying. |
| `ppm2png.py` | Turns saved `.ppm` frames into `.png` pictures that can be opened or sent, with no extra programs needed. |
| `ps2gpu_tricenter_patch.py` | Fix for the dashed tile outlines on the Tartarus minimap: in the graphics-card route (browser build and PC window) triangle colours and textures are read at pixel centres, like the real chip. Rebuild both builds after applying. |
| `ps2run_primarea_patch.py` | `PS2_TRACE_PRIMAREA=N` makes `PS2_TRACE_PRIM` print only shapes covering at least N pixels, so long frame ranges stay small. |
| `ps2web_logcapture_patch.py` | Browser debugging aid: `?capture=SECONDS` collects everything the game prints (trace lines too) and downloads it as `ps2web_log.txt`. |
| `ps2run_fix_path3_mask.py` | Fix for the floor noise, dark rooms and title-scene corruption: makes the PS2 Web Recomp runtime hold PATH3 (texture upload) data while VIF1 has it masked and release it one packet per mask pulse. Confirmed in the single-thread test runs; the last step covers the threaded window build but has only been compiled (see formats.md). |
| `ps2run_window_capture_patch.py` | Adds F12 "rewind capture" to the game window: the last 300 shown frames are saved as pictures (they stay on your PC) so a split-second glitch can be inspected afterwards. |
| `ps2run_window_savestate_patch.py` | Adds an F6 key to the game window that saves the exact machine state (`live_1.state`, `live_2.state`, ...) so a short glitch can be replayed again and again without the window (`--load-state`). State files are game data and stay on your PC. Needs the capture patch applied first. |
| `p3fes_vu.py` | `scan` reports how the boot executable uses the PS2 vector units: VU0 macro-mode instructions, VU microcode blocks and microprogram uploads (numbers and addresses only). |
| `p3fes_bf.py` | The `.BF` scripts: `survey`, `analyse`, `messages`, `listing` (one script as readable statements), `msgcheck`, `balance`, `export` (every script as readable text), `context` (sample call sites of one function), `disasm` (raw instructions), `hex`; and for the boot executable: `functions`, `peek`, `code` (MIPS), `limit`, `lui`, `switch`, `ref`, `comm` (the script function table). |
| `p3fes_textsurvey.py` | Surveys the message files and file-type counts of an extracted folder. |

## Quick start (Windows)
1. Install Python from python.org (tick "Add python.exe to PATH"). In a Command Prompt, use `py` instead of `python`.
2. Download this repository (green **Code** button, then **Download ZIP**) and unzip it. Open a Command Prompt in the `tools` folder (type `cmd` in the folder's address bar). If you copy the tools elsewhere, run them from that folder.
3. Check your dump: `py p3fes_inspect.py "C:\path\to\game.iso"`
4. Extract it (about 4-8 GB): `py p3fes_unpack.py "C:\path\to\game.iso" -o "C:\p3fes\extracted" --containers --skip-video`
5. Look at the pictures: `py p3fes_tmx.py "C:\p3fes\extracted" --limit 100 --gallery`, then open `index.html` in the new `extracted_png` folder.
6. Try the audio: `py p3fes_audio.py "C:\p3fes\extracted" --wav --limit 5`

Every tool prints what it did and writes a short report or a `problems.txt`. If something looks wrong, see [docs/qa-guide.md](docs/qa-guide.md).

## Common tasks
**Change some game text and try it in an emulator**
1. `py p3fes_text.py extract "C:\p3fes\extracted"` writes `C:\p3fes\extracted_text`. (It refuses to run again if that folder exists, so it can never overwrite your edits; add `--overwrite` to start over. To find a line, use `py p3fes_textfind.py "C:\p3fes\extracted_text" "some words"`.)
2. Edit the `.txt` files. Keep every `{..}` code as it is ([docs/text-codes.md](docs/text-codes.md)).
3. `py p3fes_text.py repack "C:\p3fes\extracted_text" "C:\p3fes\extracted" -o "C:\p3fes\mod_files"` (delete an old `mod_files` folder first so no stale files get patched).
4. `py p3fes_patch.py "C:\path\to\game.iso" "C:\p3fes\mod_files" --dry-run`, then again with `-o "C:\p3fes\modded.iso"` instead of `--dry-run`. Your original image is never changed. Edited text must still fit in the space it had.

**Look at a 3D model in Blender** (File, Import, Wavefront .obj)
- One model: `py p3fes_rmd.py export "C:\p3fes\extracted\BTL.CVM\MODEL\NPC\N00001A.RMD" -o "C:\p3fes\model_test"`
- All models, geometry only (a few minutes): `py p3fes_rmd.py batch "C:\p3fes\extracted\BTL.CVM\MODEL" -o "C:\p3fes\model_batch" --no-textures`. Leave `--no-textures` off to include textures (needs much more disk space). The report is `batch_report.txt` in the output folder.

**Pose and animate a character in Blender** (File, Import, glTF 2.0)
- One model: `py p3fes_rmd.py gltf "C:\p3fes\extracted\BTL.CVM\MODEL\NPC\N00001A.RMD" -o "C:\p3fes\model_gltf"`
- A whole folder: `py p3fes_rmd.py batch "C:\p3fes\extracted\BTL.CVM\MODEL\NPC" -o "C:\p3fes\gltf_batch" --gltf` (add `--match C0` to pick files by name, `--limit 20` for a quick trial).
- In Blender: select the armature, open the Animation workspace, set the lower panel to Action Editor, and pick an animation from the dropdown. Select all bones (A) to see its keys; Space plays.

**Batch files for a full re-run (Windows)**
- `tools/rerun_checks.bat` and `tools/rerun_script_checks.bat` rerun the field checks on an extraction (`extracted3`); results go to the folder `rerun3`.
- `tools/redo_exports.bat` and `tools/redo_sound_banks.bat` redo the model, text, texture, audio and sound exports from `extracted3` into new folders. Copy them next to the `p3fes_*.py` tools and run them from there. They never touch your game files.

## What we know
- [docs/findings.md](docs/findings.md): the disc layout and what the executable is built from.
- [docs/formats.md](docs/formats.md): how the file formats are put together.
- [docs/text-codes.md](docs/text-codes.md): what the control codes inside message text mean.
- [docs/script-functions.md](docs/script-functions.md): the script functions (`COMM` numbers) and where they live in the executable.
- [docs/roadmap.md](docs/roadmap.md): the phases and the open questions.
- [docs/phase1-summary.md](docs/phase1-summary.md): what Phase 1 settled and the first build milestone; [docs/windows-build.md](docs/windows-build.md): how to build and first-run it on Windows (through WSL2).
- [docs/phase0-todo.md](docs/phase0-todo.md): what is left in Phase 0, item by item.

In short: the game is one code image with no overlays, built on Sony's PS2 SDK and CRI middleware from early 2005. It reads all its data through CRI's file-system calls from three archives on the disc, and nearly all of that data is in simple, readable container formats.

## How to help
- **Developers:** experience with C or C++, MIPS, Ghidra, PS2 hardware or recompilation projects is what we need most. The open questions are in [docs/roadmap.md](docs/roadmap.md).
- **Testers:** run the tools on your own dump (especially other regions and dumps) and report what you see. The [QA guide](docs/qa-guide.md) explains how.
- **Format researchers:** scripts (`.BF`) are not decoded yet; the `.BED` effect parameter fields and the sound sequence details (timing, pitch, envelopes, pan, control events) are only partly known. The model chunks whose meaning is unknown are listed in [docs/formats.md](docs/formats.md#not-understood-yet).
- Open an issue before starting large work so we do not duplicate effort.

## Related work
An independent matching-decompilation project for this game exists at https://github.com/snaku/Persona3-FES-Decompilation. We are not affiliated with it and have not coordinated with its authors. A native port would build on that kind of work, so we hope to cooperate in future.

## License
The tools and documentation are released under the MIT license (see LICENSE).

- [Playtest plan](docs/playtest-plan.md): what works, what is broken, and everything left to test.
