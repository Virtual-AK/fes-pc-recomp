# Dialogue Log (backlog): plan

**Status (20 Oct): built and tested by the maintainers.** Launcher > LOG lists every line with speaker and icon, and clicking a speaker icon replays the voice. The sections below are the research notes in the order they happened; later sections correct earlier ones. Log key inside the game window: TAB (ps2run_logkey_patch.py, 24 Oct, untested in game). Open: more speaker names.

Goal: a window that lists the last lines of dialogue, each with a speaker icon (voiced) or a crossed speaker (not voiced), and
lets you replay the voice. Needs three things from the running game:

1. **The text of each line as it is shown.** Where the game keeps the line, and how it is encoded (it may use its own table).
   Step now: press F7 (ps2run_probe_patch.py) while a line is on screen, then
   `python3 tools/p3fes_ramgrep.py ramdump_NNN_fFRAME.bin "a phrase from the line"`. The tool finds the phrase whatever the
   encoding. Send me the hit lines (addresses and the bytes around them), not the dump.
2. **When a new line starts.** A memory word that changes (a pointer, a counter) at each line: found with `PS2_WATCH` once the
   text address is known.
3. **Whether the line has a voice.** Probably visible as a read of a voice file from the disc, or a sound command. Plan: log
   the disc reads (file names) with the frame number while dialogue plays, and match them to lines.

Then the runner writes a log file of lines (text, voice file or none) and the launcher or a key in the window shows it.

## Findings so far (one memory dump, dorm lobby, 20 Oct)
* Text is plain ASCII in memory, inside whole message scripts that stay loaded. A script is a table of blocks named `MSG_000`, `MSG_001`, ...
  (other scripts use names like `LOUNGE_TV_NEWS_0122`). Each block has a small header (type, speaker number, pointers to each page, size).
* A page of dialogue starts with the bytes `f2 08 ff ff f1 3f` and ends with `f1 04`; a line break inside a page is `0a`.
  The speaker is a code near the start (`f5 1f NN 01`, NN is the speaker number).
* Voiced pages carry `f2 48 NN 01` before the text and `f2 47 0b 01` after it; NN counts up through the script. TV news pages have
  neither. Working guess: `f2 48 NN` starts voice clip NN, so "has `f2 48`" = voiced. To confirm with a voiced and an unvoiced line.
* Not found yet: the variable that says which page is on screen now (no word in memory points at the page). Plan: two dumps one
  line apart and compare them (`p3fes_ramfind.py` with the situations "line A" and "line B", several dumps each helps).

## Correction after more dumps
The `f2 48 NN 01` code also appears in an unvoiced narration block ("You hear something..."), so it is NOT a voice marker. Voice
has to be found another way: `ps2run_disclog_patch.py` + `PS2_LOG_DISC=1` (put that line in `~/.p3fes-window-env`) prints every
disc read with its frame number into `~/.p3fes-window.log`. Play one voiced and one unvoiced line and compare what was read.

## Voiced vs unvoiced test (20 Oct, Yukari unvoiced f2689, Shuji voiced f8929)
* The unvoiced Yukari page (`Oh! There you are!`) has the speaker code `f5 1f 03 01 02 01 03 01 02 01` and NO `f2 48`.
  The voiced Shuji page (`Ah, there you are.`) has `f5 1f 0c 01 0b 01 02 01 02 01 f2 48 02 01`, text, `f2 47 0b 01`.
  Every voiced cutscene checked (Mitsuru, Shuji, the dorm introductions) has `f2 48 NN 01` on every spoken page, NN rising through the scene.
  So `f2 48` is a strong voiced sign. The earlier counter-example (narration "You hear something") is probably a page that carries a clip
  number but has no clip; to be handled by ignoring pages whose speaker is the narrator.
* (superseded below) Disc reads: before the voiced line there is a 146-sector read of DATA.CVM at sector 666437 (a whole scene voice pack, loaded once at
  the start of the scene) and small reads at 771825 / 771840. Nothing like that before the unvoiced line. So the voice is probably one
  pack per scene and `NN` picks the clip inside it.
