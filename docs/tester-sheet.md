# Clean-install tester sheet

Thank you for testing. You need: Windows 10 or 11, about 20 GB free space, Chrome or Edge, and your own Persona 3 FES (USA) disc image as an `.iso` file. Set aside an hour or two (a bit more if you try Part 4); most of that is waiting (the build took about 10 minutes on one laptop, so please time yours). Nothing from the game is ever sent to anyone except screenshots you choose to share.

Before you start, open `chrome://gpu` (or `edge://gpu`) and note the line that says WebGPU. If it says "Disabled" or "Unavailable", the browser version will run badly: tell me, and try the PC window instead. Firefox is not supported; use Chrome or Edge.

Follow the steps below. Write down roughly what time each step started and finished. If anything does not match, send a screenshot of the window. The commands in [install.md](install.md) still work as a fallback.

## Part 1: get Ubuntu on Windows (once)

| Step | You should see | If not, send |
|---|---|---|
| `wsl --install -d Ubuntu` in PowerShell (administrator) | It installs Ubuntu and asks to restart | A screenshot of the PowerShell window |
| Open **Ubuntu** from the Start menu | A black window asking for a user name and password. Pick them, then close the window | A screenshot |
| Disc `.iso` in `C:\p3fes`, repository unzipped there | A `launcher` folder inside `tools`, with `launch.bat` in it | A screenshot of the folder |

## Part 2: set up from the launcher

| Step | You should see | If not, send |
|---|---|---|
| Double-click `launch.bat` | A blue launcher window titled LAUNCHER, with SET UP as the first item | A screenshot of whatever opened |
| Press SET UP | The SETUP screen with four steps: FIND YOUR DISC, GET THE TOOLS, BUILD THE GAME, PLAY | A screenshot |
| Choose disc | A Windows file window (it may be behind the launcher). After choosing your USA disc, the first step says DONE. A wrong or changed disc is refused with a reason | The message shown and a screenshot |
| Get the tools: START SETUP | A second black window opens and asks for your Ubuntu password once (typing shows nothing, which is normal) | Tell me if it asked more than once, or if no window appeared |
| Build the game | The launcher shows a counter (about 337 pieces) that goes up, and the last file names. The black window sits quiet for long stretches | A screenshot of both windows |
| Build finishes | The black window says Finished. The launcher says Ready and PLAY works | The last 30 lines of the black window |
| If setup stops | Press SET UP again, then CONTINUE SETUP. It carries on where it stopped | A screenshot of the black window |

## Part 3: play

| Step | You should see | If not, send |
|---|---|---|
| PLAY with BROWSER selected | Only one browser opens (Settings > Display chooses which), with the title screen and the P3F logo | A screenshot of the page |
| Press Start, choose a new game | The opening plays, and the buttons Backups, Autosave and Keys are at the bottom | A screenshot |
| Save in the game, then open SAVES in the launcher | MEMORY CARD shows the time of your save. After a few minutes AUTOSAVES lists entries | A screenshot |

## Part 4: launcher extras (optional, after the game runs)
Try whichever of these you have time for. They are all in the launcher and none needs the game to be running.

| Step | You should see | If not, send |
|---|---|---|
| SETTINGS > THEME, press a few themes | The colours change at once. Ten themes: Blue, Pink, Reload, Moon, Dawn, Seal, Daybreak, Horizon, Ceremony, Eclipse. The colour squares under the buttons match the themes. Close and reopen the launcher: your pick is kept | A screenshot of a theme that is hard to read |
| Same panel, THE JOURNEY: press I FINISHED THE JOURNEY | Only press it if you have reached the end of The Journey, as it works on trust. A green TWELVE theme appears, and a gold THE JOURNEY · COMPLETE badge shows on the home screen. LOCK IT AGAIN removes both | A screenshot |
| MODS > BROWSE GAMEBANANA | A list of Persona 3 FES mods with pictures. Choosing one shows a preview (pictures, description, version, files) and nothing downloads until you press INSTALL SELECTED FILE | The message shown. If the list is empty or an error appears, a screenshot |
| MODS > FILE MODS, add a mod folder, zip, 7z or rar | The mod appears with a label (FOLDER, ZIP, 7Z or RAR). 7z and rar need 7-Zip installed in Ubuntu: the launcher says so if it is missing. The ▲ button raises a mod in the priority list, and the top one wins where mods overlap. Press PLAY with BROWSER afterwards, and start the game to see the change | A screenshot of the list and the message shown |
| PLAY IN: PC WINDOW (only if you are curious) | Known to be slow, about 15 to 25 frames per second. Please do not spend time on it | Only the frame rate in the window's title bar |

## What to send back
Please send one message with: the answers below, the `chrome://gpu` WebGPU line, your graphics card, Windows version, any screenshots from the "If not" column, and the last 30 lines of the black window if setup stopped. If everything worked, say so too: that is useful.

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
3. Did setup stop? If so, which step in the launcher, and what did the black window say (a message starting `STOPPED:` says where)?
4. Did the game run smoothly at 60 frames per second (shown at the bottom of the page)?
5. Anything that looked wrong in the picture or sounded wrong?
6. Did you try Part 4? Which parts worked, and did anything look wrong or hard to read?

## Good to know
- If setup stops, press CONTINUE SETUP in the launcher: finished steps are skipped.
- Closing the launcher window closes the launcher. A game window or browser tab already open keeps running.
- Screenshots of the game are fine to send to the project lead. They must not be posted publicly with the repository.
