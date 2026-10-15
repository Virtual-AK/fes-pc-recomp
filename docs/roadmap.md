# Roadmap and open questions

| Phase | Goal |
| --- | --- |
| 0 | Research and tooling (nearly done): map the disc and executable, unpack the data, convert textures, audio, text and models. |
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
Done and checked on a real NTSC-U disc: reading the disc and CVM archives, extracting and splitting containers, textures (.TMX) to PNG, audio to WAV, game text extract, edit, repack and patch (an edited tutorial plays in game), and 3D models (geometry, materials and textures; all 2,934 models in `BTL.CVM/MODEL` export).

Remaining format work that would help later phases, roughly in order of usefulness:
1. **Model skeletons and animation:** the HAnim skeleton and the animation chunks inside `.RMD`; skin weights (needed to pose characters).
2. **Scripts (`.BF`)** and **sound sequences (`.BED`)**, and the field data files.
3. Text: the exact meaning of each control code, and making room for text that is longer than the original (the patch tool currently needs edited files to fit their existing space).
4. Models: what the game-specific chunks (`F0F000E0` and the trailing `F0F000xx` chunks) hold; confirming 4-bit textures on a texture that fills its whole area; the models in other folders.
