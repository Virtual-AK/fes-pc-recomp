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
`.BF` scripts, `.BED` effect data (`BED4`, header layout read, blobs not decoded), `.SQ` sequences inside `.SE` banks, `.EPL` effects, `.CIN` cut-in data, `.SPR` sprites (`SPR0`), `.ANM` animations, `.TBL` tables of skill, persona and battle values, `.ENV`, `.CMR`, `.FBN`, `.HBN` field data, and the animation and skeleton data inside `.RMD` models.
