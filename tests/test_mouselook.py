import os, re, shutil, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, '..', 'tools', 'ps2run_mouselook_patch.py')
d = tempfile.mkdtemp()
os.makedirs(d + '/host')
src = ('void poll_port(int port) {\n  x;\n    rumble(port);\n    static std::uint64_t last[2] = {};\n}\n'
       'void poll() {\n        if (e.type == SDL_CONTROLLERDEVICEADDED) open_pad(e.cdevice.which);\n}\n'
       'bool open_window() {\n    SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "linear");\n}\n')
open(d + '/host/window.cpp', 'w').write(src)
def run():
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True).stdout.strip()
assert run().startswith('patched (4'), 'first'
assert run() == 'already patched'
out = open(d + '/host/window.cpp').read()
assert 'SDL_MaximizeWindow' in out and 'mouse_look_apply(rx, pressed)' in out and 'SDL_SetRelativeMouseMode(SDL_TRUE)' in out
open(d + '/host/window.cpp', 'w').write('nothing')
assert 'PATCH NOT APPLIED' in run()
if shutil.which('g++'):
    body = re.search(r"FN_NEW = r'''(.*?)''' \+ FN_OLD", open(tool).read(), re.S).group(1)
    cpp = ('#include <cstdint>\n#include <cstdio>\ntypedef unsigned Uint32;\nstatic Uint32 g_t = 1000;\nUint32 SDL_GetTicks() { return g_t; }\n'
           'enum { kL1 = 1u << 10, kR1 = 1u << 11 };\n' + body.replace('void poll_port(int port) {\n', '') + '''
int main() {
  std::uint8_t rx = 128; std::uint16_t p = 0;
  g_mouse_dx = 3; mouse_look_apply(rx, p);
  std::printf("%d %d\\n", rx, (p & kR1) != 0);
  rx = 128; p = 0; g_mouse_dx = -5; mouse_look_apply(rx, p);
  std::printf("%d %d\\n", rx, (p & kL1) != 0);
  rx = 128; p = 0; g_t += 500; mouse_look_apply(rx, p);
  std::printf("%d %d\\n", rx, p);
}
''')
    open(d + '/t.cpp', 'w').write(cpp)
    r = subprocess.run(['g++', '-std=c++17', '-o', d + '/t', d + '/t.cpp'], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[:600]
    o = subprocess.run([d + '/t'], capture_output=True, text=True).stdout.split('\n')
    assert o[:3] == ['146 1', '98 1', '128 0'], o
print('ok mouse look patch: applies once, idempotent, refuses unknown source, stick and L1/R1 logic')
