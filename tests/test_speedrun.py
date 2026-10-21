import os, subprocess, shutil, tempfile, re
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, '..', 'tools', 'ps2run_speedrun_patch.py')
src = '/tmp/src/ps2-web-recomp/host/window.cpp'
fixture = '''namespace {
SDL_Window *g_window = nullptr;
void poll_port(int port) {
}
void poll() {
    SDL_Event e;
    poll_port(0);
    poll_port(1);
}

void show_pixels(const std::uint32_t *rgba, std::uint32_t w, std::uint32_t h) {
}
}
'''
d = tempfile.mkdtemp()
os.makedirs(d + '/host')
open(d + '/host/window.cpp', 'w', newline='').write(fixture.replace('\n', '\r\n'))
def run():
    return subprocess.run(['python3', tool, d], capture_output=True, text=True).stdout.strip()
assert run() == 'patched (3 edits)', run()
t1 = open(d + '/host/window.cpp', newline='').read()
assert '\r\n' in t1 and 'speedrun_tick();   // ps2run' in t1 and 'PS2_SPEEDRUN' in t1
assert run() == 'already patched'
assert open(d + '/host/window.cpp', newline='').read() == t1
open(d + '/host/window.cpp', 'w').write('nothing here')
assert run().startswith('PATCH NOT APPLIED')
h = open(os.path.join(here, '..', 'tools', 'launcher', 'ui', 'index.html')).read()
assert "'sr:1'" in h and "'srr'" in h and "'SPEEDRUN'" in h
py = open(os.path.join(here, '..', 'tools', 'launcher', 'p3fes_launcher.py')).read()
assert 'PS2_SPEEDRUN' in py and '/api/speedrun/reset' in py
assert 'ps2run_speedrun_patch.py' in open(os.path.join(here, '..', 'tools', 'p3fes_install.sh')).read()
shutil.rmtree(d)
print('ok speedrun: patch applies, repeats cleanly, refuses unknown source; launcher setting and installer wired')
