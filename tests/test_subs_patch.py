import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, '..', 'tools', 'ps2run_subs_patch.py')
sys.path.insert(0, os.path.join(here, '..', 'tools'))
def run(d):
    return subprocess.run([sys.executable, tool, d], capture_output=True, text=True)
FILES = {
 'runtime/include/ps2/system.hpp': 'namespace ps2 {\nstd::uint64_t frame_count();\n}\n',
 'runtime/src/system.cpp': 'bool load_state(const std::uint8_t *data, std::size_t size) {\n}\n',
 'runtime/src/disc.cpp': 'bool read() {\n    const std::size_t want = static_cast<std::size_t>(count) * kSector;\n    const std::size_t got = g_reader(a);\n}\n',
 'host/window.cpp': '#include <vector>\n\nvoid poll() {\n    SDL_Event e;\n        if (e.type == SDL_QUIT) ps2::halt("window closed");\n}\n',
}
def make(d, files):
    for rel, t in files.items():
        os.makedirs(os.path.dirname(os.path.join(d, rel)), exist_ok=True)
        open(os.path.join(d, rel), 'w', newline='').write(t)
with tempfile.TemporaryDirectory() as d:
    make(d, dict(FILES, **{'host/window.cpp': 'int y;\n'}))
    assert run(d).returncode != 0                      # unknown source is refused
with tempfile.TemporaryDirectory() as d:
    make(d, FILES)
    r = run(d)
    assert r.returncode == 0 and 'patched: host/window.cpp' in r.stdout, r.stdout + r.stderr
    w = open(os.path.join(d, 'host/window.cpp')).read()
    assert '#include "subs.inc"' in w and 'subs_draw(g_window);' in w and 'subs_event(e);' in w
    assert 'movie_note(m.name.c_str()' in open(os.path.join(d, 'runtime/src/disc.cpp')).read()
    assert 'bool movie_now' in open(os.path.join(d, 'runtime/include/ps2/system.hpp')).read()
    assert 'void movie_note' in open(os.path.join(d, 'runtime/src/system.cpp')).read()
    inc = open(os.path.join(d, 'host/subs.inc')).read()
    assert 'UpdateLayeredWindow' in inc and 'parse_srt' in inc
    font = open(os.path.join(d, 'host/subs_font.inc')).read()
    assert 'kFontParts' in font and len(font) > 100000
    assert 'already patched' in run(d).stdout
# the tool's own srt reader agrees with the rules the PC window uses
import p3fes_subs as S
c = S.parse_srt('\ufeff1\r\n00:00:01,500 --> 00:00:03,000\r\n<i>Hola</i>\r\nmundo\r\n\r\n2\r\n0:00:04.000 --> 0:00:05.25\r\nAdiós\r\n')
assert c == [(1.5, 3.0, 'Hola\nmundo'), (4.0, 5.25, 'Adiós')], c
import tempfile as _t
assert S.srt_time(3723.4567) == '01:02:03,457'
_d = _t.mkdtemp(); S.write_srt(_d + '/x.srt', [(1.0, 2.5, 'Hola'), (3, 3.1, 'Adiós')])
assert S.parse_srt(open(_d + '/x.srt', encoding='utf-8').read()) == [(1.0, 2.5, 'Hola'), (3.0, 3.4, 'Adiós')]
print('ok   Subtitle patch: applies once, refuses unknown source, is idempotent; .srt reading')
_w = [(1.0 + i * 0.3, 1.25 + i * 0.3, x) for i, x in enumerate("Welcome to the Velvet Room, my dear young man.".split())] + [(30, 30.3, 'See?'), (30.4, 30.8, 'There'), (30.9, 31.2, 'it'), (31.3, 31.6, 'is!')]
_c = S.group_words(_w)
assert len(_c) == 2 and _c[0][2].count('\n') == 1 and _c[0][1] < 5 and _c[1][0] == 30 and _c[1][1] < 32.5, _c
print('ok   Subtitle lines from word timings: pauses split lines, long lines make two rows, no line outlives its words')
_p = S.polish([(1, 2, "I'll do it myself! You"), (2.3, 4, "don't get it, do you?"), (5, 6, 'Thank you for watching!'), (20, 22, 'Welcome to GeckoCon.')])
assert _p == [(1, 4, "I'll do it myself! You don't get it, do you?".replace("myself! You", "myself!\nYou") if False else "I'll do it myself! You\ndon't get it, do you?"), (20, 22, 'Welcome to Gekkoukan.')] or [x[2].replace('\n', ' ') for x in _p] == ["I'll do it myself! You don't get it, do you?", 'Welcome to Gekkoukan.'], _p
print('ok   Subtitle polish: joins broken lines, drops invented sign-offs, fixes names')
