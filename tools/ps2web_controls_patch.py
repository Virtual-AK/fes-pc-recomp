"""Browser keyboard layout like PCSX2's default, plus mouse look. Patches web/shell.html.
Keys: arrows = D-pad, W A S D = left stick, T F G H = right stick, I = triangle, J = square, L = circle, K = cross,
Q = L1, E = R1, 1 = L2, 3 = R2, 2 = L3, 4 = R3, Enter = Start, Backspace = Select.
Mouse: click the game picture to capture the mouse (Esc gives it back). Moving the mouse sideways drives the right stick and also taps L1/R1
(the buttons Persona 3 uses for turning the camera in Tartarus): left = L1, right = R1.
The old fullscreen key F moves to the ` key (double click and the button still work), because F is now the right stick.
Usage (in the ps2-web-recomp folder): python3 ps2web_controls_patch.py [web/shell.html]
Safe to run twice. Rebuild afterwards (web: scripts/build_web.sh p3fes, then copy cut.state back if you use it)
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'web/shell.html'
s = open(p).read()
if 'mouseLook' in s:
    print("already patched"); raise SystemExit
K_OLD = """const keyMap = { ArrowUp: 4, ArrowRight: 5, ArrowDown: 6, ArrowLeft: 7, KeyZ: 14, KeyX: 13, KeyA: 15, KeyS: 12,
                 KeyQ: 10, KeyW: 11, Digit1: 8, Digit2: 9, Enter: 3, Backspace: 0 };
const stickKeys = new Set(['KeyI', 'KeyJ', 'KeyK', 'KeyL']);
"""
K_NEW = """// buttons: 0 select, 1 L3, 2 R3, 3 start, 4-7 up right down left, 8 L2, 9 R2, 10 L1, 11 R1, 12 triangle, 13 circle, 14 cross, 15 square
const keyMap = { ArrowUp: 4, ArrowRight: 5, ArrowDown: 6, ArrowLeft: 7, KeyI: 12, KeyL: 13, KeyK: 14, KeyJ: 15,
                 KeyQ: 10, KeyE: 11, Digit1: 8, Digit3: 9, Digit2: 1, Digit4: 2, Enter: 3, Backspace: 0 };
const stickKeys = new Set(['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyT', 'KeyF', 'KeyG', 'KeyH']);
// mouse look: click the picture to capture the mouse, Esc releases it
let mouseDx = 0, mouseDir = 0, mouseUntil = 0;
canvas.addEventListener('click', () => {
  if (document.pointerLockElement === canvas || !canvas.requestPointerLock) return;
  const lock = canvas.requestPointerLock();
  if (lock && lock.catch) lock.catch(() => {});
});
document.addEventListener('mousemove', (e) => { if (document.pointerLockElement === canvas) mouseDx += e.movementX; });
function mouseLook() {
  const now = performance.now();
  let rx = 128, buttons = 0;
  if (mouseDx) {
    rx = 128 + Math.max(-127, Math.min(127, Math.round(mouseDx * 6)));
    if (Math.abs(mouseDx) >= 2) { mouseDir = mouseDx < 0 ? -1 : 1; mouseUntil = now + 80; }
    mouseDx = 0;
  }
  if (now < mouseUntil) buttons |= 1 << (mouseDir < 0 ? 10 : 11);
  return { buttons, rx };
}
"""
S_OLD = """    if (keys.has('KeyJ')) lx = 0;
    if (keys.has('KeyL')) lx = 255;
    if (keys.has('KeyI')) ly = 0;
    if (keys.has('KeyK')) ly = 255;
"""
S_NEW = """    if (keys.has('KeyA')) lx = 0;
    if (keys.has('KeyD')) lx = 255;
    if (keys.has('KeyW')) ly = 0;
    if (keys.has('KeyS')) ly = 255;
    if (keys.has('KeyF')) rx = 0;
    if (keys.has('KeyH')) rx = 255;
    if (keys.has('KeyT')) ry = 0;
    if (keys.has('KeyG')) ry = 255;
    const look = mouseLook();
    buttons |= look.buttons;
    if (look.rx !== 128) rx = look.rx;
"""
F_OLD = "if (e.code !== 'KeyF' || e.repeat"
F_NEW = "if (e.code !== 'Backquote' || e.repeat"
T_OLD = 'title="Fullscreen (F or double click)"'
T_NEW = 'title="Fullscreen (` or double click)"'
for o in [K_OLD, S_OLD, F_OLD, T_OLD]:
    if s.count(o) != 1:
        print("PATCH NOT APPLIED: web/shell.html does not look like the expected source"); raise SystemExit(1)
s = s.replace(K_OLD, K_NEW, 1).replace(S_OLD, S_NEW, 1).replace(F_OLD, F_NEW, 1).replace(T_OLD, T_NEW, 1)
open(p, 'w').write(s)
print("patched (PCSX2-style keys and mouse look)")
