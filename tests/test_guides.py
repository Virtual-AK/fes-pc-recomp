import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
import p3fes_launcher as L
assert L.guide_url('faqs', 'a & b').startswith('https://gamefaqs.gamespot.com/search?game=a+%26+b')
assert L.guide_url('web', 'x').startswith('https://duckduckgo.com/?q=')
assert L.guide_url('evil', 'x') is None and L.guide_url('wiki', '   ') is None
assert len(L.guide_url('web', 'x' * 500)) < 200
L.GUIDES_DIR = tempfile.mkdtemp()
assert L.guide_list() == []
bad = '<p onclick="x()">Hi <script>alert(1)</script><iframe src="x"></iframe><a href="javascript:alert(1)">l</a></p>'
r = L.guide_save('Yukari Takeba', bad)
assert r['ok'] and r['slug'] == 'yukari-takeba'
g = L.guide_get('yukari-takeba')
assert g['ok'] and g['title'] == 'Yukari Takeba' and '<script' not in g['html'] and 'onclick' not in g['html'] and '<iframe' not in g['html'] and 'javascript:' not in g['html'] and 'Hi' in g['html']
assert [x['title'] for x in L.guide_list()] == ['Yukari Takeba']
assert not L.guide_get('../../etc/passwd')['ok'] and not L.guide_save('', 'x')['ok']
L.guide_delete('yukari-takeba')
assert L.guide_list() == [] and not L.guide_get('yukari-takeba')['ok']
assert L.GUIDE_TOOLS['fusion'].startswith('https://aqiu384.github.io/')
assert 'golden' in L.THEMES_ALL
print('ok guides: saved pages are scrubbed, listed, read back and deleted; window searches limited to known sites')
