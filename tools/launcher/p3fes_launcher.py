#!/usr/bin/env python3
"""Persona 3 FES launcher: a small local server plus an app window (Edge or Chrome in --app mode).

Run inside Ubuntu (WSL):  python3 p3fes_launcher.py
It reads what the installer left behind, shows the Home screen, and starts the game.
Nothing from the game is read except the disc's SYSTEM.CNF line (to check the version).
Standard library only.
"""
import argparse, glob, json, os, re, socket, struct, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, "ui")
DIR = os.environ.get("P3F_DIR", os.path.expanduser("~/ps2-web-recomp"))
NAME = "p3fes"
GAME_PORT = 8620
CFG = os.path.expanduser("~/.p3fes-launcher.json")
LAUNCHER_VERSION = "0.2"
WANT_ID = "SLUS_216.21"          # SLUS-21621, Persona 3 FES (USA)
PIECES = 337                     # pieces in a full browser build (estimate for the progress bar)
state_lock = threading.Lock()
last_ping = [0.0]
bye_time = [0.0]
children = []


KEY_ROWS = ["cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2", "start", "select"]
KEY_DEFAULTS = {"cross": "K", "circle": "L", "square": "J", "triangle": "I", "l1": "Q", "r1": "E", "l2": "1", "r2": "3",
                "start": "Return", "select": "Backspace"}
KEY_OK = re.compile(r"^([A-Za-z0-9]|Up|Down|Left|Right|Return|Backspace|Space|Left Shift|Right Shift|Left Ctrl|Tab|Keypad [0-9]|none)$")
KEYS_FILE = os.path.expanduser("~/.p3fes-keys.txt")


def read_keys():
    m = dict(KEY_DEFAULTS)
    try:
        with open(KEYS_FILE) as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if "=" in line:
                    a, b = [x.strip() for x in line.split("=", 1)]
                    if a in m and KEY_OK.match(b):
                        m[a] = b
    except Exception:
        pass
    return m


