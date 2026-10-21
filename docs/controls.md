# Keys and remapping

Default keys (same as PCSX2): arrows = D-pad, W A S D = left stick, T F G H = right stick, I = triangle, J = square,
L = circle, K = cross, Q = L1, E = R1, 1 = L2, 3 = R2, 2 = L3, 4 = R3, Enter = Start, Backspace = Select.
The ` key toggles fullscreen in the browser build.

## Browser build

`python3 tools/ps2web_keyremap_patch.py web/shell.html` (after `ps2web_controls_patch.py`), then rebuild.
A **Keys** button appears next to Backups. Click a row, press the new key, and it is used at once. Choices are saved
in the browser (local storage), so they stay across reloads on the same address. Rules:

- If the key is already used by another row, that other row becomes "not set".
- `Esc` cancels the row you are changing, or closes the panel. The ` key is reserved for fullscreen.
- **Reset to defaults** restores the table above.

## Controller panel (browser build)

`python3 tools/ps2web_padremap_patch.py web/shell.html` (after `ps2web_keyremap_patch.py`), then rebuild.
When a controller is connected the Keys button reads **Controller** and opens a panel that uses that controller's own
names: PlayStation (Cross, Circle, Square, Triangle, Create, Options), Xbox (A, B, X, Y, View, Menu) or Nintendo
(B, A, Y, X, Minus, Plus); anything else shows Bottom, Right, Left and Top button. Click a row and press the new button
on the controller. The layout is saved in the browser for each controller type, the controller does not press anything in
the game while the panel waits, and the sticks follow the controller's sticks. A **Keyboard keys** button switches to the
key panel, and the key panel has a **Controller** button to come back.
The type is guessed from the name the browser reports (vendor ids and words such as DualSense, Xbox, Pro Controller).

## PC runner

`python3 tools/ps2run_keyremap_patch.py host/window.cpp` (after `ps2run_controls_patch.py`), then rebuild.
The runner reads `keys.txt` from the folder it is started in, or the file named by the `PS2_KEYS` environment variable.
One `name = key` per line; `#` starts a comment; lines you leave out keep their default.

Names: `up down left right cross circle square triangle l1 r1 l2 r2 l3 r3 start select`, and for the sticks
`lup ldown lleft lright rup rdown rleft rright`. Keys use SDL names: `A`-`Z`, `0`-`9`, `Up`, `Down`, `Left`, `Right`,
`Return`, `Backspace`, `Space`, `Left Shift`, `Right Shift`, `Left Ctrl`, `Tab`, `Keypad 1`, and so on. `none` leaves a
button without a key.

```
# keys.txt: swap confirm and cancel to Z and X, left stick on the arrows
cross = Z
circle = X
lup = Up
ldown = Down
lleft = Left
lright = Right
up = none
down = none
left = none
right = none
```

The runner prints `[keys] reading keys.txt` at start and a line for any name or key it does not understand. A key given
to two rows does both things; the runner prints a warning. The window keys (F6 save state, F11 fullscreen and the others)
are not remappable.

## Mouse look in the PC window
Click the game picture to capture the mouse, then move it sideways: it turns the camera (right stick, and it taps L1 or R1, which is what
Persona 3 uses in Tartarus). Esc, or switching to another window, gives the mouse back. This is the same as the browser build. The PC
window also opens maximized; put `PS2_NO_MAXIMIZE=1` in `~/.p3fes-window-env` if you prefer the small window. F11 toggles real full screen.
