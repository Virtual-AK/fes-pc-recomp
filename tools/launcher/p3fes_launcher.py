#!/usr/bin/env python3
"""Persona 3 FES launcher: a small local server plus an app window (Edge or Chrome in --app mode).

Run inside Ubuntu (WSL):  python3 p3fes_launcher.py
It reads what the installer left behind, shows the Home screen, and starts the game.
Nothing from the game is read except the disc's SYSTEM.CNF line (to check the version).
Standard library only.
"""
import argparse, bisect, glob, io, math, wave, urllib.request, json, os, re, shlex, shutil, socket, struct, subprocess, sys, threading, time, urllib.parse, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, "ui")
DIR = os.environ.get("P3F_DIR", os.path.expanduser("~/ps2-web-recomp"))
NAME = "p3fes"
GAME_PORT = 8620
SERVER_PORT = [8630]
WINCWD = "/mnt/c" if os.path.isdir("/mnt/c") else None   # cmd.exe wants a Windows-side folder to start in
CARD_BYTES = 8650752
CARD_MAGIC = b"Sony PS2 Memory Card Format "
CFG = os.path.expanduser("~/.p3fes-launcher.json")
LAUNCHER_VERSION = "0.49"
WANT_ID = "SLUS_216.21"          # SLUS-21621, Persona 3 FES (USA)
PIECES = 337                     # pieces in a full browser build (estimate for the progress bar)
state_lock = threading.Lock()
last_ping = [0.0]
bye_time = [0.0]
game_keep = [0.0]   # the browser game uses this server for card sync and autosave: stay alive while it is in use


game_seen = [0.0]   # when the browser game last talked to this server


def keep_game_alive():
    game_keep[0] = time.time() + 1800
children = []
serving = [None]   # which build our game server is serving
MOD_NAME = "p3fesmod"


KEY_ROWS = ["cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2", "start", "select"]
KEY_DEFAULTS = {"cross": "K", "circle": "L", "square": "J", "triangle": "I", "l1": "Q", "r1": "E", "l2": "1", "r2": "3",
                "start": "Return", "select": "Backspace"}
KEY_OK = re.compile(r"^([A-Za-z0-9]|Up|Down|Left|Right|Return|Backspace|Space|Left Shift|Right Shift|Left Ctrl|Tab|Keypad [0-9]|none)$")
KEYS_FILE = os.path.expanduser("~/.p3fes-keys.txt")
# controller buttons for the PC window (lines "pad.NAME = BUTTON" in the same file, read by ps2run_padremap_patch.py; SDL button names)
PAD_ROWS = ["cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2", "l3", "r3", "start", "select", "up", "down", "left", "right"]
PAD_DEFAULTS = {"cross": "a", "circle": "b", "square": "x", "triangle": "y", "l1": "leftshoulder", "r1": "rightshoulder",
                "l2": "lefttrigger", "r2": "righttrigger", "l3": "leftstick", "r3": "rightstick", "start": "start", "select": "back",
                "up": "dpup", "down": "dpdown", "left": "dpleft", "right": "dpright"}
PAD_OK = re.compile(r"^(a|b|x|y|back|guide|start|leftstick|rightstick|leftshoulder|rightshoulder|dpup|dpdown|dpleft|dpright|lefttrigger|righttrigger|none)$")


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


def read_pad():
    m = dict(PAD_DEFAULTS)
    try:
        with open(KEYS_FILE) as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if "=" in line:
                    a, b = [x.strip() for x in line.split("=", 1)]
                    a = a.lower()
                    b = b.lower()
                    if a.startswith("pad.") and a[4:] in m and PAD_OK.match(b):
                        m[a[4:]] = b
    except Exception:
        pass
    return m


def write_keys(m, pad=None):
    """Write the keys file: keyboard keys that differ from the default, then controller buttons that differ (pad=None keeps the ones already saved)."""
    if pad is None:
        pad = read_pad()
    lines = ["# Persona 3 FES launcher: PC window keys and controller buttons. Only the ones that differ from the default are listed.",
             "# Change them in the launcher (Settings > Controls and Controller) or add lines such as:  cross = K   pad.cross = b  (see docs/controls.md)"]
    for k in KEY_ROWS:
        v = m.get(k, KEY_DEFAULTS[k])
        if v != KEY_DEFAULTS[k] and KEY_OK.match(v):
            lines.append("%s = %s" % (k, v))
    for k in PAD_ROWS:
        v = pad.get(k, PAD_DEFAULTS[k])
        if v != PAD_DEFAULTS[k] and PAD_OK.match(v):
            lines.append("pad.%s = %s" % (k, v))
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
        "widescreen: %s   essential mods mask: %s   file mods: %s" % ("on" if load_cfg().get("widescreen") else "off", packed_mask(), "on" if overlay_file() else "none"),
    ])


BUG_EMAIL = "kingbackup1876@gmail.com"   # where Help > Bug Report sends mail (the maintainer's second address)


def bug_mail_urls():
    """(mailto link, Gmail compose link) for a bug report: a few lines to fill in, then the launcher report (no disc data, no saves)."""
    subject = "P3FES launcher bug report (version %s)" % LAUNCHER_VERSION
    body = "What went wrong:\n\n\nWhat I was doing when it happened:\n\n\nWhat I expected to happen:\n\n\n----- launcher report (made by the launcher) -----\n" + report() + "\n"
    q = urllib.parse.quote
    mailto = "mailto:%s?subject=%s&body=%s" % (BUG_EMAIL, q(subject, safe=""), q(body.replace("\n", "\r\n"), safe=""))
    gmail = "https://mail.google.com/mail/?view=cm&fs=1&to=%s&su=%s&body=%s" % (q(BUG_EMAIL, safe=""), q(subject, safe=""), q(body, safe=""))
    return mailto, gmail


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
    chosen = load_cfg().get("iso")
    if chosen and os.path.isfile(chosen):
        return chosen
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


THEMES_ALL = ("blue", "pink", "reload", "moon", "dawn", "seal", "daybreak", "horizon", "ceremony", "eclipse", "golden", "bloodmoon", "lagoon", "persona1", "persona2is", "persona2ep", "persona5", "persona6", "twelve")


def theme_now(cfg):
    t = cfg.get("theme", "blue")
    if t == "twelve" and not cfg.get("journey"):
        return "blue"
    return t if t in THEMES_ALL else "blue"


def mods_state():
    return {"direct": os.path.exists(os.path.join(DIR, "build", "web-" + MOD_NAME, "ps2web.html")), "direct_on": direct_on(), "direct_win": bool(win_mod_exe()), "has_winexe": bool(win_exe()), "check": load_cfg().get("mod_check"), "overlay": bool(overlay_path()), "files": lm_state(), "packed": packed_state()}


# ------------------------------------------------------------------ loose-file mods
# A mod is a folder of replacement files laid out like the game (DATA/, BTL/ ...). Added mods are kept in C:\\p3fes\\mods\\<id>\\files,
# and the enabled ones are merged into mods\\active.ovl, which the browser game's server lays over the disc (docs/mod-folder-plan.md).
lm_work = {"busy": False, "msg": ""}
lm_cache = {}
LM_ID = re.compile(r"^[a-z0-9_-]{1,60}$")
PACKED_ID = re.compile(r"^[a-z0-9]{1,30}$")


def lm_dir():
    d = os.path.join(os.path.dirname(saves_dir()), "mods")
    os.makedirs(d, exist_ok=True)
    return d


def lm_load():
    try:
        with open(os.path.join(lm_dir(), "mods.json")) as f:
            return json.load(f)
    except Exception:
        return []


def lm_save(lst):
    p = os.path.join(lm_dir(), "mods.json")
    with open(p + ".tmp", "w") as f:
        json.dump(lst, f, indent=1)
    os.replace(p + ".tmp", p)


def lm_state():
    mine = set((packed_cfg().get("lm") or {}).values())   # file mods that belong to Essential Mods / Cheats are managed there
    lst = [m for m in lm_load() if m.get("id") not in mine]
    return {"list": lst, "busy": lm_work["busy"], "msg": lm_work["msg"], "on": sum(1 for m in lst if m.get("enabled")),
            "serve_ok": serve_has_overlay()}


def serve_has_overlay():
    try:
        return "ps2-overlay" in open(os.path.join(DIR, "scripts", "serve.py")).read()
    except Exception:
        return False


def lm_modmap():
    sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
    import p3fes_modmap
    return p3fes_modmap


def lm_locate(iso):
    key = (iso, os.path.getsize(iso), os.path.getmtime(iso))
    if lm_cache.get("key") != key:
        lm_cache["loc"] = lm_modmap().locate(iso)
        lm_cache["key"] = key
    return lm_cache["loc"]


def lm_rebuild(iso, loc):
    """Merge the enabled mods (the one higher in the list wins where two change the same thing) into active.ovl, or remove it when none are enabled."""
    M = lm_modmap()
    ovl = os.path.join(lm_dir(), "active.ovl")
    merged = {}
    for m in reversed(lm_load()):            # the list is shown with the highest priority on top; apply from the lowest up so it wins
        if m.get("enabled") and LM_ID.match(m.get("id", "")):
            for it in M.plan(iso, os.path.join(lm_dir(), m["id"], "files"), loc=loc):
                if it["ok"]:
                    merged.pop(it["key"], None)
                    merged[it["key"]] = it
    if not merged:
        if os.path.exists(ovl):
            os.remove(ovl)
        try:
            os.remove(os.path.join(lm_dir(), "active.pokes"))
        except OSError:
            pass
        return 0
    M.write_overlay(list(merged.values()), os.path.getsize(iso), ovl, iso)
    lm_write_pokes(M, iso, loc, os.path.join(lm_dir(), "active.pokes"))
    return len(merged)


def lm_write_pokes(M, iso, loc, path):
    """A moved file also needs the game's own file table changed (see table_pokes in p3fes_modmap.py). Writes ADDR=VALUE,... for the PC window, or removes the file."""
    text = ""
    try:
        moves = list(getattr(M, "MOVES", []))
        if moves and hasattr(M, "table_pokes"):
            ent = (loc[0] if loc else {}).get("/SLUS_216.21")
            program = b""
            if ent:
                with open(iso, "rb") as f:
                    f.seek(ent[0])
                    program = f.read(ent[1])
            pokes, notes = M.table_pokes(program, moves)
            text = ",".join("%08X=%08X" % (a, v) for a, v in pokes)
            lm_work["pokes"] = notes
    except Exception:
        text = ""
    try:
        if text:
            with open(path, "w") as f:
                f.write(text)
        elif os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def lm_pokes_text():
    try:
        with open(os.path.join(lm_dir(), "active.pokes")) as f:
            t = f.read().strip()
        return t if re.match(r"^[0-9A-Fa-f]{8}=[0-9A-Fa-f]{8}(,[0-9A-Fa-f]{8}=[0-9A-Fa-f]{8})*$", t) else ""
    except OSError:
        return ""


def lm_extract_zip(zpath, dest):
    total = 0
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            if info.is_dir():
                continue
            if name.startswith("/") or ".." in name.split("/") or ":" in name.split("/")[0]:
                raise ValueError("The zip has an unsafe path (%s)." % name[:60])
            total += info.file_size
            if total > 4 * 1024 ** 3:
                raise ValueError("The zip is larger than 4 GB when unpacked.")
            target = os.path.join(dest, *name.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out, 1 << 20)


def lm_kind(path):
    """What was added, for the mod list: FOLDER, ZIP, 7Z or RAR (by content, not by name)."""
    if os.path.isdir(path):
        return "FOLDER"
    try:
        with open(path, "rb") as f:
            head = f.read(8)
    except Exception:
        return "ARCHIVE"
    return "ZIP" if head[:2] == b"PK" else "7Z" if head[:2] == b"7z" else "RAR" if head[:4] == b"Rar!" else "ARCHIVE"


def lm_archive_tool():
    for n in ("7z", "7zz", "7za", "7zr", "unrar", "bsdtar"):
        t = shutil.which(n)
        if t:
            return n, t
    return None, None


def lm_extract_archive(apath, dest):
    """Unpack a .zip, .7z or .rar (found by what is inside the file, not its name). zip uses Python; 7z and rar use 7-Zip, unrar or bsdtar if installed."""
    with open(apath, "rb") as f:
        head = f.read(8)
    if head[:2] == b"PK":
        return lm_extract_zip(apath, dest)
    kind = "7z" if head[:6] == b"7z\xbc\xaf\x27\x1c" else "rar" if head[:4] == b"Rar!" else None
    if not kind:
        raise ValueError("That file is not a .zip, .7z or .rar.")
    name, tool = lm_archive_tool()
    if not name:
        raise ValueError("To open .%s files, install 7-Zip once in Ubuntu: sudo apt install p7zip-full p7zip-rar. Then add the mod again." % kind)
    os.makedirs(dest, exist_ok=True)
    if name == "unrar":
        cmd = [tool, "x", "-y", "-idq", apath, dest + "/"]
    elif name == "bsdtar":
        cmd = [tool, "-xf", apath, "-C", dest]
    else:
        cmd = [tool, "x", "-y", "-o" + dest, "--", apath]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout).strip().splitlines()[-1:] or [""]
        raise ValueError("Could not unpack it (%s). %s" % (name, tail[0][:120]))
    total, root = 0, os.path.realpath(dest)
    for dp, dn, fn in os.walk(dest):
        for x in dn + fn:
            q = os.path.join(dp, x)
            if os.path.islink(q) or not os.path.realpath(q).startswith(root + os.sep):
                raise ValueError("The archive has an unsafe path (%s)." % x[:60])
        for x in fn:
            total += os.path.getsize(os.path.join(dp, x))
    if total > 4 * 1024 ** 3:
        raise ValueError("The archive is larger than 4 GB when unpacked.")


def lm_add_work(path):
    tmp = os.path.join(lm_dir(), "_new")
    try:
        iso = find_iso()
        if not iso:
            lm_work["msg"] = "Your disc was not found. Finish setup first."
            return
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        lm_work["msg"] = "Reading the mod…"
        if os.path.isdir(path):
            shutil.copytree(path, os.path.join(tmp, "src"))
        else:
            lm_extract_archive(path, os.path.join(tmp, "src"))
        lm_work["msg"] = "Checking it against your disc (this can take a minute the first time)…"
        loc = lm_locate(iso)
        M = lm_modmap()
        root = M.mod_root(os.path.join(tmp, "src"), loc[0])
        if not root:
            lm_work["msg"] = "No game folders (like DATA or BTL) were found in that mod, so it is not a loose-file mod this launcher can use."
            return
        base = re.sub(r"[^a-z0-9_-]+", "-", os.path.splitext(os.path.basename(path.rstrip("/")))[0].lower()).strip("-")[:40] or "mod"
        lst = lm_load()
        ids = {m["id"] for m in lst}
        mid, n = base, 2
        while mid in ids or os.path.exists(os.path.join(lm_dir(), mid)):
            mid = "%s-%d" % (base, n)
            n += 1
        os.makedirs(os.path.join(lm_dir(), mid))
        shutil.move(root, os.path.join(lm_dir(), mid, "files"))
        items = [i for i in M.plan(iso, os.path.join(lm_dir(), mid, "files"), loc=loc) if "/" in i["rel"] or i["ok"]]   # ignore Package.xml, Preview.png and the like
        fit = sum(1 for i in items if i["ok"])
        lst.insert(0, {"id": mid, "kind": lm_kind(path), "name": os.path.splitext(os.path.basename(path.rstrip("/")))[0][:60], "enabled": fit > 0, "fit": fit, "total": len(items),
                    "skipped": [("%s: %s" % (i["rel"], i["why"]))[:140] for i in items if not i["ok"]][:6]})
        lm_save(lst)
        lm_work["msg"] = "Building…"
        lm_rebuild(iso, loc)
        kind = lst[0]["kind"]
        lm_work["msg"] = ("Added (%s). %d of %d files fit your disc." % (kind, fit, len(items))) if fit else "Added (%s), but none of its files fit your disc." % kind
    except Exception as e:
        lm_work["msg"] = "Could not add that mod: %s" % e
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        lm_work["busy"] = False


def lm_change_work(mid, remove, up=False):
    try:
        iso = find_iso()
        lst = lm_load()
        if remove:
            lst = [m for m in lst if m["id"] != mid]
            shutil.rmtree(os.path.join(lm_dir(), mid), ignore_errors=True)
        elif up:
            ix = next((k for k, m in enumerate(lst) if m["id"] == mid), None)
            if ix:
                lst[ix - 1], lst[ix] = lst[ix], lst[ix - 1]
        else:
            for m in lst:
                if m["id"] == mid:
                    m["enabled"] = not m.get("enabled")
        lm_save(lst)
        if iso:
            lm_work["msg"] = "Updating…"
            lm_rebuild(iso, lm_locate(iso))
        lm_work["msg"] = "Done."
    except Exception as e:
        lm_work["msg"] = "Could not do that: %s" % e
    finally:
        lm_work["busy"] = False


def lm_start(target, *args):
    if lm_work["busy"]:
        return {"ok": False, "msg": "Still working on the last change."}
    lm_work["busy"] = True
    lm_work["msg"] = ""
    threading.Thread(target=target, args=args, daemon=True).start()
    return {"ok": True, "msg": "Working…"}



# ------------------------------------------------------------------ essential mods
# Community mods that ship with a switch in the launcher. Code mods (.pnach files) are baked into ONE extra build of the game, each with its own
# on/off switch (tools/p3fes_packed_build.py, docs/packed-mods.md); file mods (Fast Start, cheat sheets ...) are ordinary FILE MODS that can be
# toggled instantly. The mod files are downloaded from the authors' GameBanana pages onto this computer and are never part of our repository.
packed_build = {"proc": None, "log": os.path.expanduser("~/.p3fes-packed-build.log")}


def packed_registry():
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "packed_mods.json")) as f:
            return json.load(f)
    except Exception:
        return []


def packed_dir():
    d = os.path.join(os.path.dirname(saves_dir()), "packed")
    os.makedirs(d, exist_ok=True)
    return d


def packed_cfg():
    c = load_cfg().get("packed")
    return c if isinstance(c, dict) else {}


def packed_src(mid):
    """The mod whose download folder holds this mod's files (Always Critical comes from the Always Cut-In download)."""
    reg = next((r for r in packed_registry() if r["id"] == mid), None)
    return (reg or {}).get("source") or mid


def packed_name_ok(reg, filename):
    """Registry "match" / "exclude": a mod can own only some of the .pnach files in a download, chosen by a word in the file name."""
    low = filename.lower()
    if reg.get("match") and not any(t in low for t in reg["match"]):
        return False
    return not any(t in low for t in (reg.get("exclude") or []))


def packed_pnach(mid):
    reg = next((r for r in packed_registry() if r["id"] == mid), {})
    if reg.get("pnach"):   # a bundled cheat: the patch text is part of packed_mods.json (the builder writes it to a file)
        return ["(bundled)"]
    out = []
    for dp, dn, fn in os.walk(os.path.join(packed_dir(), packed_src(mid))):
        out += [os.path.join(dp, x) for x in sorted(fn) if x.lower().endswith(".pnach") and packed_name_ok(reg, x)]
    return out


def packed_gb(mid):
    """GameBanana page number of a mod's download: the player's own link, else the one in packed_mods.json ("gb"), else 0."""
    src = packed_src(mid)
    g = packed_cfg().get("gb")
    if isinstance(g, dict) and g.get(src):
        return int(g[src])
    reg = next((r for r in packed_registry() if r["id"] == src), None)
    return int((reg or {}).get("gb") or 0)


def packed_levels(r):
    return r.get("levels") if isinstance(r.get("levels"), list) else []


def packed_level(r):
    """The chosen strength of a cheat with levels (EXP x3 / x5 / x10, run speed ...): the saved value, else the default, else the first."""
    lv = packed_levels(r)
    if not lv:
        return ""
    want = (packed_cfg().get("level") or {}).get(r["id"])
    ok = [x["v"] for x in lv]
    return want if want in ok else (r.get("level_default") if r.get("level_default") in ok else ok[0])


def packed_set_level(mid, v):
    reg = next((r for r in packed_registry() if r["id"] == mid), None)
    if not reg or v not in [x["v"] for x in packed_levels(reg)]:
        return {"ok": False, "msg": "Unknown choice."}
    c = load_cfg()
    p = c.get("packed") if isinstance(c.get("packed"), dict) else {}
    p.setdefault("level", {})[mid] = v
    c["packed"] = p
    save_cfg(c)
    return {"ok": True, "msg": "%s: %s. It applies the next time you press Play." % (reg["name"], next(x["label"] for x in packed_levels(reg) if x["v"] == v))}


