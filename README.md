# ps2-native-tools

A community effort to run a PlayStation 2 role-playing game (Persona 3 FES, NTSC-U, serial SLUS-21621) natively on PC and in the browser, with no emulator. The goals are higher resolutions, higher frame rates and easy mod support.

**Status: research and tooling.** Nothing here runs the game yet. The tools read, unpack, convert and (for text) edit and repack the game's data from your own disc, and the file formats are documented. Working so far: disc and archive reading, textures, audio, game text (extract, edit, repack, patch back into a disc copy that plays), and 3D models (geometry and textures). Not decoded yet: model skeletons and animation, scripts, sound sequences. The next phases need developers; see [How to help](#how-to-help).

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

**Text (editing works)**
| Tool | What it does |
| --- | --- |
| `p3fes_text.py` | `extract` writes the game's message (`.BMD`) text to editable text files; `repack` builds modified `.BMD` files from your edits. |
| `p3fes_textfind.py` | Searches the extracted text for a word or phrase and shows the file, message and line of each match. |
| `p3fes_textcodes.py` | Counts the control codes (the `{F1 05}` style tokens) in the extracted text, with examples. |
| `p3fes_patch.py` | Writes changed files (from a folder laid out like the extracted one) into a COPY of the disc image, then verifies the copy. In-place only: files must fit their existing space. Use `--dry-run` first. |

**3D models**
| Tool | What it does |
| --- | --- |
| `p3fes_rmd.py` | `export` writes one model (`.RMD`) as `.obj` and `.mtl` with its textures as PNG; `batch` does a whole folder and writes a report of what failed and why; `info` lists what is inside; `textures` writes only the textures. Characters export as a static T-pose (no skeleton yet). |

**Research tools** (for people working on formats; most users never need these)
| Tool | What it does |
| --- | --- |
| `p3fes_exe_scan.py` | Scans the boot executable for library versions, device paths, file-name patterns and library function names. |
| `p3fes_formats.py` | Surveys how the main file types are built: containers, AFS, ADX, SFD, and header samples for every other type. |
| `p3fes_models.py` | Surveys the `.RMD` files: header patterns, chunk lists, strings. `--tree` and `--hex` look inside one file. |
| `p3fes_bmd.py` | Shows the structure (and optional hex dump) of one `.BMD` message file. |
| `p3fes_textsurvey.py` | Surveys the message files and file-type counts of an extracted folder. |

## Quick start (Windows)
1. Install Python from python.org (tick "Add python.exe to PATH"). In a Command Prompt, use `py` instead of `python`.
2. Download this repository (green **Code** button, then **Download ZIP**) and unzip it. Open a Command Prompt in the `tools` folder (type `cmd` in the folder's address bar).
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

## What we know
- [docs/findings.md](docs/findings.md): the disc layout and what the executable is built from.
- [docs/formats.md](docs/formats.md): how the file formats are put together.
- [docs/text-codes.md](docs/text-codes.md): what the control codes inside message text mean.
- [docs/roadmap.md](docs/roadmap.md): the phases and the open questions.

In short: the game is one code image with no overlays, built on Sony's PS2 SDK and CRI middleware from early 2005. It reads all its data through CRI's file-system calls from three archives on the disc, and nearly all of that data is in simple, readable container formats.

## How to help
- **Developers:** experience with C or C++, MIPS, Ghidra, PS2 hardware or recompilation projects is what we need most. The open questions are in [docs/roadmap.md](docs/roadmap.md).
- **Testers:** run the tools on your own dump (especially other regions and dumps) and report what you see. The [QA guide](docs/qa-guide.md) explains how.
- **Format researchers:** model skeletons and animation (inside `.RMD`), scripts (`.BF`) and sound sequences (`.BED`) are not decoded yet. The model chunks whose meaning is unknown are listed in [docs/formats.md](docs/formats.md#not-understood-yet).
- Open an issue before starting large work so we do not duplicate effort.

## Related work
An independent matching-decompilation project for this game exists at https://github.com/snaku/Persona3-FES-Decompilation. We are not affiliated with it and have not coordinated with its authors. A native port would build on that kind of work, so we hope to cooperate in future.

## License
The tools and documentation are released under the MIT license (see LICENSE).
