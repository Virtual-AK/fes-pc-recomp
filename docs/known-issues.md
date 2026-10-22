# Known issues

## Characters stall in place, and some appear too early (found 21 October 2026)
- **Where:** the opening, from the "Early Morning" walk to school (school gate, 4/21) through the "After School" scene. Seen on Kenji (stands at the bottom left of the gate scene for a moment, in view earlier than in the original), Junpei (stalls before walking up to the protagonist) and Adachi (stalls after trying to walk off screen).
- **Same in:** the PC window and the browser; with every mod off (normal game) and with the mods build. So it is in the recompiled game code or the shared runtime, not in the mods or in either window.
- **Deterministic:** happens at the same moment on every run.
- **Checked against the original game** (a PS2 longplay of the same scene): there Kenji is not visible yet at that moment, so this is a real fault, not authentic behaviour.
- **Not the cause:** Turbo (off in the PC window by default now), frame pacing (60 fps steady). Disc reads are timed (about 0.25 ms per sector plus 0.4 ms, no seek time), a slow-disc test (x20 per sector, +100 ms per read, confirmed active in the log) left the stalls exactly the same, 3 to 4 seconds each, so load timing is ruled out.
- **Open:** which script step or code path moves or shows the character too early. Next step would be a per-frame position log of the characters in the scene and a comparison with the video.
- **Also open:** PC-window Turbo (Tab) froze the game around the classroom scene; see fast-forward.md.

### Investigation tool: script-command trace
`tools/ps2run_commtrace_patch.py` (run by the installer): with `PS2_COMM_TRACE=FROM,TO` in `~/.p3fes-window-env` the window log lists every script function call (COMM number, register values, frame) between those frames. Used to see which script step shows or moves a character at the gate scene.