def packed_cheat_pokes(built=None):
    """PS2_POKE text for the code cheats that have levels: ADDR=VALUE for each one that is built in and on (the game keeps the strength in memory)."""
    if built is None:
        built, legacy = packed_built()
        if legacy:
            return ""
    out = []
    for r in packed_registry():
        if r.get("kind") == "code" and packed_levels(r) and r["id"] in built and packed_active(r):
            v = packed_level(r)
            val = next(x["poke"] for x in packed_levels(r) if x["v"] == v)
            out.append("%s=%s" % (r["level_addr"].zfill(8).upper(), val.zfill(8).upper()))
    return ",".join(out)


def packed_built():
    """-> ({id: bit} of the code mods inside the mod build, legacy). A build made before switches existed holds Direct Commands, always on."""
    g = os.path.join(DIR, "games", MOD_NAME)
    try:
        with open(os.path.join(g, "variants.txt")) as f:
            built = {}
            for ln in f:
                t = ln.split()
                if len(t) == 3 and t[0] == "M" and t[2].isdigit():
                    built[t[1]] = int(t[2])
            return built, False
    except OSError:
        pass
    old = os.path.exists(os.path.join(DIR, "build", "web-" + MOD_NAME, "ps2web.html")) or bool(win_mod_exe())
    return ({"directcmd": 0} if old else {}), True


def packed_on(mid):
    on = packed_cfg().get("on") or {}
    if mid in on:
        return bool(on[mid])
    if mid == "directcmd":   # on by default, as before there was a list
        return load_cfg().get("direct_on", True) is not False
    return False


def packed_set_on(mid, flag):
    c = load_cfg()
    p = c.get("packed") if isinstance(c.get("packed"), dict) else {}
    p.setdefault("on", {})[mid] = bool(flag)
    c["packed"] = p
    save_cfg(c)


def packed_mask():
    """PS2_MODS for the mod build: the switch bit of every code mod that is both built in and turned on (0 when the build is an old one)."""
    built, legacy = packed_built()
    if legacy:
        return 0
    m = 0
    for r in packed_registry():
        if r.get("kind") == "code" and r["id"] in built and packed_active(r):
            m |= 1 << built[r["id"]]
    return m


def packed_active(r):
    """Is this code mod switched on? A mod with "follows": "widescreen" has no switch of its own: it is on when Settings > Widescreen is on."""
    if r.get("follows") == "widescreen":
        if not load_cfg().get("widescreen") or r["id"] in ws_parts_off():
            return False
        return (not r.get("default_off")) or r["id"] in ws_parts_on()
    return packed_on(r["id"])


def ws_parts_line(key):
    """Research: a line like P3F_WS_OFF=ws2,ws5 (or P3F_WS_ON=ws7) in ~/.p3fes-window-env, no rebuild needed."""
    try:
        with open(os.path.expanduser("~/.p3fes-window-env")) as f:
            for ln in f:
                if ln.strip().startswith(key + "="):
                    return {t.strip().lower() for t in ln.split("=", 1)[1].split(",") if t.strip()}
    except OSError:
        pass
    return set()


def ws_parts_off():
    """Parts of the widescreen patch left off (P3F_WS_OFF=ws2,ws5)."""
    return ws_parts_line("P3F_WS_OFF")


def ws_parts_on():
    """Parts that are off by default and are switched on (P3F_WS_ON=ws7)."""
    return ws_parts_line("P3F_WS_ON")


def ws_menus_status():
    """Settings > Widescreen: is the community patch for menus and the HUD in the mod build? -> built | needbuild | nofile"""
    built, legacy = packed_built()
    if "widescreen" in built and not legacy:
        return "built"
    return "needbuild" if packed_pnach("widescreen") else "nofile"


def packed_wanted():
    """Should Play use the mod build?"""
    built, legacy = packed_built()
    return packed_on("directcmd") if legacy else packed_mask() != 0


def packed_lm(mid):
    lmid = (packed_cfg().get("lm") or {}).get(mid)
    return next((m for m in lm_load() if m["id"] == lmid), None) if lmid else None


def packed_build_status():
    pr = packed_build["proc"]
    state = "idle"
    if pr is not None:
        state = "running" if pr.poll() is None else ("done" if pr.returncode == 0 else "failed")
    last = ""
    try:
        with open(packed_build["log"], errors="replace") as f:
            lines = [x.strip() for x in f.read()[-4000:].splitlines() if x.strip()]
        last = lines[-1][:140] if lines else ""
    except OSError:
        pass
    return {"state": state, "last": last}


def packed_state():
    built, legacy = packed_built()
    cfg = packed_cfg()
    rows, need = [], []
    for r in packed_registry():
        if r.get("hidden"):
            continue
        row = {"id": r["id"], "name": r["name"], "kind": r.get("kind", "code"), "by": r.get("by", ""), "desc": r.get("desc", ""),
               "cheat": bool(r.get("cheat")),
               "url": ("https://gamebanana.com/mods/%d" % packed_gb(r["id"])) if packed_gb(r["id"]) else ""}
        if packed_levels(r):
            row["levels"] = [{"v": x["v"], "label": x["label"]} for x in packed_levels(r)]
            row["level"] = packed_level(r)
        row["bundled"] = bool(r.get("pnach"))
        if row["kind"] == "code":
            have = len(packed_pnach(r["id"]))
            row.update({"have": have > 0 or (legacy and r["id"] == "directcmd" and r["id"] in built), "built": r["id"] in built, "on": packed_on(r["id"])})
            if r.get("with_files"):
                lmm = packed_lm(r["id"])
                row["files_fit"] = ("%s of %s" % (lmm.get("fit"), lmm.get("total"))) if lmm else ""
            if row["on"] and have and r["id"] not in built:
                need.append(r["name"])
        else:
            m = packed_lm(r["id"])
            row.update({"have": bool(m), "built": bool(m), "on": bool(m and m.get("enabled")), "fit": (m or {}).get("fit"), "total": (m or {}).get("total")})
        rows.append(row)
    return {"list": rows, "legacy": legacy, "busy": lm_work["busy"], "msg": lm_work["msg"], "build": packed_build_status(), "need_build": need,
            "auto": {"busy": auto["busy"], "state": auto["state"], "step": auto["step"], "msg": auto["msg"], "last": auto_last() if auto["busy"] or auto["state"] == "failed" else "", "need": essentials_need()},
            "win_stale": win_mod_stale(), "mask": packed_mask(), "mod_page": os.path.exists(os.path.join(DIR, "build", "web-" + MOD_NAME, "ps2web.html")), "has_winexe": bool(win_exe()),
            "win_mod": bool(win_mod_exe()), "dub": dub_state()}


# ------------------------------------------------------------------ voice language (Settings > Audio)
DUB_ID = "undub"   # the Japanese Dub file mod (GameBanana 292547): a hidden entry of packed_mods.json, downloaded when Japanese is chosen


def dub_state():
    m = packed_lm(DUB_ID)
    return {"have": bool(m), "on": bool(m and m.get("enabled")), "busy": lm_work["busy"], "msg": lm_work["msg"],
            "fit": (m or {}).get("fit"), "total": (m or {}).get("total"), "gb": packed_gb(DUB_ID) or 0}


def dub_work(download):
    """Thread: download the Japanese Dub when it is not there, then switch it on."""
    try:
        if download:
            gb = packed_gb(DUB_ID)
            if not gb:
                lm_work["msg"] = "The Japanese Dub has no GameBanana link."
                return
            packed_get_work(DUB_ID, gb)         # downloads and adds it (off); sets lm_work["msg"] and clears busy
            lm_work["busy"] = True
        m = packed_lm(DUB_ID)
        if not m:
            lm_work["busy"] = False
            return
        if not m.get("enabled"):
            lm_work["msg"] = "Switching to the Japanese voices…"
            lm_change_work(m["id"], False)      # switches it on and rebuilds the disc overlay; clears busy
        m = packed_lm(DUB_ID) or {}
        note = ""
        if m.get("fit") != m.get("total"):
            note = " Only %s of %s of its files fit your disc, so some voices stay English." % (m.get("fit"), m.get("total"))
        lm_work["msg"] = "Japanese voices are on. They apply the next time you press Play." + note
    except Exception as e:
        lm_work["msg"] = "Could not switch the voices: %s" % str(e)[:100]
    finally:
        lm_work["busy"] = False


def dub_set(lang):
    m = packed_lm(DUB_ID)
    if lang == "ja":
        if not find_iso():
            return {"ok": False, "msg": "Finish the setup first: the Japanese voices are laid over your own disc."}
        if m and m.get("enabled"):
            return {"ok": True, "msg": ""}
        r = lm_start(dub_work, not m)
        if r["ok"] and not m:
            r["msg"] = "Downloading the Japanese voices (about 500 MB). This takes a few minutes."
        return r
    if lang == "en":
        if not (m and m.get("enabled")):
            return {"ok": True, "msg": ""}
        return lm_start(lm_change_work, m["id"], False)
    return {"ok": False, "msg": "Unknown language."}


def packed_link(mid, text):
    mid = packed_src(mid)
    mt = re.search(r"gamebanana\.com/mods/(\d+)", text or "")
    c = load_cfg()
    p = c.get("packed") if isinstance(c.get("packed"), dict) else {}
    g = p.setdefault("gb", {})
    if not text:
        g.pop(mid, None)
    elif mt:
        g[mid] = int(mt.group(1))
    else:
        return {"ok": False, "msg": "That is not a GameBanana mod link. It looks like https://gamebanana.com/mods/123456."}
    c["packed"] = p
    save_cfg(c)
    return {"ok": True, "msg": "Link saved." if text else "Link removed."}


def gb_download_file(f, dest, limit):
    """Download one file listed on a GameBanana page (only from gamebanana.com). Returns an error text, or None."""
    url = str(f.get("_sDownloadUrl", ""))
    if not gb_host_ok(url):
        return "GameBanana gave an address that is not on gamebanana.com, so it was not used."
    req = urllib.request.Request(url, headers={"User-Agent": "p3fes-launcher/1.0"})
    got = 0
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as out:
        if not gb_host_ok(r.geturl()):
            return "The download moved to an address that is not on gamebanana.com, so it was stopped."
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            got += len(b)
            if got > limit:
                return "A download is larger than allowed, so it was stopped."
            out.write(b)
    return None


def packed_add_files(mid, reg, archive):
    """Add an archive as the file mod of packed mod mid (off at first). Returns True when a file mod was made."""
    old = packed_lm(mid)
    if old:   # replace an earlier copy
        try:
            lm_change_work(old["id"], True)
        except Exception:
            pass
    before = {m["id"] for m in lm_load()}
    lm_add_work(archive)
    now = [m for m in lm_load() if m["id"] not in before]
    if not now:
        return False
    c = load_cfg()
    p = c.get("packed") if isinstance(c.get("packed"), dict) else {}
    p.setdefault("lm", {})[mid] = now[0]["id"]
    c["packed"] = p
    save_cfg(c)
    lst = lm_load()
    for m in lst:
        if m["id"] == now[0]["id"]:
            m["name"] = reg["name"]
            m["enabled"] = False   # essential mods start off
    lm_save(lst)
    try:
        lm_rebuild(find_iso(), lm_locate(find_iso()))
    except Exception:
        pass
    return True


def packed_pick_archive(reg, ar):
    """The archive to use from a GameBanana page: the first whose name has every word of reg["pick"] and none of reg["avoid"], else the first."""
    pick = [w.lower() for w in (reg.get("pick") or [])]
    avoid = [w.lower() for w in (reg.get("avoid") or [])]
    for f in ar:
        low = str(f.get("_sFile", "")).lower()
        if all(w in low for w in pick) and not any(w in low for w in avoid):
            return f
    return ar[0]


def packed_get_work(mid, gbid):
    tmp = os.path.join(packed_dir(), "_dl")
    try:
        reg = next((r for r in packed_registry() if r["id"] == mid), None)
        if not reg:
            lm_work["msg"] = "Unknown mod."
            return
        lm_work["msg"] = "Asking GameBanana for the files…"
        info = gb_get("%s/Mod/%d/ProfilePage" % (GB_API, gbid))
        files = [f for f in (info.get("_aFiles") or []) if f.get("_sDownloadUrl")]
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        if reg.get("kind") == "code":
            pn = [f for f in files if str(f.get("_sFile", "")).lower().endswith(".pnach")]
            ar = [f for f in files if str(f.get("_sFile", "")).lower().endswith(GB_EXTS)]
            pick = (pn or ([packed_pick_archive(reg, ar)] if ar else []))[:6]
            data_zip = None
            if not pick:
                lm_work["msg"] = "That page has no .pnach, .zip, .7z or .rar file I can use."
                return
            found = []
            for k, f in enumerate(pick):
                name = re.sub(r"[^A-Za-z0-9 ._-]+", "", str(f.get("_sFile", "file"))) or "file"
                dest = os.path.join(tmp, "%d_%s" % (k, name))
                lm_work["msg"] = "Downloading %s…" % name[:50]
                err = gb_download_file(f, dest, 200 * 1024 ** 2)
                if err:
                    lm_work["msg"] = err
                    return
                if name.lower().endswith(".pnach"):
                    found.append(dest)
                else:
                    lm_work["msg"] = "Unpacking…"
                    x = os.path.join(tmp, "x%d" % k)
                    lm_extract_archive(dest, x)
                    if reg.get("with_files"):
                        data_zip = dest
                    for dp, dn, fn in os.walk(x):
                        found += [os.path.join(dp, y) for y in sorted(fn) if y.lower().endswith(".pnach")]
            if not found:
                lm_work["msg"] = "There was no .pnach file in it, so nothing was added."
                return
            out = os.path.join(packed_dir(), mid)
            shutil.rmtree(out, ignore_errors=True)
            os.makedirs(out)
            used = set()
            for k, src in enumerate(found[:12]):
                base = re.sub(r"^\d+_", "", os.path.basename(src))
                nm = base if base not in used else "%d_%s" % (k, base)
                used.add(nm)
                shutil.copyfile(src, os.path.join(out, nm))
            lm_work["msg"] = "Downloaded %d patch file%s for %s. Press SET UP ESSENTIAL MODS to put it into the game." % (len(found[:12]), "" if len(found) == 1 else "s", reg["name"])
            if data_zip:   # the same download also carries game files: lay them over the disc as a file mod
                packed_add_files(mid, reg, data_zip)
                lm_work["msg"] += " Its game files were added too."
            return
        ar = [f for f in files if str(f.get("_sFile", "")).lower().endswith(GB_EXTS)]
        if not ar:
            lm_work["msg"] = "That page has no .zip, .7z or .rar file I can use."
            return
        f = packed_pick_archive(reg, ar)
        name = re.sub(r"[^A-Za-z0-9 ._-]+", "", str(f.get("_sFile", "mod"))) or "mod.zip"
        dest = os.path.join(tmp, name)
        lm_work["msg"] = "Downloading %s…" % name[:50]
        err = gb_download_file(f, dest, 2 * 1024 ** 3)
        if err:
            lm_work["msg"] = err
            return
        if packed_add_files(mid, reg, dest):
            lm_work["msg"] = "%s downloaded. Turn it on with its ON button." % reg["name"]
    except Exception as e:
        lm_work["msg"] = "Could not download that mod: %s" % str(e)[:100]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        lm_work["busy"] = False


def packed_toggle(mid, flag):
    reg = next((r for r in packed_registry() if r["id"] == mid), None)
    if not reg:
        return {"ok": False, "msg": "Unknown mod."}
    if reg.get("kind") == "code":
        packed_set_on(mid, flag)
        built, legacy = packed_built()
        m = packed_lm(mid) if reg.get("with_files") else None
        if m and bool(m.get("enabled")) != bool(flag):   # its game files follow the switch
            lm_start(lm_change_work, m["id"], False)
        if flag and mid not in built:
            return {"ok": True, "msg": "On, but it is not in the build yet. Press SET UP ESSENTIAL MODS first."}
        return {"ok": True, "msg": "%s is %s. It applies the next time you press Play." % (reg["name"], "on" if flag else "off")}
    m = packed_lm(mid)
    if not m:
        return {"ok": False, "msg": "Download it first."}
    if bool(m.get("enabled")) == bool(flag):
        return {"ok": True, "msg": ""}
    return lm_start(lm_change_work, m["id"], False)


def packed_remove(mid):
    reg = next((r for r in packed_registry() if r["id"] == mid), None)
    if not reg:
        return {"ok": False, "msg": "Unknown mod."}
    if reg.get("pnach"):
        return {"ok": False, "msg": "This one is part of the launcher, so there is nothing to remove. Turn it off instead."}
    if reg.get("kind") == "code":
        if reg.get("source") or reg.get("match") or reg.get("exclude"):   # a mod that shares its download: remove only its own files
            for f in packed_pnach(mid):
                try:
                    os.remove(f)
                except OSError:
                    pass
        else:
            shutil.rmtree(os.path.join(packed_dir(), mid), ignore_errors=True)
        m = packed_lm(mid) if reg.get("with_files") else None
        if m:
            lm_start(lm_change_work, m["id"], True)
        return {"ok": True, "msg": "Removed. The game keeps it until the next SET UP."}
    m = packed_lm(mid)
    if not m:
        return {"ok": False, "msg": "Nothing to remove."}
    return lm_start(lm_change_work, m["id"], True)


def packed_build_start():
    if packed_build["proc"] is not None and packed_build["proc"].poll() is None:
        return {"ok": False, "msg": "A build is already running."}
    script = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "p3fes_packed_build.py"))
    if not os.path.isfile(script):
        return {"ok": False, "msg": "p3fes_packed_build.py is missing from the tools folder."}
    if get_state()["state"] != "ready":
        return {"ok": False, "msg": "Finish setup first."}
    try:
        log = open(packed_build["log"], "w")
        packed_build["proc"] = subprocess.Popen([sys.executable, script, "--packed", packed_dir()], cwd=DIR, stdout=log, stderr=subprocess.STDOUT)
    except OSError as e:
        return {"ok": False, "msg": "Could not start the build: %s" % e}
    return {"ok": True, "msg": "Building. This takes a while (about as long as the first game build). You can keep using the launcher."}


# ------------------------------------------------------------------ one button: download, build, build the PC window
# "SET UP ESSENTIAL MODS" does every step that used to be separate: download the mods that have a GameBanana link (and are not cheats),
# build the essential mods game in Ubuntu (tools/p3fes_packed_build.py), then build the PC window's copy with the Visual Studio tools
# (the same steps as tools\p3fes_win_mod.bat, started through vcvars64 so nobody has to open the Native Tools prompt).
auto = {"busy": False, "state": "idle", "step": "", "msg": "", "log": os.path.expanduser("~/.p3fes-essentials.log"), "need": []}


def auto_say(step=None, msg=None):
    if step is not None:
        auto["step"] = step
    if msg is not None:
        auto["msg"] = msg


def auto_last():
    try:
        with open(auto["log"], errors="replace") as f:
            lines = [x.strip() for x in f.read()[-4000:].splitlines() if x.strip()]
        return lines[-1][:140] if lines else ""
    except OSError:
        return ""


# Patches that may be added by an update and are safe on a project folder made by an older installer (no list of applied patches):
# patch name -> (source file, text that is only there once it is applied). The installer's LATE list names the same patches.
LATE_TOOL_PATCHES = {"ps2run_logkey_patch.py": ("host/window.cpp", "SDL_WINDOWEVENT_CLOSE && g_window")}


def tool_patches_pending():
    """Tool patches listed in p3fes_install.sh that this computer's project folder has not had applied yet (a launcher update can add some)."""
    inst = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "p3fes_install.sh"))
    applied = os.path.join(DIR, ".p3fes_applied")
    try:
        txt = open(inst).read()
    except OSError:
        return []
    a = txt.find('PATCHES="')
    if a < 0 or not os.path.isdir(os.path.join(DIR, "runtime")):
        return []
    body = [x for x in txt[a + 9:txt.find('"', a + 9)].split() if x.endswith(".py")]
    try:
        have = set(open(applied).read().split())
    except OSError:      # an older installer left no list: look at the source itself, for the patches that are safe to try
        out = []
        for name, (rel, mark) in LATE_TOOL_PATCHES.items():
            try:
                if name in body and mark not in open(os.path.join(DIR, rel), errors="replace").read():
                    out.append(name)
            except OSError:
                pass
        return out
    return [x for x in body if x not in have]


