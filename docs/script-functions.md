# Script functions (COMM numbers)

> Project progress: `██░░░░░░░░░░░░░░░░░░` 13% overall, see [docs/progress.md](progress.md) and [README](../README.md).

A script calls a game function with `COMM n`. The functions are a table of 502 records of 8 bytes starting at address 0x7B92B0 of the boot executable (record n = function address, then the number of values the function takes). This page lists the 213 numbers that scripts use, grouped by the source file the game's own strings name. Functions of one source file sit next to each other in the executable, so a function without a name of its own is listed with the nearest named file when it lies within 0x2000 bytes of one; that grouping is a guess. Numbers are decimal; `n(k)` means function n takes k values (second word of its record; confirmed: with these counts the scripts' stack code balances in all but 3 of 1,051,225 statements). Use counts are over the 510 scripts of an NTSC-U disc.

**Checked against the scripts' own text:** the value passed to function 0 is a message number of the script's own message data (36,314 of 36,338 calls with a constant value are inside the script's message list); the same holds for functions 3 (all 4,625 calls) and 38 (all 990). So 0 is very likely "show message n", and 3 and 38 are related message calls. Function 28 gets small numbers (0 to 5, a choice or window setting?) and 40 always gets 6. Functions 1 and 2 take no value and are called 13,631 and 20,595 times, mostly around messages (waiting for the window?). The result of a function is read afterwards with PUSHREG 0; for example `f001`'s first procedure calls field_215, compares the result with 1 and branches.

**Seen in a real scene** (an export of one script, checked by eye): a party-gathering routine loops over the party, calls function 1 (no values) before function 0 with a message number, function 2 (no values) after it, and function 28 with three values (a code, a value read from a result, and a slot number 0 to 5) between them, which looks like filling placeholders of the message that follows; the message text itself carries matching placeholder codes (`{F4 20 03 ...}`). So 0 shows a message, 1 and 2 probably open and close or end the window, and 28 sets a value for the message. Names found so far are kept in `tools/script_names.txt`; the listing and export commands use them.

**More names, from reading exported scripts** (guesses are marked with ? in `tools/script_names.txt`): function 12 is a wait (the value is a frame count: 1 inside wait loops, 30 between two messages), 7, 8 and 9 look like test, set and clear for a numbered flag (one script tests flag 0, then sets it and shows one message, or clears it and shows another; flag numbers are sums such as 1024 + 16, so they probably encode a block and an index), 3 shows a message with a choice, and 308 and 309 (named H_FRStatusDisp in the executable) show a status screen for one member or all. Together the named functions cover about 44% of all calls in scripts.

**From the first sample call sites:** functions 128 and 129 (no values; 8,781 and 16,262 calls) are compared with pairs such as (7, 7), (20, 4) and (5, 3), and 128 is once compared with 12, which looks like the calendar (month and day); function 138 (no values) is compared with 264, the number of floors in the tower, and stored by floor setup routines; function 118 takes (0, step, event number) with steps 1, 2, 4 and 5 seen; function 121 takes (on or off, object). These are guesses, marked with ? in `tools/script_names.txt`. In listings a function whose result is used once is now written where the result is used, e.g. `if (0 == flag_test(473))`.

**Operand and argument order (strongly supported by the data, not yet checked in the engine code).** Scripts seem to push right to left: the value on top of the stack is the first argument of a call and the left operand of an operator. Evidence: with the other order, loops update `x = 1 - x` and tests read `2 >= (a - b)`; with this order they read `x = x - 1` and `(a - b) >= 2`, and calls start with the object or index (`field_121(object, on or off)`, `field_118(event, step, 0)`, the object first in `field_137`). The listing and export commands use this order. Further checks: `date_in_range?` (132) reads (month, day, month, day) with this order, e.g. (4,20,6,11), while the other order would give impossible months such as 20; `message_set_var?(slot, value, kind)` counts slots 0..5 in the first position; `(items - index) >= 2` matches the two-items-per-message report (messages 13 and 14).

**More guesses from sample calls:** a save point runs `fade out, (wait), save menu (399, 400), fade in, (wait)`, so 14 and 13 are fades, 127 waits, and 399/400 are probably the save menu; a movie plays through 426/427 (the executable names 426 `H_SfdPlay`) and the name entry through 447/448 (`M_NameEntry`); 212 turns a party slot (0 to 3) into a character number; every field `init` procedure starts with `if (field_215() == 1)`.

The file names are strings the game itself contains; what each function does is not decided yet. Likely roles from the names: `itfMesManager.c` message windows, `scrComuCommand.c` the social link ("Comu") commands, `k_command.c` field commands, `scrCommonCommand.c` general script commands, `mt_evtCutin.c` cut-ins, `mt_evtMisc.c` event helpers.

| Source file (named in the executable) | Address range | Functions n(values) |
| --- | --- | --- |
| other / unlabelled | 0x10BE60-0x45EBA0 | 42(1), 43(0), 119(1), 145(2), 146(0), 147(0), 148(1), 166(0), 185(2), 188(1), 189(6), 190(0), 191(0), 295(1), 308(1), 309(1), 310(0), 324(1), 325(0), 334(1), 335(2), 336(2), 337(1), 338(2), 362(0), 363(0), 364(1), 365(3), 366(2), 367(2), 368(1), 379(1), 382(0), 394(1), 396(0), 399(0), 400(0), 415(4), 417(0), 418(1), 419(0), 420(0), 421(0), 422(1), 426(1), 427(0), 447(0), 448(0), 450(0), 451(0), 468(0), 471(0), 472(0), 480(0), 481(0), 486(0), 491(3), 494(0), 499(0), 500(0) |
| g_data.c | 0x16EA80-0x16EE90 | 133(2), 134(1), 209(0), 210(1), 211(1), 212(1), 213(1) |
| k_command.c | 0x1C2010-0x1C5EB0 | 13(1), 14(2), 33(4), 118(3), 120(1), 121(2), 122(0), 126(0), 127(0), 128(0), 129(0), 130(0), 131(0), 132(4), 135(4), 136(0), 137(5), 138(0), 192(1), 193(1), 194(1), 197(2), 201(1), 202(2), 204(2), 214(0), 215(0), 216(2), 217(2), 226(0), 229(0), 230(0), 231(0), 232(0), 233(1), 276(1), 277(2), 278(0), 279(2), 281(1), 282(2), 283(3), 284(2), 287(1), 288(1), 296(2), 304(0), 305(1), 311(1), 312(2), 313(2), 314(2), 315(2), 316(1), 339(2), 340(2), 341(2), 342(1), 357(2), 358(2), 359(2), 360(2), 361(0), 371(1), 372(0), 376(0), 377(1), 387(2), 389(1), 390(1), 395(2), 398(0), 401(4), 416(0), 428(2), 464(0), 465(1), 467(4), 469(1), 470(1), 473(0), 477(2), 482(0), 483(2), 484(0), 487(0), 488(0), 489(0), 490(1), 498(0), 501(2) |
| br_friend.c | 0x1FAEA0-0x1FAEA0 | 369(1) |
| scrCommonCommand.c | 0x35AEB0-0x35B400 | 7(1), 8(1), 9(1), 10(1), 11(0), 12(1), 18(1), 23(2), 24(1), 25(1) |
| scrComuCommand.c | 0x35F170-0x360D40 | 123(1), 124(1), 186(0), 207(2), 208(2), 218(1), 219(1), 220(1), 221(1), 222(0), 223(0), 224(1), 225(1), 234(2), 285(1), 290(2), 292(1), 293(1), 294(2), 297(0), 298(0), 331(0), 332(0), 333(0), 370(0), 381(1), 414(3), 424(1), 425(0), 495(1), 496(0), 497(3) |
| mt_evtMisc.c | 0x38D980-0x38D980 | 184(1) |
| mt_evtCutin.c | 0x3971A0-0x3973E0 | 182(7), 183(1) |
| itfMesManager.c | 0x3A2150-0x3A2C10 | 0(1), 1(0), 2(0), 3(1), 6(1), 28(3), 38(1), 40(2) |
| (no function in the table) | - | 31(2) |

Most used (uses over all scripts): 0(1) x43400, 7(1) x24181, 2(0) x20595, 8(1) x18130, 129(0) x16262, 1(0) x13631, 9(1) x10330, 121(2) x8843, 128(0) x8781, 138(0) x7523, 127(0) x7371, 118(3) x6503.
Other names found in the functions: H_SfdPlay (movie playback, 426/427), H_CampTradeDraw (324/325), H_FRStatusDisp (308/309), M_NameEntry (447/448), GameClearDraw (480/481), HikitugiDataProc (499/500), br_friend.c (369), g_data.c (210/211), "edsr draw" (468).

## Party loot report (334-338, 324, 325, 484)

Seen in AEGIS.BF/AMADA.BF `party_end_gather`, and in the member loops of ns004_010.bf and ns007_006.bf (`party_member?(i)` for i in 0..2):

- 334(member) returns how many items that member picked up; the script loops over them.
- Per entry the script sets three message values from 338, 335 (both kind 17) and 336 (kind 0, a number), two entries at a time (messages 13 and 14 show one or two "Obtained x." lines).
- After the report: message close, then 324(member), 325(), 337(member). All names are guesses (`loot_*?`); confirm in game.
- 484 takes no values and starts event procs (also `dungeon_upstair`): guessed `event_begin?`.

## More guesses from `context` (all unconfirmed)

- 132 `date_in_range?(m1, d1, m2, d2)`: arguments are month/day pairs, e.g. (4,20,6,11) and (5,23,6,7).
- 137 `object_anim?(object, animation, 0, 0, 1)`: followed by wait_frames(25) in the box-opening scripts.
- 182/183 `cutin_open?`/`cutin_close?`: wrap a message with a speaker cut-in.
- 40 `message_choice_set?(6, 1)`: sits between message_show(40) and the choice message_choice?(41).
- 201/202 `party_state?`/`party_state_set?(member[, value])`: compared against 0..3; meaning unknown.
- 277, 360: (id, value) pairs, meaning unknown (360 may be a sound call).

## Object and scene functions (all unconfirmed)

- 33 `scene_change?(a, b, c, d)` follows a fade-out and ends the script, e.g. (5,1,0,0) at the counter door, (5,3,0,0) at the Velvet Room door.
- Object pattern: `h = object_find?(5, id)` (313) or `object_find2?(6, id)` (357), then `o = object_create?(h, n)` (314) or `object_create2?(h, n)` (358), then `object_setup?(o, n)` (312), `object_anim?`, `object_show?(o, 1)`. `object_player?(0)` (311) gives the first object.
- 371 `party_ready?(i)` and 304/305 `party_count?`/`party_id?`: loops over the party.

Checked on 2,533 calls (all `field_313` and `field_357` calls in the exported scripts): in `field_357(a, n)` the first value is always either the number of the script's own field (1,107 calls) or -1 (1,012 calls), so it is "object n of field a" (-1 = this field). In `field_313(a, b)` the first value is 5 or 2 (kind) and the second an id (206, 157, 306, 33, 34, 201 ...); it is not a field number. Neither value matches the numbers at the end of `.FBN` file names in the same pack (5 of 217 and 24 of 1,012 by chance), so the FBN files are not looked up by these calls.
