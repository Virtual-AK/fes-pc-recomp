# Widescreen (PC window and browser)

Settings → Widescreen → ON. Works in the PC window and the browser game. The 3D view and the picture need `ps2run_widescreen_patch.py` (and `ps2run_widescreen_web_patch.py` for the browser; the installer applies both); the menus, HUD, portraits and Social Link screens come from the community patch parts below, which need the essential mods build (Mods → BUILD, then `p3fes_win_mod.bat` for the PC window).

## What it does
* **Display**: the picture is shown at 16:9 instead of 4:3 (`PS2_ASPECT=16:9`). The game still draws a 4:3-shaped image.
* **3D view**: one data value in the game's memory (the x field of view, `007cad1c`, 4:3 → 16:9) is rewritten every frame
  (`PS2_PATCH=007cad1c=3fe38e38/3faaaaab`). It is only written when the game holds the expected 4:3 value there.
  The runner logs `[widescreen] ...` lines to `~/.p3fes-window.log`: look there to see whether it was applied.

## Menus, portraits and the HUD (community patch, not tested in every screen yet)
The community widescreen file for PCSX2 (`94A82AAA.pnach`, about 184 patches) changes the game's **code**. Our mod build can bake code
patches in (see docs/mods.md), so the file is split into part files in `packed\widescreen` (`ws1_core` to `ws11_zoom`, one per
section of the file, plus `ws3a_clock`, `ws3b_menuport` and `ws3c_zoom`, the three hand-converted routines). The tag at the start of the file name picks the part (`ws1_`, not `ws1`, so `ws10_` is not taken by `ws1`). They are hidden code mods (switches 7 to 13) with no switch of their own: they are on when Settings > Widescreen
is on. BUILD in Mods, then `p3fes_win_mod.bat`.
* The data line for the 3D field of view (`007cad1c`) is left out of the build (`skip_addrs`): the PC window sets it itself.
* **Conditional codes.** PCSX2 can apply a patch only while a game value has a given state (`e0020000,extended,107cdf48`, "if the halfword at
  007cdf48 is not zero, apply the next 2 lines"). `p3fes_pnach_apply.py` skips those lines, which made the patches after them apply all the
  time (the first test showed a stray orange bar in the Command menu). `ws3_detect.pnach` is the hand-converted version: three hooks
  (`004aa460`, `00112b8c`, `004aa444`) jump to small routines in new memory (`000c0800`, `000c0840`, `000c0880`) that read the same game
  values (007cdf48 in-game menu open, 007cded4 scene changing) and choose the same result at run time.
* `ws5_slink` is split into three: `ws5_slink` (X-position values inside the Social Link screen code), `ws5a_hook` (hook at 00114390: width of the 2D characters and cards, routine at 005a1d68) and `ws5e_cards2` (hook at 00115148: width of the Cards #2, routine at 000c00b0). The two hooks sit in shared sprite routines, so they are the suspects for the Tartarus entrance screen. Test result (23 October 2026): `ws5,ws5a` fixes the Social Link screen (card and character right) but brings the Tartarus entrance bug back, because the hook narrows every quad of the generic quad routine at 001140d0, which also draws that screen. `ws5a_hook` is therefore changed: its routine (at 000c0900) reads the caller's return address saved at 0x90(sp) and narrows only for callers in 00130000-0013C000 (the Social Link code). Tested with the caller check: Social Link screen and Tartarus entrance both correct, so all three are on by default.
* `ws3a_clock` and `ws3c_zoom` stay off for good: with both off the clock, popup portraits, fades and the circle transition all look right (tested 23 October 2026), and each of them breaks something when on (ws3a squeezes the fade overlay to 3/4 of the width, ws3c zooms the Dark Hour clock).
* Off by default: `ws3a_clock` (the dark overlay of fades and the circle transition only covers 4:3 of the width), `ws3c_zoom` (zooms the Dark Hour clock), `ws7_title` (it shades the right side of the title screen) and `ws8_font` (spacing errors around names and items). `P3F_WS_ON=ws3a,ws3c` switches them on.
* Research: a line `P3F_WS_OFF=ws2,ws5` in `~/.p3fes-window-env` leaves those parts off without a rebuild (remove it when done).
* Known limit from the file itself: its font patch (`ws8_font`) causes spacing errors around names and items ("Obtained  Imitation Katana  !"); it is off by default. The first full test also showed that the NPC stall (Kenji, Junpei, Adachi) was gone with these parts on; `P3F_WS_OFF` found it: it is `ws11_zoom` (its narrower field of view); see known-issues.md.

## Known problems (this PC window, widescreen on)
* Thin lines at the edges of text boxes and in day transitions. They also appear with Widescreen OFF, so they are a general renderer artifact, not a widescreen bug Cause found: at 2x/3x resolution the two triangles of a text quad both rejected samples lying exactly on their shared diagonal (float rounding), leaving a hairline. `ps2gpu_edgetie_patch.py` fixes the tie with the top-left rule (needs the graphics-code rebuild). Confirmed fixed in the PC window (23 October 2026).
* Clock zoom in the Dark Hour transition and a missing piece on the Tartarus entrance screen come from one of `ws3a`, `ws4`, `ws5` (being narrowed down).