* `p3fes_cvmmap.py <iso> disclog.txt --skip-bgm` names the files inside DATA.CVM for those sectors (needs the disc image).

## Voice file found (cvmmap output, 20 Oct)
* Voice lives in `SOUND/V<event>001.AFS` inside DATA.CVM (one archive per event; the Shuji scene is `V129001.AFS`, event E120/E129_001).
  Boot reads the 1-sector headers of V450001/V451001/V452001...; a scene reads its header (1 sector, frame 8517) and then each clip
  (9 sectors at sector 771840, frame 8835) shortly before the voiced line shows (F7 at 8929).
* The 146-sector read at 666437 is `BUSTUP/I_B_11A1.BIN` (portrait), not voice. The unvoiced line has no V*.AFS read before it.
* Plan: runner logs every V*.AFS read with the current frame; a line is voiced when such a read lands just before it appears. Replay:
  read the clip from the AFS (sector + length are in the log) and decode it (format still to identify).

## Page counter found (20 Oct, three consecutive Shuji lines)
* The game keeps a message-window record (pattern `00000290 00000a48 ... 00000360 00000b18`, array inside 0x1060000..0x1070000).
  In the record: +0x18 = pointer to the script block being read, +0x28 low 16 bits = number of the page on screen (0, 1, 2 for the three lines).
  The pages are the pointers to `f2 08 ff ff` just after the block name. Pages without a speaker code use the speaker of an earlier page in the block.
* Speaker byte in `f5 1f NN`: 03 Yukari, 05 Mitsuru, 06 Junpei, 08 Akihiko, 0c Shuji (more to collect). Voice clip = `f2 48 NN`.
* `ps2run_dialoglog_patch.py` + `PS2_DIALOG_LOG=1` writes `dialog_log.tsv` (frame, speaker, clip, block, page, text). Next: a viewer, speaker names, voice replay.

## First viewer (20 Oct)
* Voiced = page has a clip number AND a speaker (narration pages carry a clip number but are unvoiced; checked in a real log).
* The launcher starts the PC window with `PS2_DIALOG_LOG=C:\p3fes\saves\dialog_log.tsv` (a line in `~/.p3fes-window-env` wins) and has a LOG screen
  on Home that reads it every 2 seconds: speaker name, text, speaker icon (crossed = no voice), a heading per play session, CLEAR LOG.
* Speaker numbers known: 3 Yukari, 5 Mitsuru, 6 Junpei, 8 Akihiko, 12 Shuji. Others show as "Speaker N" until a log shows who they are.
* Still open: voice replay (needs the voice file format).

## Voice replay (20 Oct)
* `p3fes_afsinfo.py` on SOUND/V129001.AFS: 68 entries, every one standard CRI ADX (header `80 00 00 24 03 12 04 01`, 24 kHz mono, 4-bit,
  18-byte frames). Entry #1 starts at disc sector 771840 = the 9-sector read seen before voice clip 2, so clip number N = entry N-1.
* The dialog log has a 7th column: the last 48 DATA.CVM reads (sector:count). The launcher maps them to the archive they fall in
  (it reads the file table of your own disc) and the LOG screen plays the clip: `/api/voice?afs=V129001&n=2` decodes the ADX to WAV on demand.
  Nothing from the disc is stored; the clip is decoded in memory when you click the speaker icon.
* The disc reads come from `ps2run_dialoglog_patch.py` (now also patches disc.cpp/disc.hpp); the PC window needs one more rebuild.

## Log key (24 Oct)
* `ps2run_logkey_patch.py`: the dialogue log code also keeps the last 40 pages in memory; TAB in the PC window opens a borderless always-on-top second SDL window over the bottom of the game with the last lines (own 8x16 bitmap font, no extra libraries). A second window works whichever way the game itself is drawn (WebGPU or SDL). It takes the keyboard focus, so the game gets no keys while it is open. Voice replay stays in the launcher. Needs more speaker names (only 3, 5, 6, 8, 12 known).
* (24 Oct) The record moved: in a later dump it sits at 0x1169484, not in 0x1060000..0x1070000. The recorder now scans all memory for the pattern (every 30 frames until found, then every 900), done by ps2run_logkey_patch.py on top of the dialogue log patch.
