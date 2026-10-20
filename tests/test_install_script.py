"""Checks tools/p3fes_install.sh: valid bash, every patch it lists exists, the project version is pinned,
and the patches are listed in a safe order (prerequisite patches first)."""
import os, re, subprocess, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(root, 'tools', 'p3fes_install.sh')
text = open(path).read()
assert subprocess.run(['bash', '-n', path]).returncode == 0
block = re.search(r'PATCHES="\n(.*?)"', text, re.S).group(1).split()
assert len(block) == len(set(block)), 'duplicate patch'
for f in block:
    assert os.path.exists(os.path.join(root, 'tools', f)), f
assert re.search(r'PIN=[0-9a-f]{40}', text)
def before(a, b):
    assert block.index(a) < block.index(b), a + ' must come before ' + b
before('ps2run_trace_patch5.py', 'ps2run_fix_path3_mask.py')
before('ps2run_trace_patch6.py', 'ps2run_trace_patch9.py')
before('ps2run_trace_patch9.py', 'ps2gs_uploadclamp_patch.py')
before('ps2gpu_tricenter_patch.py', 'ps2gpu_flipfix_patch.py')
before('ps2run_controls_patch.py', 'ps2run_keyremap_patch.py')
before('ps2run_window_capture_patch.py', 'ps2run_window_savestate_patch.py')
before('ps2run_window_savestate_patch.py', 'ps2web_autosave_patch.py')
for a, b in [('ps2web_cardbackup_patch.py', 'ps2web_controls_patch.py'), ('ps2web_controls_patch.py', 'ps2web_keyremap_patch.py'),
             ('ps2web_keyremap_patch.py', 'ps2web_padremap_patch.py'), ('ps2web_padremap_patch.py', 'ps2web_autosave_patch.py'),
             ('ps2web_autosave_patch.py', 'ps2web_autosaveopts_patch.py'), ('ps2web_cardsync_patch.py', 'ps2web_autosavesync_patch.py'), ('ps2web_autosaveopts_patch.py', 'ps2web_autosavesync_patch.py')]:
    before(a, b)
assert 'game data' not in text.lower() or 'No game data' in text
print("ok install script: %d patches in a safe order, version pinned" % len(block))
