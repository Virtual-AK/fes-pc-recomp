import http.server, os, sys, tempfile, threading, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'launcher'))
import p3fes_launcher as L

seen = []
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        seen.append((self.headers.get("User-Agent", ""), self.headers.get("Referer", "")))
        if self.path == "/gone" or self.headers.get("User-Agent", "").startswith("p3fes"):
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Length", "5"); self.end_headers(); self.wfile.write(b"hello")
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_port
L.gb_host_ok = lambda u: True
d = tempfile.mkdtemp(); dest = os.path.join(d, "x.zip")
# a server that turns the launcher away with 404 but serves a browser: second try gets the file, with the mod page as referer
assert L.gb_download_file({"_sDownloadUrl": base + "/file"}, dest, 1 << 20, "https://gamebanana.com/mods/1") is None
assert open(dest, "rb").read() == b"hello"
assert seen[0][0].startswith("p3fes") and seen[1][0].startswith("Mozilla") and seen[1][1] == "https://gamebanana.com/mods/1", seen
# a file that is really gone still raises the 404 (after both tries)
seen.clear()
try:
    L.gb_download_file({"_sDownloadUrl": base + "/gone"}, dest, 1 << 20, "")
    raise SystemExit("expected an error")
except urllib.error.HTTPError as e:
    err = e
    assert e.code == 404 and len(seen) == 2
e = err
assert "404" in L.gb_err_text(e, "https://gamebanana.com/dl/1") and "/gone" in L.gb_err_text(e, "x")
srv.shutdown()
print("ok GameBanana download retries as a browser after 404, still reports a gone file")
