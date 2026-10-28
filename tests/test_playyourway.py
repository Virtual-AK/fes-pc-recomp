"""About > Play Your Way (0.56): two Steam links and a sale check that never blocks the launcher."""
import json, os, sys, urllib.request
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..', 'tools', 'launcher')); sys.path.insert(0, os.path.join(here, '..', 'tools'))
import p3fes_launcher as L

assert L.STEAM_GAMES['p3p']['id'] == 1809700 and L.STEAM_GAMES['p3r']['id'] == 2161700
assert L.steam_store_url(2161700) == 'https://store.steampowered.com/app/2161700/'

class Resp:
    def __init__(self, obj): self.b = json.dumps(obj).encode()
    def read(self): return self.b
    def __enter__(self): return self
    def __exit__(self, *a): return False

calls = []
def fake(req, timeout=0):
    calls.append(req.full_url)
    assert req.full_url.startswith('https://store.steampowered.com/api/appdetails?appids=') and 'filters=price_overview' in req.full_url
    if '1809700' in req.full_url:
        return Resp({'1809700': {'success': True, 'data': {'price_overview': {'final_formatted': '$9.89', 'initial_formatted': '$19.99', 'discount_percent': 50}}}})
    return Resp({'2161700': {'success': True, 'data': {'price_overview': {'final_formatted': '$69.99', 'initial_formatted': '', 'discount_percent': 0}}}})
real = urllib.request.urlopen
urllib.request.urlopen = fake
d = L.steam_prices(force=True)
assert d['p3p']['sale'] and d['p3p']['pct'] == 50 and d['p3p']['final'] == '$9.89' and d['p3p']['initial'] == '$19.99'
assert not d['p3r']['sale'] and d['p3r']['final'] == '$69.99' and d['p3r']['initial'] == '$69.99'
n = len(calls); L.steam_prices(); assert len(calls) == n, 'cached for 30 minutes'
assert L.STEAM_CACHE['ttl'] == 1800

def boom(req, timeout=0): raise OSError('no network')
urllib.request.urlopen = boom
d = L.steam_prices(force=True)
assert not d['p3p']['ok'] and not d['p3p']['sale'] and L.STEAM_CACHE['ttl'] == 120, 'a failed check is retried soon'

def free(req, timeout=0): return Resp({'1809700': {'success': True, 'data': []}, '2161700': {'success': False}})
urllib.request.urlopen = free
d = L.steam_prices(force=True)
assert d['p3p']['ok'] and d['p3p']['final'] == '' and not d['p3r']['ok']
urllib.request.urlopen = real

html = open(os.path.join(here, '..', 'tools', 'launcher', 'ui', 'index.html'), encoding='utf-8').read()
assert "'PLAY YOUR WAY'" in html and "about:[0,2,3,4,1]" in html and "'/api/steam/open'" in html and "'/api/steam/prices'" in html
src = open(os.path.join(here, '..', 'tools', 'launcher', 'p3fes_launcher.py'), encoding='utf-8').read()
assert '"/api/steam/open"' in src and '"/api/steam/prices"' in src
print('ok   About > Play Your Way: two Steam pages, price and sale check (cached, never blocks)')
