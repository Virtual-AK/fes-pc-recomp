# Phase 0 findings (NTSC-U, SLUS-21621)

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
