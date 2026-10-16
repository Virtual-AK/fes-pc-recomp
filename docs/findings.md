# Phase 0 findings (NTSC-U, SLUS-21621)

> Project progress: `██░░░░░░░░░░░░░░░░░░` 13% overall, see [docs/progress.md](progress.md) and [README](../README.md).

All results come from the tools in this repository, run on a verified dump (matches the Redump entry). Only structure, names and sizes are recorded here.

## Disc layout
- Standard ISO9660 image, 2048-byte sectors, boot file `SLUS_216.21` (MIPS R5900 ELF, entry 0x00100008).
- Three CVM archives hold nearly everything: 12,019 files in total. Each CVM is a CRI container with a "CVMH" header and a plain, unencrypted ISO9660 file system starting at offset 0x1800.
- File types seen inside: models (.RMD), textures (.TMX), packs (.PAC, .FPC, .BIN), audio (.ADX, .AFS), scripts (.BMD, .BF), effects (.EPL), video (.SFD) and cut-in data (.CPK).
- The community "deinterlaced" image differs from the plain dump in about 830 bytes of the executable plus 42 re-encoded .SFD cutscene videos.

## Executable
- ELF with one code-and-data image from 0x00100000 to 0x009ACC80; sections `main`, `.relmain` (empty) and `heap`. No symbol table (stripped).
- No overlay or dynamic code-loading strings found. Not proof, but all code is probably in this one file.
- Built with Sony PS2 SDK libraries (libcdvd, libsif, libgraph, libmc2, libpad, libsd, libmpeg) and CRI middleware built Feb-Mar 2005: CVFS 2.39, ROFS 1.77, ADXT 9.44, ADXF 7.30, AHX 1.44, AIXP 2.21, PS2RNA 1.32, SFD 1.958, MWSFD 3.50.
- About 15 IOP modules (.IRX programs for the secondary processor) are loaded from `cdrom0:\LIB31\`.
- Files are opened through CRI calls (`cvFsOpen`, `ROFS_Open`, `ROFS_SetDir`, ...). Source paths in the strings: `pfs_cvfs.c` and `rofs_*.c`.
- Paths are built at run time, for example `field/pack/f%03d_%03d.pac`, `sound/v%03d%03d.afs`, `bustup/%s`.
- Save data uses `/BASLUS-21621Save%d` folder names on the memory card.
- Videos play through CRI Sofdec / Movie Wing (`mwPlyStartFname` and related).
- 205 CRI and Sony function names are visible in strings.

## Implications
- File access goes through a small set of calls, which is the natural place to add mod support (a mod folder answers first, the disc second).
- Audio and video are standard middleware: replace with modern decoders rather than recompiling them.
- The remaining hard problems are the game code itself (static recompilation or decompilation), the PS2 graphics path, and the IOP modules.

## File formats (from p3fes_formats.py, NTSC-U)
- **Containers (.PAC, .PAK, .BIN, .CPK):** a repeating layout of a 256-byte header (a name of up to 252 bytes, then a 4-byte little-endian size) followed by the data. Names inside are ordinary file names (.RMD models, .BF scripts, .ENV, .BMD text, .TMX textures, .CIN, .ACX, .BED/.SE sound data). Entries are padded to a boundary (64, 128 or 256 bytes seen) that can contain leftover non-zero bytes, and the file usually ends with a 256-byte terminator header (empty name). Some .BIN files (tables) are not containers at all.
- **AFS (366 files, 12,196 entries):** all standard AFS archives with 2048-byte aligned entries and a file-name table. They hold the voice audio.
- **ADX audio:** all 601 files are CRI ADX (encoding 3). Music is stereo at 48 kHz or 24 kHz (about 139 minutes); voice and effects are mostly 24 kHz.
- **SFD video (42 files, about 1.9 GB):** MPEG-2 at 29.97 fps. Picture sizes are 640x368 (27 files), 640x448 (14 files) and 512x448 (1 file). All are low resolution, so upscaling or replacement will be needed at higher output resolutions.
- **Other formats, from header samples:** .RMD models start with F0 00 F0 F0; .TMX textures start with 02 00 00 00 followed by "TMX0"; .BMD text files contain "MSG1"; .BED sound files start "BED4"; .CIN files start "CIN"; .SPR files contain "SPR0". .TBL files are numeric tables (skills, personas and AI values are visible by name).

### Container check results
All 530 + 45 + 22 container files in BTL.CVM (.PAC, .CPK, .PAK) and all 434 + 299 + 67 in DATA.CVM parse with this layout, plus 244 of 246 and 592 of 607 .BIN files. Most of the remaining .BIN files are plain data tables (item, enemy and dungeon data). Two files in BTL.CVM (BRP_BASE.BIN, SFL_GROUND.BIN) use a different container type: a small table of numbers (0x64, a count, offsets) followed by the data, with a "MSG1" or "TMX0" file starting at each offset.

### Converted output (p3fes_tmx.py, p3fes_audio.py)
Textures convert to PNG from the header layout in [formats.md](formats.md), and ADX audio decodes sample-for-sample identically to ffmpeg on test files. Results on the real NTSC-U disc are collected in the issue tracker.
