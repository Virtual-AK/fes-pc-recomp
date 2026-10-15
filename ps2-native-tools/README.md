# ps2-native-tools

A community effort to run a PlayStation 2 role-playing game (Persona 3 FES, NTSC-U, serial SLUS-21621) natively on PC and in the browser, with no emulator. Goals: higher resolutions, higher frame rates and easy mod support.

**Status: Phase 0 (research and tooling).** Nothing here runs the game yet. We are mapping how the game is built so that a developer can decide the best route.

## Ground rules
- **Bring your own disc.** Players use their own legally owned dump. This repository contains no game code, assets, BIOS files or disc images, and never will. Please do not attach any to issues or pull requests.
- **Tools and documentation only.** The scripts only read your image and write reports of file names, sizes and short format markers.
- **Independent project.** It is not affiliated with or endorsed by the game's publisher or developer. We avoid their names and logos in the project branding.
- Nothing here is legal advice.

## Tools (Python 3.8+, standard library only)
Run from a Command Prompt or terminal in the `tools` folder. On Windows use `py`.

| Tool | What it does |
| --- | --- |
| `p3fes_inspect.py` | Checks a disc image: region, serial, boot executable, hashes and file list. `--compare OTHER_ISO` lists the differences between two images. |
| `p3fes_cvm.py` | Opens the CVM archives on the disc and reports their file types, sizes and folders. |
| `p3fes_exe_scan.py` | Scans the boot executable for library versions, device paths, file-name patterns and library function names. |

```
py p3fes_inspect.py "game.iso"
py p3fes_cvm.py "game.iso"
py p3fes_exe_scan.py "game.iso"
```
Reports are written next to each script as `.json` files. Do not commit reports from your own disc.

## What we know so far
See [docs/findings.md](docs/findings.md). In short: the game is one code image with no overlays, built on Sony's PS2 SDK and CRI middleware from early 2005, and it reads all its data through CRI's file-system calls from three archives on the disc.

## How to help
- **Developers:** experience with C or C++, MIPS, Ghidra, PS2 or emulator internals is what we need most. See [docs/roadmap.md](docs/roadmap.md) for the open questions and phases.
- **Testers:** run the tools on your own dump and report mismatches (other regions, other dumps).
- Open an issue before starting large work so we do not duplicate effort.

## License
The tools are released under the MIT license (see LICENSE).
