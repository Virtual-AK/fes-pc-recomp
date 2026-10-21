# Plan: a native Windows PC window (no Ubuntu, no display layer)

Written 20 October 2026 from reading the runner source (ps2-web-recomp, the tested version with our patches, 23,000 lines of C++ outside `third_party`). **Nothing here has been built on Windows yet.** Why: on WSL1 (XLaunch) the PC window runs at about 25 fps, on WSL2 with WSLg about 15 fps, because Ubuntu has no Vulkan driver for the graphics card. A native Windows program uses the real Windows graphics driver through wgpu-native (Direct3D 12 or Vulkan).

## What the source looks like
Good news: the code is already close to portable. It uses standard C++ threads, `std::FILE`, SDL2 for the window, audio and controllers, and wgpu-native for drawing. The disc reader already has a Windows branch (`_fseeki64`). Only a handful of places are Linux-only.

## Changes needed (small)
| # | Where | Problem | Fix |
|---|---|---|---|
| 1 | `runtime/src/gs/queue.cpp` | Waits with Linux `futex` system calls | Use C++20 `std::atomic::wait` / `notify_one` (or `WaitOnAddress`) |
| 2 | `host/window.cpp` (`attach_gpu`) and `runtime/src/gs/gpu/gpu.cpp` (`attach_surface`) | Only X11 and Wayland windows can be handed to wgpu | Add a Windows case: SDL gives the `HWND`; wgpu has `WGPUSurfaceSourceWindowsHWND` |
| 3 | `host/window.cpp` (title-bar numbers) | `getrusage`, `/proc/self/statm`, `sysconf`, `<unistd.h>` | `GetProcessTimes` and `GetProcessMemoryInfo` behind `#ifdef _WIN32` |
| 4 | `host/window.cpp` (emulation thread) | A `std::thread` has a 1 MB stack on Windows (8 MB on Linux). The browser build asks for 16 MB, which suggests deep stacks | Start the emulation thread with a 16 MB stack (Windows thread API) |
| 5 | `CMakeLists.txt` | Links `dl pthread m` and a Linux `libwgpu_native.a`; `scripts/fetch_wgpu.sh` knows only Linux and macOS | Windows branch: wgpu-native Windows release plus its system libraries, SDL2 for Windows |
| 6 | `host/profile.cpp` | Linux-only profiler | Already excluded by CMake outside Linux |
| 7 | Launcher | Starts `ps2run` inside Ubuntu | Start the `.exe` instead; same shared memory card, key file and mod overlay options |

