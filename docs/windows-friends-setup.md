# PC window on Windows: setup for friends

The PC window (`ps2run.exe`, runs at 60 fps on a real graphics driver) is built on your own computer from your own disc. Nothing of the game is downloaded or shared: the translated game code is made from your disc by the Ubuntu install, and the programs recorded in step 3 are pieces of that same code.

**Status:** tested on one PC only (Windows 10 22H2, RTX 3060 Ti). The one-step script below has been checked for its Ubuntu half and its file handling, but not yet run start to finish on a clean PC. The first friend to try it is the test: send me the screen if it stops.

## What you need first
- Windows 10 or 11 with Ubuntu (WSL) and `p3fes_install.sh` finished once. See [install.md](install.md). The long build step in it makes the game code the PC window needs.
- About 8 GB free on `C:` for the build tools and the build, and an internet connection.
- Keep this repository folder as it is: the scripts sit in its `tools` folder.

## Step 1: one script
Double-click `tools\p3fes_win_setup.bat` (or run it in a Command Prompt). It does four things and skips any that are already done, so running it again is safe:
1. Installs Visual Studio Build Tools with clang and CMake (Windows asks for permission; about 3 GB, 10 to 20 minutes the first time).
2. Downloads SDL2 and wgpu-native into `C:\p3fes\winbuild`.
3. Prepares `C:\p3fes\winbuild` from your Ubuntu install (`p3fes_win_prepare.sh`): copies the source, applies `ps2run_windows_patch.py`, copies the generated game code.
4. Builds `C:\p3fes\winbuild\build\ps2run.exe` (5 to 10 minutes).

Then open the launcher and press Play; it starts the PC window by itself when `ps2run.exe` exists.

## Step 2 (optional but worth it): smooth play in every scene
Only some of the game's graphics programs (VU1) are compiled ahead of time. The rest run through a slower interpreter, which shows as frame dips (the classroom was about 38 fps before, 60 after).
1. Double-click `C:\p3fes\winbuild\p3fes_win_record.bat` and play through many different scenes: school, town, Tartarus, battles, menus, cut-scenes. Close the window.
2. In Ubuntu: `bash /mnt/c/p3fes/winbuild/p3fes_vu_compile.sh`
3. In the **x64 Native Tools Command Prompt for VS 2022**: `cd /d C:\p3fes\winbuild`, then `build_win.bat game`.

Repeat after playing new parts of the game. The recorded files stay on your computer and are never shared.

## If it stops
- *Build tools not installed:* if you declined the Windows permission prompt, run the script again. Otherwise install "Build Tools for Visual Studio 2022" by hand with "Desktop development with C++", "C++ Clang Compiler for Windows" and "C++ CMake tools".
- *"did not fit the copied source":* the Ubuntu install or the project has changed; send me the lines shown.
- *Build failed:* the script prints the last lines of `C:\p3fes\winbuild\build.log` or `configure.log`; send them.
