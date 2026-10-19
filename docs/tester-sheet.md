# Clean-install tester sheet

Thank you for testing. You need: Windows 10 or 11, about 20 GB free space, Chrome or Edge, and your own Persona 3 FES (USA) disc image as an `.iso` file. Set aside an hour or two; most of that is waiting (the build took about 10 minutes on one laptop, so please time yours). Nothing from the game is ever sent to anyone except screenshots you choose to share.

Before you start, open `chrome://gpu` (or `edge://gpu`) and note the line that says WebGPU. If it says "Disabled" or "Unavailable", the browser version will run badly: tell me, and try the PC window instead. Firefox is not supported; use Chrome or Edge.

Follow [install.md](install.md) from the top. Below is what you should see at each step, and what to send if it doesn't match. Write down roughly what time each step started and finished.

## Checklist

| Step | You should see | If not, send |
|---|---|---|
| `wsl --install -d Ubuntu` in PowerShell (administrator) | It installs Ubuntu and asks to restart | A screenshot of the PowerShell window |
| Open **Ubuntu** from the Start menu | A black window asking for a user name and password | A screenshot |
| Disc in `C:\p3fes`, repository unzipped there | `p3fes_install.sh` exists inside a `tools` folder | The output of `find /mnt/c -name p3fes_install.sh` |
| Run the install command | Lines starting `== [1/5]`, `[2/5]` and so on, then a long quiet build | The last 30 lines of the window |
| Ubuntu password prompt | Asked once; typing shows nothing, which is normal | Tell me if it asked more than once |
| Build finishes | `== Done` and a line naming `play.sh` | The last 30 lines |
| Run `play.sh`, open `http://localhost:8620/` | The title screen with the P3F logo and a clear background | A screenshot of the page |
| Press Start, choose a new game | The opening plays, and the buttons Backups, Autosave and Keys are at the bottom | A screenshot |

## What good looks like (reference run)
One desktop, Windows 10 22H2, NVIDIA RTX 3060 Ti, 63 GB memory, Chrome 155, browser build at 3x resolution (1920x1536):
**60.0 fps (60 on screen)**, "GPU 1% idle", emulation thread about 82% busy, and the opening hall (Dark Hour, 1F Entrance)
drawn correctly with sound. Your numbers will differ on a weaker computer; please send the line at the bottom of the page
(frame count, fps, GPU, emu, vu and gs percentages) with your answers. The page's Resolution box is also set by the
launcher (Settings > Display), 3x by default.

## Questions to answer
0. What did the WebGPU line in `chrome://gpu` say, and what graphics card does the computer have?
1. Which step took longest, and how long?
2. Was any instruction unclear or did you have to guess? Which one?
3. Did the install stop? If so, at which line (a message starting `STOPPED:` says where)?
4. Did the game run smoothly at 60 frames per second (shown at the bottom of the page)?
5. Anything that looked wrong in the picture or sounded wrong?

## Good to know
- If the install stops, run the same command again: finished steps are skipped.
- To stop the game server, press Ctrl+C in the Ubuntu window. Closing the browser tab does not stop it.
- Screenshots of the game are fine to send to the project lead. They must not be posted publicly with the repository.