def tools_newer_than(path):
    """A tool patch changed the project source after this file was made, so it has to be made again. Looks at the list of applied patches
    and at the runner's own source files (an older install has no list, but the patched source still carries its date)."""
    try:
        mine = os.path.getmtime(path)
    except OSError:
        return False
    for rel in (".p3fes_applied", "host/window.cpp", "runtime/src/system.cpp"):
        try:
            if mine < os.path.getmtime(os.path.join(DIR, rel)):
                return True
        except OSError:
            pass
    return False


def essentials_need():
    """What is left to do, as short phrases: downloads with a known link, a build of the essential mods game, a build of the PC window."""
    out = []
    built, legacy = packed_built()
    for r in packed_registry():
        if r.get("hidden") or r.get("pnach") or r.get("source") or r.get("kind") not in ("code", "files", "cheat"):   # "source": it comes with another mod's download
            continue
        if r.get("kind") == "code" and not packed_pnach(r["id"]) and packed_gb(r["id"]) and not (legacy and r["id"] == "directcmd" and r["id"] in built):
            out.append("download " + r["name"])
        elif r.get("kind") in ("files", "cheat") and not packed_lm(r["id"]) and packed_gb(r["id"]):
            out.append("download " + r["name"])
    code_have = [r for r in packed_registry() if r.get("kind") == "code" and packed_pnach(r["id"])]
    if code_have and tool_patches_pending():
        out.insert(0, "update the game tools")
    if code_have and (legacy or any(r["id"] not in built for r in code_have) or tools_newer_than(os.path.join(DIR, "games", MOD_NAME, "variants.txt")) or tool_patches_pending()):
        out.append("build the essential mods game")
    if win_exe() and code_have and (not win_mod_exe() or win_mod_stale()):
        out.append("build the PC window")
    return out


def vcvars_win():
    """Windows path of vcvars64.bat from the Visual Studio Build Tools that p3fes_win_setup.bat installed, or None."""
    vsw = "/mnt/c/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe"
    if not os.path.isfile(vsw):
        return None
    try:
        out = subprocess.run([vsw, "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Llvm.Clang",
                              "Microsoft.VisualStudio.Component.VC.CMake.Project", "-property", "installationPath"],
                             capture_output=True, text=True, timeout=60, cwd=WINCWD).stdout.strip().splitlines()
    except Exception:
        return None
    base = (out[0].strip() if out else "")
    return (base + "\\VC\\Auxiliary\\Build\\vcvars64.bat") if base else None


def auto_run(cmd, logf, cwd=None):
    """Run a command with its output going to the log; returns the exit code."""
    return subprocess.run(cmd, cwd=cwd, stdout=logf, stderr=subprocess.STDOUT).returncode


def essentials_work():
    try:
        tools = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        with open(auto["log"], "w") as logf:
            need = essentials_need()
            auto["need"] = need
            if not need:
                auto.update(state="done", step="", msg="Everything is already set up.")
                return
            # 1. downloads
            missing = []
            for r in packed_registry():
                if r.get("hidden") or r.get("pnach") or r.get("source") or r.get("kind") not in ("code", "files", "cheat"):
                    continue
                have = bool(packed_pnach(r["id"])) if r.get("kind") == "code" else bool(packed_lm(r["id"]))
                if have:
                    continue
                gb = packed_gb(r["id"])
                if not gb:
                    missing.append(r["name"])
                    continue
                auto_say("Downloading " + r["name"], "")
                logf.write("download %s (GameBanana %d)\n" % (r["name"], gb)); logf.flush()
                lm_work["busy"] = True
                packed_get_work(r["id"], gb)       # sets lm_work["msg"], clears busy
                logf.write(lm_work.get("msg", "") + "\n"); logf.flush()
            # 1b. new tool patches (a launcher update can add some; the PC window gets them from the patched project folder)
            if tool_patches_pending() and get_state()["state"] == "ready":
                auto_say("Updating the game tools", "")
                inst = os.path.join(tools, "p3fes_install.sh")
                logf.write("== applying new tool patches: %s\n" % ", ".join(tool_patches_pending())); logf.flush()
                if auto_run(["bash", inst, "--new-patches"], logf, DIR) != 0:
                    logf.flush()
                    try:
                        why = " | ".join(l.strip() for l in open(auto["log"], errors="replace").read().splitlines()[-6:] if l.strip())[-300:]
                    except OSError:
                        why = ""
                    auto.update(state="failed", msg="A new tool patch did not fit. " + why + " (full log: ~/.p3fes-essentials.log; send it to us)")
                    return
            # 2. the essential mods game, in Ubuntu
            built, legacy = packed_built()
            code_have = [r for r in packed_registry() if r.get("kind") == "code" and packed_pnach(r["id"])]
            if code_have and (legacy or any(r["id"] not in built for r in code_have) or tools_newer_than(os.path.join(DIR, "games", MOD_NAME, "variants.txt"))):
                auto_say("Building the essential mods game (takes a while)", "")
                if get_state()["state"] != "ready":
                    auto.update(state="failed", msg="Finish the setup first.")
                    return
                script = os.path.join(tools, "p3fes_packed_build.py")
                if not os.path.isfile(script):
                    auto.update(state="failed", msg="p3fes_packed_build.py is missing from the tools folder.")
                    return
                logf.write("== building the essential mods game\n"); logf.flush()
                if auto_run([sys.executable, script, "--packed", packed_dir()], logf, DIR) != 0:
                    auto.update(state="failed", msg="The build stopped. The last lines are in ~/.p3fes-essentials.log.")
                    return
            # 3. the PC window's copy
            code_have = [r for r in packed_registry() if r.get("kind") == "code" and packed_pnach(r["id"])]
            if win_exe() and code_have and (not win_mod_exe() or win_mod_stale()):
                auto_say("Building the PC window version (takes a while)", "")
                vc = vcvars_win()
                if not vc:
                    auto.update(state="failed", msg="The Visual Studio build tools were not found. Run tools\\p3fes_win_setup.bat once, then try again.")
                    return
                wb = to_win(os.path.join(tools, "p3fes_win_mod.bat"))
                if not wb or not WINCWD:
                    auto.update(state="failed", msg="Could not find tools\\p3fes_win_mod.bat for Windows.")
                    return
                wrap = os.path.join(os.path.dirname(saves_dir()), "_essentials_win.bat")
                with open(wrap, "w", newline="") as f:
                    f.write("@echo off\r\ncall \"%s\" >nul\r\nif errorlevel 1 exit /b 1\r\ncall \"%s\"\r\nexit /b %%errorlevel%%\r\n" % (vc, wb))
                logf.write("== building the PC window version\n"); logf.flush()
                if auto_run(["cmd.exe", "/c", to_win(wrap)], logf, WINCWD) != 0:
                    auto.update(state="failed", msg="The PC window build stopped. The last lines are in ~/.p3fes-essentials.log.")
                    return
            note = ""
            if missing:
                note = " No GameBanana link yet for: %s (use ADD LINK on its row)." % ", ".join(missing)
            auto.update(state="done", step="", msg="Done." + note)
    except Exception as e:
        auto.update(state="failed", msg="Stopped: %s" % str(e)[:140])
    finally:
        auto["busy"] = False


def essentials_start():
    if auto["busy"] or (packed_build["proc"] is not None and packed_build["proc"].poll() is None):
        return {"ok": False, "msg": "This is already running."}
    if lm_work["busy"]:
        return {"ok": False, "msg": "Still working on the last change."}
    auto.update(busy=True, state="running", step="Starting", msg="")
    threading.Thread(target=essentials_work, daemon=True).start()
    return {"ok": True, "msg": "Working. You can keep using the launcher; the steps are listed under the buttons."}


# ------------------------------------------------------------------ GameBanana browsing
# Lists the Persona 3 FES mods on GameBanana (its public API) and installs one into FILE MODS when the player asks. Nothing is shipped or cached on disk;
# the list is read when the screen is opened, the mod file is downloaded straight from gamebanana.com and then goes through the normal add flow.
GB_GAME = 8502
GB_API = "https://gamebanana.com/apiv11"
GB_PAGE = 6
gb_cache = {"t": 0.0, "mods": [], "err": ""}
gb_lock = threading.Lock()


def gb_host_ok(url):
    try:
        h = urllib.parse.urlparse(url)
        return h.scheme == "https" and (h.hostname == "gamebanana.com" or (h.hostname or "").endswith(".gamebanana.com"))
    except Exception:
        return False


