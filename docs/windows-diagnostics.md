# Windows window: how the frame-rate dips were found

The native Windows PC window dipped to 35 to 50 fps in busy scenes (classroom, opening ceremony, walks home) while the graphics card was idle. The patches in `tools/windows-diagnostics/` were written to find the cause. **None of them is needed to build or play.** The fix was the VU1 recording step (see `windows-native-plan.md`). Only `tools/ps2run_windows_patch.py`, `tools/build_win.bat`, `tools/ps2recomp_vubranch_patch.py` and `tools/p3fes_vu_compile.sh` matter for a working build.

## What each step showed
| Step | What it added | What it showed |
|---|---|---|
| 2 | title bar `threads 99/41/12%` (now off unless `PS2_THREADS=1` after step 7) | one thread looked pinned near 100% |
| 3 to 6, 12 | sampling profiler (`PS2_PROFILE_WIN=1`, `render`, `busy`, `vu`), `ps2run.map`, `winprof_resolve.py` | game thread and graphics thread were mostly waiting; the VU thread spent about 70% of its time in the VU1 interpreter |
| 7 | graphics thread waits with `WaitOnAddress` instead of 1 ms sleeps | no change in fps, kept as harmless |
| 8, 11 | `PS2_STAGES=1` timing lines | both threads waited on each other; queued pictures waited about 73 ms |
| 9, 10 | `PS2_SPIN_WAIT=1` | wake-up delay was not the cause |

## Lesson
The Windows CPU percentages were misleading (Windows counts short, frequent wake-ups as busy time). Measuring where each thread waited, then profiling the thread everything passed through, found the cause. The cause: only the VU1 programs seen during the first install run are compiled ahead of time; the native runner interprets the rest (the browser build compiles them on the fly).

## Using them again
Apply in order from the `ps2-web-recomp` folder (step 1 is `tools/ps2run_windows_patch.py`; steps 3 to 6 and 12 need step 3; 7 needs 2; 9 needs 7; 10 needs 9). `winprof_resolve.py ps2run.map prof_win.txt` lists the busiest functions.
