# Fast forward (PC window and browser)

**Browser (0.26):** Tab in the game page does the same (`ps2web_turbo_patch.py`, needs `ps2run_turbo_patch.py` first; the installer applies both). A TURBO badge shows at the top right.

**Step 1, done:** Tab in the game window turns turbo on, Tab again turns it off (`ps2run_turbo_patch.py`; the installer applies it,
for an existing Windows build apply it like the other runner patches and rebuild). While on, the frame limiter is off, sound is
muted and the title bar shows [TURBO]. It speeds up everything, not only dialogue.

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

## Status of PC-window Turbo (0.29)
Tab-Turbo in the PC window is switched off by default: with it on, the game froze for good around the classroom scene (Junpei, "aura around her") even with every mod off, at unlimited speed, at 2x and with frame skipping removed. The code is still there; set the environment variable `PS2_TURBO=1` to switch Tab back on while we look for the cause. Browser Turbo is unchanged.
