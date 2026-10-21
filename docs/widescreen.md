# Widescreen (PC window, experimental)

Settings → Widescreen · PC window → ON. Needs a PC window built after applying `ps2run_widescreen_patch.py`
(the installer applies it; for an existing Windows build apply it like the other runner patches, then rebuild).

## What it does
* **Display**: the picture is shown at 16:9 instead of 4:3 (`PS2_ASPECT=16:9`). The game still draws a 4:3-shaped image.
* **3D view**: one data value in the game's memory (the x field of view, `007cad1c`, 4:3 → 16:9) is rewritten every frame
  (`PS2_PATCH=007cad1c=3fe38e38/3faaaaab`). It is only written when the game holds the expected 4:3 value there.
  The runner logs `[widescreen] ...` lines to `~/.p3fes-window.log`: look there to see whether it was applied.

## What it cannot do (yet)
The community widescreen file for PCSX2 (`94A82AAA.pnach`) has about 200 lines. All but one change the game's **code**
(menu, HUD, portraits, fonts, FMV, plus new code written into empty memory). This project converts the game's code ahead
of time, so those cannot be written at run time. Expect the 3D world to be correct but menus, portraits and the HUD to be
stretched. Doing more means patching the boot file and redoing the long conversion, which is a separate project.
