# Building and first-running the port on Windows

Goal (the "first build milestone" in [phase1-summary.md](phase1-summary.md)): translate our game, run it, and see how far it gets, using the existing open-source PS2 Web Recomp project (MIT) with your own disc image.

**Why WSL2:** that project's scripts are written for Linux (and macOS); they do not run in plain Windows. Windows 10/11 can run Linux inside it ("WSL2") and the finished browser build is then opened in Chrome or Edge on Windows, where WebGPU works. A plain-Windows build of the native runner is untested and not part of this plan.

**What you need:** Windows 10 (2004 or later) or 11, about 20 GB free disk space, 16 GB RAM recommended, an up-to-date Chrome or Edge, and `Shin Megami Tensei - Persona 3 FES (USA).iso` (the original, never `modded.iso`).

**Rules:** everything generated (translated code, builds, screenshots, logs with game text) stays on your computer. Never put the `ps2-web-recomp` folder, `generated`, `games` or `build` into our GitHub repository. Only short lists of names and numbers (below) are sent back.

## Step 1: install Linux inside Windows (once)
1. Open **PowerShell as administrator** and run: `wsl --install -d Ubuntu`
2. Restart when asked, open **Ubuntu** from the Start menu and choose a user name and password.
3. In the Ubuntu window install the tools:
   `sudo apt update && sudo apt install -y git cmake ninja-build clang python3 p7zip-full libsdl2-dev curl unzip build-essential mesa-vulkan-drivers vulkan-tools`
   (`mesa-vulkan-drivers` gives a software graphics driver the game's test runs may need inside WSL.)

## Step 2: get the project and your disc (once)
1. `cd ~ && git clone https://github.com/snuri00/ps2-web-recomp.git && cd ps2-web-recomp`
2. Copy your disc image into Linux's own disk (much faster than reading it from Windows):
   `cp "/mnt/c/p3fes/Shin Megami Tensei - Persona 3 FES (USA).iso" ~/p3fes.iso`
   (`C:\p3fes` appears as `/mnt/c/p3fes`. The copy needs about 4.5 GB.)

## Step 3: a quick test run without playing (about 10 minutes)
`scripts/port.sh p3fes ~/p3fes.iso --no-explore --native-only`

This sets up the tools, translates the executable (we already know this works: it took 1.7 seconds on our side) and compiles it. Expect a long compile (297 pieces); it is normal for it to sit quietly. If it stops with an error, send me the **last 30 lines** shown.

## Step 4: the real run
`scripts/port.sh p3fes ~/p3fes.iso`

This also installs the browser tooling the first time (it downloads a few hundred MB), then plays the game by itself in several rounds to find code the translation missed, and finally builds the browser page. It can take an hour or more. Leave it running. Each round prints one line like `round 1: <reason it stopped>, N new entry points`.

## Step 5: what to send back
Send these, as text (copy from the window or paste into a file). They contain names and numbers only:
1. All the `round ...` lines and the last 30 lines the script printed.
2. The summary of what the game asked for that was missing:
   `grep -hE "^\[(sys|iop|ee)\]" games/p3fes/explore.log | sort | uniq -c | sort -rn | head -60`
That list is the work plan: each line is one system call or IOP function that nobody has written yet.

To see all the pictures at once, copy `tools/p3fes_contact.py` into the Linux folder and run `python3 p3fes_contact.py games/p3fes/shots -o sheet`; it writes a few PNG contact sheets with the frame numbers on them.

Screenshots from `games/p3fes/shots` are game pictures: you may send me a few in this chat to show how far it got, but they never go to GitHub.

## Step 6: look at it (only if step 4 finished)
1. `python3 scripts/serve.py build/web-p3fes games/p3fes/disc.iso`
2. In Chrome or Edge on Windows open `http://localhost:8620/`.
The disc is streamed from your own file; the page is only for you. Keep it private.

## If something goes wrong
- *`wsl --install` says virtualization is off:* turn on virtualization (VT-x or SVM) in the PC's BIOS settings.
- *Out of disk space:* the project needs about 300 MB per game for generated code plus builds, plus the 4.5 GB disc copy; Linux inside Windows keeps its disk in a file on `C:`.
- *The test rounds crash at once with a graphics error:* re-run step 3 only (`--no-explore`) and tell me the error text; the exploring needs a graphics driver and that part may need a fix.
- *Anything else:* send me the last 30 lines. I'd rather see a failure than have you guess.

## What this does and does not prove
It shows whether the translated game starts, how far it gets, and what is missing. It does not prove the game is playable. The expected result, in the project author's own words, is that "another game will most likely stop at a system call or an IOP library function nobody implemented yet". Each stop is then one small task for us.
