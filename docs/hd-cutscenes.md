# HD cutscenes

## What works now (0.55)
**Simply Better FMVs** (GameBanana mod 435297, English) replaces all 41 movies with cleaned-up, deinterlaced versions. Add its folder under Mods > File mods (the folder with `DATA` and `cheats` in it). Details, from the pack on a real disc:
- The 41 files have the same names as the disc's `DATA.CVM/SFD` files. The picture size is unchanged except for seven movies (see below): 34 are 640x368 and 7 are 640x448. What changes is the video quality: `GAME_START` goes from 2.9 to 7.3 Mbit/s, and the video is deinterlaced.
- Every file is bigger than the original (1.4 to 4.2 times, 3.1 GB against about 1.9 GB in all), so they are moved to the end of the image like any bigger file, and the game's file table is poked (`table_pokes`): all 41 files have exactly one table entry.
- The mod ships no subtitles of its own (the files are video and sound only); our `.srt` subtitles keep working on top.
- **Seven cutscenes without black bars:** P3CT002_00, P3CT008, P3CT019_01, P3CT029, P3CT030_01, P3CT030_02 and P3FCT006 are 640x368 in the mod and 640x448 on the disc. The mod's `LetterBoxBe-Gone` cheat changes two values per movie in the game's movie table (a flag, 5 to 6, and the expected picture height, 448 to 368). They are data, not code, so the launcher turns them into pokes (`p3fes_modmap.pnach_data_pokes`, `letterbox_pokes`) for any enabled file mod with a `cheats/*letterbox*.pnach`. Not tested in the game yet.
- Not used: the mod's other cheats (FMV widescreen, opening swap, credits fix with new staff-roll fonts) are PCSX2 code patches or need the staff roll fonts; the widescreen opening add-on (`P3CTOP.SFD`, 24 fps) is a separate optional movie.

## Where the movies go (the 4 GB limit)
The pack is 3.3 GB, 1.2 GB more than the movies on the disc. Placing all of it past the end of the image (as for any bigger file) made the PC window stall right after start-up with a black screen (log: the game's main thread spins after reading `I_MES_WIN01.SPR`). Tests, 27 October 2026: 20 movies (434 MB) placed below sector 2,097,152 of DATA.CVM start normally; the same movies with some of them above that sector give the black screen. So a file must end before sector 2^21 of its CVM (4 GB; `LIMIT_SECTORS`). The game most likely computes a file's position as sector x 2048 in 32 bits.
The layout now: the 41 old movies lie side by side (2.05 GB), so when they are all replaced their old places are one free area; `plan_moves` puts each new movie into the free areas (smallest first, best fit), then at the end of the image, and what does not end below the limit keeps the disc's copy. With the whole pack, 40 of 41 movies fit (tested on the real disc, 27 October 2026: the game starts normally and the opening cutscenes play) (maximum end sector 2,092,137 of 2,097,151); STAFF_ROLL_B keeps the original unless the staff rolls are made smaller (next section).

## Making the staff rolls fit
The three staff rolls (`STAFF_ROLL_A/B/F`) are 319, 319 and 307 MB in the pack: the picture is at 6.8 Mbit/s, the most the movie format carries, and the credits are mostly still, so most of it is padding. On the disc they are 186, 186 and 183 MB (about 3.65 Mbit/s). Re-encoded at the disc's rate with the same remux path as the other tests, all 41 movies fit under the 4 GB limit (checked 28 October 2026 on the real disc layout: nothing left out, furthest end sector 2,092,137 of 2,097,151).
```
ffmpeg -i STAFF_ROLL_B.SFD -an -c:v mpeg2video -g 12 -bf 0 -b:v 3650k -minrate 3650k -maxrate 3650k -bufsize 1835k -flags +cgop -sc_threshold 1000000000 -aspect 4:3 -f mpeg2video B.m2v
python3 p3fes_sfd.py remux STAFF_ROLL_B.SFD B.m2v -o NEW/STAFF_ROLL_B.SFD
```
Constant rate on purpose: a variable rate made the credits only 72 MB, and the movie then reaches the game much faster than the disc's own copy does. Result per roll: 173 to 180 MB, 10,939 pictures (10,551 for F) as in the source, audio byte for byte the same, picture 55 dB PSNR against the pack's version (47 dB at worst, frame by frame). Not yet watched in the game (the credits come at the end); the pack's originals are kept in `sbfmv-staffroll-orig` next to the launcher.

## Known limits
- Subtitles follow moved movies: the launcher writes `mods/active.movies` (NAME, old first sector, new first sector, new sector count) and rebuilds `movies.txt` when it changes.
- TO FIX LATER: the FES opening (cutscene clips spliced with gameplay from The Journey and The Answer) shows with parts of the picture cut off since Simply Better FMVs is in. Seen 27 October 2026 in the PC window. Not yet traced to a movie: candidates are `P3CTOP2` (movie table entry 35: flag 5, 640x448; the mod keeps it 640x448) and `P3FCT007` (entry 43: flag 5, height 368 although the mod's file is 640x368 and the cheat does not touch it). To find it: log which movie plays (subtitle clock), compare a frame of the original and the mod's file, then try the table values (flag 6 / height 0x170 or 0x1C0) for that entry with PS2_POKE.
- The seven movies without black bars need the movie table pokes (above); not tested in the game yet. Checked without the game (28 October 2026): the pokes turn exactly those seven table entries into flag 6 / height 368, the state the game's own table has for the 30 movies whose pictures are 368 high on the disc; every movie's picture height (disc and pack) matches its table entry.

## What does not work: a bigger picture
`p3fes_sfd.py remux` can put a new picture into a movie. A replaced picture of the original size (640x448) plays. A 1280x896 picture froze the game as soon as the movie started (PC window, 27 October 2026), with the same builder. The game decodes into buffers made for 640x448, so real HD movies need a different route:
1. Patch the game's movie setup to take bigger pictures (buffers, the strip drawing). Uncertain.
2. Let the PC window play the HD movie itself over the game's own 640 movie, which keeps playing underneath for timing, skipping and the subtitle clock (the subtitle window already follows the movie from the disc reads). Needs a video player in the runner; the HD movies would be ordinary video files kept outside the disc image. PC window only.

## The SFD format
See `docs/formats.md` and `python3 tools/p3fes_sfd.py info MOVIE.SFD`.