def write_keys(m):
    lines = ["# Persona 3 FES launcher: PC window keys. Only keys that differ from the default are listed.",
             "# Change them in the launcher (Settings > Controls) or add lines such as:  cross = K  (see docs/controls.md)"]
    for k in KEY_ROWS:
        v = m.get(k, KEY_DEFAULTS[k])
        if v != KEY_DEFAULTS[k] and KEY_OK.match(v):
            lines.append("%s = %s" % (k, v))
    with open(KEYS_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")


def report():
    st = get_state()
    d = st.get("disc") or {}
    try:
        kernel = subprocess.run(["uname", "-r"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        kernel = "?"
    exe = os.path.join(DIR, "build", "native-" + NAME, "ps2run")
    exe_t = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(exe))) if os.path.exists(exe) else "not built"
    return "\n".join([
        "Persona 3 FES launcher report (no disc data, no saves)",
        "launcher: %s   python: %s   linux: %s" % (LAUNCHER_VERSION, sys.version.split()[0], kernel),
        "state: %s%s" % (st["state"], (" (" + st["reason"] + ")") if st.get("reason") else ""),
        "disc file: %s   region: %s   game id: %s   contents: %s" % (d.get("file"), d.get("region"), d.get("game_id"), d.get("contents")),
        "browser build: %s   PC window build: %s" % (st.get("built") or "none", exe_t),
        "play in: %s   preferred browser: %s   resolution: %sx" % (st["mode"], st["browser"], st["scale"]),
        "keys changed: %s" % (", ".join("%s=%s" % (k, v) for k, v in read_keys().items() if v != KEY_DEFAULTS[k]) or "none"),
    ])


def load_cfg():
    try:
        with open(CFG) as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(c):
    try:
        with open(CFG, "w") as f:
            json.dump(c, f)
    except Exception:
        pass


# ------------------------------------------------------------------ disc checks
def find_iso():
    p = os.path.join(DIR, "games", NAME, "disc.iso")
    if os.path.exists(p):
        return os.path.realpath(p)
    cands = sorted(glob.glob("/mnt/c/p3fes/*.iso")) + [os.path.expanduser("~/p3fes.iso")] + sorted(glob.glob(os.path.expanduser("~/*.iso")))
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


REGIONS = {"SLUS": "NTSC-U", "SCUS": "NTSC-U", "SLES": "PAL", "SCES": "PAL", "SLPS": "NTSC-J", "SCPS": "NTSC-J", "SLPM": "NTSC-J", "SCAJ": "NTSC-J"}


def check_disc(path):
    """Returns dict: name, size, region, game_id, contents ('ok'|'short'|'unreadable'|'modified'), checks."""
    r = {"file": os.path.basename(path), "region": None, "game_id": None, "contents": "unreadable"}
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(16 * 2048)
            pvd = f.read(2048)
            if pvd[1:6] != b"CD001":
                return r
            vol_blocks = struct.unpack_from("<I", pvd, 80)[0]
            root_lba, root_len = struct.unpack_from("<I", pvd, 156 + 2)[0], struct.unpack_from("<I", pvd, 156 + 10)[0]
            f.seek(root_lba * 2048)
            d = f.read(min(root_len, 65536))
            pos, cnf = 0, None
            while pos < len(d):
                n = d[pos]
                if n == 0:
                    pos = (pos // 2048 + 1) * 2048
                    continue
                lba, ln = struct.unpack_from("<I", d, pos + 2)[0], struct.unpack_from("<I", d, pos + 10)[0]
                nm = d[pos + 33:pos + 33 + d[pos + 32]].decode("latin1", "replace").upper()
                if nm.startswith("SYSTEM.CNF"):
                    cnf = (lba, ln)
                    break
                pos += n
            if cnf:
                f.seek(cnf[0] * 2048)
                txt = f.read(min(cnf[1], 2048)).decode("latin1", "replace")
                m = re.search(r"BOOT2\s*=\s*cdrom0:\\([A-Z0-9_.]+)", txt, re.I)
                if m:
                    gid = m.group(1).upper()
                    r["game_id"] = gid
                    r["region"] = REGIONS.get(gid[:4], "unknown")
        if r["game_id"] is None:
            return r
        r["contents"] = "short" if size < vol_blocks * 2048 else "ok"
        if "modded" in os.path.basename(path).lower():
            r["contents"] = "modified"
    except Exception:
        r["contents"] = "unreadable"
    return r


# ------------------------------------------------------------------ install state
def build_running():
    try:
        out = subprocess.run(["pgrep", "-af", "port.sh|p3fes_install.sh|ninja|cmake --build|emcc"], capture_output=True, text=True, timeout=5).stdout
        mine = os.getpid()
        for line in out.splitlines():
            pid = int(line.split()[0])
            if pid != mine and "p3fes_launcher" not in line and "pgrep" not in line:
                return True
    except Exception:
        pass
    return False


def pieces_done():
    p = os.path.join(DIR, "build", "web-" + NAME, ".ninja_log")
    try:
        with open(p) as f:
            return max(0, sum(1 for _ in f) - 1)
    except Exception:
        return 0


def get_state():
    cfg = load_cfg()
    web = os.path.join(DIR, "build", "web-" + NAME, "ps2web.html")
    exe = os.path.join(DIR, "build", "native-" + NAME, "ps2run")
    iso = find_iso()
    disc = check_disc(iso) if iso else None
    out = {"dir": DIR, "mode": cfg.get("mode", "browser"), "disc": disc, "disc_path": iso,
           "has_web": os.path.exists(web), "has_exe": os.path.exists(exe), "built": None,
           "pieces": 0, "pieces_total": PIECES, "browser": cfg.get("browser", "msedge"), "scale": cfg.get("scale", "3"), "keys": read_keys(),
           "key_defaults": KEY_DEFAULTS, "version": LAUNCHER_VERSION, "dir_found": os.path.isdir(DIR), "game_running": port_open(GAME_PORT)}
    if out["has_web"]:
        out["built"] = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(web)))
    if disc:
        bad = disc["game_id"] is None or disc["region"] != "NTSC-U" or disc["game_id"] != WANT_ID or disc["contents"] != "ok"
        out["disc_ok"] = not bad
    else:
        out["disc_ok"] = False
    if out["has_web"]:
        out["state"] = "ready"
    elif build_running() and os.path.isdir(DIR):
        out["state"] = "building"
        out["pieces"] = pieces_done()
    elif disc and not out["disc_ok"]:
        out["state"] = "wrong"
        if disc["game_id"] is None:
            out["reason"] = "damaged"
        elif disc["region"] != "NTSC-U" or disc["game_id"] != WANT_ID:
            out["reason"] = "region"
        else:
            out["reason"] = "modded" if disc["contents"] == "modified" else "damaged"
    else:
        out["state"] = "setup"
    return out