## Toolchain
- The generated game code uses `[[clang::musttail]]` and clang vector extensions, so it **needs clang** (not plain MSVC `cl`). Plan: LLVM clang for Windows, with Visual Studio Build Tools (Windows SDK and MSVC libraries, which the Windows wgpu library is built for), CMake, Ninja and SDL2.
- **No Windows recompiler needed.** The recompiler (`eerecomp`) already ran in Ubuntu. The Windows build compiles the existing `generated/*.cpp` folder (about 173 MB, made from the player's own disc) with `-DPS2_GENERATED=...`. That folder stays on the player's computer and is never uploaded.
- wgpu-native: the project pins v29.0.1.1. Needs the Windows release of that version. I have not checked the exact release file names or which system libraries it needs; that is the first thing to confirm.

## Steps, with what to check
1. **Install the tools** (clang, Build Tools, CMake, Ninja, SDL2, wgpu-native for Windows). Check: `clang --version`, `cmake --version`.
2. **Compile the runtime library only** (no game). Check: it builds, errors list the Linux-only spots (items 1, 3, 4).
3. **Make the code changes** (items 1 to 5) and build the game executable against the existing `generated` folder. Compile time is the unknown: the Linux build took about 10 minutes; Windows may be longer and need a lot of memory.
4. **First run**: open a window, draw the title screen. Check: the title bar fps, and Task Manager GPU 3D load well above 6%.
5. Sound, keyboard and controller, memory card, resume states. Then the launcher change (item 7) and the mod overlay.

## Estimate
About 3 to 5 working sessions of 1 to 2 hours each. A window that draws the title screen on the card is the first milestone, probably the end of session 2 or 3 if the wgpu library links without trouble. Smooth play with controls and saves comes after that.

## Main risks
- The wgpu-native Windows library may need different link flags than I expect (first thing to find out).
- The stack size (item 4) is a guess; a crash at the title screen would point at it.
- The generated code is large; the Windows compile may be slow or need a lot of RAM.
- The speed result is not guaranteed: the processor was also busy (about 500%) in the Linux runs, so some of the slowness may be the emulation itself and not only the drawing. A native build should fix the drawing part; we will not know how much until step 4.

## Result of the first build and run (20 October 2026)
Windows 10 22H2, RTX 3060 Ti, LLVM clang 19.1.5 (clang-cl) from Visual Studio 2022 Build Tools, CMake 3.31, Ninja 1.12, SDL2 2.32.2 (VC development package), wgpu-native v29.0.1.1 (`wgpu-windows-x86_64-msvc-release.zip`, linked through the DLL import library).
- Changes made: `Win32` window target (`system.hpp`, `gpu.hpp`, `gpu.cpp`, `window.cpp`), Windows versions of the title-bar CPU and memory readings, a 64 MB-reserved stack for the emulation thread, and a Windows branch in `CMakeLists.txt`. `queue.cpp` needed no change (it already had a portable fallback for the futex calls).
- Both builds succeeded on the first try: the runtime library, then `ps2run.exe` with the 319 generated source files (about 5 minutes).
- First run, from the Native Tools prompt, with the boot file copied out of the Ubuntu install and a throwaway memory card: the title screen and opening ran at 60 fps (about 25 under VcXsrv, about 15 under WSL2). A second, longer run (about 21 minutes, 77,714 frames, closed normally, no crash) went from the opening to the first battle: 60 fps everywhere except the classroom scenes (about 40 fps), the opening ceremony (about 35 to 40 fps at first) and the walks home (about 55 fps). The first battle ran at 60 fps. At a smooth moment the title bar read 60 fps, CPU 59%, GPU 22%, 367 MB. Saving worked. The cause of the dips is not known yet: the CPU and GPU readings during a dip are needed.
- Not yet done: sound and controller check, the launcher starting the .exe, keys and mod overlay options for the Windows build, a package that does not need Visual Studio.


## Launcher and repeatable setup
The launcher now starts the native window itself when `ps2run.exe` is in `C:\p3fes\winbuild\build` (tested by `tests/test_launcher_filemods.py`; the real start is for you to confirm). `tools/ps2run_windows_patch.py` applies the source changes to a fresh copy of the runner (tested: clean, already patched, wrong source) and `tools/build_win.bat` builds it. The one-step script for friends now exists (`p3fes_win_setup.bat`, `p3fes_win_prepare.sh`, `p3fes_win_record.bat`; see `windows-friends-setup.md`); it still needs a run on a clean PC. The cause of the classroom dips was found (see below).

## Why the classroom dips, and the fix (20 October 2026)
Profiles of each thread (patches 3 to 12, measurement only) showed the PC window is not limited by the graphics card or the main threads: every frame passes through the VU thread, and in the classroom that thread spent about 70% of its time in the VU1 interpreter (`run_fast`, `set_flags`, `lower`), because only the VU1 programs recorded during the first exploring run are compiled ahead of time. The browser build compiles the rest on the fly; the native runner interprets them. Fix: record the programs missing from the compiled set while playing (`set PS2_VU_RECORD=C:\p3fes\winbuild\vu1rec`), compile them with `tools/p3fes_vu_compile.sh` (runs `vurecomp`), rebuild with `build_win.bat game`. The same recorded programs help the Ubuntu native build after it is rebuilt.

**Result (20 October 2026):** after recording and compiling 33 more VU1 programs (89 recorded, 475 with jump targets) and rebuilding, the classroom runs at 60 fps (was about 38) and the walk home at 60 (was about 52), with CPU use falling from 140% to 61-100%. The earlier dips in the opening ceremony were not rechecked yet. Patches 2 to 12 (now in `tools/windows-diagnostics/`, see `windows-diagnostics.md`) were measurement only and can be left out of a friend's build; only `ps2run_windows_patch.py` (and optionally patch 2 and 7) plus the VU1 recording step matter. Still to do: recording a fuller set of programs across the whole game before sharing the recipe, (the one-step build script for friends is written, see `windows-friends-setup.md`).

**Cut-in portraits came back (20 October 2026).** The newly compiled VU1 programs showed the old half-drawn portraits: the branch fix (parts 1 and 2) covers the interpreter and the browser compiler, but not `vurecomp`, which writes the ahead-of-time code. `ps2recomp_vubranch_patch.py` (part 3) fixes it; `p3fes_vu_compile.sh` applies it when the patch file sits next to the script, rebuilds `vurecomp`, regenerates all recorded programs and copies them to the Windows build; then `build_win.bat game`. Tested on a synthetic program (ISUBIU vi5 followed by IBEQ vi5,vi2): generated code now saves vi5 and vi2 first and the branch compares the saved copies.
