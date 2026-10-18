import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2run_controls_patch.py")
def run(f):
    return subprocess.run([sys.executable, tool, f], capture_output=True, text=True)
SRC = """    {SDL_SCANCODE_UP, kUp},         {SDL_SCANCODE_DOWN, kDown},     {SDL_SCANCODE_LEFT, kLeft},
    {SDL_SCANCODE_RIGHT, kRight},   {SDL_SCANCODE_Z, kCross},       {SDL_SCANCODE_X, kCircle},
    {SDL_SCANCODE_A, kSquare},      {SDL_SCANCODE_S, kTriangle},    {SDL_SCANCODE_Q, kL1},
    {SDL_SCANCODE_W, kR1},          {SDL_SCANCODE_1, kL2},          {SDL_SCANCODE_2, kR2},
    {SDL_SCANCODE_RETURN, kStart},  {SDL_SCANCODE_BACKSPACE, kSelect},
        if (keys[SDL_SCANCODE_LEFT]) lx = 0x00;
        if (keys[SDL_SCANCODE_RIGHT]) lx = 0xFF;
        if (keys[SDL_SCANCODE_UP]) ly = 0x00;
        if (keys[SDL_SCANCODE_DOWN]) ly = 0xFF;
        rx = axis(pad, SDL_CONTROLLER_AXIS_RIGHTX);
        ry = axis(pad, SDL_CONTROLLER_AXIS_RIGHTY);
"""
with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "window.cpp")
    open(f, "w").write("int x;\n")
    r = run(f)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(f, "w").write(SRC)
    r = run(f)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    s = open(f).read()
    assert "SDL_SCANCODE_E, kR1" in s and "SDL_SCANCODE_T]) ry" in s and "if (rx == 0x80) rx = axis" in s
    assert "already patched" in run(f).stdout
print("ok   PC runner controls patch (PCSX2-style keys) applies once, is idempotent and refuses unknown source")