def gb_get(url, timeout=25):
    if not gb_host_ok(url):
        raise ValueError("Not a GameBanana address.")
    req = urllib.request.Request(url, headers={"User-Agent": "p3fes-launcher/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(8 * 1024 * 1024).decode("utf-8", "replace"))


def gb_fetch_all():
    mods, page = [], 1
    while page <= 14:
        url = "%s/Mod/Index?_nPage=%d&_nPerpage=50&_aFilters%%5BGeneric_Game%%5D=%d&_sSort=Generic_Newest" % (GB_API, page, GB_GAME)
        d = gb_get(url)
        recs = d.get("_aRecords") or []
        for r in recs:
            try:
                mods.append({"id": int(r["_idRow"]), "name": str(r.get("_sName", "?"))[:90], "by": str((r.get("_aSubmitter") or {}).get("_sName", ""))[:40],
                             "likes": int(r.get("_nLikeCount") or 0), "views": int(r.get("_nViewCount") or 0), "date": int(r.get("_tsDateAdded") or 0),
                             "cat": str((r.get("_aRootCategory") or {}).get("_sName", ""))[:30]})
            except (KeyError, TypeError, ValueError):
                continue
        meta = d.get("_aMetadata") or {}
        if len(recs) < 50 or meta.get("_bIsComplete"):
            break
        page += 1
    return mods


def packed_gb_ids():
    """GameBanana pages of the mods that Essential Mods and Cheats manage (built-in numbers and the player's own links)."""
    ids = {int(r["gb"]) for r in packed_registry() if r.get("gb")}
    g = packed_cfg().get("gb")
    if isinstance(g, dict):
        ids |= {int(v) for v in g.values() if str(v).isdigit()}
    return ids


def gb_view(q="", sort="new", page=0, refresh=False):
    with gb_lock:
        if refresh or not gb_cache["mods"] or time.time() - gb_cache["t"] > 900:
            try:
                gb_cache["mods"] = gb_fetch_all()
                gb_cache["t"] = time.time()
                gb_cache["err"] = "" if gb_cache["mods"] else "GameBanana returned no mods."
            except Exception as e:
                gb_cache["err"] = "Could not reach GameBanana (%s)." % str(e)[:80]
        hide = packed_gb_ids()
        mods = [x for x in gb_cache["mods"] if x.get("id") not in hide]
        err = gb_cache["err"]
    q = (q or "").strip().lower()
    if q:
        mods = [x for x in mods if q in x["name"].lower() or q in x["by"].lower() or q in x["cat"].lower()]
    mods.sort(key=lambda x: -x["likes"] if sort == "liked" else -x["views"] if sort == "viewed" else -x["date"])
    pages = max(1, (len(mods) + GB_PAGE - 1) // GB_PAGE)
    page = max(0, min(int(page or 0), pages - 1))
    return {"ok": not err or bool(gb_cache["mods"]), "err": err, "total": len(mods), "page": page, "pages": pages, "q": q, "sort": sort,
            "mods": mods[page * GB_PAGE:(page + 1) * GB_PAGE]}


GB_EXTS = (".zip", ".7z", ".rar")


def gb_text(html, limit=30000):
    """A mod's description (HTML) as plain text."""
    from html.parser import HTMLParser

    class T(HTMLParser):
        def __init__(self):
            super().__init__()
            self.out, self.skip = [], 0

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style"):
                self.skip += 1
            elif tag in ("br", "p", "div", "li", "h1", "h2", "h3", "h4", "tr"):
                self.out.append("\n")

        def handle_endtag(self, tag):
            if tag in ("script", "style") and self.skip:
                self.skip -= 1
            elif tag in ("p", "div", "li", "h1", "h2", "h3", "h4"):
                self.out.append("\n")

        def handle_data(self, d):
            if not self.skip:
                self.out.append(d)
    t = T()
    try:
        t.feed(str(html or ""))
    except Exception:
        pass
    txt = re.sub(r"[ \t\xa0]+", " ", "".join(t.out))
    txt = re.sub(r"\n\s*\n\s*\n+", "\n\n", txt).strip()
    return txt[:limit] + ("…" if len(txt) > limit else "")


def gb_full_desc(info):
    """The whole description: the body text plus the extra sections GameBanana shows beneath it."""
    parts = []
    body = gb_text(info.get("_sText") or "", 60000)
    short = gb_text(info.get("_sDescription") or "", 2000)
    if short and short not in body:
        parts.append(short)
    if body:
        parts.append(body)
    ai = info.get("_aAdditionalInfo")
    if isinstance(ai, dict):
        for k, v in ai.items():
            v = gb_text(v if isinstance(v, str) else json.dumps(v), 4000)
            if v:
                parts.append(str(k).strip("_").replace("_", " ").upper() + ": " + v)
    cr = []
    for g in (info.get("_aCredits") or []):
        if isinstance(g, dict):
            names = ", ".join(str(a.get("_sRole", "") + (" - " if a.get("_sRole") else "") + a.get("_sName", "")) for a in (g.get("_aAuthors") or []) if isinstance(a, dict))
            if names:
                cr.append(str(g.get("_sGroupName", "Credits")) + ": " + names)
    if cr:
        parts.append("\n".join(cr))
    return "\n\n".join(parts) or "The author did not write a description."


def gb_mod(mid):
    """What the preview screen shows: description, pictures and the files that can be installed."""
    info = gb_get("%s/Mod/%d/ProfilePage" % (GB_API, mid))
    imgs = []
    for im in ((info.get("_aPreviewMedia") or {}).get("_aImages") or []):
        base, f = str(im.get("_sBaseUrl", "")), str(im.get("_sFile530") or im.get("_sFile") or "")
        if base and f and gb_host_ok(base + "/" + f):
            imgs.append(base + "/" + f)
    files = []
    for f in (info.get("_aFiles") or []):
        name = str(f.get("_sFile", ""))
        files.append({"id": int(f.get("_idRow") or 0), "name": name[:80], "size": int(f.get("_nFilesize") or 0), "desc": str(f.get("_sDescription", ""))[:120],
                      "date": int(f.get("_tsDateAdded") or 0), "ok": name.lower().endswith(GB_EXTS) and bool(f.get("_sDownloadUrl"))})
    return {"ok": True, "id": mid, "name": str(info.get("_sName", "?"))[:90], "by": str((info.get("_aSubmitter") or {}).get("_sName", ""))[:40],
            "version": str(info.get("_sVersion", ""))[:20], "likes": int(info.get("_nLikeCount") or 0), "views": int(info.get("_nViewCount") or 0),
            "desc": gb_full_desc(info), "images": imgs[:8], "files": files[:12]}


gb_img_cache = {}


def gb_image(url):
    if url in gb_img_cache:
        return gb_img_cache[url]
    if not gb_host_ok(url):
        raise ValueError("Not a GameBanana address.")
    req = urllib.request.Request(url, headers={"User-Agent": "p3fes-launcher/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        ct = r.headers.get("Content-Type", "")
        if not gb_host_ok(r.geturl()) or not ct.startswith("image/") or "svg" in ct:
            raise ValueError("Not an image.")
        data = r.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError("Image too large.")
    if len(gb_img_cache) > 24:
        gb_img_cache.pop(next(iter(gb_img_cache)))
    gb_img_cache[url] = (ct, data)
    return ct, data


def gb_install_work(mid, fid=0):
    tmp = os.path.join(lm_dir(), "_dl")
    if mid in packed_gb_ids():
        lm_work["msg"] = "That mod is managed in Mods > Essential Mods or Cheats. Use SET UP ESSENTIAL MODS there."
        lm_work["busy"] = False
        return
    try:
        lm_work["msg"] = "Asking GameBanana for the files…"
        info = gb_get("%s/Mod/%d/ProfilePage" % (GB_API, mid))
        title = str(info.get("_sName", "mod"))
        files = [f for f in (info.get("_aFiles") or []) if str(f.get("_sFile", "")).lower().endswith(GB_EXTS) and f.get("_sDownloadUrl")]
        if not files:
            kinds = sorted({os.path.splitext(str(f.get("_sFile", "")))[1].lower() for f in (info.get("_aFiles") or [])} - {""})
            lm_work["msg"] = "This mod has no .zip, .7z or .rar file%s, so it cannot be added here." % (" (it has: %s)" % ", ".join(kinds) if kinds else "")
            return
        if fid:
            pick = [x for x in files if int(x.get("_idRow") or 0) == fid]
            if not pick:
                lm_work["msg"] = "That file is no longer listed on GameBanana."
                return
            files = pick
        f = files[0]
        size = int(f.get("_nFilesize") or 0)
        if size > 2 * 1024 ** 3:
            lm_work["msg"] = "That download is over 2 GB, which is too large for this."
            return
        if not gb_host_ok(str(f["_sDownloadUrl"])):
            lm_work["msg"] = "GameBanana gave an address that is not on gamebanana.com, so it was not used."
            return
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        ext = os.path.splitext(str(f["_sFile"]).lower())[1]
        dest = os.path.join(tmp, (re.sub(r"[^A-Za-z0-9 ._-]+", "", title).strip()[:50] or "mod") + ext)
        lm_work["msg"] = "Downloading %s…" % str(f["_sFile"])[:50]
        req = urllib.request.Request(str(f["_sDownloadUrl"]), headers={"User-Agent": "p3fes-launcher/1.0"})
        got = 0
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as out:
            if not gb_host_ok(r.geturl()):
                lm_work["msg"] = "The download moved to an address that is not on gamebanana.com, so it was stopped."
                return
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                got += len(b)
                if got > 2 * 1024 ** 3:
                    raise ValueError("the download is larger than 2 GB")
                out.write(b)
                lm_work["msg"] = "Downloading %s… %d MB" % (str(f["_sFile"])[:40], got >> 20)
        extra = ""
        lm_add_work(dest)
        lm_work["msg"] = lm_work["msg"] + extra
        return
    except Exception as e:
        lm_work["msg"] = "Could not download that mod: %s" % str(e)[:100]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        lm_work["busy"] = False


def lm_pick(kind):
    if kind == "zip":
        ps = ("Add-Type -AssemblyName System.Windows.Forms; $d = New-Object System.Windows.Forms.OpenFileDialog; $d.Title = 'Choose a mod (.zip, .7z or .rar)'; "
              "$d.Filter = 'Mod archive (*.zip;*.7z;*.rar)|*.zip;*.7z;*.rar'; if ($d.ShowDialog() -eq 'OK') { $d.FileName }")
    else:
        ps = ("Add-Type -AssemblyName System.Windows.Forms; $d = New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description = 'Choose the mod folder'; "
              "if ($d.ShowDialog() -eq 'OK') { $d.SelectedPath }")
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True, timeout=600, cwd=WINCWD)
        win = r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else ""
        path = subprocess.run(["wslpath", "-u", win], capture_output=True, text=True, timeout=5).stdout.strip() if win else ""
    except Exception:
        return None, "Could not open the file window."
    if not path:
        return None, "Nothing chosen."
    if not (os.path.isdir(path) if kind != "zip" else os.path.isfile(path)):
        return None, "Could not read that."
    return path, ""


def installer_running():
    try:
        out = subprocess.run(["pgrep", "-af", "p3fes_install.sh"], capture_output=True, text=True, timeout=5).stdout
        return any("p3fes_launcher" not in l and "pgrep" not in l for l in out.splitlines())
    except Exception:
        return False


def build_log():
    """Last three compiled files, for the setup screen."""
    p = os.path.join(DIR, "build", "web-" + NAME, ".ninja_log")
    try:
        with open(p) as f:
            lines = [l.rstrip("\n").split("\t") for l in f if not l.startswith("#")]
        n = len(lines)
        return ["[%d/%d] %s" % (n - 2 + k, PIECES, os.path.basename(l[3])) for k, l in enumerate(lines[-3:]) if len(l) > 3]
    except Exception:
        return []


def web_has_card_sync():
    try:
        with open(os.path.join(DIR, "build", "web-" + NAME, "ps2web.html"), "r", errors="ignore") as f:
            t = f.read()
            return "ps2-card-sync" in t or "CS_URL" in t
    except Exception:
        return False


def get_state():
    cfg = load_cfg()
    web = os.path.join(DIR, "build", "web-" + NAME, "ps2web.html")
    exe = os.path.join(DIR, "build", "native-" + NAME, "ps2run")
    iso = find_iso()
    disc = check_disc(iso) if iso else None
    out = {"dir": DIR, "mode": cfg.get("mode", "browser"), "disc": disc, "disc_path": iso,
           "has_web": os.path.exists(web), "has_exe": os.path.exists(exe), "has_winexe": bool(win_exe()), "built": None,
           "pieces": 0, "pieces_total": PIECES, "browser": cfg.get("browser", "msedge"), "scale": cfg.get("scale", "3"), "theme": theme_now(cfg), "journey": bool(cfg.get("journey")), "widescreen": bool(cfg.get("widescreen")), "ws_menus": ws_menus_status(), "skip_launcher": bool(cfg.get("skip_launcher")), "close_on_play": cfg.get("close_on_play", True) is not False, "update_repo": cfg.get("update_repo", "") or DEFAULT_UPDATE_REPO, "speedrun": bool(cfg.get("speedrun")), "vol_master": vol_get(cfg, "vol_master"), "vol_fx": vol_get(cfg, "vol_fx"), "vol_music": vol_get(cfg, "vol_music"), "vol_voice": vol_get(cfg, "vol_voice"), "vol_launcher": vol_get({"v": cfg.get("vol_launcher", 70)}, "v"), "keys": read_keys(),
           "key_defaults": KEY_DEFAULTS, "pad": read_pad(), "pad_defaults": PAD_DEFAULTS, "card": card_info(), "autosaves": as_state(), "pc_autosaves": pc_as_state(), "card_sync": web_has_card_sync(), "version": LAUNCHER_VERSION, "dir_found": os.path.isdir(DIR), "game_running": port_open(GAME_PORT), "playing": playing_now(), "music_hold": music_hold(), "midnight_date": load_cfg().get("midnight_play", ""),
           "installing": installer_running(), "mods": mods_state(), "tools_done": os.path.exists(os.path.join(DIR, ".tools-ok")) or os.path.exists(web), "log": build_log()}
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
        out["tools_done"] = True
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


def win_open(url, app=False, prefer=None, size=None):
    """Open a URL in Windows (from WSL). Prefers Edge, then Chrome, then the default browser."""
    # cmd.exe treats & as "run another command", so escape it. Unescaped, the URL was cut at the first &,
    # the leftover failed, and the loop then opened every browser in turn.
    cu = url.replace("&", "^&")
    flag = ["--app=" + cu, "--start-maximized"] if app else [cu]
    if app and size:
        flag = ["--app=" + cu, "--window-size=%d,%d" % size]
    order = ["msedge", "chrome"]
    if prefer in order:
        order.remove(prefer)
        order.insert(0, prefer)
    if prefer == "default" and not app:
        order = []
    for exe in order:
        try:
            r = subprocess.run(["cmd.exe", "/c", "start", "", exe] + flag, capture_output=True, timeout=10, cwd=WINCWD)
            if r.returncode == 0:
                return exe
        except Exception:
            pass
    if not app:
        try:
            subprocess.run(["cmd.exe", "/c", "start", "", cu], capture_output=True, timeout=10, cwd=WINCWD)
            return "default"
        except Exception:
            pass
    return None


GUIDE_SITES = {   # where the Guides screen may send you: a search on each site, nothing is copied into the launcher
    "wiki": "https://megamitensei.fandom.com/wiki/Special:Search?query=",
    "faqs": "https://gamefaqs.gamespot.com/search?game=",
    "web": "https://duckduckgo.com/?q=",
}


def guide_url(src, q):
    """The search page for a guide topic, or None if the source is not one of ours."""
    base = GUIDE_SITES.get(src)
    q = " ".join(str(q or "").split())[:120]
    if not base or not q:
        return None
    return base + urllib.parse.quote_plus(q)


DEFAULT_UPDATE_REPO = "Virtual-AK/fes-pc-recomp"   # where updates come from unless the player enters another address
UPDATE_DIR = os.path.dirname(os.path.abspath(__file__))
UPDATE_BACKUP = os.path.expanduser("~/.p3fes-launcher-backup")


def update_repo_ok(r):
    return bool(re.match(r"^[A-Za-z0-9_.-]{1,60}/[A-Za-z0-9_.-]{1,100}$", str(r or "")))


def ver_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v)))


def update_parse_version(src):
    m = re.search(r'^LAUNCHER_VERSION\s*=\s*"([^"]+)"', src, re.M)
    return m.group(1) if m else ""


def update_http(url, limit):
    req = urllib.request.Request(url, headers={"User-Agent": "p3fes-launcher-updater"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError("The download was larger than expected.")
    return data


def update_check():
    repo = load_cfg().get("update_repo", "") or DEFAULT_UPDATE_REPO
    out = {"ok": True, "configured": bool(repo), "repo": repo, "current": LAUNCHER_VERSION, "latest": "", "newer": False}
    if not repo:
        return out
    if not update_repo_ok(repo):
        return {"ok": False, "configured": True, "repo": repo, "current": LAUNCHER_VERSION, "msg": "The update source must look like owner/name."}
    last = ""
    for branch in ("main", "master"):
        try:
            src = update_http("https://raw.githubusercontent.com/%s/%s/tools/launcher/p3fes_launcher.py" % (repo, branch), 8 * 1024 * 1024).decode("utf-8", "replace")
            v = update_parse_version(src)
            if v:
                out.update(latest=v, branch=branch, newer=ver_tuple(v) > ver_tuple(LAUNCHER_VERSION))
                return out
        except Exception as e:
            last = str(e)[:100]
    return {"ok": False, "configured": True, "repo": repo, "current": LAUNCHER_VERSION, "msg": "Could not read the latest version from %s (%s)." % (repo, last or "no launcher file found")}


def update_apply(zip_bytes, dest_dir, backup_dir, current):
    """Install the launcher files from a repository zip: only the launcher .py and its ui folder, checked before anything is replaced."""
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = [n for n in zf.namelist() if not n.endswith("/")]
    root = names[0].split("/")[0] if names else ""
    want = {}
    for n in names:
        rel = n[len(root) + 1:] if n.startswith(root + "/") else ""
        if not rel or ".." in rel.split("/") or rel.startswith("/"):
            continue
        if rel == "tools/launcher/p3fes_launcher.py":
            want[rel] = (n, os.path.join(dest_dir, "p3fes_launcher.py"))
        elif rel.startswith("tools/launcher/ui/"):
            want[rel] = (n, os.path.join(dest_dir, "ui", rel[len("tools/launcher/ui/"):]))
    if "tools/launcher/p3fes_launcher.py" not in want:
        raise ValueError("The download does not contain the launcher.")
    newpy = zf.read(want["tools/launcher/p3fes_launcher.py"][0])
    compile(newpy.decode("utf-8"), "p3fes_launcher.py", "exec")   # refuse a file that does not even parse
    ver = update_parse_version(newpy.decode("utf-8"))
    if not ver:
        raise ValueError("The downloaded launcher has no version.")
    bdir = os.path.join(backup_dir, current)
    os.makedirs(bdir, exist_ok=True)
    cur_py = os.path.join(dest_dir, "p3fes_launcher.py")
    if os.path.isfile(cur_py):
        shutil.copy2(cur_py, os.path.join(bdir, "p3fes_launcher.py"))
    cur_ui = os.path.join(dest_dir, "ui")
    if os.path.isdir(cur_ui):
        shutil.copytree(cur_ui, os.path.join(bdir, "ui"), dirs_exist_ok=True)
    n_files = 0
    for rel, (full, dst) in sorted(want.items(), key=lambda kv: kv[0] == "tools/launcher/p3fes_launcher.py"):   # the .py goes last
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".new"
        with open(tmp, "wb") as f:
            f.write(zf.read(full))
        os.replace(tmp, dst)
        n_files += 1
    return ver, n_files


def update_install():
    chk = update_check()
    if not chk.get("ok"):
        return chk
    if not chk.get("newer"):
        return {"ok": True, "installed": False, "msg": "You already have the latest version (%s)." % LAUNCHER_VERSION}
    try:
        data = update_http("https://codeload.github.com/%s/zip/refs/heads/%s" % (chk["repo"], chk["branch"]), 60 * 1024 * 1024)
        ver, n = update_apply(data, UPDATE_DIR, UPDATE_BACKUP, LAUNCHER_VERSION)
    except Exception as e:
        return {"ok": False, "msg": "The update did not install (%s). Nothing was changed." % str(e)[:120]}
    return {"ok": True, "installed": True, "version": ver, "msg": "Updated to %s (%d files). Restart the launcher to use it. The old version is kept in %s." % (ver, n, os.path.join(UPDATE_BACKUP, LAUNCHER_VERSION))}


GUIDE100_FILE = os.path.expanduser("~/.p3fes-guide100.json")   # tick boxes of the built-in 100% guide
GUIDE100_ID = re.compile(r"^[a-z0-9._-]{1,40}$")

def guide100_load():
    try:
        with open(GUIDE100_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        ids = [x for x in d.get("done", []) if isinstance(x, str) and GUIDE100_ID.match(x)]
        return sorted(set(ids))
    except Exception:
        return []

def guide100_apply(data):
    """data: {} (just read) | {id, on} (tick or untick one box) | {reset: true}. Returns the ticked ids."""
    done = set(guide100_load())
    if data.get("reset"):
        done = set()
    elif isinstance(data.get("id"), str) and GUIDE100_ID.match(data["id"]):
        if data.get("on"):
            if len(done) < 2000:
                done.add(data["id"])
        else:
            done.discard(data["id"])
    else:
        return sorted(done)
    ids = sorted(done)
    try:
        tmp = GUIDE100_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"done": ids}, f)
        os.replace(tmp, GUIDE100_FILE)
    except Exception:
        pass
    return ids

GUIDES_DIR = os.path.expanduser("~/.p3fes-guides")   # wiki pages the player saved for offline reading
WIKI_BASES = {"mt": "https://megamitensei.fandom.com/wiki/", "sm": "https://shin-megami-tensei-persona.fandom.com/wiki/"}
GUIDE_TOOLS = {"fusion": "https://aqiu384.github.io/megaten-fusion-tool/p3f/personas"}   # community tools the Guides screen can open


def guide_scrub(html):
    """Defence in depth for saved pages (the viewer is also sandboxed): no scripts, frames or event handlers."""
    html = re.sub(r"(?is)<script\b.*?</script\s*>", "", str(html))
    html = re.sub(r"(?is)<(iframe|object|embed|form|style)\b.*?(</\1\s*>|/>)", "", html)
    html = re.sub(r"(?i)\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", html)
    html = re.sub(r"(?i)javascript:", "", html)
    return html[:3 * 1024 * 1024]


def guide_slug(title):
    return re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-")[:80] or "page"


def guide_list():
    out = []
    try:
        for f in sorted(glob.glob(os.path.join(GUIDES_DIR, "*.json"))):
            try:
                d = json.load(open(f, encoding="utf-8"))
                out.append({"slug": os.path.basename(f)[:-5], "title": str(d.get("title", ""))[:120], "saved": str(d.get("saved", ""))})
            except Exception:
                pass
    except Exception:
        pass
    out.sort(key=lambda x: x["title"].lower())
    return out


def guide_save(title, html, wiki="mt"):
    title = " ".join(str(title or "").split())[:120]
    if not title or not html:
        return {"ok": False, "msg": "Nothing to save."}
    os.makedirs(GUIDES_DIR, exist_ok=True)
    slug = guide_slug(title)
    with open(os.path.join(GUIDES_DIR, slug + ".json"), "w", encoding="utf-8") as f:
        json.dump({"title": title, "wiki": wiki if wiki in WIKI_BASES else "mt", "saved": time.strftime("%Y-%m-%d"), "html": guide_scrub(html)}, f)
    return {"ok": True, "slug": slug, "msg": "Saved for offline reading."}


def guide_get(slug):
    slug = re.sub(r"[^a-z0-9-]", "", str(slug))
    f = os.path.join(GUIDES_DIR, slug + ".json")
    if not slug or not os.path.isfile(f):
        return {"ok": False, "msg": "That page is not saved."}
    d = json.load(open(f, encoding="utf-8"))
    return {"ok": True, "title": d.get("title", ""), "html": guide_scrub(d.get("html", "")), "saved": d.get("saved", ""), "wiki": d.get("wiki", "mt")}


def guide_delete(slug):
    slug = re.sub(r"[^a-z0-9-]", "", str(slug))
    f = os.path.join(GUIDES_DIR, slug + ".json")
    if slug and os.path.isfile(f):
        os.remove(f)
    return {"ok": True}


MAXIMIZE_PS = r"""
Add-Type -TypeDefinition @'
using System; using System.Text; using System.Runtime.InteropServices;
public class W2 {
  public delegate bool EP(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EP p, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  public static int Max() {
    int n = 0;
    EnumWindows((h, l) => {
      if (!IsWindowVisible(h)) return true;
      StringBuilder t = new StringBuilder(256); StringBuilder c = new StringBuilder(256);
      GetWindowText(h, t, 256); GetClassName(h, c, 256);
      if (t.ToString().StartsWith("Launcher") && c.ToString().StartsWith("Chrome_WidgetWin")) { ShowWindow(h, 3); n++; }
      return true;
    }, IntPtr.Zero);
    return n;
  }
}
'@
$end = (Get-Date).AddSeconds(12)
$found = 0
while ((Get-Date) -lt $end -and $found -eq 0) { $found = [W2]::Max(); if ($found -eq 0) { Start-Sleep -Milliseconds 300 } }
Write-Output ('maximized windows: ' + $found)
"""


def maximize_launcher():
    """Maximize the launcher's own window (Edge and Chrome remember the last size and ignore the start flag).
    The script goes in encoded, so no quote characters get lost on the way to PowerShell."""
    import base64
    try:
        enc = base64.b64encode(MAXIMIZE_PS.encode("utf-16-le")).decode("ascii")
        r = subprocess.run(["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-EncodedCommand", enc], capture_output=True, text=True, timeout=30, cwd=WINCWD)
        with open(os.path.expanduser("~/.p3fes-maximize.log"), "w") as f:
            f.write((r.stdout or "") + (r.stderr or ""))
    except Exception:
        pass


def choose_disc():
    """Windows file dialog (from WSL via PowerShell). Returns (ok, message). A usable disc is remembered."""
    ps = ("Add-Type -AssemblyName System.Windows.Forms; $d = New-Object System.Windows.Forms.OpenFileDialog; "
          "$d.Title = 'Choose your Persona 3 FES (USA) disc image'; $d.Filter = 'Disc image (*.iso)|*.iso|All files (*.*)|*.*'; "
          "if (Test-Path 'C:\\p3fes') { $d.InitialDirectory = 'C:\\p3fes' }; if ($d.ShowDialog() -eq 'OK') { $d.FileName }")
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True, timeout=600, cwd=WINCWD)
    except Exception:
        return False, "Could not open the file window. Put your .iso in C:\\p3fes and reopen the launcher."
    win = r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else ""
    if not win:
        return False, "No file chosen."
    try:
        path = subprocess.run(["wslpath", "-u", win], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        path = ""
    if not path or not os.path.isfile(path):
        return False, "Could not read that file."
    d = check_disc(path)
    if d["game_id"] is None:
        return False, "That file is not a readable disc image."
    if d["region"] != "NTSC-U" or d["game_id"] != WANT_ID:
        return False, "That is not Persona 3 FES (USA). Choose the USA disc."
    if d["contents"] != "ok":
        return False, "That disc image is damaged or has been changed. Use an untouched copy."
    c = load_cfg()
    c["iso"] = path
    save_cfg(c)
    return True, "Disc accepted: " + os.path.basename(path)


def check_pnach(path):
    """Compare a .pnach with the boot program on the player's disc using p3fes_pnach_apply.py. Nothing is built."""
    elf = os.path.join(DIR, "games", NAME, "disc", "SLUS_216.21")
    tool = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "p3fes_pnach_apply.py"))
    res = {"file": os.path.basename(path), "fits": False, "lines": [], "verdict": ""}
    if not os.path.isfile(elf):
        res["verdict"] = "Your disc has not been unpacked yet, so there is nothing to check against. Finish setup first."
        return res
    if not os.path.isfile(tool):
        res["verdict"] = "The checking tool was not found next to the launcher folder."
        return res
    tmp = os.path.join(os.path.expanduser("~"), ".p3fes-modcheck.tmp")
    try:
        r = subprocess.run([sys.executable, tool, elf, path, "-o", tmp], capture_output=True, text=True, timeout=60)
    except Exception as e:
        res["verdict"] = "The check could not run: %s" % e
        return res
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    out = r.stdout + r.stderr
    m = re.search(r"(\d+) match, (\d+) differ", out)
    w = re.search(r"written: (\d+) \((\d+) changed a value\), outside the image: (\d+)", out)
    if not w:
        res["verdict"] = "This file could not be read as a code patch. " + (out.strip().splitlines()[-1][:120] if out.strip() else "")
        return res
    written, changed, outside = int(w.group(1)), int(w.group(2)), int(w.group(3))
    match, differ = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    res["lines"] = ["%d patch line%s apply to your program" % (written, "" if written == 1 else "s"), "%d of them change%s something" % (changed, "s" if changed == 1 else "")]
    if match + differ:
        res["lines"].append("%d of %d original-code notes match your disc" % (match, match + differ))
    else:
        res["lines"].append("This file has no original-code notes, so only the addresses were checked")
    if outside:
        res["lines"].append("%d lines point outside the game program" % outside)
    if written == 0:
        res["verdict"] = "Nothing in this file applies to the game program."
    elif differ or outside:
        res["verdict"] = "Part of this file does not fit your disc. It may be for a different version of the game."
    else:
        res["fits"] = True
        res["verdict"] = "It fits your disc."
    return res


