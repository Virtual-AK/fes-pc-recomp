"""PC runner keyboard layout like PCSX2's default and like the browser build. Patches host/window.cpp.
Keys: arrows = D-pad, W A S D = left stick, T F G H = right stick, I = triangle, J = square, L = circle, K = cross,
Q = L1, E = R1, 1 = L2, 3 = R2, 2 = L3, 4 = R3, Enter = Start, Backspace = Select.
(The old layout used Z X A S for the buttons and the arrows as the left stick too; the arrows are now only the D-pad.)
Usage (in the ps2-web-recomp folder): python3 ps2run_controls_patch.py [host/window.cpp]
Safe to run twice. Rebuild afterwards (scripts/build_native.sh p3fes, or the build command you normally use).
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'host/window.cpp'
s = open(p).read()
if 'SDL_SCANCODE_E, kR1' in s:
    print("already patched"); raise SystemExit
K_OLD = """    {SDL_SCANCODE_UP, kUp},         {SDL_SCANCODE_DOWN, kDown},     {SDL_SCANCODE_LEFT, kLeft},
    {SDL_SCANCODE_RIGHT, kRight},   {SDL_SCANCODE_Z, kCross},       {SDL_SCANCODE_X, kCircle},
    {SDL_SCANCODE_A, kSquare},      {SDL_SCANCODE_S, kTriangle},    {SDL_SCANCODE_Q, kL1},
    {SDL_SCANCODE_W, kR1},          {SDL_SCANCODE_1, kL2},          {SDL_SCANCODE_2, kR2},
    {SDL_SCANCODE_RETURN, kStart},  {SDL_SCANCODE_BACKSPACE, kSelect},
"""
K_NEW = """    {SDL_SCANCODE_UP, kUp},         {SDL_SCANCODE_DOWN, kDown},     {SDL_SCANCODE_LEFT, kLeft},
    {SDL_SCANCODE_RIGHT, kRight},   {SDL_SCANCODE_K, kCross},       {SDL_SCANCODE_L, kCircle},
    {SDL_SCANCODE_J, kSquare},      {SDL_SCANCODE_I, kTriangle},    {SDL_SCANCODE_Q, kL1},
    {SDL_SCANCODE_E, kR1},          {SDL_SCANCODE_1, kL2},          {SDL_SCANCODE_3, kR2},
    {SDL_SCANCODE_2, kL3},          {SDL_SCANCODE_4, kR3},
    {SDL_SCANCODE_RETURN, kStart},  {SDL_SCANCODE_BACKSPACE, kSelect},
"""
S_OLD = """        if (keys[SDL_SCANCODE_LEFT]) lx = 0x00;
        if (keys[SDL_SCANCODE_RIGHT]) lx = 0xFF;
        if (keys[SDL_SCANCODE_UP]) ly = 0x00;
        if (keys[SDL_SCANCODE_DOWN]) ly = 0xFF;
"""
S_NEW = """        if (keys[SDL_SCANCODE_A]) lx = 0x00;
        if (keys[SDL_SCANCODE_D]) lx = 0xFF;
        if (keys[SDL_SCANCODE_W]) ly = 0x00;
        if (keys[SDL_SCANCODE_S]) ly = 0xFF;
        if (keys[SDL_SCANCODE_F]) rx = 0x00;
        if (keys[SDL_SCANCODE_H]) rx = 0xFF;
        if (keys[SDL_SCANCODE_T]) ry = 0x00;
        if (keys[SDL_SCANCODE_G]) ry = 0xFF;
"""
R_OLD = """        rx = axis(pad, SDL_CONTROLLER_AXIS_RIGHTX);
        ry = axis(pad, SDL_CONTROLLER_AXIS_RIGHTY);
"""
R_NEW = """        if (rx == 0x80) rx = axis(pad, SDL_CONTROLLER_AXIS_RIGHTX);
        if (ry == 0x80) ry = axis(pad, SDL_CONTROLLER_AXIS_RIGHTY);
"""
for o in [K_OLD, S_OLD, R_OLD]:
    if s.count(o) != 1:
        print("PATCH NOT APPLIED: host/window.cpp does not look like the expected source"); raise SystemExit(1)
s = s.replace(K_OLD, K_NEW, 1).replace(S_OLD, S_NEW, 1).replace(R_OLD, R_NEW, 1)
open(p, 'w').write(s)
print("patched (PCSX2-style keys for the PC runner)")
