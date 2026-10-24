# Roadmap and open questions

<!-- progress:start -->
**Overall progress: about 83%** (rough estimate by the maintainers; the game starts and plays in the browser and in a native Windows window, and most of what is left is testing and polish)

`█████████████████░░░` 83%

| Phase | Progress | |
| --- | --- | --- |
| 0. Research and tooling | `█████████████████░░░` | 85% |
| 1. Pick the approach, prototype | `████████████████████` | 100% |
| 2. Runtime layer (files, audio, video, input, saves) | `██████████████████░░` | 92% |
| 3. Graphics (GS and vector units to a modern API) | `██████████████████░░` | 88% |
| 4. Playable desktop build, QA | `████████░░░░░░░░░░░░` | 40% |
| 5. Browser build and mod tooling | `███████████████████░` | 95% |

Phase 0 is about 85%: disc, archives, textures, audio, sound effects, text, models, animations and field geometry are done; scripts, effect data, field tables and the remaining model chunks are partly understood. Phases 1 to 3 work end to end: the game is recompiled and runs from the player's own disc with graphics, sound, movies, input and saves, and the opening, town and first dungeon floors have been played through. The native Windows PC window now exists (it runs at 60 fps on the graphics card, with a resolution setting, a widescreen option, fast-forward on Tab, autosave and resume), which moved phases 3 and 4 forward; phase 4 (testing the whole game, and a clean-PC test of the one-step Windows setup) is still the biggest gap. Phase 5 has the browser build with card backups, autosave, key and controller settings, a speedrun clock, widescreen, volume settings, turbo on Tab, a one-command installer ([docs/install.md](install.md)), and the launcher: loose-file mods (folders, zip, 7z and rar, merged Aemulus-style with a priority order), browsing and previewing GameBanana mods before installing, battle and menu portrait mods, ten colour themes (one, Twelve, unlocked by saying you finished The Journey; automatic detection from the memory card is on hold until before and after card copies exist), in-launcher wiki guides, one-key screenshots, launcher music, updating the launcher from GitHub, and a dialogue Log that lists every line shown with its speaker and a clickable speaker icon that replays the voice clip ([docs/log-plan.md](log-plan.md)). Widescreen now covers the 3D view, menus, HUD, portraits and Social Link screens, in the PC window and the browser (the community patch baked into the mod build; a few of its parts stay off, see [docs/widescreen.md](widescreen.md)). Not done: subtitle languages, a Log key inside the game window, and frame rates other than 60. The percentages are a guide, not a promise. See [docs/roadmap.md](roadmap.md).
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
1. **Scripts (`.BF`)**: layout (`FLW0`), instruction set, embedded message text and the table of the 213 game functions the scripts call are known; next: decode what each function does (start with the most used: message window, flags, field commands) by reading their code and checking arguments against the data. Also the field data files: models and textures are done; what `.FBN`, `.HBN`, `n*.bin` and `h*.bin` place, and `n*.bin` is a calendar and `.FBN` records are placements. `field_357(F, id)` returns an object handle that `field_358` places in a slot (the scripts use different ids per season); a link from those ids to the calendar groups was tried and is not supported at the scene level. What `.HBN`, `h*.bin`, `field_313` ids and the `.FBN` ids mean is still open.
2. **Effect data (`.BED`)**: the element trees and parameter-block headers are read; the fields inside the blocks (timings, sizes, colour curves) need comparison with how effects look in game.
3. Text: the exact meaning of each control code, and making room for text that is longer than the original (the patch tool currently needs edited files to fit their existing space).
4. Sound: exact sequence timing, pitch, envelopes and pan; control events 0x0E/0x0F.
5. Models: what the game-specific chunks (`F0F000E0` and the trailing `F0F000xx` chunks) hold; the 4 unknown floats in the effect-model animation keys; trailing bytes in 88 model files.
