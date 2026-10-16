# Roadmap and open questions

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

Phase 0 is about 85%%: disc, archives, textures, audio, sound effects, text, models, animations and field geometry are done; scripts, effect data, field tables and the remaining model chunks are partly understood. The percentages are a guide, not a promise. See [docs/roadmap.md](docs/roadmap.md).
<!-- progress:end -->

| Phase | Goal |
| --- | --- |
| 0 | Research and tooling (nearly done): map the disc and executable, unpack the data, convert textures, audio, sound effects, text, models and animation. |
| 1 | Pick the approach: static recompilation of the executable to C++ with a runtime that replaces the PS2 hardware, versus a gradual decompilation. Prototype on a small piece. |
| 2 | Runtime layer: file system (CVFS/ROFS replacement with mod folders), audio (ADX decode), video (SFD decode), input, saves. |
| 3 | Graphics: translate PS2 graphics synthesizer and vector unit work to a modern API, with resolution and frame-rate scaling. |
| 4 | Playable build on desktop; QA across the whole game. |
| 5 | Browser build (WebAssembly and WebGPU) and mod tooling. |

## Open questions
- Recompile or decompile? Which existing PS2 recompilation work can be reused?
- How the game uses the vector units for graphics, and how much can be translated automatically.
- How the CVFS/ROFS calls map onto the archives, and the formats of the main file types.
- How the game paces its frames (needed before raising the frame rate safely).
- How the IOP modules are used, and which need replacing.
- Other regions: the tools read any region, but only NTSC-U is a target.

## Phase 0 results
Done and checked on a real NTSC-U disc: reading the disc and CVM archives, extracting and splitting containers, textures (.TMX) to PNG, audio to WAV, game text extract, edit, repack and patch (an edited tutorial plays in game), and 3D models with skeletons and animations (all 3,766 models export to glTF; animations confirmed moving in Blender), and sound effects (`.SE` banks decode to WAV, sequences render; checked by ear). Field (map) geometry: all 819 field `.RWS` files export to `.obj` with textures (5,344 models, 7,689 textures; 4-bit field textures are 16-bit uploads, confirmed on real data; checked in Blender on several fields).

Remaining format work that would help later phases, roughly in order of usefulness:
1. **Scripts (`.BF`)**: layout (`FLW0`), instruction set, embedded message text and the table of the 213 game functions the scripts call are known; next: decode what each function does (start with the most used: message window, flags, field commands) by reading their code and checking arguments against the data. Also the field data files: models and textures are done; what `.FBN`, `.HBN`, `n*.bin` and `h*.bin` place, and `n*.bin` is a calendar and `.FBN` records are placements. `field_357(F, id)` ids are calendar date groups (id = 100 x k + group; what k means is open). What `.HBN`, `h*.bin`, `field_313` ids and the `.FBN` ids mean is still open.
2. **Effect data (`.BED`)**: the element trees and parameter-block headers are read; the fields inside the blocks (timings, sizes, colour curves) need comparison with how effects look in game.
3. Text: the exact meaning of each control code, and making room for text that is longer than the original (the patch tool currently needs edited files to fit their existing space).
4. Sound: exact sequence timing, pitch, envelopes and pan; control events 0x0E/0x0F.
5. Models: what the game-specific chunks (`F0F000E0` and the trailing `F0F000xx` chunks) hold; the 4 unknown floats in the effect-model animation keys; trailing bytes in 88 model files.
