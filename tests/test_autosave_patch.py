import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
tool = os.path.join(here, "..", "tools", "ps2web_autosave_patch.py")
def run(cpp, html):
    return subprocess.run([sys.executable, tool, cpp, html], capture_output=True, text=True)
CPP = """    if (g_state_url) {
        const double size = ps2web_url_size(g_state_url);
extern "C" EMSCRIPTEN_KEEPALIVE int ps2web_rumble(int pad) { return ps2::pad_rumble(pad); }
"""
HTML = """// ps2-card-backups: keep
  <button id="backups" type="button" title="Earlier versions of the memory card kept in this browser">Backups</button>
document.getElementById('backups').addEventListener('click', bkShow);
        else backupCard('game save');
    start.disabled = false;
    start.textContent = 'Start';
  ps2CardSaved: () => storeCard(),
"""
with tempfile.TemporaryDirectory() as d:
    c, h = os.path.join(d, "web.cpp"), os.path.join(d, "shell.html")
    open(c, "w").write("int main() {}\n"); open(h, "w").write("<html></html>\n")
    r = run(c, h)
    assert "NOT APPLIED" in r.stdout and r.returncode != 0
    open(c, "w").write(CPP); open(h, "w").write(HTML.replace("// ps2-card-backups: keep\n", "<html>\n"))
    r = run(c, h)
    assert "NOT APPLIED" in r.stdout and "ps2web_cardbackup_patch.py" in r.stdout and "ps2_save_state" not in open(c).read()
    open(h, "w").write(HTML)
    r = run(c, h)
    assert "patched" in r.stdout and "NOT" not in r.stdout, r.stdout + r.stderr
    cpp, html = open(c).read(), open(h).read()
    assert "ps2web_save_state" in cpp and "/resume.state" in cpp and "ps2ResumeFailed" in cpp and "else if (g_state_url)" in cpp
    assert 'id="autosave"' in html and "asOfferResume(start);" in html and "asSoon(); }" in html and "ps2ResumeFailed: () => asResumeFailed()" in html
    assert "asComplete" in html and "'end'" in html
    assert "already patched" in run(c, h).stdout
print("ok   web autosave patch applies once, is idempotent and refuses unknown source")
