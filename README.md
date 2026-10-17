# ps2-native-tools

A community effort to run a PlayStation 2 role-playing game (Persona 3 FES, NTSC-U, serial SLUS-21621) natively on PC and in the browser, with no emulator. The goals are higher resolutions, higher frame rates and easy mod support.

**Status: research and tooling.** Nothing here runs the game yet. The tools read, unpack, convert and (for text) edit and repack the game's data from your own disc, and the file formats are documented.

<!-- progress:start -->
**Overall progress: about 13%** (rough estimate by the maintainers; most of the work is still ahead)

`██░░░░░░░░░░░░░░░░░░` 13%

| Phase | Progress | |
| --- | --- | --- |
| 0. Research and tooling | `█████████████████░░░` | 85% |
| 1. Pick the approach, prototype | `░░░░░░░░░░░░░░░░░░░░` | 0% |
| 2. Runtime layer (files, audio, video, input, saves) | `░░░░░░░░░░░░░░░░░░░░` | 0% |
| 3. Graphics (GS and vector units to a modern API) | `░░░░░░░░░░░░░░░░░░░░` | 0% |
| 4. Playable desktop build, QA | `░░░░░░░░░░░░░░░░░░░░` | 0% |
| 5. Browser build and mod tooling | `░░░░░░░░░░░░░░░░░░░░` | 0% |

Phase 0 is about 85%: disc, archives, textures, audio, sound effects, text, models, animations and field geometry are done; scripts, effect data, field tables and the remaining model chunks are partly understood. The percentages are a guide, not a promise. See [docs/roadmap.md](docs/roadmap.md).
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
