# Install (the simple way)

For Windows 10 or 11. You need your own Persona 3 FES (USA) disc image (`.iso`), about 30 GB of free space on `C:` (20 GB for the game, 8 GB for the Windows build tools), an internet connection, and Chrome or Edge. Most of the time is waiting for installs and builds.

The path has five parts, in this order. Each one is safe to run again if it stops: finished steps are skipped.

1. Ubuntu on Windows (once)
2. The `C:\p3fes` folder, your disc and these tools
3. Build the game in Ubuntu (this also gives you the browser version)
4. Build the native Windows PC window (the 60 fps one)
5. Start the launcher

If you only want the browser version you can stop after part 3 and use the Play section below, but the PC window is the better way to play, so most people should do part 4.

## 1. Ubuntu on Windows (once)
Open **PowerShell as administrator** and run `wsl --install -d Ubuntu`. Restart when asked, then open **Ubuntu** from the Start menu and pick a user name and password.

## 2. The folder, your disc and these tools
1. In Windows, create the folder `C:\p3fes` yourself (File Explorer, `C:\`, New, Folder, named exactly `p3fes`). Nothing creates it for you.
2. Put your disc image (`.iso`, the original, not a modded one) in `C:\p3fes`.
3. Download this repository (green **Code** button, **Download ZIP**) and unzip it into `C:\p3fes`: right-click the zip, **Extract All**, destination `C:\p3fes` (do not just open the zip).
4. Find where the install script ended up. The folder name depends on the zip (`fes-pc-recomp-main` from GitHub, `ps2-native-tools` or `ps2-native-tools-0.57` from a release zip), and Windows often unzips into a folder inside a folder of the same name, so do not guess. In Ubuntu run:
```
find /mnt/c/p3fes -maxdepth 4 -name p3fes_install.sh
```
It prints the exact path, for example `/mnt/c/p3fes/fes-pc-recomp-main/fes-pc-recomp-main/tools/p3fes_install.sh`. Keep it for part 3. Type the command as shown: a plain hyphen, and a space before `-name`.
- If it prints nothing, check `ls /mnt/c/p3fes`. "No such file or directory" means the folder from step 1 does not exist; an empty list means the unzip did not go there.

## 3. Build the game in Ubuntu
In the Ubuntu window, run the path that `find` printed with `bash` in front:
```
bash /mnt/c/p3fes/<folders>/tools/p3fes_install.sh
```
It installs what it needs (asks for your Ubuntu password once), downloads the open-source PS2 Web Recomp project at the version these tools were tested with, applies all our patches, finds your disc in `C:\p3fes`, and builds the game. It takes about 10 minutes or more (longer on older computers) and sits quiet for stretches: leave the window open. It ends with `== Done`. If it stops, run the same command again; finished steps are skipped. A line starting `STOPPED:` says which step failed: send the last 30 lines to the people helping you.

If your disc is somewhere else, add its path at the end of the command.

## 4. Build the native Windows PC window (60 fps)
Without this part the launcher can only start a slower copy of the PC window that runs through Ubuntu (about 15 frames per second). The browser version is not affected.

1. In Windows, open the `tools` folder of the repository (the same folder that holds `p3fes_install.sh`) and double-click **`p3fes_win_setup.bat`**. Or, in a Command Prompt, `cd` into that folder and run `p3fes_win_setup.bat` so the window stays open if something goes wrong.
2. It runs four steps, printed as `== [1/4]` to `== [4/4]`, and skips any that are already done:
   1. Installs Visual Studio Build Tools with clang and CMake. **Windows asks for permission: say yes.** About 3 GB, 10 to 20 minutes the first time.
   2. Downloads SDL2 and wgpu-native into `C:\p3fes\winbuild`.
   3. Prepares `C:\p3fes\winbuild` from your Ubuntu install.
   4. Builds `ps2run.exe` (5 to 10 minutes).
3. It ends with `BUILD OK` and `Done: C:\p3fes\winbuild\build\ps2run.exe`, then "Press any key". That message appears whether it worked or not, so check the lines above it. To be sure: `dir C:\p3fes\winbuild\build\ps2run.exe` must list the file.
4. If it stops, the line starting `STOPPED:` says why. Run it again after fixing that. The last lines of `C:\p3fes\winbuild\build.log` or `configure.log` help the people helping you.

You need about 8 GB free on `C:` for this part. Some graphics programs run slowly until you record and compile them (smooth play in every scene): that is optional, see [windows-friends-setup.md](windows-friends-setup.md), step 2.

## 5. Start the launcher
Double-click `tools\launcher\launch.bat` (in the same repository folder). A small console window stays open while the launcher runs; closing the launcher window stops it. Choose the PC window as the version to play (the `Q` and `E` keys switch between Browser and PC window), then press Play. The launcher starts the 60 fps window by itself when `ps2run.exe` exists. See [launcher.md](launcher.md).

Mods are set up under Mods > Essential Mods. Each one downloads from its GameBanana page. If a download fails, get the file from the mod's page in your browser: for a patch mod press **FOLDER** and put its `.pnach` files in, for a file mod add it under FILE MODS. Then press SET UP ESSENTIAL MODS.

## Play without the launcher (browser version)
```
~/ps2-web-recomp/play.sh
```
Then open `http://localhost:8620/` in Chrome or Edge. Stop with Ctrl+C in the Ubuntu window. Keys, controller, backups and autosave are in the buttons at the top of the page (see [controls.md](controls.md) and [autosave.md](autosave.md)).

## If something goes wrong
| What you see | What it means |
|---|---|
| `bash: ...p3fes_install.sh: No such file or directory` | The path is wrong. Use the exact path from the `find` command in part 2. |
| `ls: cannot access '/mnt/c/p3fes'` | `C:\p3fes` does not exist. Create it (part 2, step 1). |
| `find` prints nothing, or hangs | A typo (a long dash instead of `-`, a missing space) or a search over the whole drive. Use `find /mnt/c/p3fes -maxdepth 4 -name p3fes_install.sh`. |
| `STOPPED: ... did not fit the downloaded project` | One of our patches does not match the downloaded project. Send the screen to the people helping you. |
| `p3fes_win_setup.bat` closes at once | Run it from a Command Prompt so you can read it. |
| The PC window runs at about 15 fps | `ps2run.exe` is missing: part 4 did not finish. Check with `dir C:\p3fes\winbuild\build\ps2run.exe`. |
| An Essential Mod says "HTTP 404" | Use the manual route in part 5. |

## Notes
- Nothing from the game is downloaded or included. Everything the installer makes stays on your computer.
- To check only that the patches fit (no build): add `--patches-only`.
- The installer pins the project version (16 October 2026). A newer version of the project may need updated patches.
- If something fails, copy the last 30 lines of the window to the people helping you. A message starting `STOPPED:` says which step.
- The older step-by-step guide is [windows-build.md](windows-build.md); it also covers opening the PC game window.
- On older Ubuntu-on-Windows (WSL1) the browser compiler's bundled Node does not run; the installer then downloads Node 20 into `~/node20` and uses that.
- The installer was first tested on 18 October 2026 on a fresh copy. That test found three missing pieces (Node 20, the save-state patches, the PATH3 picture fix), all now included.
- Testing the install on a clean machine? Use the checklist in [tester-sheet.md](tester-sheet.md).
