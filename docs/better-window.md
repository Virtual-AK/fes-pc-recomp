# Getting a better picture and speed than VcXsrv

Written 19 October 2026 from reading the project source and our notes. **None of the steps below have been tested on a
real machine yet**; each says what to check so a tester can tell whether it worked.

## Why the PC window is slow under VcXsrv
The PC window draws with wgpu-native (Vulkan on Linux). Windows 10's old Linux layer (WSL1) cannot reach the graphics
card, so Vulkan falls back to a processor-only driver: our one recorded session ran 21 to 26 frames per second with the
processor fully busy. VcXsrv only shows the finished picture; it is not the main cost, so tuning it will not help much.
The fix is a way to reach the real graphics card.

## First machine checked (19 October 2026)
Windows 10 22H2 (build 19045), NVIDIA GeForce RTX 3060 Ti with a current driver, 63 GB memory, 12 threads, Chrome 155.
`chrome://gpu` says **WebGPU: Hardware accelerated** (Direct3D 12 backend on the RTX 3060 Ti). So Option A should run well here, and the
Windows version is new enough for Option B. Frame rates in the browser build are not measured yet.

## Option A: the browser build (works today, try first)
The browser game uses WebGPU in Chrome or Edge, which uses the real graphics card, and has a **Resolution** box in the
bottom bar (1x, 2x, 3x; the page reloads to apply it).
1. Open `chrome://gpu` and check the WebGPU line says "Hardware accelerated". If it says Disabled or Unavailable, update
   the graphics driver or try the other browser.
2. In the launcher, Settings > Display, choose Chrome (or Edge) and press Play with **Browser** selected.
3. Pick a Resolution; watch the frame rate shown at the bottom of the page.
Limits: saves stay inside that browser until shared saves are built (see saves-plan.md).

## Option B: WSL2 with WSLg (real graphics card for the PC window)
WSL2 can give Linux programs a window without VcXsrv (WSLg) and access to the graphics card through a Direct3D layer.
1. **Check what you have.** In PowerShell: `wsl -l -v` (VERSION 1 means the old layer) and `winver` (needs Windows 10
   version 21H2 or newer, or Windows 11). Virtualization must be on in the BIOS (Task Manager > Performance > CPU says
   "Virtualization: Enabled").
2. **Update** Windows and the graphics driver from the maker (NVIDIA, AMD or Intel; the driver must support WSL).
3. **Back up Ubuntu**: `wsl --export Ubuntu C:\p3fes\ubuntu-backup.tar` (it is large; the game files are inside).
4. **Update and convert**: `wsl --update`, then `wsl --set-version Ubuntu 2` (several minutes; your files and the build
   are kept).
5. **Check in Ubuntu:** `uname -r` should contain `microsoft-standard-WSL2`, and `ls /mnt/wslg` should exist.
6. **Check the graphics card is seen:** `sudo apt install -y mesa-vulkan-drivers vulkan-tools`, then
   `vulkaninfo --summary | grep deviceName`. A line naming your card (often "Microsoft Direct3D12 (...)") is good;
   only "llvmpipe" means no card access. If so, Ubuntu's Mesa may be too old: Ubuntu 24.04 is the safest.
7. Close VcXsrv. The launcher sees `/mnt/wslg` and starts the PC window without it. Compare the frame rate with before.
Risk: if step 6 only shows llvmpipe, the PC window will be no faster, and Option A is the way.

## Option C: a native Windows program (no WSL, no VcXsrv)
Best result (real drivers, fullscreen at any resolution, controllers) but not available: the project is built and tested
on Linux and macOS only. A Windows build needs wgpu-native for Windows, SDL2, replacing the Linux-only calls (`dl`,
`pthread`) and fixing paths. Not started; it is a project of its own, to be scoped before any promise is made.

## Option D: VcXsrv settings
Little gain. Keep "Native OpenGL" off as in windows-build.md, and use F11 for fullscreen.
Nothing here changes the processor-only drawing.

## Suggested order
Try A now. If you want the PC window, try B. Report the frame rate and the `vulkaninfo` line either way.

## WSL2 result on one PC (20 October 2026)
Ubuntu (resolute, Mesa 26.0.8) under WSL2 with WSLg and an RTX 3060 Ti: `/dev/dxg`, `libd3d12` and the NVIDIA driver are present, but Vulkan lists only llvmpipe (no `dzn_icd.json`; Ubuntu's `mesa-vulkan-drivers` has no Dozen). OpenGL picks llvmpipe by default, but `GALLIUM_DRIVER=d3d12 glxinfo -B` names the card. The launcher therefore sets `GALLIUM_DRIVER=d3d12` and `WGPU_BACKEND=gl` for the PC window under WSLg. Untested: whether the window build can draw through wgpu's OpenGL backend. To go back to Vulkan, put `P3F_RENDER=vulkan` in `~/.p3fes-window-env` (other `KEY=VALUE` lines there are passed to the window).
