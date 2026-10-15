# QA guide

You do not need to read code. Run a tool, look at the result, and report what you see.

## What to include in every report
- Your disc: region and serial (`py p3fes_inspect.py game.iso` prints them), and whether it is a plain dump or a modified one (for example a "deinterlaced" image).
- Your system: Windows, macOS or Linux, and the Python version (`py --version`).
- The exact command you ran and what the tool printed. Copy the text from the Command Prompt.
- The `.report.json` file or `problems.txt` the tool wrote, if there is one.
- **Not** any game files, pictures or sound.

## Checks, by tool
**p3fes_inspect.py**
- Does it report the right region and serial?
- Does the image hash match a known-good database entry (for example on redump.org)? If not, your dump may be damaged.

**p3fes_unpack.py**
- The count of files printed by `--dry-run` should be 12,044 for the NTSC-U disc.
- Open `manifest.csv`: every row should point to a file that exists in the output folder.
- Spot-check a few folders (`MODEL`, `FIELD`, `BUSTUP`, `SOUND`) for files with sensible names and sizes.

**p3fes_tmx.py**
- Open `index.html` in a browser. Do pictures look right (portraits, menus, icons), or scrambled?
- If colours look scrambled, run again with `--palette linear` and say which setting looked right.
- If whole pictures look like noise or stripes, note the file names (not the pictures) and the sizes shown in the gallery.
- `problems.txt` lists files that could not be converted.

**p3fes_audio.py**
- Play a few `.wav` files. Do music and voices sound clean? Any crackling, wrong speed, or silence?
- Note which files, by name, sound wrong.

**p3fes_text.py, p3fes_textfind.py** (text)
- Does `extract` report that every message file rebuilds identically (the "exactly" counts in its summary)? Report any file it lists as a problem.
- Does the text read sensibly? Look at a few files in `extracted_text`. Report files full of odd symbols, by file name.
- Edit one short line, then `repack` and `p3fes_patch.py` into a COPY of the disc, and play that line in an emulator. Does the edit show up, and does the game still run? Say which emulator and version.

**p3fes_rmd.py** (3D models)
- `py p3fes_rmd.py batch <MODEL folder> -o <output> --no-textures` should end with almost every model "ok". Send the summary it prints (it lists the reasons for any failures, with file names).
- Export a few models with textures and open them in Blender (File, Import, Wavefront .obj). Do shapes look right? Are the colours natural, or camouflage-like noise? Do any look stretched, inside out or mirrored? Report by file name, without attaching the pictures or models.

**p3fes_formats.py**
- Do most container files parse (the `parsed_as_pak` counts)? Large drops compared with the NTSC-U disc point to a different layout on your disc.

## Other regions and editions
We have only tested the NTSC-U (SLUS-21621) disc. If you have a PAL or Japanese copy, please run `p3fes_inspect.py`, `p3fes_cvm.py` and `p3fes_formats.py` and report the results. Differences in file counts and formats are exactly what we need to learn.

## Reporting a problem
Open an issue using one of the templates. Describe what you expected and what happened, in your own words. Small, specific reports are better than big vague ones.

## Later: testing the port
Once a playable build exists, this guide will add checklists for graphics, audio, saves, controls and mod loading, plus a method for comparing against the original console behaviour.