def choose_pnach():
    ps = ("Add-Type -AssemblyName System.Windows.Forms; $d = New-Object System.Windows.Forms.OpenFileDialog; "
          "$d.Title = 'Choose a mod patch file'; $d.Filter = 'PCSX2 patch (*.pnach)|*.pnach|All files (*.*)|*.*'; "
          "if ($d.ShowDialog() -eq 'OK') { $d.FileName }")
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True, timeout=600, cwd=WINCWD)
    except Exception:
        return {"ok": False, "msg": "Could not open the file window."}
    win = r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else ""
    if not win:
        return {"ok": False, "msg": "No file chosen."}
    try:
        path = subprocess.run(["wslpath", "-u", win], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        path = ""
    if not path or not os.path.isfile(path) or os.path.getsize(path) > 5 * 1024 * 1024:
        return {"ok": False, "msg": "Could not read that file."}
    res = check_pnach(path)
    c = load_cfg()
    c["mod_check"] = res
    save_cfg(c)
    return {"ok": True, "msg": res["verdict"]}


def start_setup():
    """Runs the installer in its own console window (it may ask for the Ubuntu password once)."""
    st = get_state()
    if st["state"] == "ready":
        return {"ok": False, "msg": "The game is already installed."}
    if installer_running() or st["state"] == "building":
        return {"ok": False, "msg": "Setup is already running in its own window."}
    if not st["disc_ok"] or not st["disc_path"]:
        return {"ok": False, "msg": "Choose your disc first."}
    inst = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "p3fes_install.sh"))
    if not os.path.isfile(inst):
        return {"ok": False, "msg": "p3fes_install.sh was not found next to the launcher folder."}
    run = os.path.expanduser("~/.p3fes-setup-run.sh")
    with open(run, "w") as f:
        f.write("#!/usr/bin/env bash\necho 'Persona 3 FES setup. Leave this window open until it says Finished.'\necho\n"
                "bash %s %s\nrc=$?\necho\nif [ $rc = 0 ]; then echo 'Finished. You can close this window and press Play in the launcher.';"
                " else echo 'Setup stopped. Take a screenshot of this window and send it to us, then run SET UP again to carry on.'; fi\n"
                "read -r -p 'Press Enter to close this window.' _\n" % (shlex.quote(inst), shlex.quote(st["disc_path"])))
    try:
        subprocess.Popen(["cmd.exe", "/c", "start", "Persona 3 FES setup", "wsl.exe", "bash", run], cwd=WINCWD,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        return {"ok": False, "msg": "Could not open the setup window: %s" % e}
    return {"ok": True, "msg": "Setup is running in its own window. It may ask for your Ubuntu password once."}


def saves_dir():
    """Folder for the PC window's memory card. Next to the disc in C:\\p3fes when that exists (easy to find and back up)."""
    d = "/mnt/c/p3fes/saves" if os.path.isdir("/mnt/c/p3fes") else os.path.expanduser("~/p3fes-saves")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = os.path.expanduser("~/p3fes-saves")
        os.makedirs(d, exist_ok=True)
    return d


def overlay_path():
    """The active loose-file mod (made by p3fes_modmap.py overlay): next to the saves, in C:\\p3fes\\mods\\active.ovl. Returns None when there is none or serve.py cannot use it."""
    p = os.path.join(os.path.dirname(saves_dir()), "mods", "active.ovl")
    try:
        if not os.path.isfile(p) or "ps2-overlay" not in open(os.path.join(DIR, "scripts", "serve.py")).read():
            return None
    except Exception:
        return None
    return p


def overlay_file():
    """The active loose-file mod overlay for the PC window (no server needed), or None."""
    p = os.path.join(os.path.dirname(saves_dir()), "mods", "active.ovl")
    return p if os.path.isfile(p) else None


_flag_cache = {}


def exe_supports(exe, flag):
    """True when the program knows the command-line switch (an older build of the PC window does not and would stop).
    Asks the program itself (it prints its usage when started without a game), then falls back to searching its bytes."""
    try:
        st = os.stat(exe)
        key = (exe, st.st_mtime, st.st_size, flag)
        if key in _flag_cache:
            return _flag_cache[key]
        found = False
        try:
            r = subprocess.run([exe], capture_output=True, text=True, timeout=20, cwd=os.path.dirname(exe))
            found = flag in ((r.stdout or "") + (r.stderr or ""))
        except Exception:
            pass
        if not found:
            needle, tail = flag.encode(), b""
            with open(exe, "rb") as f:
                while True:
                    chunk = f.read(8 << 20)
                    if not chunk:
                        break
                    if needle in tail + chunk:
                        found = True
                        break
                    tail = chunk[-len(needle):]
        _flag_cache[key] = found
        return found
    except OSError:
        return False


def card_path():
    return os.path.join(saves_dir(), "Mcd001.ps2")


BK_RE = re.compile(r"^Mcd001-\d{8}-\d{6}\.ps2$")


def backups_list():
    d = os.path.join(saves_dir(), "backups")
    out = []
    if os.path.isdir(d):
        for n in sorted(os.listdir(d), reverse=True):
            if BK_RE.match(n):
                t = n[7:22]
                out.append({"name": n, "when": "%s-%s-%s %s:%s" % (t[0:4], t[4:6], t[6:8], t[9:11], t[11:13]), "size": os.path.getsize(os.path.join(d, n))})
    return out


AS_ID = re.compile(r"^\d{1,20}$")


def as_root():
    return os.path.join(saves_dir(), "autosaves")


def as_dir(key):
    return os.path.join(as_root(), re.sub(r"[^0-9A-Za-z-]", "_", key)[:80] or "x")


def as_items(d):
    out = []
    if os.path.isdir(d):
        for n in os.listdir(d):
            if n.endswith(".json") and n != "deleted.json":
                try:
                    with open(os.path.join(d, n)) as f:
                        m = json.load(f)
                    if os.path.isfile(os.path.join(d, n[:-5] + ".bin")):
                        out.append(m)
                except Exception:
                    pass
    out.sort(key=lambda m: -m["id"])
    return out


def as_deleted(d):
    try:
        with open(os.path.join(d, "deleted.json")) as f:
            return [int(i) for i in json.load(f)]
    except Exception:
        return []


def as_current_key():
    try:
        with open(os.path.join(as_root(), "current.txt")) as f:
            return f.read().strip()
    except Exception:
        return ""


def as_delete(d, i):
    for ext in (".bin", ".json"):
        try:
            os.remove(os.path.join(d, "%d%s" % (i, ext)))
        except OSError:
            pass
    gone = as_deleted(d)
    if i not in gone:
        gone.append(i)
        with open(os.path.join(d, "deleted.json"), "w") as f:
            json.dump(gone[-500:], f)


def as_state():
    """Autosaves for the build the browser game last announced (else the newest folder); the rest are counted as 'older'."""
    root = as_root()
    folders = []
    total = 0
    if os.path.isdir(root):
        for n in os.listdir(root):
            d = os.path.join(root, n)
            if os.path.isdir(d):
                items = as_items(d)
                folders.append((d, items))
                for m in items:
                    try:
                        total += os.path.getsize(os.path.join(d, "%d.bin" % m["id"]))
                    except OSError:
                        pass
    key = as_current_key()
    pick = None
    if key:
        pick = as_dir(key)
    elif folders:
        pick = max(folders, key=lambda f: f[1][0]["id"] if f[1] else 0)[0]
    cur = []
    older = 0
    for d, items in folders:
        if d == pick:
            cur = items
        else:
            older += len(items)
    lst = [{"id": m["id"], "reason": m.get("reason", ""), "time": m.get("time", 0),
            "when": time.strftime("%Y-%m-%d %H:%M", time.localtime(m.get("time", 0) / 1000)), "size": m.get("bytes", 0)} for m in cur]
    return {"list": lst, "older": older, "bytes": total}


def card_info():
    p = card_path()
    d = os.path.join(saves_dir(), "backups")
    n = len(glob.glob(os.path.join(d, "Mcd001-*.ps2"))) if os.path.isdir(d) else 0
    ok = os.path.exists(p)
    win = saves_dir()
    try:
        win = subprocess.run(["wslpath", "-w", saves_dir()], capture_output=True, text=True, timeout=5).stdout.strip() or win
    except Exception:
        pass
    bl = backups_list()
    return {"dir": win, "exists": ok, "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(p))) if ok else None,
            "backups": len(bl), "list": bl, "size": os.path.getsize(p) if ok else 0}


def pc_window_running():
    if any(c.poll() is None and "ps2run" in str(c.args[0]) for c in children):
        return True
    try:
        return subprocess.run(["pgrep", "-x", "ps2run"], capture_output=True, timeout=5).returncode == 0
    except Exception:
        return False


def store_card(data):
    """Write the shared card. The old file is kept as a timestamped backup when it differs (newest 10 kept)."""
    p = card_path()
    if os.path.exists(p):
        with open(p, "rb") as f:
            old = f.read()
        if old == data:
            return
        bd = os.path.join(saves_dir(), "backups")
        os.makedirs(bd, exist_ok=True)
        with open(os.path.join(bd, time.strftime("Mcd001-%Y%m%d-%H%M%S.ps2")), "wb") as f:
            f.write(old)
        for extra in sorted(glob.glob(os.path.join(bd, "Mcd001-*.ps2")))[:-10]:
            try:
                os.remove(extra)
            except Exception:
                pass
    tmp = p + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, p)


WS_PATCH = "007cad1c=3fe38e38/3faaaaab"   # the game's X field of view (a data value, 4:3 -> 16:9); see docs/widescreen.md


def widescreen_env(env):
    """Switch on the PC window's widescreen (picture shown at 16:9 plus the field-of-view data patch)."""
    if load_cfg().get("widescreen"):
        env["PS2_ASPECT"] = "16:9"
        env["PS2_PATCH"] = WS_PATCH
        return True
    return False


def web_pokes_param(ovl, mod=False):
    """The file-mod table pokes (mods\\active.pokes) as a page parameter, for the browser game; only when the server lays the overlay over the disc.
    Cheat strengths (EXP x5 ...) are pokes too, when the mods build is the one that starts."""
    pk = lm_pokes_text() if ovl else ""
    cp = packed_cheat_pokes() if mod and packed_mask() else ""
    pk = ",".join(x for x in (pk, cp) if x)
    return "&PS2_POKE=" + urllib.parse.quote(pk, safe="") if pk else ""


def web_params(cfg=None):
    """Settings that the browser game reads from its page address: widescreen, volumes (only when below 100) and the speedrun clock."""
    cfg = cfg if cfg is not None else load_cfg()
    q = ""
    if cfg.get("widescreen"):
        q += "&PS2_ASPECT=%s&PS2_PATCH=%s" % (urllib.parse.quote("16:9", safe=""), urllib.parse.quote(WS_PATCH, safe=""))
    for key, var in (("vol_master", "PS2_VOL_MASTER"), ("vol_fx", "PS2_VOL_FX"), ("vol_music", "PS2_VOL_MUSIC"), ("vol_voice", "PS2_VOL_VOICE")):
        v = vol_get(cfg, key)
        if v != 100:
            q += "&%s=%d" % (var, v)
    if cfg.get("speedrun"):
        q += "&speedrun=1"
        if cfg.get("speedrun_zero_web"):
            q += "&srzero=1"
    return q


def display_env():
    """Environment for the PC window. WSL2 with WSLg has a display already; WSL1 needs an X server
    on Windows (VcXsrv, see docs/windows-build.md). Returns (env, problem or None)."""
    env = dict(os.environ)
    wslg = os.path.isdir("/mnt/wslg")
    if not wslg and not port_open(6000):
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
    sc = load_cfg().get("scale", "3")
    env["PS2_SCALE"] = sc if sc in ("1", "2", "3") else "3"
    widescreen_env(env)
    if wslg:
        # WSL2: Ubuntu has no Vulkan driver for the card (no Dozen), but Mesa's Direct3D12 OpenGL driver works.
        # Default: draw through OpenGL on the card. Put "P3F_RENDER=vulkan" in ~/.p3fes-window-env to go back.
        extra = {}
        try:
            with open(os.path.expanduser("~/.p3fes-window-env")) as f:
                for ln in f:
                    if "=" in ln and not ln.lstrip().startswith("#"):
                        k, v = ln.strip().split("=", 1)
                        extra[k.strip()] = v.strip()
        except OSError:
            pass
        if extra.get("P3F_RENDER", "gl") == "gl":
            env.setdefault("GALLIUM_DRIVER", "d3d12")
            env.setdefault("WGPU_BACKEND", "gl")
        for k, v in extra.items():
            if k != "P3F_RENDER":
                env[k] = v
        return env, None
    env["DISPLAY"] = "127.0.0.1:0"
    env["SDL_VIDEODRIVER"] = "x11"
    env.pop("WAYLAND_DISPLAY", None)
    env.pop("XDG_RUNTIME_DIR", None)
    return env, None


def win_exe():
    """The native Windows PC window (ps2run.exe built with tools/build_win.bat), or None.
    Looked for in C:\\p3fes\\winbuild\\build, or at the path in the P3F_WINEXE variable."""
    cands = [os.environ.get("P3F_WINEXE", ""), "/mnt/c/p3fes/winbuild/build/ps2run.exe"] + sorted(glob.glob("/mnt/[a-z]/p3fes/winbuild/build/ps2run.exe"))
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def win_mod_exe():
    """The Direct Commands build of the Windows PC window (tools/p3fes_win_mod.bat makes it in C:\\p3fes\\winbuild\\build-mod), or None."""
    base = win_exe()
    if not base:
        return None
    p = os.path.join(os.path.dirname(os.path.dirname(base)), "build-mod", "ps2run.exe")
    return p if os.path.isfile(p) else None


def direct_on():
    """Direct Commands is a toggle, on unless switched off (Mods > Essential Mods)."""
    return packed_on("directcmd")


def win_mod_stale():
    """The PC window's mod build was made before the newest BUILD of the essential mods (or before the newest tool patch), so it would not have what was added since."""
    exe = win_mod_exe()
    try:
        return bool(exe) and (os.path.getmtime(exe) < os.path.getmtime(os.path.join(DIR, "games", MOD_NAME, "variants.txt")) or tools_newer_than(exe))
    except OSError:
        return False


def direct_available(mode):
    """Is the essential mods build there for this way of playing?"""
    if mode == "exe":
        if win_exe():
            return bool(win_mod_exe()) and not win_mod_stale()
        return os.path.exists(os.path.join(DIR, "build", "native-" + MOD_NAME, "ps2run"))
    return os.path.exists(os.path.join(DIR, "build", "web-" + MOD_NAME, "ps2web.html"))


def active_win_exe():
    """The PC window Play would start now: the Direct Commands build when the toggle is on and it is built."""
    base = win_exe()
    if not base:
        return None
    return win_mod_exe() if direct_on() and win_mod_exe() else base


_AFS = {"key": None, "starts": [], "files": {}}