### Investigation tool: slow disc
`tools/ps2run_discslow_patch.py` (run by the installer): `PS2_DISC_SLOW=N` and `PS2_DISC_SEEK_MS=M` in `~/.p3fes-window-env` make the simulated disc N times slower per sector and add M milliseconds per read. It patches both disc files: `cdvdfsv.cpp` (the game's own reads) and `cdvd.cpp` (the console modules). The first version only patched `cdvd.cpp` and had no effect on the game. Test for the stalling characters: if the stall changes with a slower disc, the cause is how fast loads finish.

### Results so far (21 October 2026)
- Same at the same moments on every run, 3 to 4 seconds each, PC window and browser, mods on or off, slow disc or normal disc.
- Script trace: the gate scene (about frames 2313 to 3975) makes no calls through the script function table, so it is not driven from there (probably a separate event engine). Script calls before it (frames 1501 to 2327) look normal, one every 2 frames.
- Disc log of that scene: only music streaming, plus one model load (BTL.CVM, 93 sectors) at frame 2638 and one DATA.CVM read (146 sectors) at 3064.
- Next ideas: (1) memory dumps (F7) at the three moments (just before, during, after the stall) and a diff to find the character's position record, then watch it with PS2_WATCH; (2) check whether the stall length matches a fixed frame count (about 200 frames) and what in the game counts that long; (3) compare a second scene with the same kind of stall (Junpei, Adachi).

### Investigation tool: actor diff
`tools/p3fes_actordiff.py STILL1 STILL2 MOVED` takes three F7 memory dumps (character standing, standing 1 to 2 seconds later, and after he has started walking) and lists the position records that are equal in the first two and changed in the third. Next, `PS2_WATCH=0xADDR,...` (probe patch) logs when those words change.

### Memory snapshot result (22 October 2026)
- Dumps at frames 2768 (Kenji standing), 2866 (still standing, 1.6 s later) and 2990 (walking). `p3fes_actordiff.py` listed the candidate records; the strongest, 0x0142660C, turned out to be copies of one value (x = -25.212 changing to -18.915, y 8.078, z 63.699 unchanged) in 220 places inside drawing data, each next to a vector that changes fast (about 2078 shrinking to 776) and a constant 60.0. That looks like the camera, not a character.
- So: the animation data of the characters changes between the first two dumps (they keep animating) while that value stays still, and it only moves after the stall. Working idea: the scene timeline (camera, then the characters) starts late; the stall is a fixed 3 to 4 seconds in every run.
- To check: does the camera in the original move while Kenji walks in? Does the music volume (music stream starts at the same moment, frame 2607) change the stall? Then find what the timeline waits for.
- Correction, same night: in the original video the camera stays still while the characters move, so the "camera" reading above is doubtful; the value may be the character's own position data (a copy in drawing data), or something else. The music-volume test proved nothing (volume does not stop the music stream). Console timers run on the same virtual clock as the frames (runtime/src/hw.cpp), so a time-based wait should line up with frames; timer speed is not the cause.
- Disc log around the stall (frames 2700 to 3000): no reads except the music stream, so nothing the scene loads ends the stall. One BTL.CVM read (93 sectors) at frame 2638, probably the scene's event data; the scene makes no script-table calls, so it is probably an event timeline from that file.
- Next: (1) measure the exact stall length in frames with PS2_WATCH on 0x0142300C (logs the frame its value changes) and compare with the video; (2) read the event data/script for this scene to find what it waits for before the characters start; (3) check the same stall in the browser build for its length.

### Thread comparison (22 October 2026)
Window closed during the stall (frame 2695) and well after it (frame 3869): the EE thread list (9 threads, the two semaphores with one waiter each, all pc/ra values) and all 44 IOP threads are identical in both logs, and the disc/audio timeline is the same in both runs (deterministic). So during the stall nothing is blocked at the system level; the wait is inside the game's own logic (the scene timeline), not a lock or resource the runtime holds back.
Where this leaves the investigation: the cheap black-box checks are done (mods, Turbo, pacing, disc speed, volume, timers, threads). What is left is to find the code that moves the characters: a debug build that reports which game function writes the position value at the frame it starts changing (needs a store watch in the runtime), or reading the scene's event data with the format tools on the PC.

### Store watch (22 October 2026)
tools/ps2run_storewatch_patch.py: `PS2_STORE_WATCH=0xADDR,...` logs `[store] frame F addr: old -> new size S ra .. sp .. stack: ...` whenever the game writes a different value to a watched word, with the call chain found on the game's stack. First target: Kenji's x position at 0x0142300C (-25.2122 standing, -18.915 moving) and the copy at 0x0142660C. Needs a full rebuild (memory.hpp is included everywhere).

### First store-watch result (22 October 2026)
Kenji's position words (0x0142300C / 0x0142660C) are not written every frame but at keyframes: frame 6307 placed, 6319/6321 moved, then NOTHING for 224 frames (6321 -> 6545, about 3.7 s = the stall), then writes at 6545, 6580, 6583, 6617, 6619, 6621, 6999, 7081. The writer is always the code called from 0x003138A0 (callers 0x00317810 / 0x00317A64 / 0x0019E934; at 6545 through 0x003293B8, at 6319-6321 through 0x004F2EE8). So the stall is a long gap between two keyframes of a scene timeline; the question is what that timeline waits on for 224 frames. tools/p3fes_showcode.py prints the recompiled code around such addresses.

### Widescreen is the trigger (22 October 2026)
With Widescreen off the NPC stall does not happen. The 16:9 picture itself cannot change game logic, so the field-of-view data patch (007cad1c, rewritten every frame) is the suspect. Research switches (launcher): in ~/.p3fes-window-env, `PS2_PATCH=none` keeps the 16:9 picture but drops the patch; `PS2_PATCH=ADDR=VAL/EXPECT` replaces it. Reads of that address in the recompiled code were checked (gp-relative constants at 0x004138E0 feeding an effect state machine, and an unrelated struct field); nothing there explains the wait yet.

### Widescreen is NOT the trigger; the wait is the game's own (22 October 2026)
Corrects the entry above. A run with Widescreen OFF shows exactly the same keyframe timeline: placed at frame N, moved at N+12/N+14, then no write for 224 frames (N+14 -> N+238), then 35, 3, 34, 2, 2, then 222 frames again. A run with the 16:9 picture but no field-of-view patch still stalls. So the game logic waits the same time in every mode; the recompiled game is deterministic. Open questions: (a) is 0x0142300C Kenji himself or a shared scene value (five records, stride 0xC0, all with the same x), (b) what ends the two ~223-frame waits (two equal lengths of 3.7 s look like a fixed-length event: a sound or voice clip, a disc read, a timer).
tools/ps2run_wakelog_patch.py: PS2_WAKE_TRACE=30 logs every thread wait of 30+ frames with what ended it (code address and call chain). Use it together with PS2_STORE_WATCH to line the waits up with the keyframes.

### What ends the wait (22 October 2026, wake log)
PS2_WAKE_TRACE=30 with the store watch: the keyframe gap (frames 2669 -> 2893) is not ended by any thread wake-up. The only long waits released around it are thread 9 (sleep, woken by game thread 1 at ra 0x0010C744 at frames 2649 and 3075), i.e. game code waking game code. So the game's main thread simply keeps running and its own timeline decides to move Kenji 224 frames after placing him. Next: find the counter the timeline compares (tools/p3fes_counters.py: three F7 dumps, two during the wait at least 100 frames apart and one after).
