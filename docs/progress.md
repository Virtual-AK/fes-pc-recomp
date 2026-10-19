<!-- progress:start -->
**Overall progress: about 75%** (rough estimate by the maintainers; the game already starts and plays in the browser and in a PC window, and most of what is left is testing and polish)

`███████████████░░░░░` 75%

| Phase | Progress | |
| --- | --- | --- |
| 0. Research and tooling | `█████████████████░░░` | 85% |
| 1. Pick the approach, prototype | `████████████████████` | 100% |
| 2. Runtime layer (files, audio, video, input, saves) | `██████████████████░░` | 90% |
| 3. Graphics (GS and vector units to a modern API) | `█████████████████░░░` | 85% |
| 4. Playable desktop build, QA | `████░░░░░░░░░░░░░░░░` | 20% |
| 5. Browser build and mod tooling | `██████████████░░░░░░` | 70% |

Phase 0 is about 85%: disc, archives, textures, audio, sound effects, text, models, animations and field geometry are done; scripts, effect data, field tables and the remaining model chunks are partly understood. Phases 1 to 3 work end to end: the game is recompiled and runs from the player's own disc with graphics, sound, movies, input and saves, and the opening, town and first dungeon floors have been played through. Phase 4 (testing the whole game) has only just started, and phase 5 has the browser build with card backups, autosave, key and controller settings, and a first mod route (patch files baked into a separate recompiled copy), and a one-command installer ([docs/install.md](docs/install.md)) tried on a fresh copy (browser build, title screen to the first Tartarus floor); the PC window from a fresh install is still untested. The percentages are a guide, not a promise. See [docs/roadmap.md](docs/roadmap.md).
<!-- progress:end -->
