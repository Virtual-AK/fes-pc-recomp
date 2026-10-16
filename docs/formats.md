# File formats

> Project progress: `██░░░░░░░░░░░░░░░░░░` 13% overall, see [docs/progress.md](progress.md) and [README](../README.md).

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

### Where the models are (NTSC-U, 3,766 .RMD files, all readable)
BTL.CVM\MODEL\NPC 1071 (characters; N00001A is the player), PACK 530 (enemies, e.g. EM11D = Nyx Avatar, inside
*.PAC.d folders), WEAPON 769, PERSONA 256, FACILITYP 256, SYMBOL 31, FIELD 21; DATA.CVM\FIELD\RMD 813 and
GRMD 15 (field objects such as grass), plus 4 more in DATA.CVM. Every model has a skeleton; 3 have no
geometry (KARA, M007_809, M032_022).

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

### Skeleton, skin and animation (partly checked on N00001A.RMD)
`p3fes_rmd.py skeleton FILE` reads these and prints what it found:
- **Bones:** each frame's extension chunk may hold a node name (0x253F2FE) and an HAnim chunk (0x11E:
  version, bone id, bone count; the root also has flags, keyframe size and a list of bones as id, index,
  flags). Bone hierarchy comes from the frame parents.
- **Skin (0x116, in the geometry extension), verified on N00001A.RMD:** bone count, used-bone count,
  max weights per vertex, the used-bone list, 4 bone indices per vertex (bytes), 4 weights per vertex
  (floats; they sum to 1 on every vertex of all three skinned meshes). Then one 4x4 inverse bone matrix
  per bone (64 bytes each, all 123 are proper matrices), then extra "split skin" style data: three
  u32 numbers, one byte per bone (a remap table; 0xFF means the bone is unused by this mesh) and
  pairs of bytes (probably start and count of bone ranges). The sizes are 12 + 123 + 16 = 151 and
  12 + 123 + 100 = 235 bytes. What the three numbers mean is not known (the first reading, as boneLimit,
  numMeshes and a pair count, did not fit); none of it is needed for posing.
- **Bones (verified):** in N00001A.RMD there are 124 frames and 123 bones with ids 1000-1097 and
  5001-5014, no node names, push/pop flags (2 = push, 1 = pop) in depth-first order, and parents agree
  with the frame list.
- **Animation (0x1B, top level after the clump):** u32 version (0x100), u32 type, u32 keyframe count,
  u32 flags, float duration, then keyframes. All 22 animations in N00001A.RMD are type 2 (compressed):
  each body is exactly 22 bytes per keyframe plus one 24-byte block. A keyframe is: float time (4 bytes),
  four 16-bit values for the rotation, three 16-bit values for the translation, and a u32 that points back
  to the previous keyframe of the same bone (in units of 24 bytes, the in-memory keyframe size; the first
  keyframe of each bone holds a constant instead). The first 123 keyframes (one per bone, in bone order)
  all have time 0; later ones are sorted by time and chained per bone through the back pointer.
- **The 16-bit number format (VERIFIED):** sign bit, 5-bit exponent, 10-bit mantissa, except that the low
  exponent bit counts as an extra top mantissa bit: with e = exponent >> 1 and M = (exponent & 1) << 10 |
  mantissa, the value is +-2^(e-15) * (1 + M/2048). So 0x7800 = 1.0, 0x7400 = 0.75, 0x7000 = 0.5, 0x0000 = 0.
  Rotation: four such values in the order x, y, z, w; they are already a unit quaternion (all 123 first
  keyframes have length 0.9998-1.0001). It is the quaternion of the transpose of the rotation rows in the
  frame list (that reading scores 0.99 against the rest pose; the transposed one 0.82).
  Translation: position = offset + scale * value per axis, with offset and scale being the six floats of the
  24-byte block after the keyframes (offset x y z, then scale x y z). Checked on all 123 bones: median error
  0.0007, 0.002 and 1e-6 units on x, y, z (the quantisation step), and 0x7800 gives offset + scale exactly.
  The block is stored once per animation.
- **Mirrored frames:** 61 of the 2,934 models (all in PERSONA) have frames whose 3x3 matrix has a negative
  determinant (a left-right mirror). The glTF export splits each frame matrix into rotation and scale, with a
  negative x scale for the mirrored ones. Checked in Blender on PS000.RMD (the creature looks right and plays its
  animation). In that file two mirrored bones score 0.000 on the first-pose check, which is not understood yet.