# ------------------------------------------------------------------ actions
def port_open(port):
    s = socket.socket()
    s.settimeout(0.3)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except Exception:
        return False
    finally:
        s.close()


def win_open(url, app=False, prefer=None):
    """Open a URL in Windows (from WSL). Prefers Edge, then Chrome, then the default browser."""
    flag = ["--app=" + url, "--window-size=1296,839"] if app else [url]
    order = ["msedge", "chrome"]
    if prefer in order:
        order.remove(prefer)
        order.insert(0, prefer)
    if prefer == "default" and not app:
        order = []
    for exe in order:
        try:
            r = subprocess.run(["cmd.exe", "/c", "start", "", exe] + flag, capture_output=True, timeout=10, cwd="/mnt/c")
            if r.returncode == 0:
                return exe
        except Exception:
            pass
    if not app:
        try:
            subprocess.run(["cmd.exe", "/c", "start", "", url], capture_output=True, timeout=10, cwd="/mnt/c")
            return "default"
        except Exception:
            pass
    return None


def saves_dir():
    """Folder for the PC window's memory card. Next to the disc in C:\\p3fes when that exists (easy to find and back up)."""
    d = "/mnt/c/p3fes/saves" if os.path.isdir("/mnt/c/p3fes") else os.path.expanduser("~/p3fes-saves")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = os.path.expanduser("~/p3fes-saves")
        os.makedirs(d, exist_ok=True)
    return d


def display_env():
    """Environment for the PC window. WSL2 with WSLg has a display already; WSL1 needs an X server
    on Windows (VcXsrv, see docs/windows-build.md). Returns (env, problem or None)."""
    env = dict(os.environ)
    if os.path.isdir("/mnt/wslg"):
        return env, None
    if not port_open(6000):
        return env, "No display found. Start VcXsrv first (see docs/windows-build.md), then try again."
    # Keys: use the launcher's own file, not a keys.txt that happens to sit in the game folder.
    # Edit ~/.p3fes-keys.txt to remap (lines like "cross = K"; see docs/controls.md). Empty means the default layout.
    kp = KEYS_FILE
    if not os.path.exists(kp):
        try:
            write_keys(dict(KEY_DEFAULTS))
        except Exception:
            pass
    env["PS2_KEYS"] = kp
    env["DISPLAY"] = "127.0.0.1:0"
    env["SDL_VIDEODRIVER"] = "x11"
    env.pop("WAYLAND_DISPLAY", None)
    env.pop("XDG_RUNTIME_DIR", None)
    return env, None


