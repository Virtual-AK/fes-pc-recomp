# File formats

What is known about the game's file formats, and how we checked it. "Verified" means a tool in this repository reads it and the results were checked on a real NTSC-U dump (file counts, sizes or converted output).

Contents: [Disc and archives](#disc-and-archives-verified) · [Containers](#container-files-pac-pak-bin-cpk-verified) · [TMX textures](#tmx-textures-understood-verified-by-conversion) · [BMD messages](#bmd-message-files-msg1-verified-on-167-files-for-type-0-type-1-verified-on-one-real-message) · [AFS](#afs-archives-verified) · [ADX](#adx-audio-verified) · [SFD](#sfd-video-partly-known) · [Models (.RMD)](#models-rmd) · [Not decoded yet](#seen-but-not-decoded)

## Disc and archives (verified)
- The disc is a standard ISO9660 image with 2048-byte sectors. The boot file named in `SYSTEM.CNF` (`SLUS_216.21`) is a MIPS R5900 ELF.
- Three `.CVM` archives (`DATA`, `BTL`, `BGM`) hold nearly all the data. A CVM is a CRI container: a "CVMH" header, then a plain ISO9660 file system starting at offset 0x1800. They are not encrypted.

## Container files: .PAC, .PAK, .BIN, .CPK (verified)
A repeating series of entries:

| Offset | Size | Meaning |
| --- | --- | --- |
| 0 | 252 | Entry name, ASCII, ends with a zero byte (bytes after it can be leftover junk). May contain `/`. |
| 252 | 4 | Data size, little-endian |
| 256 | size | Data |

Entries start on a 16-byte boundary, usually 64 or 128 bytes. The padding between entries can contain leftover non-zero bytes, so the next entry is found by testing each aligned position for a valid header. The file ends with a 256-byte terminator header: an empty name (first byte zero), sometimes with leftover name bytes after it.

Not every `.BIN` is a container: many are plain tables. A few (`BRP_BASE.BIN`, `SFL_GROUND.BIN`) use a second layout: a small table of numbers (0x64, a count, then offsets) followed by the data. This is not decoded yet.

## .TMX textures (understood; verified by conversion)
A 0x40-byte header, then the palette, then the pixels:

| Offset | Size | Meaning |
| --- | --- | --- |
| 0 | 2 | Always 2 |
| 4 | 4 | File size, little-endian |
| 8 | 4 | "TMX0" |
| 16 | 1 | Number of palettes |
| 17 | 1 | Palette format (0 = 32-bit colour) |
| 18, 20 | 2, 2 | Width, height |
| 22 | 1 | Pixel format: 0x00 32-bit, 0x01 24-bit, 0x02 16-bit, 0x13 8-bit palette, 0x14 4-bit palette |
| 23 | 1 | Mipmap count (not used so far) |

The file size equals 0x40 + palette bytes + pixel bytes for every sample checked. (The size does not reveal the order. The palette-first order was confirmed from a real file: the first 1024 bytes after the header form a smooth colour ramp with alpha near 0x80, and the last bytes are mostly the background index.) 8-bit textures have a 256-colour palette (the PS2 stores these with index bits 3 and 4 swapped) and alpha values from 0 to 0x80, where 0x80 is fully opaque. 4-bit textures have a 16-colour palette and the low nibble comes first.

### TMX notes from the full disc run (NTSC-U)

- 2,816 TMX files: 2,532 8-bit palette, 281 4-bit palette, 2 32-bit.
- One file (`OPED/OP_TITLE.BIN.d/.../i_new_title009.tmx`) is empty (0 bytes), so it is not a texture.
- Two files in `CUTIN/SHAPE/C02_0000.CPK.d/` carry extra bytes after the palette (1,920 and 960 bytes). The picture decodes fine because pixels are read from the front; the extra data is not understood yet.

## .BMD message files, "MSG1" (verified on 167 files for type 0; type 1 verified on one real message)

All integers little-endian. Every pointer counts from byte 0x20 (so absolute position = stored value + 0x20).

- Header, 0x20 bytes: u32 type (7), u32 file size, "MSG1", u32 0, u32 position of the relocation table, u32 relocation table size, u32 message count, u32 (0x00020000).
- Then one 8-byte entry per message: u32 type (0 = dialogue, 1 = menu/choice) and u32 position.
- Then 16 bytes: a u32 and 12 zero bytes. The u32 is the relocation table position minus 0x20 for most files.
- Each message starts 4-byte aligned. A type-0 message: 24-byte name, u16 line count, u16 speaker (0xFFFF, 0, 1...), one u32 position per line, u32 text size, then the lines. Most lines end with the code F1 04; some do not (marked {NOEND} by the tool). The text size covers the lines plus trailing zero bytes.
- A type-1 (menu/choice) message: 24-byte name, u16 (0), u16 option count, u32 (0), one u32 position per option, u32 text size, then the options. Each option ends with a zero byte instead of F1 04. Checked against one real message (BRP_SHIFT_YN); the full-disc check is pending.
- After the text some messages carry a speaker-name table: one u32 position per name, then the names as NUL-terminated strings.
- The relocation table (a few bytes to a few dozen) comes last, 4-byte aligned, and runs to the end of the file. It lists where every pointer field is, so the game can fix the pointers when it loads the file. It must be rebuilt whenever a message moves (a pointer field moves with its message). Format, starting from position 0x20: an even byte v means the next pointer is 2*v bytes ahead (4..508); a byte whose low three bits are 111 means a run of n pointers one word (4 bytes) apart, n = (byte >> 3) + 2; a byte whose low two bits are 01 starts a long jump: that byte and the next form a little-endian 16-bit number v and the jump is v - 1 bytes (used for jumps over 508). Pointer fields: each message's entry position, the u32 in the 16-byte block after the entry list, each message's line positions, and each speaker-name position. Reproduces four real tables exactly (including long jumps of 512, 612, 672, 704, 1128). Runs longer than 33 and jumps over 65534 are untested. `p3fes_text.py extract` reports how many files it can regenerate exactly.
- Text is mostly plain ASCII with line breaks as 0x0A. Control codes (F1..FF) and two-byte characters (80..EF) are described in [text-codes.md](text-codes.md): their structure is known and the tool shows each as one `{..}` token and keeps it exactly; what each code does in game is only partly known.
- Checked: all 167 NTSC-U message files rebuild byte-identical from the parsed form.

## .AFS archives (verified)
Standard CRI AFS: "AFS\0", an entry count, a table of (offset, size) pairs, and a name table whose position and length are stored after the entry table (48 bytes per entry, 32 for the name). Entries are 2048-byte aligned. The entries are ADX audio.

## .ADX audio (verified)
Standard CRI ADX, encoding 3 (four-bit ADPCM with two fixed predictor coefficients). Music is stereo at 48 kHz or 24 kHz; voices are mostly 24 kHz. Decoding is checked sample-for-sample against ffmpeg.

## .SFD video (partly known)
MPEG-2 program streams from CRI Sofdec, 29.97 fps, at 640x368 or 640x448 (one at 512x448). They should play in ffmpeg or VLC. Replacing or upscaling them is a later task.

## Models (.RMD)

Geometry, materials and textures are decoded and checked in Blender (all 2,934 files under
`BTL.CVM/MODEL` open with `p3fes_rmd.py batch`; the only exception is the 1 KB `KARA.RMD`, which
holds no geometry). Skeletons and animation are present in the files but not decoded yet. Other
folders with `.RMD` files (for example in `DATA.CVM`) have not been run through the batch tool.

### File layout
Every number is little-endian. A chunk is a 12-byte header (type, size, version) followed by `size` bytes.

1. **Game-specific chunks** (type `F0F0xxxx`, version `40000000`) at the start of most files. The first is
   always type `F0F000F0` with a 2-byte payload (many different values), so the next thing starts at
   byte 0x0E (not 4-byte aligned). Some files, mostly stage models in `FACILITYP`, carry one or two more
   chunks of type `F0F000E0` (1,524 and 1,668 bytes seen): floats (many 1.0) and short names such as
   `P-SMOKE`, `R-CRCLE`, `p_jackr_00`, probably effect or object setup. Up to 15 padding bytes can sit
   between chunks (they align the next chunk to 16 bytes). 273 files (weapons) have no prefix at all.
2. **A RenderWare 3.x stream**, version stamp `1C020037` (`1C02002D` in a few files): a texture
   dictionary (type 0x16) holding PS2 native textures (0x15), then a clump (0x10) with the frame list
   (0x0E), geometry list (0x1A) and atomics (0x14). Skeleton data is the HAnim plugin (0x11E).
3. **Trailing chunks** after the clump: game-specific chunks `F0F00003`, `F0F00004`, `F0F00005`,
   `F0F00006`, `F0F00080`, `F0F00001` alternating with RenderWare "anim animation" (0x1B). Not decoded;
   `p3fes_models.py --tree` prints them. 88 files have extra bytes after the last chunk.

`p3fes_rmd.py` finds the stream by walking the game-specific chunks first (`skip_atlus_chunks`) and
also trying every offset up to 0x40. `p3fes_rmd.py chunks FILE` shows this walk for one file.

### Geometry (verified)
- **Frame list** struct: u32 frame count, then 56 bytes per frame: 9 floats (3x3 rotation), 3 floats
  (position), i32 parent index, u32 flags. World matrices are built with a row-vector convention
  (`p' = p*R + t`).
- **Atomic** struct: frame index, geometry index, flags, unused (4 x u32).
- **Geometry** struct: u32 flags (0x1 triangle strip, 0x2 positions, 0x4 textured, 0x8 pre-lit,
  0x10 normals, 0x01000000 PS2 native data), u32 triangle count, u32 vertex count, u32 morph target
  count; then pre-lit colours (4 bytes/vertex, if flagged), UV sets (8 bytes/vertex each), triangles
  as 4 x u16 (vertex 2, vertex 1, material, vertex 3), then per morph target a 24-byte header (bounding
  sphere as 4 floats, has-vertices, has-normals), vertices (3 floats each) and normals (3 floats each).
  Geometry in these models is plain (not the PS2 native VIF form), which is why it is easy to read.
- **Materials**: a Material struct (flags, colour as RGBA, unused, textured flag) and, when textured,
  a Texture chunk with two strings (name, mask name). Texture names match the texture dictionary.
- Characters (for example `N00001A.RMD`) export as a static T-pose: skin weights and bone matrices are
  not read yet. Blender shows the exported models the right way round; `--mirror-x` exists for viewers
  that flip them.

### PS2 native textures
A `TextureNative` chunk (0x15) holds: Struct (platform id 6, filter/addressing), two Strings
(name, mask name), then a Struct whose payload is two nested chunks:

1. Struct, 64 bytes: width, height, depth (4 or 8), raster format, GS registers TEX0, TEX1,
   MIPTBP1, MIPTBP2 (8 bytes each), texel data size, palette data size,
   GPU data size, sky mipmap value.
2. Struct: the texel packet then the palette packet. Each packet is a GIF tag (NLOOP=3),
   three A+D register writes (TRXPOS 0x51, TRXREG 0x52 with RRW/RRH, TRXDIR 0x53), an IMAGE
   GIF tag (NLOOP = number of 16-byte units), then the data. 80 bytes of overhead per packet.

**8-bit pixels (verified).** The picture is uploaded as 32-bit pixels (PSMCT32) of w/2 x h/2 with the
size given by TRXREG, so a reader replays the upload into a model of GS memory (`ct32_word`), then reads
the picture back as PSMT8 (`t8_index`) using the TBW field of TEX0. The block and column tables were
checked against two independent descriptions of the GS and visually on faces, clothes and signs.

**Palettes (verified on 8-bit).** The palette packet holds the entries in *file order*; do not replay
it into GS memory. For 8-bit palettes, entries 8-15 and 16-23 are swapped in every group of 32 (index
`i` reads file entry `(i & ~0x18) | ((i & 8) << 1) | ((i & 16) >> 1)`). Alpha 0x80 is opaque. 4-bit
palettes: the first 16 entries in file order.

**4-bit pixels (looks right, not proven).** With the palette order above, `p_sakim_02` decodes to a
crisp, regular checker pattern and the protagonist's hair texture to a smooth navy ramp (the hair
looks right on the model). The texel packet's TRXREG says w/2 x h/2 words but only half that much data
follows. The decoder reads the data as the header's width in raster order and leaves the rest of the
picture flat. Not yet checked on a 4-bit texture that fills its whole area. `p3fes_rmd.py textures
--variants` writes alternative readings for such textures. (A "smoothness" score is misleading here:
a reading that leaves most of the picture blank scores high, so judge by eye.)

### Not understood yet
Payload of `F0F000F0` (2 bytes); contents of `F0F000E0`; the trailing game-specific chunks and the
anim animation chunks (0x1B, type 2 compressed); skin weights; what the 88 files with trailing bytes
hold; whether any model shares textures with another (a model whose materials name a texture that is not
in its own dictionary exports without that texture).

## Seen but not decoded
`.BF` scripts, `.BED` and `.SE` sound sequence data (`BED4`), `.EPL` effects, `.CIN` cut-in data, `.SPR` sprites (`SPR0`), `.ANM` animations, `.TBL` tables of skill, persona and battle values, `.ENV`, `.CMR`, `.FBN`, `.HBN` field data, and the animation and skeleton data inside `.RMD` models.
