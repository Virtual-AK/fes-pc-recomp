import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, '..', 'tools', 'ps2run_logkey_patch.py')
def run(d):
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True)
FILES = {
 'runtime/include/ps2/system.hpp': 'namespace ps2 {\n}\n',
 'runtime/src/system.cpp': 'void dlog_tick() {\n    for (std::uint32_t a = 0x1060000; a < 0x1070000; a += 4) {\n  disc::recent_data_reads().c_str());\n        std::fflush(out);\n}\nbool load_state(const std::uint8_t *data, std::size_t size) {\n}\n',
 'host/window.cpp': 'void poll() {\n    SDL_Event e;\n        if (e.type == SDL_CONTROLLERDEVICEADDED) open_pad(e.cdevice.which);\n    poll_port(0);\n    poll_port(1);\n}\n',
}
def make(d, files):
    for rel, t in files.items():
        os.makedirs(os.path.dirname(os.path.join(d, rel)), exist_ok=True)
        open(os.path.join(d, rel), 'w', newline='').write(t)
with tempfile.TemporaryDirectory() as d:
    make(d, dict(FILES, **{'runtime/src/system.cpp': 'int x;\n'}))
    r = run(d)
    assert 'NOT APPLIED' in r.stdout and r.returncode != 0, r.stdout       # needs the dialogue log patch first
with tempfile.TemporaryDirectory() as d:
    make(d, dict(FILES, **{'host/window.cpp': 'int y;\n'}))
    assert run(d).returncode != 0
with tempfile.TemporaryDirectory() as d:
    make(d, FILES)
    r = run(d)
    assert 'patched (7 edits)' in r.stdout, r.stdout + r.stderr
    w = open(os.path.join(d, 'host/window.cpp')).read()
    c = open(os.path.join(d, 'runtime/src/system.cpp')).read()
    assert 'SDL_SCANCODE_TAB' in w and 'log_draw();' in w and 'kLogFont[95][16]' in w and w.count('0x') > 95 * 16
    assert 'g_frames % 60 == 0' in c and 'dialog_push(speaker, text);' in c and 'std::vector<std::string> dialog_recent' in c
    assert 'already patched' in run(d).stdout
    # an earlier patch run that lost one edit is completed, not refused
    open(os.path.join(d, 'runtime/src/system.cpp'), 'w').write(c.replace('        dialog_push(speaker, text);   // ps2run_logkey_patch.py\n', ''))
    assert 'patched (1 edits)' in run(d).stdout
    # a tree patched by the previous version gets the close handling and the faster scan, and nothing else changes
    sc = os.path.join(d, 'runtime/src/system.cpp'); wc = os.path.join(d, 'host/window.cpp')
    s0 = open(sc).read(); w0 = open(wc).read()
    open(sc, 'w').write(s0.replace('    if (g_frames % 60 == 0) {\n', '    if (recs.empty() ? g_frames % 30 == 0 : g_frames % 900 == 0) {\n'))
    i = w0.index('        // with the log box open'); j = w0.index('\n', w0.index('ps2::halt("window closed");')) + 1
    open(wc, 'w').write(w0[:i] + w0[j:])
    r = run(d)
    assert 'patched (2 edits)' in r.stdout, r.stdout + r.stderr
    assert open(sc).read() == s0 and open(wc).read() == w0
    assert 'already patched' in run(d).stdout
print('ok   Log key patch: needs the dialogue log patch, applies once, is idempotent, completes a half-applied tree')