def _iso_dir(f, base, lba, size, prefix, out, depth=0):
    f.seek(base + lba * 2048)
    data = f.read(size)
    pos = 0
    while pos < len(data):
        ln = data[pos]
        if ln == 0:
            pos = (pos // 2048 + 1) * 2048
            continue
        rec = data[pos:pos + ln]
        pos += ln
        if len(rec) < 34:
            continue
        ext, sz, flags, nlen = struct.unpack_from("<I", rec, 2)[0], struct.unpack_from("<I", rec, 10)[0], rec[25], rec[32]
        nm = rec[33:33 + nlen]
        if nm in (b"\x00", b"\x01"):
            continue
        nm = nm.decode("latin-1").split(";")[0]
        if flags & 2:
            if depth < 6 and sz:
                _iso_dir(f, base, ext, sz, prefix + nm + "/", out, depth + 1)
        else:
            out.append((prefix + nm, ext, sz))


def _iso_volume(f, base):
    f.seek(base + 16 * 2048)
    pvd = f.read(2048)
    if pvd[1:6] != b"CD001":
        return None
    out = []
    _iso_dir(f, base, struct.unpack_from("<I", pvd, 156 + 2)[0], struct.unpack_from("<I", pvd, 156 + 10)[0], "", out)
    return out


def voice_iso():
    real = os.path.realpath(os.path.join(DIR, "games", NAME, "disc.iso"))
    if os.path.isfile(real):
        return real
    c = sorted(glob.glob("/mnt/c/p3fes/*.iso"))
    return c[0] if c else None


def afs_index(iso=None):
    """Where each voice archive (SOUND/V*.AFS inside DATA.CVM) sits on the disc: {name: (first sector, size)} and a sorted list of starts."""
    iso = iso or voice_iso()
    if not iso:
        return _AFS
    key = (iso, os.path.getmtime(iso))
    if _AFS["key"] == key:
        return _AFS
    files, starts = {}, []
    try:
        with open(iso, "rb") as f:
            outer = _iso_volume(f, 0) or []
            dat = [x for x in outer if x[0].upper() == "DATA.CVM"]
            if dat:
                first = dat[0][1]
                for path, lba, size in _iso_volume(f, (first + 3) * 2048) or []:
                    m = re.match(r"^SOUND/(V[0-9]+)\.AFS$", path.upper())
                    if m:
                        files[m.group(1)] = (first + 3 + lba, size)
                        starts.append((first + 3 + lba, first + 3 + lba + (size + 2047) // 2048, m.group(1)))
    except OSError:
        pass
    starts.sort()
    _AFS.update(key=key, starts=starts, files=files)
    return _AFS


def afs_for_reads(reads, idx=None):
    """The voice archive named by the most recent disc read in 'sector:count,sector:count,...' that lies inside one."""
    idx = idx or afs_index()
    st = idx["starts"]
    if not st:
        return None
    for item in reversed([x for x in (reads or "").split(",") if ":" in x]):
        try:
            sec = int(item.split(":")[0])
        except ValueError:
            continue
        i = bisect.bisect_right([s[0] for s in st], sec) - 1
        if i >= 0 and st[i][0] <= sec < st[i][1]:
            return st[i][2]
    return None


def adx_to_wav(data):
    """Decode standard CRI ADX (4-bit, 18-byte frames, 1 or 2 channels) to a 16-bit WAV."""
    if data[:2] != b"\x80\x00":
        raise ValueError("not an ADX clip")
    off = struct.unpack(">H", data[2:4])[0] + 4
    enc, bsize, bits, ch = data[4], data[5], data[6], data[7]
    rate, total = struct.unpack(">II", data[8:16])
    cutoff = struct.unpack(">H", data[16:18])[0]
    if enc != 3 or bsize != 18 or bits != 4 or ch not in (1, 2):
        raise ValueError("unsupported ADX variant")
    a = math.sqrt(2) - math.cos(2 * math.pi * cutoff / rate)
    b = math.sqrt(2) - 1
    c = (a - math.sqrt((a + b) * (a - b))) / b
    c0, c1 = int(math.floor(c * 2 * 4096 + 0.5)), int(math.floor(-(c * c) * 4096 + 0.5))
    pcm = [[] for _ in range(ch)]
    h1, h2 = [0] * ch, [0] * ch
    frames = (len(data) - off) // (18 * ch)
    for fr in range(frames):
        for k in range(ch):
            p = off + (fr * ch + k) * 18
            scale = ((data[p] << 8) | data[p + 1]) & 0x1FFF
            s1, s2, out = h1[k], h2[k], pcm[k]
            for byte in data[p + 2:p + 18]:
                for d in (byte >> 4, byte & 15):
                    if d >= 8:
                        d -= 16
                    s = (((d * 4096) * scale) + s1 * c0 + s2 * c1) >> 12
                    s = -32768 if s < -32768 else 32767 if s > 32767 else s
                    out.append(s)
                    s2, s1 = s1, s
            h1[k], h2[k] = s1, s2
    n = min(total, len(pcm[0])) if total else len(pcm[0])
    buf = io.BytesIO()
    w = wave.open(buf, "wb")
    w.setnchannels(ch)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(b"".join(struct.pack("<" + "h" * ch, *[pcm[k][i] for k in range(ch)]) for i in range(n)))
    w.close()
    return buf.getvalue()


_WAVS = {}


def voice_wav(afs, n):
    """WAV of clip number n (1-based, as the dialogue log counts) from voice archive afs, read from the player's own disc."""
    key = (afs, n)
    if key in _WAVS:
        return _WAVS[key]
    idx = afs_index()
    iso = voice_iso()
    if afs not in idx["files"] or not iso:
        raise ValueError("voice archive not found on the disc")
    start, size = idx["files"][afs]
    with open(iso, "rb") as f:
        f.seek(start * 2048)
        head = f.read(8)
        if head[:4] != b"AFS\x00":
            raise ValueError("not an AFS archive")
        count = struct.unpack_from("<I", head, 4)[0]
        if not 1 <= n <= count:
            raise ValueError("no such clip")
        f.seek(start * 2048 + 8 + (n - 1) * 8)
        off, sz = struct.unpack("<II", f.read(8))
        f.seek(start * 2048 + off)
        wav = adx_to_wav(f.read(sz))
    if len(_WAVS) > 40:
        _WAVS.clear()
    _WAVS[key] = wav
    return wav


def vol_get(cfg, key):
    try:
        return max(0, min(100, int(cfg.get(key, 100))))
    except (TypeError, ValueError):
        return 100


def speedrun_file():
    return os.path.join(saves_dir(), "speedrun_clock.txt")


def speedrun_reset():
    try:
        os.remove(speedrun_file())
    except OSError:
        pass
    c = load_cfg()
    c["speedrun_zero_web"] = True   # the browser game's clock is zeroed the next time it opens
    save_cfg(c)


def dialog_log_path():
    """Where the PC window writes the dialogue log (ps2run_dialoglog_patch.py). Next to the memory card."""
    return os.path.join(saves_dir(), "dialog_log.tsv")


def dialog_log_entries(path=None, limit=800, use_afs=True):
    """Lines of the dialogue log, newest last. A new play session starts where the frame number goes back down.
    Voiced means the page has a voice clip AND a speaker (narration pages carry a clip number but have no clip)."""
    path = path or dialog_log_path()
    rows, sess, last = [], 0, -1
    idx = None
    try:
        with open(path, "r", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return {"ok": True, "entries": [], "have_file": False}
    for ln in lines:
        p = ln.split("\t")
        if len(p) < 6:
            continue
        try:
            fr, spk, clip, pg = int(p[0]), int(p[1]), int(p[2]), int(p[4])
        except ValueError:
            continue
        if fr < last:
            sess += 1
        last = fr
        voiced = clip >= 0 and spk >= 0
        afs = None
        if voiced and len(p) > 6 and use_afs:
            if idx is None:
                idx = afs_index()
            afs = afs_for_reads(p[6], idx)
        rows.append({"f": fr, "spk": spk, "clip": clip, "blk": p[3], "pg": pg, "t": p[5].replace("\\n", "\n"),
                     "voiced": voiced, "sess": sess, "afs": afs})
    return {"ok": True, "entries": rows[-limit:], "have_file": True}


def dialog_log_clear(path=None):
    try:
        open(path or dialog_log_path(), "w").close()
        return True
    except OSError:
        return False


def to_win(path):
    """Windows spelling of a Linux path (C:\\... for /mnt/c, \\\\wsl.localhost\\... for files inside Ubuntu)."""
    try:
        return subprocess.run(["wslpath", "-w", path], capture_output=True, text=True, timeout=5).stdout.strip() or None
    except Exception:
        return None


def win_disc():
    """A disc image the Windows program can read quickly: the real disc when it is on a Windows drive,
    otherwise a same-size .iso in C:\\p3fes. Reading through the Ubuntu network path also works but is slower."""
    real = os.path.realpath(os.path.join(DIR, "games", NAME, "disc.iso"))
    if not os.path.isfile(real):
        real = find_iso() or ""
    if not real or not os.path.isfile(real):
        return None
    if real.startswith("/mnt/"):
        return to_win(real)
    size = os.path.getsize(real)
    for c in sorted(glob.glob("/mnt/c/p3fes/*.iso")):
        if os.path.getsize(c) == size and "modded" not in os.path.basename(c).lower():
            return to_win(c)
    return to_win(real)


PC_AS_RE = re.compile(r"^(timer|card|manual)_(\d{8})-(\d{6})\.state$")
PC_AS_REASON = {"timer": "timer", "card": "game save", "manual": "manual"}


def pc_as_root():
    return os.path.join(saves_dir(), "pc-autosaves")


def pc_as_dir(exe):
    """Each build of the PC window gets its own folder: a state only fits the build that made it."""
    try:
        st = os.stat(exe)
        return os.path.join(pc_as_root(), "%d-%d" % (st.st_size, int(st.st_mtime)))
    except OSError:
        return os.path.join(pc_as_root(), "unknown")


def pc_as_cfg():
    c = load_cfg()
    try:
        every = float(c.get("pc_as_every", "2"))
    except ValueError:
        every = 2.0
    try:
        keep = int(c.get("pc_as_keep", "3"))
    except ValueError:
        keep = 3
    return {"every": every if every >= 0 else 2.0, "keep": keep if 1 <= keep <= 20 else 3, "card": bool(c.get("pc_as_card", True))}


def pc_as_state():
    """The PC window's autosaves for the current build of ps2run.exe, newest first. 'older' counts other builds' files."""
    exe = active_win_exe()
    out = {"available": bool(exe), "list": [], "bytes": 0, "older": 0, "cfg": pc_as_cfg()}
    if not exe:
        return out
    cur = pc_as_dir(exe)
    root = pc_as_root()
    if os.path.isdir(root):
        for d in os.listdir(root):
            full = os.path.join(root, d)
            if not os.path.isdir(full):
                continue
            for n in os.listdir(full):
                m = PC_AS_RE.match(n)
                if not m:
                    continue
                try:
                    size = os.path.getsize(os.path.join(full, n))
                except OSError:
                    continue
                out["bytes"] += size
                if full != cur:
                    out["older"] += 1
                    continue
                t = m.group(2) + m.group(3)
                out["list"].append({"id": n, "reason": PC_AS_REASON[m.group(1)], "size": size, "stamp": t,
                                    "when": "%s-%s-%s %s:%s" % (t[0:4], t[4:6], t[6:8], t[8:10], t[10:12])})
    out["list"].sort(key=lambda a: a["stamp"], reverse=True)
    return out


def play_windows(exe, resume=None, mod=False):
    """Start the native Windows window. Returns the same {ok, msg} as play(). mod: the Direct Commands build (its own boot file)."""
    exe_dir = os.path.dirname(exe)
    elf_src = os.path.join(DIR, "games", MOD_NAME, "core.elf") if mod else os.path.join(DIR, "games", NAME, "disc", "SLUS_216.21")
    elf = os.path.join(os.path.dirname(exe_dir), "core.elf" if mod else "SLUS_216.21")
    if mod and os.path.isfile(elf_src) and (not os.path.isfile(elf) or os.path.getsize(elf) != os.path.getsize(elf_src)):
        try:
            shutil.copyfile(elf_src, elf)
        except OSError as e:
            return {"ok": False, "msg": "Could not copy the Direct Commands boot file next to the Windows program: %s" % e}
    if not os.path.isfile(elf):
        if not os.path.isfile(elf_src):
            return {"ok": False, "msg": "The game's boot file is missing. Run setup again."}
        try:
            shutil.copyfile(elf_src, elf)
        except OSError as e:
            return {"ok": False, "msg": "Could not copy the boot file next to the Windows program: %s" % e}
    disc, card, welf = win_disc(), to_win(os.path.join(saves_dir(), "Mcd001.ps2")), to_win(elf)
    if not (disc and card and welf):
        return {"ok": False, "msg": "Could not work out the Windows paths for the disc, card or boot file."}
    if any(c.poll() is None and "ps2run" in str(c.args[0]) for c in children):
        return {"ok": False, "msg": "The PC window is already running. Close it first (two would overwrite each other's saves)."}
    env = dict(os.environ)
    if not os.path.exists(KEYS_FILE):
        try:
            write_keys(dict(KEY_DEFAULTS))
        except Exception:
            pass
    env["PS2_KEYS"] = KEYS_FILE
    scale = load_cfg().get("scale", "3")
    env["PS2_SCALE"] = scale if scale in ("1", "2", "3") else "3"
    widescreen_env(env)
    names = ["PS2_KEYS/p", "PS2_SCALE", "PS2_ASPECT", "PS2_PATCH"]
    if mod and packed_mask():
        env["PS2_MODS"] = str(packed_mask())
        names.append("PS2_MODS")
    wlog = to_win(dialog_log_path())
    if wlog:   # the Log screen reads this file; a PS2_DIALOG_LOG line in ~/.p3fes-window-env still wins
        env["PS2_DIALOG_LOG"] = wlog
        names.append("PS2_DIALOG_LOG")
    for key, var in (("vol_master", "PS2_VOL_MASTER"), ("vol_fx", "PS2_VOL_FX"), ("vol_music", "PS2_VOL_MUSIC"), ("vol_voice", "PS2_VOL_VOICE")):   # Settings > Audio
        env[var] = str(vol_get(load_cfg(), key))
        names.append(var)
    if load_cfg().get("speedrun"):   # Settings > Speedrun: clock in the top left of the PC window (time kept in this file)
        sr = to_win(speedrun_file())
        if sr:
            env["PS2_SPEEDRUN"] = sr
            names.append("PS2_SPEEDRUN")
    try:   # research switches: lines like PS2_LOG_DISC=1 in ~/.p3fes-window-env (only PS2_ names are passed on)
        with open(os.path.expanduser("~/.p3fes-window-env")) as f:
            for ln in f:
                if "=" in ln and not ln.lstrip().startswith("#"):
                    k, v = ln.strip().split("=", 1)
                    k = k.strip()
                    if k == "PS2_PATCH" and env.get("PS2_ASPECT"):   # research: PS2_PATCH=none keeps the 16:9 picture but drops the field-of-view patch; any other value replaces it
                        if v.strip().lower() == "none":
                            env.pop("PS2_PATCH", None)
                            if "PS2_PATCH" in names:
                                names.remove("PS2_PATCH")
                        elif v.strip():
                            env["PS2_PATCH"] = v.strip()
                    elif re.match(r"^PS2_[A-Z0-9_]+$", k) and k not in ("PS2_KEYS", "PS2_SCALE", "PS2_ASPECT", "PS2_PATCH"):
                        env[k] = v.strip()
                        if k not in names:
                            names.append(k)
    except OSError:
        pass
    pk = lm_pokes_text() if overlay_file() else ""
    cp = packed_cheat_pokes() if mod and packed_mask() else ""   # cheat strengths (EXP x5, run speed ...): numbers the patched code reads from memory
    pk = ",".join(x for x in (pk, cp) if x)
    if pk:   # a moved file mod: the game's file table gets the new place and size (ps2run_poke_patch.py)
        if env.get("PS2_POKE"):   # a PS2_POKE line in ~/.p3fes-window-env is added to the mod pokes
            pk = pk + "," + env["PS2_POKE"]
        env["PS2_POKE"] = pk
        if "PS2_POKE" not in names:
            names.append("PS2_POKE")
    env["WSLENV"] = (env.get("WSLENV", "") + ":" if env.get("WSLENV") else "") + ":".join(names)
    asdir = pc_as_dir(exe)
    try:
        os.makedirs(asdir, exist_ok=True)
    except OSError:
        pass
    wasdir = to_win(asdir)
    cmd = [exe, welf, "--disc", disc, "--window", "--memcard", card]
    cfg = pc_as_cfg()
    if wasdir:
        cmd += ["--autosave", wasdir, "--autosave-every", "%g" % cfg["every"], "--autosave-keep", str(cfg["keep"]), "--autosave-card", "1" if cfg["card"] else "0"]
    mods = ""
    ovl = overlay_file()
    if ovl:
        wovl = to_win(ovl)
        if wovl and exe_supports(exe, "--overlay"):
            cmd += ["--overlay", wovl]
            mods = " File mods are on."
        else:
            mods = " Your file mods are not applied: this build of the PC window is older than file mod support (see docs/mod-folder-plan.md)."
    if resume:
        state = os.path.join(asdir, resume)
        if not PC_AS_RE.match(resume) or not os.path.isfile(state):
            return {"ok": False, "msg": "That autosave is gone, or was made by an older build of the PC window."}
        wstate = to_win(state)
        if not wstate:
            return {"ok": False, "msg": "Could not work out the Windows path of that autosave."}
        cmd += ["--load-state", wstate]
    log = open(os.path.expanduser("~/.p3fes-window.log"), "w")
    children.append(subprocess.Popen(cmd, cwd=exe_dir, env=env, stdout=log, stderr=subprocess.STDOUT))
    return {"ok": True, "msg": ("Resuming the PC window from your autosave." if resume else "Started the PC window (Windows version). Its memory card is in " + saves_dir() + ".") + mods}


def play(mode, resume=None, mod=False, pcresume=None):
    """Start the game. The essential mods build (a separate build of the game) is used when a mod in it is turned on and it is built for this way of
    playing; a browser autosave resume always uses the normal build (a state only fits the build that made it)."""
    note = ""
    if not mod and packed_wanted() and not resume:
        if direct_available(mode):
            mod = True
            note = " Essential mods are on."
        elif direct_available("browser" if mode == "exe" else "exe"):
            note = " Essential mods are on, but they are not built for the %s yet (see Mods > Essential Mods)." % ("PC window" if mode == "exe" else "browser")
    built, legacy = packed_built()
    if not resume and not legacy:
        need = packed_state()["need_build"]
        if need:
            note += " Not in the build yet: %s (press SET UP ESSENTIAL MODS in Mods > Essential Mods)." % ", ".join(need)
    r = play_inner(mode, resume, mod, pcresume)
    if r.get("ok") and note:
        r["msg"] = (r.get("msg") or "") + note
    return r


def play_inner(mode, resume=None, mod=False, pcresume=None):
    st = get_state()
    name = MOD_NAME if mod else NAME
    if st["state"] != "ready":
        return {"ok": False, "msg": "The game is not installed yet."}
    if mod and mode != "exe" and not os.path.exists(os.path.join(DIR, "build", "web-" + name, "ps2web.html")):
        return {"ok": False, "msg": "That mod is not built on this computer yet."}
    if pcresume and not (mode == "exe" and win_exe()):
        return {"ok": False, "msg": "Resuming a PC window autosave needs the Windows PC window (build it first)."}
    if mode == "exe" and win_exe():
        exe = win_mod_exe() if mod else win_exe()
        if not exe:
            return {"ok": False, "msg": "The Direct Commands build of the PC window is not built yet (see Mods > Direct Commands)."}
        return play_windows(exe, pcresume or None, mod)
    if mode == "exe":
        exe = os.path.join(DIR, "build", "native-" + name, "ps2run")
        if not os.path.exists(exe):
            return {"ok": False, "msg": "The PC window version is not built yet."}
        prog = os.path.join(DIR, "games", name, "core.elf") if mod else os.path.join(DIR, "games", NAME, "disc", "SLUS_216.21")
        cmd = [exe, prog,
               "--disc", os.path.join(DIR, "games", name, "disc.iso"), "--window",
               "--memcard", os.path.join(saves_dir(), "Mcd001.ps2")]
        if any(c.poll() is None and "ps2run" in str(c.args[0]) for c in children):
            return {"ok": False, "msg": "The PC window is already running. Close it first (two would overwrite each other's saves)."}
        env, problem = display_env()
        if problem:
            return {"ok": False, "msg": problem}
        if mod and packed_mask():
            env["PS2_MODS"] = str(packed_mask())
            cp = packed_cheat_pokes()
            if cp:
                env["PS2_POKE"] = (env["PS2_POKE"] + "," + cp) if env.get("PS2_POKE") else cp
        children.append(subprocess.Popen(cmd, cwd=DIR, env=env))
        return {"ok": True, "msg": "Started the PC window. Its memory card is in " + saves_dir() + ". If none appears, check VcXsrv is running."}
    ovl = overlay_path()   # file mods work with the essential mods build too (same disc, same overlay)
    want = (name, ovl, os.path.getmtime(ovl) if ovl else None)
    if port_open(GAME_PORT) and serving[0] not in (None, want):
        # the other build is being served: stop our server so this one can take the port
        for c in children:
            if c.poll() is None and "serve.py" in " ".join(map(str, c.args)):
                c.terminate()
        for _ in range(30):
            if not port_open(GAME_PORT):
                break
            time.sleep(0.2)
    if not port_open(GAME_PORT):
        cmd = [sys.executable, "scripts/serve.py", "build/web-" + name, "games/%s/disc.iso" % name]
        if ovl:
            cmd += ["--overlay", ovl]
        children.append(subprocess.Popen(cmd, cwd=DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        serving[0] = want
        for _ in range(30):
            if port_open(GAME_PORT):
                break
            time.sleep(0.2)
    pref = load_cfg().get("browser", "msedge")
    scale = load_cfg().get("scale", "3")
    url = "http://localhost:%d/?PS2_SCALE=%s&cardsync=%d" % (GAME_PORT, scale, SERVER_PORT[0]) + web_params()
    if mod and packed_mask():
        url += "&PS2_MODS=%d" % packed_mask()
    url += web_pokes_param(ovl, mod)
    if resume:
        url += "&resume=%d" % resume
    if load_cfg().get("speedrun_zero_web"):
        c = load_cfg()
        c.pop("speedrun_zero_web", None)
        save_cfg(c)
    how = win_open(url, prefer=pref)
    keep_game_alive()
    return {"ok": True, "msg": "Opened in " + (how or "your browser") if how else "Open http://localhost:%d/ in Chrome or Edge." % GAME_PORT}


# ------------------------------------------------------------------ screenshots
SHOT_KEYS = ["F8", "F9", "F10", "F12", "PrintScreen", "Insert"]
SHOT_RE = re.compile(r"^P3FES_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(_\d+)?\.png$")

# Runs in Windows PowerShell. It waits for one global key and saves the window that is in front as a PNG.
# It reads its settings from .helper.cfg every 2 seconds and quits when the launcher stops writing .alive.
SHOT_PS1 = r'''
$ErrorActionPreference = 'Stop'
$dir = '@DIR@'
try {
Add-Type -ReferencedAssemblies System.Windows.Forms, System.Drawing -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;

public class P3ShotHost : Form
{
    [DllImport("user32.dll")] static extern bool RegisterHotKey(IntPtr h, int id, uint mod, uint vk);
    [DllImport("user32.dll")] static extern bool UnregisterHotKey(IntPtr h, int id);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
    [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }
    [StructLayout(LayoutKind.Sequential)] struct POINT { public int X, Y; }

    string dir; string cfgPath; string alivePath; string logPath;
    string curKey = ""; bool curOn = false; bool sound = true;
    string lastAlive = ""; DateTime lastChange = DateTime.UtcNow;
    System.Windows.Forms.Timer tick;

    public static void Run(string d)
    {
        bool created;
        Mutex m = new Mutex(true, "P3FES_ShotHelper", out created);
        if (!created) return;
        SetProcessDPIAware();
        Application.EnableVisualStyles();
        Application.Run(new P3ShotHost(d));
        GC.KeepAlive(m);
    }

    P3ShotHost(string d)
    {
        dir = d;
        cfgPath = Path.Combine(d, ".helper.cfg");
        alivePath = Path.Combine(d, ".alive");
        logPath = Path.Combine(d, ".helper.log");
        ShowInTaskbar = false;
        FormBorderStyle = FormBorderStyle.None;
        Opacity = 0;
        var h = Handle;
        tick = new System.Windows.Forms.Timer();
        tick.Interval = 2000;
        tick.Tick += delegate { Poll(); };
        tick.Start();
        Poll();
    }

    protected override void SetVisibleCore(bool v) { base.SetVisibleCore(false); }

    void Log(string s)
    {
        try { File.AppendAllText(logPath, DateTime.Now.ToString("s") + " " + s + "\r\n"); } catch (Exception) { }
    }

    void Poll()
    {
        try
        {
            string a = File.Exists(alivePath) ? File.ReadAllText(alivePath) : "";
            if (a != lastAlive) { lastAlive = a; lastChange = DateTime.UtcNow; }
            if ((DateTime.UtcNow - lastChange).TotalSeconds > 40) { Quit(); return; }
            bool on = false; string key = "F9"; bool snd = true;
            if (File.Exists(cfgPath))
            {
                foreach (string line in File.ReadAllLines(cfgPath))
                {
                    int i = line.IndexOf('=');
                    if (i < 1) continue;
                    string k = line.Substring(0, i).Trim(); string v = line.Substring(i + 1).Trim();
                    if (k == "on") on = (v == "1");
                    else if (k == "key") key = v;
                    else if (k == "sound") snd = (v == "1");
                }
            }
            sound = snd;
            if (on != curOn || key != curKey)
            {
                UnregisterHotKey(Handle, 1);
                curOn = on; curKey = key;
                if (on)
                {
                    Keys kk = (Keys)Enum.Parse(typeof(Keys), key);
                    if (!RegisterHotKey(Handle, 1, 0, (uint)kk)) Log("Could not register " + key + " (another program may be using it).");
                    else Log("Ready on " + key);
                }
            }
            File.WriteAllText(Path.Combine(dir, ".helper.alive"), DateTime.UtcNow.ToString("o"));
        }
        catch (Exception e) { Log("poll: " + e.Message); }
    }

    void Quit()
    {
        try { UnregisterHotKey(Handle, 1); } catch (Exception) { }
        tick.Stop();
        Application.Exit();
    }

    protected override void WndProc(ref Message m)
    {
        if (m.Msg == 0x0312 && m.WParam.ToInt32() == 1)
        {
            try { TakeShot(); } catch (Exception e) { Log("shot: " + e.Message); }
        }
        base.WndProc(ref m);
    }

    void TakeShot()
    {
        int x, y, w, h;
        IntPtr fg = GetForegroundWindow();
        RECT r; POINT p = new POINT();
        bool okWin = fg != IntPtr.Zero && GetClientRect(fg, out r) && ClientToScreen(fg, ref p);
        if (okWin)
        {
            GetClientRect(fg, out r);
            x = p.X; y = p.Y; w = r.R - r.L; h = r.B - r.T;
        }
        else { x = 0; y = 0; w = 0; h = 0; }
        if (w < 200 || h < 150)
        {
            Rectangle b = Screen.PrimaryScreen.Bounds;
            x = b.X; y = b.Y; w = b.Width; h = b.Height;
        }
        string stamp = DateTime.Now.ToString("yyyy-MM-dd_HH-mm-ss");
        string name = "P3FES_" + stamp + ".png";
        int n = 1;
        while (File.Exists(Path.Combine(dir, name))) { n++; name = "P3FES_" + stamp + "_" + n + ".png"; }
        using (Bitmap bmp = new Bitmap(w, h, PixelFormat.Format24bppRgb))
        {
            using (Graphics g = Graphics.FromImage(bmp)) { g.CopyFromScreen(x, y, 0, 0, new Size(w, h)); }
            bmp.Save(Path.Combine(dir, name), ImageFormat.Png);
            string td = Path.Combine(dir, "thumbs");
            Directory.CreateDirectory(td);
            int tw = 320; int th = Math.Max(1, (int)((long)h * tw / w));
            using (Bitmap t = new Bitmap(tw, th, PixelFormat.Format24bppRgb))
            {
                using (Graphics g2 = Graphics.FromImage(t))
                {
                    g2.InterpolationMode = InterpolationMode.HighQualityBicubic;
                    g2.DrawImage(bmp, 0, 0, tw, th);
                }
                t.Save(Path.Combine(td, name.Replace(".png", ".jpg")), ImageFormat.Jpeg);
            }
        }
        if (sound) { try { System.Media.SystemSounds.Asterisk.Play(); } catch (Exception) { } }
    }
}
"@
[P3ShotHost]::Run($dir)
} catch {
    try { Add-Content -Path (Join-Path $dir '.helper.log') -Value ((Get-Date -Format s) + ' ' + $_.Exception.Message) } catch {}
}
'''


def shots_dir():
    """Where screenshots are kept: C:\\p3fes\\screenshots next to the saves, else a folder in Ubuntu."""
    s = saves_dir()
    d = os.path.join(os.path.dirname(s), "screenshots") if s.startswith("/mnt/c/p3fes") else os.path.expanduser("~/p3fes-screenshots")
    try:
        os.makedirs(os.path.join(d, "thumbs"), exist_ok=True)
    except Exception:
        d = os.path.expanduser("~/p3fes-screenshots")
        os.makedirs(os.path.join(d, "thumbs"), exist_ok=True)
    return d


def shots_settings(cfg=None):
    cfg = cfg if cfg is not None else load_cfg()
    key = cfg.get("screenshot_key", "F9")
    return {"on": cfg.get("screenshots_on", True) is not False, "key": key if key in SHOT_KEYS else "F9",
            "sound": cfg.get("screenshot_sound", True) is not False}


def shots_write_cfg():
    d = shots_dir()
    s = shots_settings()
    with open(os.path.join(d, ".helper.cfg"), "w") as f:
        f.write("on=%d\nkey=%s\nsound=%d\n" % (1 if s["on"] else 0, s["key"], 1 if s["sound"] else 0))


def shots_beat():
    try:
        with open(os.path.join(shots_dir(), ".alive"), "w") as f:
            f.write(repr(time.time()))
    except Exception:
        pass


def shots_helper_start():
    """Start the capture helper in Windows (it quits by itself if the launcher goes away; a second copy exits at once)."""
    if not os.path.isdir("/mnt/c"):
        return False
    try:
        d = shots_dir()
        wd = to_win(d)
        if not wd:
            return False
        shots_write_cfg()
        shots_beat()
        ps = os.path.join(d, ".helper.ps1")
        with open(ps, "w", newline="") as f:
            f.write(SHOT_PS1.replace("@DIR@", wd.replace("'", "''")).replace("\r\n", "\n").replace("\n", "\r\n"))
        wp = to_win(ps)
        subprocess.Popen(["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", wp],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=WINCWD)
        return True
    except Exception:
        return False


def shots_alive_thread():
    while True:
        shots_beat()
        time.sleep(5)


def shots_list():
    d = shots_dir()
    out = []
    try:
        for n in os.listdir(d):
            if SHOT_RE.match(n):
                st = os.stat(os.path.join(d, n))
                out.append({"name": n, "size": st.st_size, "t": int(st.st_mtime)})
    except Exception:
        pass
    out.sort(key=lambda e: (e["t"], e["name"]), reverse=True)
    return out


def shots_info():
    d = shots_dir()
    alive = False
    try:
        alive = time.time() - os.stat(os.path.join(d, ".helper.alive")).st_mtime < 15
    except Exception:
        pass
    log = ""
    try:
        with open(os.path.join(d, ".helper.log")) as f:
            ls = [x for x in f.read().splitlines() if re.match(r"^\d{4}-\d\d-\d\dT", x)]
            log = re.sub(r"^\S+ ", "", ls[-1])[:200] if ls else ""
    except Exception:
        pass
    s = shots_settings()
    return {"ok": True, "on": s["on"], "key": s["key"], "sound": s["sound"], "keys": SHOT_KEYS, "dir": to_win(d) or d,
            "helper": alive, "log": log, "items": shots_list()}


def shots_file(name, thumb=False):
    """Bytes and type of one screenshot (or its small picture), or None. Only names the helper makes are allowed."""
    if not SHOT_RE.match(name or ""):
        return None
    d = shots_dir()
    if thumb:
        p = os.path.join(d, "thumbs", name[:-4] + ".jpg")
        if os.path.isfile(p):
            with open(p, "rb") as f:
                return f.read(), "image/jpeg"
    p = os.path.join(d, name)
    if not os.path.isfile(p):
        return None
    with open(p, "rb") as f:
        return f.read(), "image/png"


def shots_delete(name):
    if not SHOT_RE.match(name or ""):
        return False
    d = shots_dir()
    ok = False
    for p in (os.path.join(d, name), os.path.join(d, "thumbs", name[:-4] + ".jpg")):
        try:
            os.remove(p)
            ok = True
        except Exception:
            pass
    return ok


def shots_clear():
    """Delete every screenshot the capture helper made (and its small pictures). Returns how many pictures were removed."""
    d = shots_dir()
    n = 0
    try:
        names = os.listdir(d)
    except Exception:
        return 0
    for name in names:
        if SHOT_RE.match(name):
            try:
                os.remove(os.path.join(d, name))
                n += 1
            except Exception:
                pass
    td = os.path.join(d, "thumbs")
    try:
        for name in os.listdir(td):
            if re.match(r"^P3FES_[0-9_\-]+\.jpg$", name):
                try:
                    os.remove(os.path.join(td, name))
                except Exception:
                    pass
    except Exception:
        pass
    return n


# ------------------------------------------------------------------ http
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json", cache=None):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache or "no-store")
        self.end_headers()
        self.wfile.write(body)

    def cors_ok(self):
        """Only the game page (localhost:8620) may use /card. Other websites are refused."""
        origin = self.headers.get("Origin")
        allowed = ("http://localhost:%d" % GAME_PORT, "http://127.0.0.1:%d" % GAME_PORT)
        return origin is None or origin in allowed, origin

    def card_reply(self, code, body=b"", origin=None, ctype="application/octet-stream"):
        self.send_response(code)
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def autosave_http(self, method, origin):
        """/autosave?key=K (list), /autosave/<id>?key=K (GET, PUT, DELETE). Used only by the game page."""
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        key = (q.get("key") or [""])[0]
        parts = u.path.strip("/").split("/")
        if not key or len(key) > 120 or len(parts) > 2:
            return self.card_reply(400, b"bad request", origin)
        d = as_dir(key)
        if len(parts) == 1:
            if method != "GET":
                return self.card_reply(405, b"", origin)
            if (q.get("announce") or [""])[0] == "1":
                os.makedirs(as_root(), exist_ok=True)
                with open(os.path.join(as_root(), "current.txt"), "w") as f:
                    f.write(key)
            body = json.dumps({"items": as_items(d), "deleted": as_deleted(d)}).encode()
            return self.card_reply(200, body, origin, "application/json")
        if not AS_ID.match(parts[1]):
            return self.card_reply(400, b"bad id", origin)
        i = int(parts[1])
        f = os.path.join(d, "%d.bin" % i)
        if method == "GET":
            if not os.path.isfile(f):
                return self.card_reply(404, b"", origin)
            with open(f, "rb") as fh:
                return self.card_reply(200, fh.read(), origin)
        if method == "DELETE":
            if os.path.isdir(d):
                as_delete(d, i)
            return self.card_reply(200, b"ok", origin)
        n = int(self.headers.get("Content-Length") or 0)
        if n < 1024 or n > 400 * 1024 * 1024:
            return self.card_reply(400, b"bad size", origin)
        reason = (q.get("reason") or [""])[0][:20]
        enc = (q.get("enc") or ["raw"])[0]
        try:
            meta = {"id": i, "key": key, "reason": reason, "time": int((q.get("time") or ["0"])[0]), "size": int((q.get("size") or ["0"])[0]),
                    "enc": enc if enc in ("gzip", "raw") else "raw", "bytes": n}
        except ValueError:
            return self.card_reply(400, b"bad request", origin)
        os.makedirs(d, exist_ok=True)
        with open(f + ".tmp", "wb") as fh:
            left = n
            while left > 0:
                chunk = self.rfile.read(min(left, 1 << 20))
                if not chunk:
                    break
                fh.write(chunk)
                left -= len(chunk)
        if left:
            os.remove(f + ".tmp")
            return self.card_reply(400, b"short upload", origin)
        os.replace(f + ".tmp", f)
        with open(os.path.join(d, "%d.json" % i), "w") as fh:
            json.dump(meta, fh)
        self.card_reply(200, b"ok", origin)

    def do_OPTIONS(self):
        ok, origin = self.cors_ok()
        if not (self.path == "/card" or self.path.startswith("/autosave")) or not ok:
            return self.card_reply(403)
        self.card_reply(204, b"", origin)

    def do_DELETE(self):
        ok, origin = self.cors_ok()
        if not self.path.startswith("/autosave") or not ok:
            return self.card_reply(403)
        self.autosave_http("DELETE", origin)

    def do_PUT(self):
        if self.path == "/card" or self.path.startswith("/autosave"):
            keep_game_alive()
        ok, origin = self.cors_ok()
        if self.path.startswith("/autosave") and ok:
            return self.autosave_http("PUT", origin)
        if self.path != "/card" or not ok:
            return self.card_reply(403)
        n = int(self.headers.get("Content-Length") or 0)
        if n != CARD_BYTES:
            return self.card_reply(400, b"not a memory card", origin)
        data = self.rfile.read(n)
        if data[:28] != CARD_MAGIC:
            return self.card_reply(400, b"not a formatted memory card", origin)
        if pc_window_running():
            return self.card_reply(409, b"the PC window is running", origin)
        try:
            store_card(data)
        except Exception as e:
            return self.card_reply(500, str(e).encode(), origin)
        self.card_reply(200, b"ok", origin)

    def do_GET(self):
        if self.path == "/card" or self.path.startswith("/autosave"):
            keep_game_alive()
        if self.path.startswith("/gamebeat"):
            ok, origin = self.cors_ok()
            if not ok:
                return self.card_reply(403)
            if "s=0" in self.path:
                game_seen[0] = 0.0   # the game page was closed: the launcher's music may come back at once
            else:
                game_seen[0] = time.time()
                keep_game_alive()
            return self.card_reply(200, b"ok", origin)
        if self.path.startswith("/autosave"):
            ok, origin = self.cors_ok()
            if not ok:
                return self.card_reply(403)
            return self.autosave_http("GET", origin)
        if self.path == "/card":
            ok, origin = self.cors_ok()
            if not ok:
                return self.card_reply(403)
            p = card_path()
            if not os.path.exists(p):
                return self.card_reply(404, b"", origin)
            with open(p, "rb") as f:
                return self.card_reply(200, f.read(), origin)
        if self.path.startswith("/api/gb/img?"):
            try:
                u = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("u", [""])[0]
                ct, data = gb_image(u)
                return self.send(200, data, ct)
            except Exception:
                return self.send(404, {"error": "no image"})
        if self.path == "/api/guide/list":
            return self.send(200, {"ok": True, "pages": guide_list()})
        if self.path.startswith("/api/guide/get?"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return self.send(200, guide_get(q.get("slug", [""])[0]))
        if self.path == "/api/state":
            last_ping[0] = time.time()
            return self.send(200, get_state())
        if self.path == "/api/report":
            return self.send(200, {"text": report()})
        if self.path == "/api/dialoglog":
            return self.send(200, dialog_log_entries())
        if self.path.startswith("/api/voice?"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                afs, n = q.get("afs", [""])[0], int(q.get("n", ["0"])[0])
                if not re.match(r"^V[0-9]{3,8}$", afs):
                    raise ValueError("bad archive name")
                return self.send(200, voice_wav(afs, n), "audio/wav")
            except Exception as e:
                return self.send(404, {"error": str(e)})
        if self.path == "/api/shots":
            return self.send(200, shots_info())
        if self.path.startswith("/api/shot/"):
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)
            r = shots_file((q.get("n") or [""])[0], thumb=u.path == "/api/shot/thumb")
            if not r:
                return self.send(404, {"error": "not found"})
            return self.send(200, r[0], r[1], cache="max-age=86400")
        if self.path == "/api/bye":
            bye_time[0] = time.time()
            return self.send(200, {"ok": True})
        if self.path == "/api/ping":
            last_ping[0] = time.time()
            return self.send(200, {"ok": True})
        p = "index.html" if self.path.split("?")[0] in ("/", "") else self.path.lstrip("/").split("?")[0]
        f = os.path.normpath(os.path.join(UI, p))
        if not f.startswith(UI) or not os.path.isfile(f):
            return self.send(404, {"error": "not found"})
        ct = {"html": "text/html; charset=utf-8", "css": "text/css", "js": "text/javascript", "svg": "image/svg+xml", "png": "image/png"}.get(f.rsplit(".", 1)[-1], "application/octet-stream")
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
        if self.path == "/api/journey":
            c = load_cfg()
            c["journey"] = bool(data.get("on"))
            if not c["journey"] and c.get("theme") == "twelve":
                c["theme"] = "blue"
            save_cfg(c)
            return self.send(200, {"ok": True})
        if self.path == "/api/theme" and data.get("theme") in THEMES_ALL:
            c = load_cfg()
            if data["theme"] == "twelve" and not c.get("journey"):
                return self.send(200, {"ok": False})
            c["theme"] = data["theme"]
            save_cfg(c)
            return self.send(200, {"ok": True})
        if self.path == "/api/dialoglog/clear":
            return self.send(200, {"ok": dialog_log_clear()})
        if self.path == "/api/direct":
            packed_set_on("directcmd", bool(data.get("on")))
            return self.send(200, {"ok": True})
        if self.path == "/api/packed/on":
            return self.send(200, packed_toggle(str(data.get("id", "")), bool(data.get("on"))))
        if self.path == "/api/dub":
            return self.send(200, dub_set(str(data.get("lang", ""))))
        if self.path == "/api/packed/link":
            return self.send(200, packed_link(str(data.get("id", "")), str(data.get("url", "")).strip()[:200]))
        if self.path == "/api/packed/level":
            return self.send(200, packed_set_level(str(data.get("id", "")), str(data.get("v", ""))))
        if self.path == "/api/packed/get":
            mid = packed_src(str(data.get("id", "")))
            if any(r["id"] == mid and r.get("pnach") for r in packed_registry()):
                return self.send(200, {"ok": False, "msg": "This one is part of the launcher, so there is nothing to download."})
            gb = packed_gb(mid)
            if not PACKED_ID.match(mid) or not any(r["id"] == mid for r in packed_registry()):
                return self.send(200, {"ok": False, "msg": "Unknown mod."})
            if not gb:
                return self.send(200, {"ok": False, "msg": "Paste the GameBanana link of this mod first (LINK)."})
            return self.send(200, lm_start(packed_get_work, mid, int(gb)))
        if self.path == "/api/packed/remove":
            return self.send(200, packed_remove(str(data.get("id", ""))))
        if self.path == "/api/packed/build":
            return self.send(200, essentials_start())
        if self.path == "/api/packed/folder":
            mid = packed_src(str(data.get("id", "")))
            d = os.path.join(packed_dir(), mid if PACKED_ID.match(mid) else "")
            os.makedirs(d, exist_ok=True)
            try:
                subprocess.Popen(["explorer.exe", to_win(d)], cwd=WINCWD if os.path.isdir("/mnt/c") else None)
                return self.send(200, {"ok": True, "msg": "Opened the folder. Put the mod's .pnach files in it, then press SET UP ESSENTIAL MODS."})
            except Exception as e:
                return self.send(200, {"ok": False, "msg": "Could not open the folder: %s" % e})
        if self.path == "/api/steam/state":
            return self.send(200, steam_state())
        if self.path == "/api/steam/key":
            c = load_cfg()
            c["steamgriddb_key"] = str(data.get("key", "")).strip()
            save_cfg(c)
            return self.send(200, {"ok": True})
        if self.path == "/api/steam/find":
            try:
                term = str(data.get("term") or STEAM_NAME)
                r = sgdb_get("/search/autocomplete/" + urllib.parse.quote(term))
                games = [{"id": g.get("id"), "name": g.get("name")} for g in (r.get("data") or [])[:8]]
                if games:
                    c = load_cfg()
                    pick = next((g for g in games if "persona 3 fes" in (g["name"] or "").lower()), games[0])
                    c["steamgriddb_game"], c["steamgriddb_name"] = pick["id"], pick["name"]
                    save_cfg(c)
                return self.send(200, {"ok": True, "games": games})
            except ValueError as e:
                return self.send(200, {"ok": False, "msg": str(e)})
        if self.path == "/api/steam/art":
            spec = ART_KINDS.get(data.get("kind"))
            gid = load_cfg().get("steamgriddb_game")
            if not spec or not gid:
                return self.send(200, {"ok": False, "msg": "Find the game first."})
            try:
                q = {"mimes": spec.get("mimes", "image/png,image/jpeg"), "page": int(data.get("page") or 0)}   # logos and icons accept fewer picture types
                q.update(spec["q"])
                r = sgdb_get("/%s/game/%s" % (spec["path"], int(gid)), q)
                items = [{"thumb": a.get("thumb"), "url": a.get("url"), "w": a.get("width"), "h": a.get("height"), "style": a.get("style"),
                          "by": (a.get("author") or {}).get("name")} for a in (r.get("data") or []) if a.get("url") and not a.get("nsfw")]
                return self.send(200, {"ok": True, "items": items})
            except ValueError as e:
                return self.send(200, {"ok": False, "msg": str(e)})
        if self.path == "/api/steam/add":
            return self.send(200, steam_add(data.get("choices") or {}))
        if self.path == "/api/steam/remove":
            return self.send(200, steam_remove())
        if self.path == "/api/volume":
            c = load_cfg()
            which = data.get("which")
            if which in ("master", "fx", "music", "voice", "launcher"):
                c["vol_" + which] = vol_get({"v": data.get("v", 100)}, "v")
            save_cfg(c)
            return self.send(200, {"ok": True, "v": c.get("vol_" + str(which))})
        if self.path == "/api/shots/settings":
            c = load_cfg()
            if "on" in data:
                c["screenshots_on"] = bool(data["on"])
            if data.get("key") in SHOT_KEYS:
                c["screenshot_key"] = data["key"]
            if "sound" in data:
                c["screenshot_sound"] = bool(data["sound"])
            save_cfg(c)
            shots_write_cfg()
            if c.get("screenshots_on", True) is not False:
                shots_helper_start()
            return self.send(200, shots_info())
        if self.path == "/api/shots/clear":
            n = shots_clear()
            return self.send(200, {"ok": True, "n": n, "msg": "Deleted %d screenshot%s." % (n, "" if n == 1 else "s")})
        if self.path == "/api/bugreport":
            mailto, gmail = bug_mail_urls()
            kind = data.get("kind")
            if kind == "mail":
                how = win_open(mailto, prefer="default")
                return self.send(200, {"ok": True, "to": BUG_EMAIL, "msg": "Opened your email app. If nothing opened, use GMAIL IN BROWSER or write to " + BUG_EMAIL + "."})
            if kind == "gmail":
                how = win_open(gmail, prefer=load_cfg().get("browser", "msedge"))
                return self.send(200, {"ok": True, "to": BUG_EMAIL, "msg": "Opened Gmail in your browser. Sign in if it asks, then press Send."})
            return self.send(200, {"ok": True, "to": BUG_EMAIL})
        if self.path == "/api/shots/delete":
            return self.send(200, {"ok": shots_delete(data.get("name"))})
        if self.path == "/api/shots/open":
            try:
                subprocess.Popen(["explorer.exe", to_win(shots_dir())], cwd=WINCWD if os.path.isdir("/mnt/c") else None)
                return self.send(200, {"ok": True})
            except Exception as e:
                return self.send(200, {"ok": False, "msg": "Could not open the folder: %s" % e})
        if self.path == "/api/speedrun":
            c = load_cfg()
            c["speedrun"] = bool(data.get("on"))
            save_cfg(c)
            return self.send(200, {"ok": True})
        if self.path == "/api/speedrun/reset":
            speedrun_reset()
            return self.send(200, {"ok": True, "msg": "Clock set back to 0:00:00.00 (it starts from zero the next time the PC window opens)."})
        if self.path == "/api/guide100":
            return self.send(200, {"ok": True, "done": guide100_apply(data)})
        if self.path == "/api/skiplauncher":
            c = load_cfg()
            c["skip_launcher"] = bool(data.get("on"))
            save_cfg(c)
            return self.send(200, {"ok": True})
        if self.path == "/api/closeonplay":
            c = load_cfg()
            c["close_on_play"] = bool(data.get("on"))
            save_cfg(c)
            return self.send(200, {"ok": True})
        if self.path == "/api/widescreen":
            c = load_cfg()
            c["widescreen"] = bool(data.get("on"))
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
        if self.path == "/api/padkeys" and isinstance(data.get("map"), dict):
            pad = dict(PAD_DEFAULTS)
            pad.update({k: str(v).lower() for k, v in data["map"].items() if k in PAD_ROWS and PAD_OK.match(str(v).lower())})
            try:
                write_keys(read_keys(), pad=pad)
                return self.send(200, {"ok": True, "pad": read_pad()})
            except Exception as e:
                return self.send(200, {"ok": False, "msg": "Could not save: %s" % e})
        if self.path in ("/api/card/restore", "/api/card/delete"):
            name = str(data.get("name", ""))
            if not BK_RE.match(name):
                return self.send(200, {"ok": False, "msg": "Unknown backup."})
            f = os.path.join(saves_dir(), "backups", name)
            if not os.path.isfile(f):
                return self.send(200, {"ok": False, "msg": "That backup is gone."})
            if self.path.endswith("delete"):
                os.remove(f)
                return self.send(200, {"ok": True, "msg": "Backup deleted."})
            if pc_window_running():
                return self.send(200, {"ok": False, "msg": "The PC window is running. Close it first."})
            with open(f, "rb") as fh:
                d = fh.read()
            if len(d) != CARD_BYTES or d[:28] != CARD_MAGIC:
                return self.send(200, {"ok": False, "msg": "That file is not a memory card."})
            store_card(d)
            return self.send(200, {"ok": True, "msg": "Card restored. The card it replaced is kept as a backup."})
        if self.path == "/api/lmod/add":
            if lm_work["busy"]:
                return self.send(200, {"ok": False, "msg": "Still working on the last change."})
            path, why = lm_pick("zip" if data.get("kind") == "zip" else "folder")
            if not path:
                return self.send(200, {"ok": False, "msg": why})
            return self.send(200, lm_start(lm_add_work, path))
        if self.path in ("/api/lmod/toggle", "/api/lmod/remove", "/api/lmod/up"):
            mid = str(data.get("id", ""))
            if not LM_ID.match(mid) or not any(m["id"] == mid for m in lm_load()):
                return self.send(200, {"ok": False, "msg": "Unknown mod."})
            return self.send(200, lm_start(lm_change_work, mid, self.path.endswith("remove"), self.path.endswith("/up")))
        if self.path == "/api/gb/view":
            return self.send(200, gb_view(str(data.get("q", ""))[:60], str(data.get("sort", "new")), data.get("page", 0), bool(data.get("refresh"))))
        if self.path in ("/api/gb/install", "/api/gb/mod"):
            try:
                gid = int(data.get("id"))
                fid = int(data.get("file") or 0)
            except (TypeError, ValueError):
                return self.send(200, {"ok": False, "msg": "Unknown mod."})
            if self.path.endswith("/mod"):
                try:
                    return self.send(200, gb_mod(gid))
                except Exception as e:
                    return self.send(200, {"ok": False, "err": "Could not load that mod (%s)." % str(e)[:80]})
            return self.send(200, lm_start(gb_install_work, gid, fid))
        if self.path == "/api/mod/choose":
            return self.send(200, choose_pnach())
        if self.path == "/api/disc/choose":
            ok, msg = choose_disc()
            return self.send(200, {"ok": ok, "msg": msg})
        if self.path == "/api/setup/start":
            return self.send(200, start_setup())
        if self.path == "/api/update/check":
            return self.send(200, update_check())
        if self.path == "/api/update/install":
            return self.send(200, update_install())
        if self.path == "/api/update/repo":
            r = str(data.get("repo") or "").strip().replace("https://github.com/", "").strip("/")
            if r and not update_repo_ok(r):
                return self.send(200, {"ok": False, "msg": "That does not look like owner/name, for example myname/persona3-pc."})
            c = load_cfg()
            c["update_repo"] = r
            save_cfg(c)
            return self.send(200, {"ok": True, "repo": r})
        if self.path == "/api/update/restart":
            self.send(200, {"ok": True})
            threading.Timer(0.6, lambda: os.execv(sys.executable, [sys.executable] + sys.argv)).start()
            return
        if self.path == "/api/guide/save":
            return self.send(200, guide_save(data.get("title"), data.get("html"), str(data.get("wiki") or "mt")))
        if self.path == "/api/guide/delete":
            return self.send(200, guide_delete(data.get("slug")))
        if self.path == "/api/guide":
            if data.get("tool"):
                u = GUIDE_TOOLS.get(str(data.get("tool")))
            elif data.get("title"):
                u = WIKI_BASES.get(str(data.get("wiki") or "mt"), WIKI_BASES["mt"]) + urllib.parse.quote(str(data.get("title")).replace(" ", "_")[:150], safe="_:()'!,-.")
            else:
                u = guide_url(data.get("src"), data.get("q"))
            if not u:
                return self.send(200, {"ok": False, "msg": "Type what you want to look up first."})
            how = win_open(u, app=True, prefer=load_cfg().get("browser", "msedge"), size=(1100, 800))
            return self.send(200, {"ok": bool(how), "msg": "Opened in a guide window." if how else "Could not open a browser window."})
        if self.path == "/api/openfolder":
            try:
                w = subprocess.run(["wslpath", "-w", saves_dir()], capture_output=True, text=True, timeout=5).stdout.strip()
                subprocess.Popen(["explorer.exe", w], cwd=WINCWD if os.path.isdir("/mnt/c") else None)
                return self.send(200, {"ok": True})
            except Exception as e:
                return self.send(200, {"ok": False, "msg": "Could not open the folder: %s" % e})
        if self.path == "/api/play":
            rid = str(data.get("resume") or "")
            pcr = str(data.get("pcresume") or "")
            return self.send(200, play(data.get("mode") or load_cfg().get("mode", "browser"), int(rid) if AS_ID.match(rid) else None, bool(data.get("mod")), pcr if PC_AS_RE.match(pcr) else None))
        if self.path == "/api/pcsave/delete":
            name, exe = str(data.get("id") or ""), active_win_exe()
            f = os.path.join(pc_as_dir(exe), name) if exe else ""
            if PC_AS_RE.match(name) and f and os.path.isfile(f):
                try:
                    os.remove(f)
                    return self.send(200, {"ok": True, "msg": "Autosave deleted."})
                except OSError as e:
                    return self.send(200, {"ok": False, "msg": "Could not delete it: %s" % e})
            return self.send(200, {"ok": False, "msg": "That autosave is gone."})
        if self.path == "/api/pcautosave":
            c = load_cfg()
            if str(data.get("every")) in ("0", "1", "2", "5", "10", "15", "30"):
                c["pc_as_every"] = str(data["every"])
            if str(data.get("keep")) in ("1", "3", "5", "10"):
                c["pc_as_keep"] = str(data["keep"])
            if data.get("card") in (True, False):
                c["pc_as_card"] = bool(data["card"])
            save_cfg(c)
            return self.send(200, {"ok": True})
        if self.path == "/api/autosave/delete":
            rid = str(data.get("id") or "")
            if not AS_ID.match(rid):
                return self.send(200, {"ok": False, "msg": "Unknown autosave."})
            root = as_root()
            for n in (os.listdir(root) if os.path.isdir(root) else []):
                d = os.path.join(root, n)
                if os.path.isfile(os.path.join(d, rid + ".bin")):
                    as_delete(d, int(rid))
                    return self.send(200, {"ok": True, "msg": "Autosave deleted."})
            return self.send(200, {"ok": False, "msg": "That autosave is gone."})
        self.send(404, {"error": "not found"})


# ---- Steam shortcut and SteamGridDB artwork (Settings > Steam)
SGDB_API = "https://www.steamgriddb.com/api/v2"
STEAM_NAME = "Persona 3 FES"
ART_KINDS = {   # what to ask SteamGridDB for, and the file name Steam looks for ({id} is the shortcut's number)
    "portrait": {"path": "grids", "q": {"dimensions": "600x900"}, "file": "{id}p"},
    "wide": {"path": "grids", "q": {"dimensions": "920x430,460x215"}, "file": "{id}"},
    "hero": {"path": "heroes", "q": {}, "file": "{id}_hero"},
    "logo": {"path": "logos", "q": {}, "mimes": "image/png", "file": "{id}_logo"},
    "icon": {"path": "icons", "q": {}, "mimes": "image/png,image/vnd.microsoft.icon", "file": "{id}_icon"},
}


def sgdb_get(path, params=None, key=None):
    """One call to the SteamGridDB API (needs the person's own free API key)."""
    key = key or load_cfg().get("steamgriddb_key", "")
    if not key:
        raise ValueError("Paste your SteamGridDB API key first.")
    url = SGDB_API + path + (("?" + urllib.parse.urlencode(params)) if params else "")
    req = urllib.request.Request(url, headers={"User-Agent": "p3fes-launcher/1.0", "Authorization": "Bearer " + key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise ValueError("SteamGridDB did not accept that API key.")
        raise ValueError("SteamGridDB answered with an error (%s)." % e.code)
    except Exception as e:
        raise ValueError("Could not reach SteamGridDB: %s" % e)


def steam_root():
    """The Steam folder as a Linux path, from the Windows registry or the usual places."""
    cands = []
    try:
        out = subprocess.run(["reg.exe", "query", r"HKCU\Software\Valve\Steam", "/v", "SteamPath"], capture_output=True, text=True, timeout=10).stdout
        m = re.search(r"SteamPath\s+REG_SZ\s+(.+)", out)
        if m:
            p = subprocess.run(["wslpath", "-u", m.group(1).strip()], capture_output=True, text=True, timeout=5).stdout.strip()
            if p:
                cands.append(p)
    except Exception:
        pass
    cands += ["/mnt/c/Program Files (x86)/Steam", "/mnt/c/Program Files/Steam"]
    c = load_cfg().get("steam_dir")
    if c:
        cands.insert(0, c)
    for p in cands:
        if os.path.isdir(os.path.join(p, "userdata")):
            return p
    return None


def steam_users(root):
    """[(account number, userdata folder)], the most recently used account first."""
    base = os.path.join(root, "userdata")
    users = [(int(n), os.path.join(base, n)) for n in os.listdir(base) if n.isdigit() and n != "0" and os.path.isdir(os.path.join(base, n))]
    recent = None
    try:
        txt = open(os.path.join(root, "config", "loginusers.vdf"), errors="replace").read()
        for m in re.finditer(r'"(\d{17})"\s*\{(.*?)\}', txt, re.S):
            if re.search(r'"MostRecent"\s*"1"', m.group(2)):
                recent = int(m.group(1)) - 76561197960265728
    except OSError:
        pass
    users.sort(key=lambda u: (u[0] != recent, u[0]))
    return users


def steam_running():
    try:
        out = subprocess.run(["tasklist.exe", "/FI", "IMAGENAME eq steam.exe", "/NH"], capture_output=True, text=True, timeout=10).stdout
        return "steam.exe" in out.lower()
    except Exception:
        return False


# Steam keeps shortcuts in a small binary file (shortcuts.vdf): nested lists of (type, name, value); 0 = list, 1 = text, 2 = number, 8 = end of list
def vdf_parse(data, pos=0):
    items = []
    while pos < len(data):
        t = data[pos]
        pos += 1
        if t == 8:
            return items, pos
        end = data.index(b"\x00", pos)
        key = data[pos:end].decode("utf-8", "replace")
        pos = end + 1
        if t == 0:
            val, pos = vdf_parse(data, pos)
        elif t == 1:
            end = data.index(b"\x00", pos)
            val = data[pos:end].decode("utf-8", "replace")
            pos = end + 1
        elif t == 2:
            val = struct.unpack_from("<I", data, pos)[0]
            pos += 4
        else:
            raise ValueError("unknown entry type %d" % t)
        items.append((t, key, val))
    return items, pos


def vdf_dump(items):
    out = bytearray()
    for t, key, val in items:
        out += bytes([t]) + key.encode("utf-8") + b"\x00"
        if t == 0:
            out += vdf_dump(val)
        elif t == 1:
            out += val.encode("utf-8") + b"\x00"
        else:
            out += struct.pack("<I", val & 0xFFFFFFFF)
    return bytes(out) + b"\x08"


def steam_app_id(exe, name):
    import zlib
    return (zlib.crc32((exe + name).encode("utf-8")) & 0xFFFFFFFF) | 0x80000000


def shortcut_entry(app_id, exe, start, icon):
    return [(2, "appid", app_id), (1, "AppName", STEAM_NAME), (1, "Exe", exe), (1, "StartDir", start), (1, "icon", icon), (1, "ShortcutPath", ""),
            (1, "LaunchOptions", ""), (2, "IsHidden", 0), (2, "AllowDesktopConfig", 1), (2, "AllowOverlay", 1), (2, "OpenVR", 0), (2, "Devkit", 0),
            (1, "DevkitGameID", ""), (2, "DevkitOverrideAppID", 0), (2, "LastPlayTime", 0), (1, "FlatpakAppID", ""), (0, "tags", [])]


def shortcuts_add(data, entry):
    """shortcuts.vdf bytes (or None) with our entry added, or replaced when it is already there (matched by name). Returns the new bytes."""
    root = vdf_parse(data)[0] if data else []
    sc = next((v for t, k, v in root if k.lower() == "shortcuts" and t == 0), None)
    if sc is None:
        sc = []
        root.append((0, "shortcuts", sc))
    for i, (t, k, v) in enumerate(sc):
        if t == 0 and any(kk == "AppName" and vv == STEAM_NAME for _, kk, vv in v):
            sc[i] = (0, k, entry)
            break
    else:
        nxt = max([int(k) for t, k, v in sc if k.isdigit()] + [-1]) + 1
        sc.append((0, str(nxt), entry))
    return vdf_dump(root)


def shortcuts_remove(data):
    root = vdf_parse(data)[0] if data else []
    gone = None
    for t, k, sc in root:
        if t == 0 and k.lower() == "shortcuts":
            keep = []
            for it in sc:
                if it[0] == 0 and any(kk == "AppName" and vv == STEAM_NAME for _, kk, vv in it[2]):
                    gone = next((vv for _, kk, vv in it[2] if kk == "appid"), None)
                else:
                    keep.append(it)
            sc[:] = [(0, str(n), it[2]) for n, it in enumerate(keep)]
    return vdf_dump(root), gone


def steam_launch_target():
    """What the Steam shortcut starts: launch.bat next to this file (it opens the launcher, Play starts the game)."""
    here = os.path.dirname(os.path.abspath(__file__))
    bat = to_win(os.path.join(here, "launch.bat"))
    return ('"%s"' % bat, bat.rsplit("\\", 1)[0] if bat and "\\" in bat else "") if bat else (None, None)


def steam_state():
    root = steam_root()
    st = {"key_set": bool(load_cfg().get("steamgriddb_key")), "steam": bool(root), "running": False, "users": [], "added": False,
          "game_id": load_cfg().get("steamgriddb_game"), "game_name": load_cfg().get("steamgriddb_name", "")}
    if root:
        st["running"] = steam_running()
        users = steam_users(root)
        st["users"] = [u[0] for u in users]
        for _, ud in users[:1]:
            try:
                st["added"] = STEAM_NAME.encode() in open(os.path.join(ud, "config", "shortcuts.vdf"), "rb").read()
            except OSError:
                pass
    return st


def steam_download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "p3fes-launcher/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        blob = r.read(20 * 1024 * 1024)
    with open(dest, "wb") as f:
        f.write(blob)


def steam_add(choices):
    """Add (or update) the Persona 3 FES shortcut and the chosen artwork for the most recently used Steam account."""
    root = steam_root()
    if not root:
        return {"ok": False, "msg": "Steam was not found on this computer."}
    if steam_running():
        return {"ok": False, "msg": "Close Steam completely first (right-click its tray icon > Exit), then try again. Steam would overwrite the change."}
    users = steam_users(root)
    if not users:
        return {"ok": False, "msg": "No Steam account has signed in on this computer yet."}
    exe, start = steam_launch_target()
    if not exe:
        return {"ok": False, "msg": "Could not work out the Windows path of launch.bat."}
    app_id = steam_app_id(exe, STEAM_NAME)
    _, ud = users[0]
    cfgdir = os.path.join(ud, "config")
    grid = os.path.join(cfgdir, "grid")
    os.makedirs(grid, exist_ok=True)
    done, failed, icon = [], [], ""
    for kind, url in (choices or {}).items():
        spec = ART_KINDS.get(kind)
        if not spec or not isinstance(url, str) or not url.startswith("https://"):
            continue
        host = urllib.parse.urlparse(url).hostname or ""
        if not host.endswith("steamgriddb.com"):
            failed.append(kind)
            continue
        ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
        ext = ext if ext in (".png", ".jpg", ".jpeg", ".ico", ".webp") else ".png"
        dest = os.path.join(grid, spec["file"].format(id=app_id) + ext)
        try:
            steam_download(url, dest)
            done.append(kind)
            if kind == "icon":
                icon = to_win(dest) or ""
        except Exception:
            failed.append(kind)
    path = os.path.join(cfgdir, "shortcuts.vdf")
    old = open(path, "rb").read() if os.path.exists(path) else b""
    if old:
        shutil.copy2(path, path + ".p3fes-backup")
    try:
        new = shortcuts_add(old, shortcut_entry(app_id, exe, start, icon))
    except Exception as e:
        return {"ok": False, "msg": "Steam's shortcut list could not be read (%s). Nothing was changed there; your old file is untouched." % e}
    with open(path, "wb") as f:
        f.write(new)
    msg = "Added to Steam (account %d). Open Steam to see it in your library under Non-Steam games." % users[0][0]
    if done:
        msg += " Artwork: " + ", ".join(done) + "."
    if failed:
        msg += " Could not download: " + ", ".join(failed) + "."
    return {"ok": True, "msg": msg}


def steam_remove():
    root = steam_root()
    if not root:
        return {"ok": False, "msg": "Steam was not found on this computer."}
    if steam_running():
        return {"ok": False, "msg": "Close Steam completely first, then try again."}
    users = steam_users(root)
    if not users:
        return {"ok": False, "msg": "No Steam account found."}
    cfgdir = os.path.join(users[0][1], "config")
    path = os.path.join(cfgdir, "shortcuts.vdf")
    if not os.path.exists(path):
        return {"ok": True, "msg": "It was not in Steam."}
    shutil.copy2(path, path + ".p3fes-backup")
    new, app_id = shortcuts_remove(open(path, "rb").read())
    with open(path, "wb") as f:
        f.write(new)
    if app_id is not None:
        for g in glob.glob(os.path.join(cfgdir, "grid", "%d*" % app_id)):
            try:
                os.remove(g)
            except OSError:
                pass
    return {"ok": True, "msg": "Removed from Steam, with the artwork this launcher added."}


def playing_now():
    """True while a game is running: the PC window (a process we started) or the browser game's server."""
    try:
        return any(c.poll() is None and "ps2run" in str(c.args[0]) for c in children) or port_open(GAME_PORT)
    except Exception:
        return False


def music_hold():
    """Launcher music pauses while the PC window runs, or while the browser game page is open (it checks in every 5 seconds and says goodbye when it closes).
    (The browser game's server stays up after its tab is closed, so the open port alone must not silence the music.)"""
    try:
        return any(c.poll() is None and "ps2run" in str(c.args[0]) for c in children) or (port_open(GAME_PORT) and time.time() - game_seen[0] < 30)
    except Exception:
        return False


def win_clock():
    """The Windows clock as ('YYYY-MM-DD', hour), or None. The Linux side may be on another time zone, so ask Windows."""
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", "Get-Date -Format yyyy-MM-dd-HH"],
                           capture_output=True, text=True, timeout=20)
        m = re.match(r"^(\d{4}-\d{2}-\d{2})-(\d{2})$", r.stdout.strip())
        return (m.group(1), int(m.group(2))) if m else None
    except Exception:
        return None


def midnight_watch():
    """The TV on the home screen shows a teaser for people who play at midnight: note the date when the game is running during the 00:00 hour."""
    while True:
        time.sleep(60)
        if not playing_now():
            continue
        now = win_clock()
        if now and now[1] == 0:
            c = load_cfg()
            if c.get("midnight_play") != now[0]:
                c["midnight_play"] = now[0]
                save_cfg(c)


def watchdog():
    # Quit when the window says goodbye and does not come back within 10 seconds (a page reload comes back at once),
    # or after 30 minutes of silence (a hidden window slows its timers, so this must be long).
    while True:
        time.sleep(3)
        now = time.time()
        if now < game_keep[0]:
            continue   # a browser game is open: it still needs the card and autosave endpoints
        if any(c.poll() is None and "ps2run" in str(c.args[0]) for c in children):
            continue   # the PC window is running: keep watching for the midnight teaser
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
        SERVER_PORT[0] = a.port
    except OSError:
        # already running: just open another window onto it
        print("The launcher is already running; opening its window.")
        if not a.no_window:
            if win_open(url, app=True):
                maximize_launcher()
        return
    print("Launcher running at", url, "(closing its window stops it)")
    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=midnight_watch, daemon=True).start()
    threading.Thread(target=shots_alive_thread, daemon=True).start()
    if shots_settings()["on"]:
        threading.Thread(target=shots_helper_start, daemon=True).start()
    if not a.no_window:
        how = win_open(url, app=True)
        if not how:
            print("Could not open a window. Open", url, "in Chrome or Edge.")
        else:
            threading.Thread(target=maximize_launcher, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
