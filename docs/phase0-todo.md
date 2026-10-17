# Phase 0: what is left

> Project progress: `█████████████████░░░` Phase 0 is about 85%, overall about 13%. See [docs/progress.md](progress.md).

Phase 0 is the research and tooling phase. This page lists what is still open in it, in plain words, so nobody has to dig through the other pages. Items marked **needed** are, as far as we can tell now, what Phase 1 (picking the approach and prototyping) depends on. Items marked **helps mods and tools** are format knowledge that is good to have but that a port built by recompiling the game's own code does not strictly need, because the game's code reads those files itself. That split is our current reading, not a proven fact; Phase 1 may change it.

How to read the status: **done** = decoded and checked on a real disc; **partly** = layout known, meaning not; **open** = not started or no result yet.

## 1. Needed before Phase 1

These are the open questions from [docs/roadmap.md](roadmap.md). None is answered yet. [docs/phase1-decisions.md](phase1-decisions.md) lays out the options and the first investigation for each. Summary of all five first-pass answers: [docs/phase1-summary.md](phase1-summary.md).

| # | Question | Status | How we would find out |
| --- | --- | --- | --- |
| 1.1 | Recompile or decompile? Which existing PS2 recompilation work can be reused? | **answered (first pass)** | Static recompilation. PS2 Web Recomp's recompiler translated our executable in 1.7 s with 0 rejected entries; generated C++ passes a syntax check. Left: link and run it with the disc image. See `docs/formats.md`. | Read what exists, try the executable on the smallest candidate (Phase 1 prototype). |
| 1.2 | How the game uses the vector units (VU0, VU1) for graphics, and how much can be translated automatically | **answered (first pass)** | See `docs/formats.md`: heavy VU0 macro-mode use, about 170 different VU1 programs uploaded through VIF/DMA. Left: read the largest programs, and how the packets reach the GS. | Find the microcode in the executable, count how many different programs there are, read the biggest ones. |
| 1.3 | How the CVFS/ROFS file calls map onto the archives | **answered (first pass)** | The game asks by path through counted request objects on top of a device-based `cvFs` layer; replace the public `cvFs*` functions with host versions. Left: check for direct `sceCd*` read calls. See `docs/formats.md`. |
| 1.4 | How the game paces its frames (needed before raising the frame rate) | answered (first pass) | Vertical-blank interrupt handler with a refresh counter; no clock reads found, so game time is per frame. See `phase1-decisions.md`. |
| 1.5 | Which IOP modules the game loads and which need replacing | **answered (first pass)** | 14 modules loaded by name: 5 for input and saves (small to replace), 9 for sound (the large piece; replace by re-implementing or by emulating the IOP). Left: open `IOPRP310.IMG`. See `docs/formats.md`. |
| 1.6 | Other regions | decided | The tools read any region; only NTSC-U is a target. |

## 2. Data formats

| Area | Status | What is left | Matters for |
| --- | --- | --- | --- |
| Disc, CVM archives, containers | done | nothing | needed |
| Textures (`.TMX`) | done | nothing | needed |
| Audio (ADX/streams), sound effects (`.SE`) | done | exact sequence timing, pitch, envelopes, pan; control events 0x0E and 0x0F | helps mods and tools |
| Text | done | the exact meaning of each control code; room for text longer than the original (the patch tool needs edited text to fit) | helps mods and tools |
| Models and animation | done | the game-specific chunks (`F0F000E0` and the trailing `F0F000xx`), 4 unknown floats in effect-model animation keys, trailing bytes in 88 model files | helps mods and tools |
| Field geometry | done | nothing | needed |
| Scripts (`.BF`) | partly | 213 functions are called by scripts; about 44% of all calls are named. Decode the rest, starting with the most used. See [docs/script-functions.md](script-functions.md). | helps mods and tools |
| Effect data (`.BED`) | partly | the fields inside the parameter blocks (timings, sizes, colour curves) | helps mods and tools |
| Field tables | partly | see section 3 | helps mods and tools |

## 3. Field tables in detail

What is known: `n*.bin` is a calendar; `.FBN` records are placements (slot = id minus 0xC00; position, facing, a character id in the high half of the word at +4, a variant number in the file name); scripts put the party on `.FBN` slots (`field_312`); `event_ctrl?` step numbers match `.FBN` variant numbers (32 of 95 against 4 of 95) and a variant is a scene state; `.HBN` layout and units; `h*.bin` holds 0x2C-byte door records (destination scene in the low half of word 3) for some doors; `field_137` ids are per-field door slots.