def play(mode):
    st = get_state()
    if st["state"] != "ready":
        return {"ok": False, "msg": "The game is not installed yet."}
    if mode == "exe":
        if not st["has_exe"]:
            return {"ok": False, "msg": "The PC window version is not built yet."}
        cmd = [os.path.join(DIR, "build", "native-" + NAME, "ps2run"), os.path.join(DIR, "games", NAME, "disc", "SLUS_216.21"),
               "--disc", os.path.join(DIR, "games", NAME, "disc.iso"), "--window",
               "--memcard", os.path.join(saves_dir(), "Mcd001.ps2")]
        if any(c.poll() is None and "ps2run" in str(c.args[0]) for c in children):
            return {"ok": False, "msg": "The PC window is already running. Close it first (two would overwrite each other's saves)."}
        env, problem = display_env()
        if problem:
            return {"ok": False, "msg": problem}
        children.append(subprocess.Popen(cmd, cwd=DIR, env=env))
        return {"ok": True, "msg": "Started the PC window. Its memory card is in " + saves_dir() + ". If none appears, check VcXsrv is running."}
    if not port_open(GAME_PORT):
        cmd = [sys.executable, "scripts/serve.py", "build/web-" + NAME, "games/%s/disc.iso" % NAME]
        children.append(subprocess.Popen(cmd, cwd=DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for _ in range(30):
            if port_open(GAME_PORT):
                break
            time.sleep(0.2)
    pref = load_cfg().get("browser", "msedge")
    scale = load_cfg().get("scale", "3")
    how = win_open("http://localhost:%d/?PS2_SCALE=%s" % (GAME_PORT, scale), prefer=pref)
    return {"ok": True, "msg": "Opened in " + (how or "your browser") if how else "Open http://localhost:%d/ in Chrome or Edge." % GAME_PORT}


# ------------------------------------------------------------------ http
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/state":
            last_ping[0] = time.time()
            return self.send(200, get_state())
        if self.path == "/api/report":
            return self.send(200, {"text": report()})
        if self.path == "/api/bye":
            bye_time[0] = time.time()
            return self.send(200, {"ok": True})
        if self.path == "/api/ping":
            last_ping[0] = time.time()
            return self.send(200, {"ok": True})
        p = "index.html" if self.path in ("/", "") else self.path.lstrip("/").split("?")[0]
        f = os.path.normpath(os.path.join(UI, p))
        if not f.startswith(UI) or not os.path.isfile(f):
            return self.send(404, {"error": "not found"})
        ct = {"html": "text/html; charset=utf-8", "css": "text/css", "js": "text/javascript", "svg": "image/svg+xml"}.get(f.rsplit(".", 1)[-1], "application/octet-stream")
        with open(f, "rb") as fh:
            self.send(200, fh.read(), ct)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            data = {}
        if self.path == "/api/mode" and data.get("mode") in ("browser", "exe"):
            c = load_cfg()
            c["mode"] = data["mode"]
            save_cfg(c)
            return self.send(200, {"ok": True})
        if self.path == "/api/browser" and data.get("browser") in ("msedge", "chrome", "default"):
            c = load_cfg()
            c["browser"] = data["browser"]
            save_cfg(c)
            return self.send(200, {"ok": True})
        if self.path == "/api/scale" and data.get("scale") in ("1", "2", "3"):
            c = load_cfg()
            c["scale"] = data["scale"]
            save_cfg(c)
            return self.send(200, {"ok": True})
        if self.path == "/api/keys" and isinstance(data.get("map"), dict):
            m = {k: str(v) for k, v in data["map"].items() if k in KEY_ROWS and KEY_OK.match(str(v))}
            try:
                write_keys(m)
                return self.send(200, {"ok": True, "keys": read_keys()})
            except Exception as e:
                return self.send(200, {"ok": False, "msg": "Could not save: %s" % e})
        if self.path == "/api/play":
            return self.send(200, play(data.get("mode") or load_cfg().get("mode", "browser")))
        self.send(404, {"error": "not found"})


def watchdog():
    # Quit when the window says goodbye and does not come back within 10 seconds (a page reload comes back at once),
    # or after 30 minutes of silence (a hidden window slows its timers, so this must be long).
    while True:
        time.sleep(3)
        now = time.time()
        if bye_time[0] and bye_time[0] > last_ping[0] and now - bye_time[0] > 10:
            os._exit(0)
        if last_ping[0] and now - last_ping[0] > 1800:
            os._exit(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8630)
    ap.add_argument("--no-window", action="store_true", help="only run the server (open the address yourself)")
    a = ap.parse_args()
    url = "http://127.0.0.1:%d/" % a.port
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    except OSError:
        # already running: just open another window onto it
        print("The launcher is already running; opening its window.")
        if not a.no_window:
            win_open(url, app=True)
        return
    print("Launcher running at", url, "(closing its window stops it)")
    threading.Thread(target=watchdog, daemon=True).start()
    if not a.no_window:
        how = win_open(url, app=True)
        if not how:
            print("Could not open a window. Open", url, "in Chrome or Edge.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
