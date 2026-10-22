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

Phase 0 is about 85%: disc, archives, textures, audio, sound effects, text, models, animations and field geometry are done; scripts, effect data, field tables and the remaining model chunks are partly understood. Phases 1 to 3 work end to end: the game is recompiled and runs from the player's own disc with graphics, sound, movies, input and saves, and the opening, town and first dungeon floors have been played through. The native Windows PC window now exists (it runs at 60 fps on the graphics card, with a resolution setting, a widescreen option, fast-forward on Tab, autosave and resume), which moved phases 3 and 4 forward; phase 4 (testing the whole game, and a clean-PC test of the one-step Windows setup) is still the biggest gap. Phase 5 has the browser build with card backups, autosave, key and controller settings, a speedrun clock, widescreen, volume settings, turbo on Tab, a one-command installer ([docs/install.md](install.md)), and the launcher: loose-file mods (folders, zip, 7z and rar, merged Aemulus-style with a priority order), browsing and previewing GameBanana mods before installing, battle and menu portrait mods, ten colour themes (one, Twelve, unlocked by saying you finished The Journey; automatic detection from the memory card is on hold until before and after card copies exist), in-launcher wiki guides, one-key screenshots, launcher music, updating the launcher from GitHub, and a dialogue Log that lists every line shown with its speaker and a clickable speaker icon that replays the voice clip ([docs/log-plan.md](log-plan.md)). Not done: subtitle languages, a Log key inside the game window, widescreen for the menus and HUD (only the 3D view is widened), and frame rates other than 60. The percentages are a guide, not a promise. See [docs/roadmap.md](roadmap.md).
<!-- progress:end -->