| # | Open item | Status | Next step |
| --- | --- | --- | --- |
| 3.1 | What the `.HBN` points are for (two rings of 32 points in the Kyoto inn bath, 0x20-byte coloured lines) | open | Compare with scripts of the same field; look for a consumer (search, camera, collision?). |
| 3.2 | How a script object is tied to the scene | partly done | Doors, rooms and shops: solved, the plain `h*.bin` records bind a trigger to a proc of the field script by index (word 2). Open: how NPC talk scripts in `NPCCOMU` (`NPC_YUKARI_01`) are bound to the people in the scene; they are not procs of the field script. |
| 3.3 | Where the entry spots of a door live (the third number of `field_33`) | **done**: record k of `.HBN` section 1 of the destination scene (x, y, z, angle in degrees); in field 6 scene 2 the procs `entrance_door_l/_c/_r` send the player to records 2, 3, 4 at the left, centre and right doors | Left: the callers of entries 0 and 1, the stray record `38FF` in field 4 scene 10, and the remaining words of the record. |
| 3.4 | The doors with a `field_137` id but no `h*.bin` record | answered: 74 door procs; records exist only for school (field 6) and Tartarus (field 34) doors; fields 4, 5, 7, 8, 9, 14, 31, 32, 39 have none | Their destinations are only in the scripts (`field_33`), and the entry spot is `.HBN` section 1 (3.3), so nothing is missing for a port. Left: whether the records of the school and Tartarus doors hold anything the scripts do not (see 3.5 and 3.6). |
| 3.5 | The plain `h*.bin` records | mostly done | Word 2 is a proc index and word 1's high half a label number (see formats.md). Open: word 6 (0 to 4), the exact use of the label number, and the proc index in door records. |
| 3.6 | Word 5 of the door records (guessed: destination field) | tested, not supported | 44 records: 23 equal the own field, 16 are -1 (Tartarus), 5 are 7 or 34 on doors that stay in their field. Unknown meaning; low priority. |
| 3.7 | The float at +0x5C of an `.FBN` record (same for every record in a variant: -74.9 in 111, 36.8 in 112) | open | Compare across many variants. |
| 3.8 | The first word and the last two words of an `.FBN` record | partly | They look like stale memory addresses; the last two link the records into two interleaved lists (see below). No use found; probably noise in the file. |
| 3.9 | Calendar groups to script ids | tried, not supported | Only revisit with a new idea. |
| 3.10 | `field_313` object ids | open | Not decoded. |
| 3.11 | `.FBN` ids in the 0xD00 range | open | Count and compare with 0xC00 ids. |
| 3.12 | The 43 empty field files | **done** | The unpacker skipped real entries (`.HBN`, `.CMR`, `.ENV`, ...) behind 16-byte fillers; fixed in `p3fes_unpack.py`. About 500 real files had been missing. Everything was re-extracted (`extracted3`), the script-based checks were rerun (`tools/rerun_checks.bat`, `tools/rerun_script_checks.bat`): no finding changed. Models, text, textures, audio and sound banks were redone (`tools/redo_exports.bat`, `tools/redo_sound_banks.bat`) with no read errors. The 43 empty field files stay empty (placeholders, not checked further). |
| 3.13 | What `field_360`, `field_276`/`277`, `common_23` and the other arguments of `field_137` mean | partly | `field_276/277(npc key, value)` is a per-NPC counter; `field_360` takes 2, 3 or 4 only. |
| 3.14 | `event_ctrl?` sub-step (third number) | open | Seen as 0 almost always, other values in `ns007_002` and the school `comu_teachers_room` procs. |
| 3.15 | Text rebuild was disabled for 40 script files | **done** | Three causes in `p3fes_text.py`: zero bytes before the pointer table (`f035`), messages listed in another order than they lie in the file (`f007`, `f012`, `NPCCOMU.BF`, `ns007_002`), and zero bytes after a message. Confirmed on the real data: `problems.txt` now lists only the two scripts without messages. Edits to the files with extra message data must keep each message's size. |

The interleaved lists (3.8): in `f006_003_111.FBN` and `_112.FBN` the records are chained through the last two words into two lists, slots 0, 6, 4, 1 and 7, 5, 2, 10, with the file order alternating between them; in `_110.FBN` the lists are 1, 55, 53, 51, 60 and 56, 54, 52, 57. Which list a person is in changes between variants, so the lists are not a property of a person.

## 4. Housekeeping

- Keep every tool tested (`python tests/run_tests.py`) and every result written into [docs/formats.md](formats.md).
- Never upload game data: exported script listings, extracted text, textures, models and pictures of maps stay local; numbers and function names are fine.
- [docs/qa-guide.md](qa-guide.md) is the test routine for the community.

## 5. When is Phase 0 done?

Our suggestion, to be agreed: Phase 0 is done when section 1 has an answer for each question (even "not needed") and the formats marked **needed** in section 2 are done. The rest of section 2 and section 3 can continue in parallel with Phase 1 as mod and tooling work, since they do not block the port. The 85% figure was a rough estimate made before this split; the maintainers may want to revisit it once section 1 is looked at.
