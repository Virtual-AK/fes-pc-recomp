# Roadmap and open questions

| Phase | Goal |
| --- | --- |
| 0 | Research and tooling (this repository): map the disc and executable. |
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
