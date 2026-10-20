# Install (the simple way)

For Windows 10 or 11 with Ubuntu (WSL), or plain Linux. You need your own Persona 3 FES (USA) disc image, about 20 GB of free space, and Chrome or Edge.

**Easiest way:** after the Ubuntu step below, unzip the repository into `C:\p3fes` and double-click `tools\launcher\launch.bat`. Press SET UP and follow the screens (see [launcher.md](launcher.md)). The commands below do the same thing by hand.

## Once: set up Ubuntu on Windows
1. Open **PowerShell as administrator** and run `wsl --install -d Ubuntu`. Restart when asked, then open **Ubuntu** from the Start menu and pick a user name and password.
2. Put your disc image (`.iso`, the original, not a modded one) in the folder `C:\p3fes`.
3. Download this repository (green **Code** button, **Download ZIP**) and unzip it into `C:\p3fes` so that `C:\p3fes\ps2-native-tools\tools\p3fes_install.sh` exists. Windows often unzips into a folder inside a folder of the same name, so the script may be at `C:\p3fes\ps2-native-tools\ps2-native-tools\tools\p3fes_install.sh`. If the command below says "No such file", run `find /mnt/c -name p3fes_install.sh` in Ubuntu to see where it is, and use that path.

## Install the game
In the Ubuntu window:
```
bash /mnt/c/p3fes/ps2-native-tools/tools/p3fes_install.sh
```
It installs what it needs (asks for your Ubuntu password once), downloads the open-source PS2 Web Recomp project at the version these tools were tested with, applies all our patches (26, including the fix for the garbled title and floor pictures), finds your disc in `C:\p3fes`, and builds the game. The first build takes about 10 minutes on a recent laptop and longer on older computers, and it sits quiet for stretches: leave the window open. If it stops, run the same command again; finished steps are skipped.

If your disc is somewhere else, add its path at the end of the command.

## Play
```
~/ps2-web-recomp/play.sh
```
Then open `http://localhost:8620/` in Chrome or Edge. Stop with Ctrl+C in the Ubuntu window. Keys, controller, backups and autosave are in the buttons at the top of the page (see [controls.md](controls.md) and [autosave.md](autosave.md)).

## Notes
- Nothing from the game is downloaded or included. Everything the installer makes stays on your computer.
- To check only that the patches fit (no build): add `--patches-only`.
- The installer pins the project version (16 October 2026). A newer version of the project may need updated patches.
- If something fails, copy the last 30 lines of the window to the people helping you. A message starting `STOPPED:` says which step.
- The older step-by-step guide is [windows-build.md](windows-build.md); it also covers opening the PC game window.
- On older Ubuntu-on-Windows (WSL1) the browser compiler's bundled Node does not run; the installer then downloads Node 20 into `~/node20` and uses that.
- The installer was first tested on 18 October 2026 on a fresh copy. That test found three missing pieces (Node 20, the save-state patches, the PATH3 picture fix), all now included.
- Testing the install on a clean machine? Use the checklist in [tester-sheet.md](tester-sheet.md).
