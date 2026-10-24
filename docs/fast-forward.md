# Fast forward (PC window and browser)

**Removed in 0.37.** Turbo (Tab fast forward) was taken out of the project: `ps2run_turbo_patch.py` and `ps2web_turbo_patch.py` are gone and the installer no longer applies them. In the PC window it was already off by default because it froze the game for good around the classroom scene (Junpei, "aura around her"), even with every mod off, at unlimited speed, at 2x and with frame skipping removed. A build made before 0.37 still has the Tab key in the browser game until its source is put back (delete `~/ps2-web-recomp/.p3fes_applied`, run `git checkout -- .` there, then run Setup > GET THE TOOLS again and rebuild); the PC window ignores Tab unless `PS2_TURBO` is set. The plan below for stopping at choices and speeding up only dialogue is kept for later but nothing is started.

**Step 2, not started: stop at choices, and speed up only dialogue.** Needs the game's own state: a flag for "a message is
being shown" and one for "a choice menu is open". Those addresses are not known yet. Plan: add a runner switch that logs
a few chosen memory words each frame (`--watch addr,addr`), play through a line of dialogue, a choice and a plain scene, and
read which words change. Then turbo can turn itself off while a choice is open.

**Step 3, not started: the Log (backlog).** Needs the same kind of discovery, plus: where the game keeps the message text, how
it is encoded (the game uses its own character table), and which sound cue a line plays, if any. The window would keep the last
N lines with a speaker icon (no X) when a voice played and a speaker with an X when it did not, and replaying a line's voice.

## Finding the game's state (probe tools)
`ps2run_probe_patch.py` adds F7 (writes the game's memory to `ramdump_NNN_fFRAME.bin` in the folder ps2run.exe runs in, normally
`C:\p3fes\winbuild\build`) and `PS2_WATCH=addr,addr` (logs when those words change). `tools/p3fes_ramfind.py` then lists words
that are the same in every dump of one situation but differ between situations. Each dump is 32 MB: delete them when done, and
do not share them (they hold game data).
