import os, subprocess, sys, tempfile, time, urllib.request, socket
here = os.path.dirname(os.path.abspath(__file__))
tools = os.path.join(here, "..", "tools")
src = open(os.path.join(here, "test_modmap.py")).read()
exec(src[:src.index("with tempfile")])      # build() and helpers for the synthetic disc
import shutil
with tempfile.TemporaryDirectory() as d:
    serve = os.path.join(d, "serve.py"); shutil.copy(os.path.join(here, "fixtures", "serve_orig.py"), serve)
    r = subprocess.run([sys.executable, os.path.join(tools, "ps2web_serveovl_patch.py"), serve], capture_output=True, text=True)
    assert "patched" in r.stdout, r.stdout + r.stderr
    assert "already patched" in subprocess.run([sys.executable, os.path.join(tools, "ps2web_serveovl_patch.py"), serve], capture_output=True, text=True).stdout
    iso = os.path.join(d, "g.iso"); build(iso)
    mod = os.path.join(d, "mod"); os.makedirs(os.path.join(mod, "TEST.CVM", "BTL.BIN.d"))
    open(os.path.join(mod, "TEST.CVM", "BTL.BIN.d", "a.bmd"), "wb").write(b"HELLO-MODDED-012")
    mod2 = os.path.join(d, "mod2"); os.makedirs(os.path.join(mod2, "TEST.CVM"))
    big = b"BIGFILE!" * 1000
    open(os.path.join(mod2, "TEST.CVM", "BTL.BIN"), "wb").write(big)
    for m in (mod, mod2):
        ovl = os.path.join(d, os.path.basename(m) + ".ovl"); copy = os.path.join(d, os.path.basename(m) + ".iso")
        for mode, out in (("overlay", ovl), ("apply", copy)):
            r = subprocess.run([sys.executable, os.path.join(tools, "p3fes_modmap.py"), mode, iso, m, "-o", out], capture_output=True, text=True)
            assert r.returncode == 0, r.stdout + r.stderr
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        build_dir = os.path.join(d, "b"); os.makedirs(build_dir, exist_ok=True)
        p = subprocess.Popen([sys.executable, serve, build_dir, iso, str(port), "--overlay", ovl], stdout=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try: urllib.request.urlopen("http://127.0.0.1:%d/disc.iso" % port, timeout=1).close(); break
                except Exception: time.sleep(0.1)
            want = open(copy, "rb").read()
            got = b""
            while len(got) < len(want):
                rq = urllib.request.Request("http://127.0.0.1:%d/disc.iso" % port, headers={"Range": "bytes=%d-%d" % (len(got), len(got) + 3000)})
                chunk = urllib.request.urlopen(rq).read()
                assert chunk
                got += chunk
            assert got[:len(want)] == want, "served bytes differ from the applied copy"
            h = urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:%d/disc.iso" % port, method="HEAD"))
            assert int(h.headers["Content-Length"]) == len(want)
            log = open(ovl + ".log").read()
            assert "hit part" in log and log.count("hit part") <= 4, log
        finally:
            p.terminate()
print("ok   serve.py overlay patch: served disc equals the applied copy (in place and moved files)")