- `p3fes_rmd.py gltf FILE -o FOLDER` writes mesh, skeleton, skin weights and all type 2 animations as glTF
  (one node per frame; verified in Blender 5.2 on N00001A: the textured character follows its animations; the inverse bind matrices are computed from the frame list because the ones stored in the file differ from it by the first bone's offset (85, 139, 145 units in the three meshes) and Blender made no armature from them; bind pose check and first-pose check are printed). Type 1 animations (36 bytes per
  keyframe: float time, 4 floats quaternion x y z w, 3 floats position, u32 back pointer, assumed to be the
  previous keyframe's index times 36) are read the same way; N00853.RMD is the only model seen with one (unchecked in Blender yet).

### A third animation layout (effect models)
Ten models in DATA.CVM\FIELD\RMD (for example M001_002.RMD: 5 flat 4-vertex quads, 6 bones, 446 keyframes,
6.667 s) hold an animation whose type field reads 0x44A07195 (odd for a type id; maybe a hash) and whose
HAnim root says keyframe size 52. Body = 52 bytes x keyframes exactly. A keyframe is 13 words: float time,
quaternion x y z w (all NaN, with junk in one word, when the bone has no rotation channel), position x y z,
four floats not understood (1 1 1 0 on the root's first keyframe; 1.5, ~0, 1, 1 later: scale, size, colour or
alpha), and a u32 back pointer = previous keyframe index x 52 (first keyframes hold junk, like the other
types). These look like particle or sprite effects. The glTF export reads time, rotation (where present) and
position, gives bones with NaN rotation a translation channel only, and ignores the four unknown floats. Checked in Blender on M001_002: six bones, each active in its own staggered time window, and the quads move.

### Not understood yet
Payload of `F0F000F0` (2 bytes); contents of `F0F000E0`; the trailing game-specific chunks and the
meaning of the split-skin header numbers; what the 88 files with trailing bytes
hold; whether any model shares textures with another (a model whose materials name a texture that is not
in its own dictionary exports without that texture).

## Sound effects (.SE) and the .BED effect data

### .SE: containers of Sony sound banks (decoded)
790 files (BTL.CVM\SKILL, BTL.CVM\MODEL\PACK em*.SE, SND_BENC, BATTLE\EFFECT, DATA.CVM\SOUND\SPU\BSE.SE). Each is the
usual 256-byte-header container (name, size, data) with exactly three entries: `.hd`, `.bd`, `.sq`.
- `.hd` and `.sq` use Sony's "SCEI" chunk format: an 8-byte chunk name written as two little-endian words, so
  `IECSsreV` is SCEIVers, `IECSdaeH` SCEIHead, `IECSigaV` SCEIVagi, `IECSbteS` and `IECSuqeS`, `IECSqseS` further chunks.
  Each chunk: name, u32 size, then its fields. SCEIHead holds the total size, the `.bd` size and offsets of the other chunks.
- **SCEIVagi** (the sample table): u32 size, u32 highest index, then one u32 offset per sample (from the chunk start);
  each entry is u32 start offset into the `.bd`, u16 sample rate, 2 more bytes (second is 0xFF).
- `.bd`: PlayStation 2 ADPCM, 16-byte blocks (shift/filter byte, flag byte, 14 data bytes); the first block is silence.
  A sample runs from its start to the block with flag 1 (end). Flag 2 = loops, 4 = loop start (6 samples in all use loops).
  Decoder filters (60,0) (115,-52) (98,-55) (122,-60). Verified by ear: the decoded samples sound like clean effects.
- 2,190 samples in 790 banks (1 to 53 per bank); rates 44100 Hz (1,956), 32000, 22050, 33075, 22056; 0.1 to 3.8 s.
- Not decoded: the `.hd` chunks other than Vagi (which sample plays for which note: key ranges, envelopes, volume, pan)
  and the `.sq` sequences that trigger them.
`p3fes_bed.py split` splits `.SE` files, `p3fes_bed.py banks` writes the WAV files.

### .sq sequences and .hd tones (all 790 banks parse; by ear the rendered sequences sound right)
`.sq` = SCEIVers, SCEISequ, SCEISesq. In SCEISesq (offsets from the chunk start c, `none` = 0xFFFFFFFF): c+0x0C highest group
number, c+0x10 a u32 X so that the group table is at c+0x10+X; each group = u32 highest block number, u32 Y, u8 volume, u8 pan,
u16 resolution (1000), u32 none, then a block table at group+4+Y (most entries none). A block = u32 offset of its events (0x10),
u8 volume, u8 pan, u16 resolution, u32 event byte count, u32 0, then the events. Events are MIDI-like: a delay (7 bits per
byte, high bit means another byte follows), then a status byte: 0x90 note on (3 bytes: 0, key, velocity), 0xA0 note off (0, key, 0),
0xFF end. The smallest bank is one block: key 0 at velocity 127, then key 1 at velocity 30 after 200 ticks (an echo).
`.hd` SCEISetb (chunk start s): s+0x10 holds the offset (0x14) of a directory: u32 highest set number, then one u32 offset (from s)
per set. A set: u32 (8), u16 record size 0x32, u8 highest tone, u8 0xFF, then 50-byte tone records: u16 sample number
(index into SCEIVagi), byte 3 volume, byte 4 pan (0x40 = middle); the rest (pitch, envelope, key range 0x3C..0x3C) not decoded.
Small banks have one set of 2 to 8 tones; the big bank (DATA.CVM\SOUND\SPU\BSE.SE) has 7 sets of 128 tones (set size
4+4+128*50 = 6408 bytes, checked against the directory offsets). A note event carries a set number (the byte after 0x90, 0 in
every small bank) and a key; the key is the tone number inside that set. The block number looks like the sound's id.
Control events: status 0xB0 + 3 bytes (set, key, control number) + a variable-length number + a little-endian u16. Checked on all
28 blocks that use it (enemy banks em049, em04A..., a few skill banks, and BSE.SE): control 0x0E with values 600, 1000, 1200, 3000
and 0x0F with 400, 1000, 1200; the variable-length number is a time in ticks (600 to 1600). Probably a gradual change (pitch or
volume, 1000 = unchanged) of the note with that key; what it changes exactly is not known and the renderer ignores them.
All 1,969 blocks of the 790 banks parse and end with 0xFF.
Not known: how many ticks a second (the render guesses 2000), whether velocity and tone volume multiply, pitch handling,
and banks whose tone table is larger than one record array (the biggest bank's SCEISetb is 42 KB).

### .BED (BED4): effect element trees (structure and block headers read, parameter fields not decoded)
704 files: 512 in BTL.CVM\SKILL (one per skill id 000-1FF; the .SE banks there use the same numbering up to 1CF), 103 in
SND_BENC\BOSS, 69 in BATTLE\EFFECT, 20 in SND_BENC\BTLEFF.BIN.d. Magic `BED4`, then the bytes `00` (version?).
File layout: a 6-word header at 0x04, 32 rows of 24 bytes from 0x1C, a 5-word header at 0x31C, 32 more rows from 0x330, and data
from 0x630 (702 of 704 files; the other two start elsewhere). A row = u32 type (0xFE empty, 7 used), u32 offset of a blob,
u32 flags (0x80400 most common, then 0x100, 0x8040C, 0x80100, 0x400 ...), three more words (mostly 0). Files hold 1 to 6 blobs.
The headers hold a repeated number (0x28, 0x32, 0x96, 0xB4, 0x64 ...) of unknown meaning.
**Blob = an effect element tree.** A 0x90-byte root record, then N records of 0xC0 bytes, then the parameter blocks.
- Root: the row at +0x60 reads (1.0, 0xFFFFFFFF, 0x80, 0) and the row at +0x80 reads (N, 0, 0x90, 0), so N elements follow.
- Element (0xC0 bytes): sixteen-byte rows of floats: +0x00 and +0x10 (0 0 0 1) (rotation, or two), +0x20 (1 1 1 1) (scale or
  colour), +0x30 zeros, +0x40 (x y z 1) a position (for example 0 5 0 1), +0x50 (0 0 0 1), +0x60 (1.0, 0xFFFFFFFF, 0x80, 0),
  +0x70 four floats (0 1 0 0 or similar), +0x80 (a, b, c, 0) with b = 1 and c = 8, 0xF8, 0xC00 ..., then +0x90 the offset of this
  element's parameter block from the blob start, two zero words, and from +0x9C a zero-ended name.
- The first parameter block starts right after the element table (offset 0x90 + 0xC0 * N); the blocks follow each other in
  element order (for D-POINT and B-MULTI the blocks are 0xD0 = 208 bytes apart).
- Names are effect primitives, written as a one-letter group, a hyphen, and a word (e.g. R-CRCLE, D-POINT, B-MULTI, N-SPIRL,
  S-SPK_T, O-MCHAR, O-MOT; P-SMOKE and R-CRCLE also appear in model files). Checked on AEGIS (1 element, name O-MOT, block at
  0x150), DOWN (4 elements) and 0DE (15 elements).
**Parameter block header** (checked on about 11,800 elements): word 0 is 0xD2 or 0xC8 (kind), word 1 a count that is fixed per
element type (R-NOMAL and R-CRCLE 12, B-MULTI 4, S-CYLND and S-RNG_T 10, F-FULL 5, E-QUAKE 0x15, P-SPARK and P-SMOKE 1), word 2
zero, word 3 a small group number fixed per type (R-NOMAL 1, B-MULTI 2, R-CRCLE 3), word 4 = 0x2C (header size), word 5 the
body size fixed per type (R-NOMAL 0x6C, R-CRCLE 0x68, B-MULTI 0xEC, S-CYLND 0x9C, F-FULL 0xD8, P-SPARK 0xE0, E-QUAKE 0x10),
word 6 zero, word 7 a mode (mostly 4, sometimes 1 or 2), word 8 the total block size when another block follows (otherwise 0).
Where the type has colours, +0x30 and +0x34 hold two ARGB colours (FFFFFFFF = white, e.g. FFFFB9B9 FFFF9BA5). Later words mix
frame counts, floats (fractions such as 0.33 / 0.63, sizes such as 5.0), packed colour bytes and small integers. Their meaning
is not decoded; `p3fes_fx.py fields` lists every word position per element type with its common values.
The first +0x80 word of an element is 0 for 4301 elements, below the element's own number for 4194, and equal to it for the rest
(AEGIS_M: 1, 2, 3 ...), so it looks like a link to another element, not strictly a parent. About 540 elements point outside
the blob (offset 0 or beyond the end); these are mostly MODEL, R-NOMAL, P-SPIRL and P-SMOKE elements and are not understood.

## Seen but not decoded
### .BF scripts (FLW0): sections and instructions read (function numbers not yet named)
510 files, all in DATA.CVM (three of them empty). Median 45 KB, largest 324 KB.
Header: u32 0, u32 size, the text `FLW0` at +0x08, u32 0, u32 section count (5 in all files) at +0x10, a u32 at +0x14 that varies
(1, 3, 13, 117 ...; probably a variable count), then from +0x20 one 16-byte header per section: type, element size, element
count, start offset. Seen: type 0 elements of 32 bytes (starts at 0x70 = right after the table), type 1 of 32 bytes, then
larger sections. **Checked on all 507 non-empty files:** the five sections are always types 0 to 4, contiguous in that order, with element sizes
32, 32, 4, 1, 1. Instructions are 4-byte words (low 16 bits opcode, high 16 bits operand; PUSHI and PUSHF are followed by one
value word). All 22,469 procedure labels point at an instruction with opcode 7, each one right after an opcode 9, and every
jump label lands inside the instruction section; no opcode outside 0-34 occurs. So the opcode list below is confirmed in shape
(opcode names are descriptive guesses): PUSHI 0, PUSHF 1, PUSHIX 2, PUSHIF 3, PUSHREG 4, POPIX 5, POPFX 6, PROC 7, COMM 8
(call game function number = operand), END 9, JUMP 10, CALL 11, RUN 12, GOTO 13, ADD 14, SUB 15, MUL 16, DIV 17, MINUS 18,
NOT 19, OR 20, AND 21, EQ 22, NEQ 23, S 24, L 25, SE 26, LE 27, IF 28, PUSHIS 29, PUSHLIX 30, PUSHLFX 31, POPLIX 32,
POPLFX 33, PUSHSTR 34. Most used: PUSHIS (816k, small constants), COMM (328k), EQ, GOTO, IF. The `COMM` operand is the number of
a function inside the game's executable: 213 different numbers occur, up to 501 (most used: 0, 7, 2, 8, 129, 1, 9, 121, 128,
138). Naming those functions needs the executable's function table. **Found in the executable (SLUS_216.21):** the script
engine runs an instruction through a 35-way jump table at 0x7B90A0 (code at 0x30FDF0, the number is checked against 35), and
the game functions are a table of 8-byte records (function address, second word) that starts at 0x7B92B0 and holds exactly
502 records (numbers 0 to 501, the highest the scripts use); some records are empty. The second word is 0 to 8 and may be the
number of values the function takes: confirmed by running the stack code of all scripts with those counts: of 1,051,225 statements only 3 needed more values than were on the stack, and 38,735 of 38,738 procedures end with an empty stack. The executable's strings name the source files of many of them (message windows, social link commands, field commands, cut-ins); see [script-functions.md](script-functions.md). What each function does is not decoded yet. The type-3 section is a complete
message file: it starts with the words 7 (file type), its size, then `MSG1`, the same layout as the `.BMD` files, so the
existing text code reads it (`p3fes_bf.py messages` checks this on all files). The header's size word is the start of the last (type 4, string) section, i.e. everything before it, so
it moves when the message data changes size (the three empty-looking files are different).
In 21 scripts (f007, ns007_002, f012, NPCCOMU and others) the message table is not in file order (an entry may point back to an
earlier position, or two entries share one message), so the text tool reads them as read-only; rebuilding them is not
supported yet.
The first words of the section table were read from the survey of all files; the meaning of each type is a
hypothesis taken from the shape (labels have a name, then numbers) and is tested by `p3fes_bf.py analyse`, which checks that
procedure labels point at the same kind of instruction and counts every opcode. The English message text is stored inside these
files (common English words are all over the survey), so text for scripted scenes lives here and not only in the `.BMD` files.

`.BF` scripts, `.BED` effect data (`BED4`, header layout read, blobs not decoded), `.SQ` sequences inside `.SE` banks, `.EPL` effects, `.CIN` cut-in data, `.SPR` sprites (`SPR0`), `.ANM` animations, `.TBL` tables of skill, persona and battle values, `.ENV`, `.CMR`, `.FBN`, `.HBN` field data, and the animation and skeleton data inside `.RMD` models.

### Field (map) data: first survey

Each field has `F###_###.PAC` (a pack, extracted to `F###_###.PAC.d`) and often an `F###_###.FPC` (up to 2 MB, entries named like `f000_000.RMC`, so probably the models). Small fixed-layout files inside the pack start with a magic word (little-endian), version `0x00010000+n` and a count:

| Type | Magic | Size | Notes |
|---|---|---|---|
| `.ENV` | 0x23456789 | 512 | version 0x10004 (396 files) or 0x10003; floats follow (e.g. 1000.1, 6000.0): probably environment (fog, light) settings |
| `.CMR` | 0x34567890 | 112 | version 0x10000; floats: probably a camera |
| `.FBN` | 0x12345678 | 248..4608 | header 0x18 bytes (magic, version, count, 0x70, 0, 0x60), then count records of 0x70 bytes, then 0xEEEEEEEE padding; size = 0x18 + count x 0x70, or that rounded up to a multiple of 512 (checked on 527 files; see below for the record) |
| `.HBN` | 0x45678901 | 88..2048 | header of 8 pairs (count, record size) from +8, sizes 0x20, 0x14, 0x14, 0x14, 0x14, 0x20, 0x14, 0x14, so records start at 0x48; size = 0x48 + sum(count x size) or rounded up to 512 (807 of 824 files fit) |
| `.BIN` | none | 0..81 KB | many start with 0xFFFFFFFF; `h###_###.bin` examples are 64 bytes |

The pack also holds `.BF` scripts, `.BMD` message files and many zero-length entries whose names look like script procedure names (`f001_001_init`, `npc_00`). Other field files: `MAP\*.MAP` (4608 bytes, mini-map?), `FILTER.FLD` (74,752 bytes), `ICON\FICON.BIN` with `.TMX` icons, `BTL_EFFECT` packs and `.EPL`. None of this is decoded yet; `p3fes_field.py` writes surveys (`survey`, `names`, `words`).

Word statistics (`p3fes_field.py words`) show that these files hold a small real part plus padding filled with leftovers from memory: `0xEEEEEEEE`, heap-like pointers (`0x014C08E0` repeated in several files) and stale text fragments ("list", "box ", "mt_s", "ENE "). That padding is noise and can be ignored.

- `.CMR`: float at +0x08 reads 35, 40, 42 ... 53.13 (a field of view in degrees; 119 of 255 files share one value); floats at +0x10..+0x3C are mostly -1..1 (orientation); +0x40..+0x48 look like a position (e.g. 957, 479, -21); +0x50 is a flag word 0x04000000 + n. 36 files are 512 bytes with stale text after +0x70.
- `.ENV`: floats at +0x10/+0x14 read about 2000 and 3000 (distances), +0x1C..+0x34 are colour-like values 0.05..1, and unit directions (0.7071 diagonals) follow; a word 3 repeats at +0x4C, +0xAC, +0xFC, +0x16C, +0x1BC, and two blocks (+0x80.. and +0x13C..) have the same value distribution (two copies of one structure).
- The pack entries list the field's parts: `f###.bf` (script), `ns###_###.bf` (sub-scripts), `nm###_###.bmd` (messages), `h###_###.bin` and `n###_###.bin` (186 and 107 files, small tables), `npc_##` and `f###_###_init` zero-length entries (names of script procedures), `.RMD` models in `EM###`/`BC###` packs.

**.FBN record (0x70 bytes, starts at 0x18 + 0x70 x n), read from `f004_002_050.FBN` (6 records):** +0 and +4 stale pointer values, +8 an id word (0xC03, 0xC08, 0xC05, 0xC06, 0xC0A, 0xC04 ...; over all 5,040 records of 866 files there are 128 distinct ids from 3072 to 3199, 22 more in the 0xD00 range and one 0x1000C; the same id repeats in many files, 3073 in 669 records, so the ids are slot numbers and not unique flags; one file, f004_010_000, has 26 records with ids 3072 to 3097 in sequence), +0xC the float 60.0 (30.0 in some), 1.0 at +0x20, +0x34 and +0x48 (like a diagonal), +0x50/+0x54/+0x58 a position (x, y, z; for example -101.2, 3.0, -34.8; 0, 3.0, 70.7; 120, 3.0, 98.8; the middle value is 3.0 in half the records, -70.71 in 478 and a real height such as 5.4, 8 or 23 in others, so 3.0 and -70.71 look like placeholder values), +0x60 the integer 3 (0x103 in some), +0x64 the float 30.0. The idea that these ids are script flags (floor boxes) did not hold up; most likely the file lists placements of characters or objects in a scene variant (a field has several, e.g. `_050`, `_051`, `_052`), with the id as the slot. Not confirmed. `p3fes_field.py fbn` lists every record of every file.

**.HBN record (section 0, 0x20 bytes) from `f004_003.HBN`:** id word 0x3400 + n (0x3400 to 0x3407), colour word 0xA80000FF, then six floats (for example -1322, 5.73, -1800, 233, -535, -40) that look like two points or a point and sizes; later sections hold 0x3800-series ids with five-word records. Meaning of the floats not decided.

The `.FBN` numbers at the end of file names (000-027, 050-056, 100-142, 150, 200-222) are not the ids the scripts pass to `field_313`/`field_357` (tested on 2,533 calls: 5 and 24 matches by chance). `n###_###.bin` (128 bytes) and `h###_###.bin` (64 bytes) are small tables full of 0xFFFFFFFF (unset) with a few small values.

**.FPC files are containers (same entry layout as .PAC), now split by `p3fes_field.py split`.** 400 of 401 split (F000_002.FPC is empty). Inside: `.RWS` 819 entries (size 1.7 KB to 1.9 MB; start with chunk type 0x16, a RenderWare texture dictionary; 2 start with 0x29), `.RMD` 812 (the usual models, start with `F0F000F0`; sizes 960 bytes to 1 MB), `.EPL` 221, `.BF` 92, plus small `.CMR` 68, `.HBN` 64, `.ENV` 14, `.userdata` 6 (27 bytes each), and one `.FBN` and one `.BIN`. So the geometry and textures of a field live in its `.FPC`, and the small field files sit in either the `.PAC` or the `.FPC`.

**.RWS (field geometry and textures), from `p3fes_field.py rws` on all 819 files:** each is a RenderWare stream that starts with a texture dictionary (0x16) followed by several clumps (0x10; 3 to 11 in most files, 6 in 169 files, 11 in 156 files), and in 43 files a world chunk (0x0B, a RenderWare world section) plus one clump. 7,695 textures in all: 4-bit 4,061, 8-bit 3,628, 32-bit 6; sizes 128x128 (2,198), 64x64 (1,959), 32x32 (1,200), 256x256 (1,010), 128x64, 64x128 and smaller. Names such as `f001_001_wood`, `f001_001_rail`, `f001_001_shadow`, `world_test001` (the test field F001_000). So the whole map of a field, with its objects as separate clumps, lives in the `.RWS` of its `.FPC`. The texture format is the one already decoded for the models; whether the geometry export of `p3fes_rmd.py` reads these clumps is being tested.

**Field textures, first look (F001_001, F004_002, F004_003, F004_004 decoded to PNG):** every 8-bit texture looks right (doors, windows, floors, walls, a vending machine, kitchen shelves, a blurred glow, a shadow sprite). Most 4-bit ones are fine too (a green floor pattern), but several 4-bit textures decode as noise or a flat grey with noise: `f001_001_01`, `_02`, `_04` (256x256), `f001_001_moji`, `_shadow`, `_wood`, `f004_003_room_d_effe`, `f007_003env01`. So the 4-bit reading is not right in every case (the 4-bit note above already said "not proven"); `p3fes_rmd.py textures FILE --variants` writes sheets of alternative readings for those. `p3fes_rmd.py gltf` on `f001_001.rws` wrote only the first of its 2 models (20 vertices, 10 triangles); `p3fes_rmd.py export --all-clumps` writes every model of a multi-model file as its own .obj.

### 4-bit field textures are uploaded as 16-bit pixels

Field `.RWS` textures (4-bit) have an upload packet whose size says `w/2 x h/2`, but the packet holds
only `w*h/2` bytes, which is exactly `w/2 x h/2` pixels of **16 bits** (PSMCT16), not 32 bits. Character
models send their 4-bit pictures as 32-bit pixels of `w/2 x h/4`. `decode_native_texture` now picks
the replay by the packet size (`rrw*rrh*2 == bytes` means 16-bit: pages of 64x64 pixels, blocks of
16x8, block table identical to the 4-bit one). Found from the sizes and **confirmed on real field textures** (f001_001: the `moji` sheet reads as the
map's place-name labels, `wood` is a tree; the city model in Blender now has readable street signs and trees).
Variant M of `textures --variants` shows the same reading.
Extra tools used while hunting this: `textures --linear NAME` (plain pictures at many widths plus
the byte distances where the data repeats) and `textures --cost` with `p3fes_solve4.py`
(works out an unknown in-block order from neighbour similarity; it did not solve a synthetic test, so don't rely on it).

### Field models: first full export (819 `.RWS` files)

`p3fes_field.py fields` exported everything: 5,344 models (clumps), 3,468,876 vertices, 7,689 textures
(4-bit 4,061, all 16-bit uploads; 8-bit 3,628; true-colour 6). No texture had an unknown upload size.
True-colour textures are read as the upload itself (32-bit pixels, alpha doubled); checked on a brick wall and a plant sheet.

What each model position holds (average over files; guesses from size only, not confirmed):

| clump | files | avg vertices | avg materials | likely role |
|---|---|---|---|---|
| 0 | 816 | 59 | 1.0 | small untextured shape (looks like a helper/collision volume; empty in 44 files) |
| 1 | 771 | 1,674 | 9.1 | main scenery |
| 2 | 762 | 1,924 | 11.5 | main scenery (second part) |
| 3-10 | 200-620 | 140-260 | 2.5-4.1 | small props/objects |
| 11 | 19 | 28 | 1.1 | tiny extra |

43 files (fields f221 and up, among others) hold one empty model (0 geometries, 0 atomics) and nothing else.
In Blender the dorm lobby, the Port Island map, the plaza stage and others look right, including textures.

### Field tables, second pass: `.FBN` records are transforms, `n*.bin` is a calendar

**`.FBN` record (0x70 bytes, from 0x18; seen in `f006_003_000.FBN`, 23 records).** This corrects the first reading:
`+0x00` stale pointer, `+0x04` word like `0xFFFF0004`, `+0x08` id `0xC00+n`, `+0x0C` float 30.0,
`+0x20 / +0x30 / +0x40` three rows of four floats forming a 3x3 rotation (about the vertical axis in every sample I saw: `[c 0 -s 0] [0 1 0 0] [s 0 c 0]`),
`+0x50 / +0x54 / +0x58` position (x, y, z; y is often 3.0 or a small height), `+0x60` flags (`3` or `0x103`), `+0x64` float 60.0, `+0x6C` stale pointer.
So an `.FBN` is a list of placed things with a position and a facing. What each id (`0xC00+n`) is, and what the flag bit `0x100` means, is still open.

**`n###_###.bin` is a calendar** (each record is 0x20 bytes; checked on `n006_002`, `n007_002`, `n008_001`, `n010_001`):
- Record 0: word 0 = number of date records, the other words `0xFFFFFFFF`.
- Then that many date records: word 0 = month (low 16 bits) and day (high 16 bits), word 1 = a time-of-day style value (1 or 6, sometimes 8), word 2 = `0xFFFFFFFF`, word 3 = a group number (mostly counting up as the dates advance, with a few out of order).
- Then groups of entries ending with a record whose word 0 is `0x0000FFFF`. An entry has word 0 = `0x0005_kkkk` (kkkk = slot 0, 1, 2, 3), word 1 = a code (7651, 6251, 6201, 7701, 6351 in field 6), word 2 = a number that rises slowly from group to group, word 4 = `0xA0F`.
- The header counts match the file sizes (39 dates in `n006_002.bin`, 364 in `n007_002.bin`), and every date I looked at is a valid month/day, so the date reading looks right. The meaning of the codes and the group numbers is not known.
- Tool: `p3fes_field.py ncal` checks that over all 107 files and prints the common values; `nbin` shows the raw records.

Script ids (`field_357(6, 21)` etc.) do appear inside the field's own data: `21`, `22`, `23` are group numbers in field 6's calendar (for 25 Sep, 3 Oct and 17 Oct in `n006_002.bin`); whether the scripts mean those groups is a guess to test.

**Calendar check on all 107 files (`ncal`):** 2,112 of 2,112 date records have a valid month and day, and every header count fits its file, so the calendar reading is solid.
Time-of-day word: 1 (1,526 records), 6 (385), 7 (139), 5 (45), 8 (15), 3 (2). Group entries: word 0 is always `0x0005_000k` with k = 0..12 (a slot number; `k` matches the `0xC00+k` ids of the `.FBN` records),
word 1 is a code. Two code shapes show up: `50*m + 1` (7651 = 50*153+1, 6251, 5351, 12801 ...) and `(h << 16) | v` with v values such as 97, 98, 197, 247, 347, 403 (131571 = 2<<16 | 403). The `v` values are the same kind of number the scripts use for `field_357(6, id)`; that is a lead, not a result. (Tested by `p3fes_field.py ncodes`; later checks in this file show that the link is to `field_357` date groups, not to these codes.)

### Calendar versus .FBN files (fbnlink, 91 folders)

No clean link found. Calendar slot numbers versus FBN ids: own 372, control 215 (of 444), mostly small-number overlap. With values of 50 and up: date groups versus FBN file-name numbers 78 vs 46 control (of 695), parameters versus file-name numbers 52 vs 23 (of 949); versus the FBN ids inside the files: groups 64 vs 45, parameters 52 vs 49 (no signal). The run 50..63 in F006_003 appears in groups, parameters and FBN ids at once, but it is one folder and does not repeat elsewhere. Treat the calendar-to-FBN link as unproven; the file-name numbers are the weak lead.

### Where script object ids show up (objwhere, 132 fields)

Hits of a field's own script ids as 32-bit values in its own files, with a control field: field_357 ids in n*.bin 21 vs 0 (offsets 0xC/0x2C = word 3 of a 0x20 record = the date-group number); field_313 kind 5 ids in n*.bin 17 vs 1 (offset 0x24 = word 1 = the entry code); field_313 kind 2 ids in .hbn 14 vs 0 (a value next to floats and pointers, in records that also hold strings such as "draw_proc"). Counts are small; `calcalls` tests the 357/313-kind-5 reading directly.

### field_357 ids are calendar date groups, with a hundreds prefix (calcalls)

`field_357(F, id)` over 107 calendars: id itself is a date-group number of field F in 230 of 1010 calls (all field 6: 21, 22, 23). Of the other 780 calls (ids of 100 and up), `id mod 100` is a date group of field F in 780 of 780, against 69 for a control field. So id = 100 x k + group (k = 1..7; 400s are 616 of the 780). The calls are heavily repeated (the same pair appears in many script files), so only about 30 distinct pairs stand behind these counts, and field 6 dominates. What k means (variant, time of day, state) is open. `field_313(5, id)` as a calendar entry code is NOT supported (21 own versus 16 control of 90).

### How field_357 is used (from the script context)

In `f006.bf`: `if (date_in_range?(4, 6, 4, 26) == 1): lvar0 = field_357(6, 403); lvar1 = field_358(lvar0, 100); object_show?(lvar1, 1)`. So `field_357(F, id)` returns a handle for a calendar group of field F (id = 100 x k + group), `field_358(handle, slot)` creates it in slot 100, 101, ... and `object_show?` shows it. Check against the data: in `n006_002.bin` group 3 has the date 26 April (groups 0 to 3 are 5, 21, 23 and 26 April), and 403 = 400 + group 3 sits under a range ending on 26 April. `p3fes_field.py datecheck` tests this prediction on all scripts.

Result of `datecheck` on all scripts: 1,037 calls tested; the group's calendar date lies inside the `date_in_range?` just before the call in 782 (first version of the chance estimate: 250, which was too low because it counted single dates while a group has several; the command now compares like with like). The ranges are the game's four seasons: 4/6-4/26 (ids 401-403), 4/27-9/22 (410, 22, 23), 9/23-12/3 (420-422) and 12/4-1/31 (430, 433, 434). The id's hundreds digit does not by itself give the season; `field_357(6, 21)` sits under the April range but group 21 has no April date.

Corrected chance level: 782 inside against 380 expected (75% against 37%) over 1,037 tested calls, so about twice chance, not three times. The test pools all `n*.bin` tables of a field, and the same calls repeat in the many scene folders of field 6, so it is a moderate result, not a proof. `datecheck` now also reports the stricter test that uses only the scene folder's own table.

### Correction: the field_357 / calendar link is not supported

The stricter `datecheck` test uses only the table in the script's own scene folder. Of 284 calls whose group exists there, 92 have a date inside the range, against 84 expected by chance (32% against 30%). So the earlier pooled result (782 against 380) came from pooling every table of the field, where a group number has dates all over the year. The same applies to "id mod 100 is a group of field F" (780 of 780 against 69): field 6 has groups 0 to about 40, so most small numbers match, and the control field has fewer groups. Treat both as chance-level. What stays solid: `field_357` returns a handle, `field_358(handle, slot)` places it, `object_show?` shows it, and the scripts choose different ids per season (the four date ranges above). The earlier example (403 and the 26 April date) was a coincidence. The `field_313(5, id)` and `field_357` links to calendar codes and groups are open again.

### .HBN layout (from `p3fes_field.py hbn`, 870 of 925 files fit the header rule)

Header: magic 0x45678901, version, then 8 (count, record size) pairs from +8; the sections follow from 0x48. Record sizes: sections 0 and 5 are 0x20 bytes, the other six 0x14. Every record starts with an id word whose high byte names the section: 0x3400+n (section 0), 0x3800+n (1), 0x3C00+n (2), 0x4000+n (3), 0x4400+n (4), 0x5400+n (section 5, with a few 0x15400 and 0x45400), 0x4800+n (6), 0x4C00+n (7); n counts up from 0 inside a file.
- Sections 1, 2, 3, 4, 6 (0x14 bytes): id, x, y, z, angle. The y is 3.0 in most records (the same height the `.FBN` placements often use), the angle is a multiple of 90 or 91.5 or 1.5-degree steps (-180, -90, 90, 180), so these look like points with a facing.
- Sections 0 and 5 (0x20 bytes): id, a colour word (0xA80000FF in section 0 and mostly 0xA8FF0000; 0xA800FF00 in section 5; alpha 0xA8), then x, y, z, a second x and z, and a last value (0, 45, 44, 36, -1, 41, -40). They look like coloured line or area markers.
- Section 7: id, x, a small float (0.8, 2, 3.8), z, 0.
- Section use (files / records): 0: 288/919, 1: 205/1074, 2: 589/1374, 3: 156/247, 4: 89/92, 5: 8/22, 6: 674/1696, 7: 8/16.
- The ASCII strings (`list`, `REMAIN`, `ENEMY`, `mt_sceneManager.c`, `draw_proc`, `kwlnTask.c`) sit after the records, in the padding that fills a file to 512 bytes. They are most likely stale memory from the tool that wrote the files, not data; the earlier "hits" of `field_313` ids next to them were therefore not meaningful. `hbnlink` checks whether the strings go with particular sections and whether the points lie on `.FBN` positions of the same field.

`hbnlink` first run (26 fields with both file types; within 1.0 unit): the points of sections 2, 3, 4 and 6 did not sit on `.FBN` positions of their own field (0 hits); the 85, 20, 20 and 73 hits in a control field are points at (0, 0), which many records have, near an `.FBN` position of that field. So the `.HBN` points are not the `.FBN` placements. The sections 0 and 5 numbers of that run (4 and 0) are void: the first version read the colour word as a coordinate; fixed. The strings are not tied to one section (ENEMY and REMAIN occur in 204 and 205 files that use different sections), which fits stale padding. Next: `hbnmap` draws each file's points so a person can recognise their shape.

### What the `hbnmap` pictures show (user's first look, five files)

Top-down pictures of the points (x and z) with the `.FBN` positions as crosses. Section 0 lines (the 0x20-byte records) run from a far point to a point near the middle of the field's `.FBN` cluster, several lines ending at nearly the same place (f004_003, f007_002). In f014_005 sections 2 and 3 (32 points each) form two rings, with ticks along the circle, and 4 section 4 points sit apart. In f006_002 and f009_007 the section 6 and section 1 points make columns of four (blue, orange, blue, red). The shapes are regular, so the points are authored layouts, not noise, and they share the `.FBN` coordinate system (the cluster is in the same place), but they do not coincide with `.FBN` positions. What they are used for (camera paths, spawn or patrol points, trigger lines) is not decided; `hbnmap --models` now draws the exported field model under the points to see where they sit on the map.

**Overlay on the field model (f014_005):** with the exported model drawn under the points, the `.HBN` points and the `.FBN` crosses share the model's units and position: the model footprint is a round area about 4000 units wide (x -2010..2010), the two rings of 32 `.HBN` points (sections 2 and 3) lie inside it, and the `.FBN` cluster sits at its entrance side. So `.HBN` coordinates are map coordinates, directly comparable with the model. What the points stand for (spots for people or objects with a facing, patrol or camera points) is not decided.

**f014_005 seen from above (textured export, user's Blender screenshot):** a round arena with a stone-like block in the middle, a ring of blue-grey rocks around it, an outer ring of pink bushes, a narrow walled corridor leading in from the north and a brown path out to the south. The two rings of 32 `.HBN` points (sections 2 and 3) lie on the dark arena floor between the central block and the rock ring (radii about 650 and 980 units against about 1,470 for the rocks and 2,010 for the outer edge). So the points mark spots on the floor of the arena, not the rocks or bushes. Whether they are places where things stand, move or are triggered is not decided. `p3fes_field.py hbnprops` tests whether `.HBN` points sit at the centres of the small objects (the `o` groups) of the exported model.

**`hbnprops` result (207 scene files with a model, radius 100 units):** the `.HBN` points are not at the centres of the model's small objects. Points within 100 units of a prop centre, own scene against a control scene: section 1: 18 against 13 (of 679), section 2: 4 against 21 (of 237), section 3: 0 against 3 (of 63), section 4: 1 against 1 (of 20), section 6: 5 against 39 (of 343). Only section 7 stands out (12 of 16 against 0 in the control, 4 mirrored), but it has 16 points in 8 files, so it is a lead, not a result. So the `.HBN` points are not the placement list of the scenery; they are separate markers on the floor.

**What field 14 is (script `f014.bf` and the user's reading of the model):** field 14 is the Kyoto school-trip inn. Its script has a hide-and-search mini game around the hot spring (procedures named `kyoto_mini_game_00` to `_06` and `bathhouse_hide`), rooms and floors (`dunge_kyoto_to2f` and so on) and a vending machine. `f014_005` is the hot spring, which fits the model (a pool ringed by rocks, a stack of wooden buckets, tiled walls; user's identification). So the two rings of 32 `.HBN` points lie on the water of the bath, not on the rocks. The script shows how objects are put in place: `field_311(n)` returns the object of party member n, and `bathhouse_hide` sets four of them up with `field_312(object, n)` using n = 2, 3, 4, 5, i.e. numbered spots. `slotcalls` tests whether those spot numbers are the `.FBN` slot numbers (id - 0xC00) or the `.HBN` record numbers of the same scene.

**`slotcalls` result (295 scenes, 1,262 distinct `field_312` numbers):** the numbers are not simply the `.FBN` slot numbers. All numbers: 280 in the own scene's slots against 242 in a control (chance level, because small numbers overlap). Numbers of 12 and up: 31 of 212 against 10, about three times chance but only 15%. The `.HBN` record numbers show no signal (section 1: 327 against 211 over all numbers, but 7 against 0 for 12 and up). So `field_312(object, n)` is not settled: n may be a spot, a pose or an action number, or a slot of a different table. Open.

**`calls312` result (2,285 calls):** the second number of `field_312(object, n)` is a spot number, and the party takes consecutive spots. Numbers 0 to 11 are mostly used on objects just created with `field_314` (NPCs and props), 12 to 17 only on party members (`field_311(i)`), always right after a screen fade-out and in groups where member i gets base + i (13, 14, 15 and 16, 17, 18 in field 51; 13, 14 and 15, 16 in field 6; 2, 3, 4, 5 in the field 14 hide-and-search). The statement after the call is `object_show?` in 1,528 calls, `field_312` again in 278, `fn_486()` in 247 (probably "apply the new positions") and `wait_frames` in 205. So n is not a pose; it names a place (and presumably a facing). Only 49 of 316 numbers of 12 and up are `.FBN` slots of the scene, so the spots live in some other table or numbering. Where the table is stays open. `warpcalls` tests whether the third number of `field_33(field, scene, k, 0)` (the scene change) is the number of an `.FBN` file of the destination, which would make the `.FBN` files the entry-point sets.

**`warpcalls` result:** the third number of `field_33(field, scene, k, 0)` is not the number of an `.FBN` file of the destination (48 of 105 against 53 for a control scene). The values of k run 0 to 10 (0 in 33 calls, 1 in 17, 2 in 15, 3 in 11, 4 in 10, 5 in 9). So entry points are not chosen by `.FBN` file name. Where the spot table is stays open; a field-wide version of the `slotcalls` test was added.

**`slotcalls` with the field-wide slot set: the `field_312` spot numbers are `.FBN` slot ids.** Numbers of 12 and up: 184 of 212 are among the slot ids (id - 0xC00) of any `.FBN` file of the field, against 51 for a control field (87% against 24%). All numbers: 760 against 539 of 1,262 (small numbers overlap by chance). Looking only at the scene's own `.FBN` files gave 31 of 212 because one script file serves every scene of a field and uses slots defined in the other scenes' files. So: `field_312(object, n)` places the object at the `.FBN` record whose id is 0xC00 + n (position x, y, z and a rotation, see the record layout above); party members take consecutive slots (base + member index). Still open: which of the variant files (the 000-027, 050-056, 100-142, 150, 200-222 name numbers) supplies the record for a given situation, since the same slot id appears in many variants (3073 in 669 records), and the 0xD00-range ids. `field_33(field, scene, k, 0)` is not an `.FBN` file number (48 of 105 against 53); k (0 to 10) may be an entry slot of the destination, untested.

**`variantargs` result (which script function takes an `.FBN` variant number, values of 50 and up):** `event_ctrl?` argument 1: 14 of 24 distinct values are variant numbers of the same field against 1 in a control field; `common_23` argument 0: 24 of 42 against 5; `field_277` argument 0: 9 of 19 against 2; `event_ctrl?` argument 0: 10 of 260 against 1. `message_show` (174 against 23 of 1,863) and `message_choice?` are not meaningful: they take message numbers, and big fields have both many messages and many variant files. The other functions show nothing. `variantcalls` lists the call sites of the three leads.

**What `variantcalls` shows:** in the school field (6) the calls `event_ctrl?(540, 112, 0)`, `(521, 110, 0)`, `(670, 112, 0)`, `(690, 112, 0)`, `(680, 112, 0)`, `(600, 114, 0)`, `(600, 111, 0)`, `(600, 115, 0)`, `(620, 110, 0)` sit between a fade-out and the community (social link) calls `comu_123(n)` / `comu_234(n, 1)`, and their second number is an `.FBN` variant number of that field (110 to 115); `(670, 199, 0)` and the other 199 calls are followed by `field_122()` and `end`, so 199 means "finish and return". In field 8, `event_ctrl?(520, 50, 0)`, `(520, 51, 0)` and `(520, 52, 0)` come in a row (52 has no `.FBN` file). So the second number of `event_ctrl?` is an event step, and for these events it equals the number of an `.FBN` variant file: the variant is the set of placements for that step of the event. That explains why the same slot id (0xC00 + n) occurs in hundreds of variant files: each variant file places the same slots for a different scene state. `common_23(n, 0)` in the school and the shops takes numbers such as 102 to 119 (club rooms: `dress_club_l`, `orchestra_r`, `swim_club` ...) and 50 to 62 elsewhere; 24 of 42 distinct values are variant numbers of the field, the rest are not, so these are probably location numbers of a related list; not decided. `field_277` is not a variant function (its numbers are item or value ids).

**`fbnvariants` (new):** `py p3fes_field.py fbnvariants <fields folder>` compares, scene by scene, each variant file with the lowest-numbered one (slots in both, slots at the same position, slots in only one) and prints a slot-by-variant table for the scene with the most variants. It tests whether variants move the same slots or add and remove slots. Result pending.

**`fbnvariants` result (143 scenes, 724 variant-vs-base comparisons):** 59 scenes have one `.FBN` file, the rest up to 46 (field 6 scene 3). Against the lowest-numbered file of the scene, variants share 2,459 slots, but only 642 sit at the same position; 1,633 slots appear only in a variant and 6,396 only in the base. So a variant is a partial set: it lists only the slots that change for that scene state, not a full copy. In field 6 scene 3 the base (000) lists slots 0 to 18 at rotation 60 with spread-out positions (the default layout), while variants 001 to 011 list a few slots at rotation 30, many with placeholder positions `0/0` or `0/71` (probably "unset/default") and a few real ones that repeat across variants (slot 50 at -102/-156, slot 51 at 165/-25, slot 54 at -127/-57). Slots 50 and up are the ones that vary most. This fits the reading that `event_ctrl?` step numbers pick a variant, i.e. which slots are moved for that step. Not yet confirmed in a real scene.

**`fbnmap` (new):** `py p3fes_field.py fbnmap <fields folder> 6:3 110 112 -o fbnmap` draws the base `.FBN` of a scene (white squares) against named variants (coloured dots, a line from each slot's base position to its variant position; grey = placeholder positions 0/0 and 0/71) and lists the slots in `fbnmap.txt`. Use it to compare variants 110 and 112 of the school and check that the moved slots match what the event shows on screen.

**`fbnmap` result (field 6 scene 3, variants 110 and 112 against base 000):** the base file has 23 slots spread out to the edges of the room (about -580..560 by -720..720). Variant 112 moves 8 of them (slots 0, 1, 2, 4, 5, 6, 7, 10) into a tight group near the centre (x -284..152, z -227..389), one at 0/0. Variant 110 holds 9 slots: eight at the placeholder 0/71 (slots 1, 51 to 57; slots 1, 52, 53, 54 are base slots) and one real position, slot 60 at 32/100, next to the centre. Reading: a variant is the state of the scene for one event step. 112 gathers a few characters in the middle (a cutscene grouping); 110 clears most slots (0/71 and 0/0 likely mean "removed or parked") and places one new object near the centre. Still not checked against what the game shows for `event_ctrl?(540, 112, 0)` or `(521, 110, 0)`.

**Field 6 scene 3 is the homeroom, and the third number of `field_33` is an entry (door) number.** In `f006.bf.script`, `proc homeroom_l` clears flag 3089, calls `field_360(2, 6)`, `field_137(10242, 0, 0, 0, 1)`, fades out and calls `field_33(6, 3, 0, 0)`; `proc homeroom_r` does the same with `field_137(10241, ...)` and `field_33(6, 3, 1, 0)`. So 0 = the left door and 1 = the right door of the classroom, and the entry number picks where the party appears. (The same procs exist in every school scene folder because one script serves the school.) `SiteibiEvent` enters the room with entry 3. The Blender export of `f006_003` shows desks, chairs, a teacher's desk and a board. Base `.FBN` slots 0 and 1 of this scene sit near each other at the z=700 edge (-301/703 and -154/699); whether they are the door spots is not checked. The earlier `warpcalls` negative (k is not an `.FBN` file number) stands.

**`fbnobj` (new):** `py p3fes_field.py fbnobj <fields folder> 6:3 110 112 -o fbnobj` writes the slots of a scene as marker `.obj` files (one pyramid per slot, named `slot_<n>`; `slot_<n>_unset` for the placeholder positions): one file for the base and one per named variant. They use the same axes as the model exports, so importing them into Blender with the same settings lines them up with the room without typing coordinates.

**`fbnobj` result (homeroom, field 6 scene 3, Blender top view):** the slot markers import with the same axes as the room model and fall inside the room footprint; the 23 base slots cover nearly the whole floor but do not sit on the desk grid (they look like standing spots for people, not furniture). Variant 112's eight slots form a compact group left of the room centre; variant 110 has one marker just below the centre (slot 60). Base slots 0 and 1 are at the south edge, away from the two notches in the right wall that look like the doorways, so the guess that entry numbers 0 and 1 of `field_33` are slots 0 and 1 is not supported. Base slots 4 and 14 (x about 559 and 555) sit at the right wall near the notches; not checked further. Where the entry spots are stored remains open.

**`callprocs` (new):** `py p3fes_field.py callprocs scripts_txt field_137 field_360 field_33 -o callprocs.txt` lists every call of the named functions, grouped by first argument, with the script and proc it sits in (`homeroom_l`, `shoe_locker`, ...). Used to find out what ids such as `field_137(10241, ...)` belong to.

**`callprocs` result (`field_137`, `field_360`):** the first argument of `field_137(id, a, 0, b)` is a door or exit id in the range 10241 and up. Within one field the numbers go with doors: in field 5 `access_to_outside_r/c/l` are 10241/10242/10243; in the school `door_into_school_l/c/r`, `homeroom_r` (10241) and `homeroom_l` (10242) share the same small numbers; the dungeon entrances and warps go by tens (`entrance_to_dungeon1` 10251, `dungeon1_warp_1` 10252, dungeon 2 10261/10262, dungeon 3 10271 to 10273, and so on up to the colosseum 10321, Tartarus blocks 10441 to 10445 in field 34). The same number is used for different places in different fields (10249 is both the drug store and the school laboratory door; 10251 is `comu_dress_club_r` and `entrance_to_dungeon1`), so the id is a per-field door slot, not a global one. The other arguments are mostly `(1, 0, 0, 1)` or `(0, 0, 0, 1)`; the second is often 1 for community rooms and 0 for plain doors. `field_360(n)` takes only 2 (`call_next_level`), 3 (`fix_floor_box_animation`) and 4 (`GAME_01` to `GAME_06` in field 8), so it looks like a mode or category number. `doorwhere` looks for these door ids in the small field files.

**`doorwhere` result (field_137 door ids vs the small field files):** the ids are found in `h*.bin` files (8 of 84 as 16-bit words and 7 as 32-bit words, against 0 for a control field), not in `.fbn` or `.hbn`. The hits are records of 0x2C bytes (11 words) that begin `FFFFFFFF`, then `(index << 16) | 0x0401`, then two words, then the id (0x2801 = 10241 and up), then three more words: for example `h006_003.bin` (the homeroom): `FFFFFFFF 00000401 0006FFFF 00010004 00002801 00000006 00000004 0...` and `FFFFFFFF 00000401 0006FFFF 00000004 00002802 ...`; field 34: `FFFFFFFF 004C0401 00220028 00000006 000028C9 FFFFFFFF 00000003`, then the next records with index 4D, 4E, 4F, word 2 = 0x00220029, 2A, 2B and word 3 = 7, 8, 9. Note that the homeroom's record for id 10241 (`homeroom_r`, which goes to entry 1) has 1 in the high half of word 3, and the record for 10242 (`homeroom_l`, entry 0) has 0. `hbinrecs` decodes all records and tests that link over every proc that calls `field_137(id)` and then `field_33(field, scene, k, 0)`.

**`hbinrecs` result (61 `h*.bin` files with records):** records are 0x2C bytes apart (110 gaps of 0x2C; the larger gaps are multiples of it, with other data between). Two kinds: (1) records with id 0, word 2 = (0, running number), word 6 = 0 to 4, and `FFFFFFFF FFFFFFFF` at the end (most records of `h004`, `h005`, `h006_001`, `h006_004`, `h006_007`); (2) door records with a `field_137` id (10241 and up), word 2 = (field, FFFF), word 3 = (high half, low half), word 5 and word 6. The high half of word 2 is the number of the field the table is in (6 in the school, 0x22 = 34 in Tartarus, 4 for field 4), so the earlier "27 of 27 against 0" is trivial: every call tested stays inside its own field, and the control record is from another field. The same id has a different word 3 in each scene's file. In field 34 the low half of word 3 equals the destination scene in 5 of the 6 comparisons that can be made: `dunge_301_in` calls `field_33(34, 11, 0)` and the record of id 10441 in `h034_003.bin` has low half 0x0B; `dunge_401_in` goes to scene 16 and `h034_004.bin` has 0x10; ids 10442 and 10443 give 12/13 and 17/18 the same way (`h034_003`: 0x0C, 0x0D; `h034_004`: 0x11, 0x12). So word 3 is probably (entry number, destination scene) and the file of a scene lists the doors of that scene. The homeroom (`h006_003.bin`) has the records 10241 = (entry 1, scene 4) and 10242 = (entry 0, scene 4), that is, both doors lead back to scene 4. The test `hbinrecs` was extended to check the scene (low half) and both halves of word 3 against `field_33(field, scene, k)`.

**`hbinrecs` scene test result:** the low half of word 3 equals the destination scene `s` of the `field_33` that follows the door id in 13 of 27 procs, against 0 of 7 for the same id in another field; both halves (entry `k` high, scene `s` low) in 10 of 27 against 0 of 7. The entry half alone matches in 16 of 27 against 2 of 7, which is weak (k is a small number). The control sample is small (7). Besides the Tartarus doors, two school doors fit: `comu_art_club_r` (10241, `field_33(6, 11, 3)`) matches `h006_016.bin` (0001/000B) and `comu_track_and_field` (10242, `field_33(6, 20, 3)`) matches `h006_016.bin` (0000/0014). The same id is a different door in each scene, which is why the same proc name appears with several values: the id is a door slot (10241 = one side, 10242 = another) of the scene it is used in, and the scene's `h*.bin` says where that slot leads. Word 5 is probably the destination field (6 in `h006_003`, 0x22 = 34 in `h006_005`, 7 in `h004_005`); `hbinrecs` now tests it on calls that leave the field.

**`hbinrecs` word 5 test:** untestable (0 of 0). Of the 84 procs with `field_137(id)` followed by `field_33`, only 27 have a record with that id in the field's `h*.bin` files, and all 27 stay inside their field (school and Tartarus), so there is no field-leaving call to test word 5 against. The other 57 doors (field 5 `access_to_outside_*`, shops, dungeon warps, and so on) have no record in their own field's `h*.bin`; `doorwhere` found their ids in only 7 to 8 of 84 cases. So the `h*.bin` door records are a partial table (school and Tartarus doors); the other doors' destinations are in the scripts alone, or in a table not yet found. Word 5 as destination field stays a guess.

**`eventvariants` (new):** `py p3fes_field.py eventvariants scripts_txt extracted\\DATA.CVM\\FIELD\\PACK -o eventvariants.txt` takes every proc with `event_ctrl?(event, step, ..)` (step 50 and up) and `field_33(field, scene, ..)` and checks whether the destination scene has an `.FBN` variant numbered like the step, against a control scene of the same field. It also lists, per step, which scenes have that variant. Result pending.

**`eventvariants` result (95 proc/warp pairs):** the destination scene of the warp has a variant file numbered like the `event_ctrl?` step in 32 of 95 pairs, against 4 of 95 for a control scene of the same field. So the step number is linked to the variant numbers, but not usually to the scene the proc warps to: the examples that miss are club procs (`comu_orchestra_*`, `comu_track_and_field`, `comu_kendo_club`, `comu_swim_club`) that warp to scenes 11 and 20, which have only variants 000, 119 and 000, 050, 051, 120 to 122. Which scenes have which step as a variant (field 6): steps 110, 111, 112 exist as `.FBN` variants only in scenes 3, 6 and 12; steps 113, 114, 115 only in scene 6; step 150 in scenes 1, 3, 4, 5, 6, 7, 8 (the school scenes in general); step 199 nowhere (it ends the event, calls `field_122()`). In field 8, step 50 exists in scenes 1, 3, 5, 8, step 51 in scenes 1 and 3, step 52 nowhere (like 199, probably an end step); in field 9, steps 110 and 111 only in scene 4. Reading: the step number names the arrangement of the scene where the event is played (homeroom, scene 6 and scene 12 for 110 to 112), and the club procs set the step before walking to the club room; the arrangement is used in the scene where the story event plays, which is not necessarily the warp destination. The homeroom's variant 110 (nearly everything parked, one new object near the centre, slot 60) and 112 (a group in the middle) are therefore the homeroom layouts for event steps 110 and 112. Not yet matched to an event on screen.

**`callprocs event_ctrl?` result (231 event numbers):** `event_ctrl?(event, step, sub)` event numbers fall in families. 104 to 339: story events, called from `SiteibiEvent` procs named after the event (`e104_1to105_1`, `e114_1to106_2`, ...) with steps 1 to 5 in order; 400 to 448: calendar phases (`phase_op`, `phase_dng01` to `phase_dng07`, `phase_end`); 5xx to 7xx: community and everyday events, with steps 110 to 115, 150 and 199. In that family the event number names a person or club: 540 student council (steps 111 to 112 in `SiteibiEvent:e540_111to112`, step 112 in `comu_student_council`, step 113 in `comu_teachers_room`), 560 Yukari (`NPC_YUKARI_01` step 110, `NPC_MARCH_YUKARI` step 150), 570 Fuuka, 580 Mitsuru, 590 Aigis (`NPC_SCRIPT_AEGIS` step 111), 600 and 620 to 640 the sports clubs (`NPC_KENDO_01`, `NPC_RIKUJO_01`, steps 111, 114, 115), 610 the couple scenes (`NPC_KOIBITO_KAIKEI_01`), 670 to 690 the culture clubs, 730 to 770 shop and town NPCs, 862 the health room. The `NPCCOMU.BF` script holds one proc per NPC (`NPC_MARCH_*` with step 150, `NPC_*_01` with step 110 to 112), so the step number is probably the NPC placement state of the event, and the `.FBN` variant of the same number is the set of slots for that state. Students walk (`NPC_MARCH_*`) in the 150 variants, which exist in the school scenes in general; the 110 to 112 variants exist in scenes 3, 6 and 12 only.

**Homeroom variants 110, 111, 112 and 150 compared (`fbnmap`):** variants 110 and 150 are identical (9 slots: base slots 1, 52, 53, 54 and new slots 51, 55, 56, 57 parked at the placeholder 0/71, plus slot 60 at 32/100). Variants 111 and 112 are identical except for slot 0 (111: 119/-27, 112: 152/-56): eight base slots (0, 1, 2, 4, 5, 6, 7, 10) moved into a group in the middle of the room, slot 1 at 0/0. So the numbers 110/150 and 111/112 share layouts; the step number picks a script, not necessarily a different layout. Reading: 110 and 150 look like the "after school" state (the classmates in slots 1, 52, 53, 54 are parked and one object, slot 60, near the centre is added); 111 and 112 gather a few people in the middle. The player reports that after school Yukari stands in the back corner of the classroom by the windows; slot 60 (32/100) is near the centre, so it is not her standing place, and where she stands is not found in these variants (it may be set by the `NPCCOMU` script).

**`NPC_YUKARI_01` (NPCCOMU script):** it is the talk script of the NPC (message 102 "......", 103 "Whaddya want?", 104 "Will you ask her out?", then a choice and community calls `comu_124(6)`, `comu_220(6)`, `comu_221(6)`, `comu_292(6)`), so community 6 is Yukari. It uses no spot numbers. It keeps a per-NPC counter with `field_276(110)` / `field_277(110, value)`: the 110 is the NPC's own key, the same number as the step in `event_ctrl?(560, 110, 0)` and as the `.FBN` variant of the school scenes. So `field_277` first arguments of 110 and up are NPC keys, not item ids. Where Yukari stands is therefore set by the scene data (an `.FBN` slot whose record names her) and not by this script; `fbndump` prints the remaining words of the records for variants 110 to 112 of the homeroom to find the field that names the NPC.

**`fbndump` result (homeroom variants 110, 111, 112):** an `.FBN` record has these used words: +0x00, +0x68, +0x6C are decreasing or chained values like 0x00F2A900 and 0x015E8800 (runtime memory addresses, probably stale, the second pair forming a linked list: one record's +0x68 equals the next one's +0x6C); +0x04 = (high half, 0x0005) where the high half follows a person across slots and variants; +0x08 = 0xC00 + slot; +0x0C = 60.0; +0x20, +0x28, +0x40, +0x48 = a rotation (cos/sin of the facing angle, 1.0 in +0x20/+0x34/+0x48 when unrotated); +0x50, +0x54, +0x58 = x, y, z; +0x5C = a float that is the same for every record of a variant (-74.937 in 111, 36.753 in 112; absent in 110); +0x60 = 3, +0x64 = 30.0. The parked slots of variant 110 have x 0, y -70.711, z 70.711 (the placeholder), slot 60 has 32.16, -39.19, 100.18. The high half of +4 is the same for the same person: slot 54 of variant 110 and slot 6 of 111 and 112 both carry 0x1901, slot 52 and slot 5 both carry 0x17D5, slot 57 and slot 2 both 0x1E15. So the classmates parked in variant 110 are the same people who gather in 111 and 112; a person has a different slot number in different variants but one id. Slot 1 carries 0x0001 in all three (probably not a character). Slot 60 of 110 carries 0x1E79. `fbnchars` lists these ids per scene for variants 110 to 115 and 150 and the ids that occur in every scene having a variant, to find out whether a variant number names a person (Yukari = 110).

**`fbnchars` result (field 6):** no character id (high half of +4) is common to the scenes that have the same variant: variants 110, 111 and 112 (scenes 3, 6, 12) and 150 (scenes 1, 3, 4, 5, 6, 7, 8) share none. For 113, 114 and 115 only scene 6 has the variant, so the common ids are simply all ids of that scene (0C4F, 0C85, 0CB3, 0CE5 for 113; 0C50 for 114; 0C4F, 0CB3, 0CE5 for 115). So a variant number does not name a person (110 is not "Yukari's id"): it is a scene state, and each scene fills that state with its own people. The "NPC key" 110 of `field_276/277(110)` and the variant 110 are the same number, but the variant does not hold that NPC's id. How an NPC script (`NPC_YUKARI_01`) is tied to an `.FBN` slot of the scene is still open.

**Chained words of an `.FBN` record:** the last two words (+0x68 and +0x6C) link the records into two lists: the +0x6C of one record equals the +0x68 of the next in its list. In `f006_003_111.FBN` and `_112.FBN` the lists are slots 0, 6, 4, 1 and 7, 5, 2, 10 and the file order alternates between them (0, 7, 6, 5, 4, 2, 1, 10); in `_110.FBN` they are 1, 55, 53, 51, 60 and 56, 54, 52, 57 (file order 1, 56, 55, 54, 53, 52, 51, 57, 60). The first word is a 256-aligned address that falls by 0xB00 or 0xC00 per record, so these are probably memory addresses of the tool or game state that wrote the files. The same person is in different lists in different variants (slot 54 of 110 is in the second list, slot 6 of 111 with the same id 0x1901 is in the first), so list membership is not a property of a person. No use found; treated as noise. The to-do list for Phase 0 is in [docs/phase0-todo.md](phase0-todo.md).

**`hbinprocs` (new):** `py p3fes_field.py hbinprocs scripts_txt extracted\\DATA.CVM\\FIELD\\PACK -o hbinprocs.txt` looks up the running number in word 2 of the plain `h*.bin` records (id 0, word 6 = 0 to 4) as an index in the list of procs of the field's script, 0-based and 1-based, and prints the proc names next to the record. Idea: these records bind a trigger or object of the scene to a script proc (the way the NPC talk procs such as `NPC_YUKARI_01` get called). Result pending.

**`hbinprocs` result (129 plain `h*.bin` records): the running number is the index of a proc in the field's script.** The numbers are 0-based indexes into the list of procs of the field script (the order in which `proc name:` lines appear), and the names fit the scene in nearly every record: `h004_003.bin` (dormitory 2F) lists `check_vondor`, `amadas_room`, `junpeis_room`, `players_room`, `sanadas_room`; `h004_004.bin` `hukas_room`, `aegiss_room`, `yukaris_room`, `mitsurus_room`; `h005_001.bin` (the mall) `night_club`, `coffee_shop`, `accessory_shop`, `police_box`, `antique_shop`, `drug_store`, `cd_shop`, `game_center`, `ufo_catcher`, `access_to_outside_l/c/r`; `h006_004.bin` (school corridor) `homeroom_r`, `homeroom_l`, `student_council`, `fire_exit_2f`, `broadcasting_room`, `classroom_1e`; `h006_011.bin` the club rooms (`art_club_l/r`, `orchestra_l/r`, `photograph_club`, `dress_club_l/r`, `laboratory_l/r`, `caretaker_room`); `h006_020.bin` `track_and_field`, `kendo_club`, `swim_club`; `h039_003.bin` runs `entrance_to_dungeon1`, `dungeon1_warp_1`, `entrance_to_dungeon2`, ... `entrance_to_colosseum` in order; the Kyoto inn files list the `dunge_*` procs. So a plain record is a trigger of the scene (a door, room entrance or interactable) bound to the script proc that runs when the player uses it. Other words of the record: the high half of word 1 is a label number (0x0D homeroom, 0x0E classroom 1E, 0x0F student council, 0x10 teachers' room, 0x11 health room, 0x12 reading room, 0x13 dress club, 0x14 orchestra, 0x15 photography, 0x16 kendo, 0x17 swim, 0x18 track and field, 0x1B broadcasting, 0x1C caretaker, 0x1D art club, 0x1E laboratory; in the mall 0x20 to 0x28 for the shops; 0x4C to 0x5A for the Tartarus doors; 0x70 to 0x78 for the entrance floor), probably the name plate or map icon of the place, or 0 when the place has none; word 6 is a small number 0 to 4 (not decoded; maybe the facing or the kind of trigger). Door records (id 10241 and up) have word 2 = (field, proc index or FFFF) and word 3 = (entry, destination scene); in the Tartarus files the proc index of a door record does not match the destination proc by name, so that field is not understood. This answers what the running number refers to. It does not answer how NPC talk scripts in `NPCCOMU` (`NPC_YUKARI_01`) are bound: they are not procs of the field script, so they are not reached through these records.

**`entrycount` (new):** `py p3fes_field.py entrycount scripts_txt extracted\\DATA.CVM\\FIELD\\PACK -o entrycount.txt` collects the entry numbers used for each destination scene (from `field_33(field, scene, k, 0)` calls and from the door records of the `h*.bin` files) and compares them with the sections of the scene's `.HBN`: which section has as many records as there are entries, or highest entry + 1, against a control scene. Idea: the `.HBN` records with an id, position and angle (sections 1, 2, 3, 4, 6, 7) look like spawn points. Result pending.

**`entrycount` result (35 scenes with entry numbers and an `.hbn`):** section 1 of the `.HBN` (id 0x38xx, 0x14-byte records of id, x, y, z, angle) has as many records as the scene has entries in 14 scenes against 5 for a control scene, and has highest entry + 1 records in 17 scenes against 3. The other sections match at about control level (section 0: 5/2 and 4/3, section 5: 3/2 and 4/1, section 6: 0/1 and 1/0, section 7: 0/3 and 0/2; sections 2 to 4 have none). So section 1 is very likely the table of entry spots (spawn position and facing) of the scene, record k for entry k. To confirm: in the homeroom (field 6 scene 3, entries 0 and 1 from `homeroom_l` and `homeroom_r`) the two section 1 points should lie at the two doorways in the right wall.

**`hbnobj` (new):** `py p3fes_field.py hbnobj <fields folder> 6:2 1 -o hbnobj` writes the points of a scene's `.hbn` (the sections named after the scene, default section 1) as marker `.obj` files for Blender: one pyramid per point named `s<section>_<record>_id<low byte of id>`, and a line from each point towards its angle (read as degrees, direction (sin, cos) in x/z, as `hbnmap` draws it; the unit is unverified). Same axes as the model exports.

**`hbnmap` field 6 scene 2 (top view):** the six section 1 points fall in two groups, two near the top of the picture and three evenly spaced in a row at the bottom plus one near the middle. Red (section 0) and blue (section 6) points sit at the same x positions as the rows, so those sections may describe the same places. The model is too faint in the picture to tell whether the points are at doorways; the Blender check with `hbnobj` is the next step.

**Empty NPC `.HBN` files:** four files in the field packs have a name of the form `SCR_<n><letter>_NPC<id>_<n>f<field>_<scene>.HBN` (fields 6 scenes 3 and 5, 10, 14); the one checked (`F006_003.PAC.d`) is 0 bytes. The homeroom (field 6 scene 3) therefore has no `.hbn` of its own, which is why `entrycount` does not list it. Treated as leftovers.

**`hbnobj` result (field 6 scene 2, Blender top view with the room model):** the six section 1 points fall into three places. Three points sit in a row at the top, inside a fan-shaped structure in the top wall of the model. Two points sit at the bottom, in the gap between two wall pieces (an opening in the bottom wall). One point sits left of the middle. The facing lines point into the open area at every point: the top three face south (into the area), the bottom two face north, the middle one faces west. This is how entry spots would look (placed at an opening, facing into the scene), so section 1 of the `.hbn` is now supported as the entry spots table (record k = entry k) by two tests: the record counts (17 of 35 scenes against 3) and this picture. Not yet done: matching each record number to a named door (the screenshots do not show which marker is which), and the angle unit (0 and 180 look natural as degrees, radians not excluded).
