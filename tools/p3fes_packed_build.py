#!/usr/bin/env python3
"""
p3fes_packed_build.py - build the "Packed-In Mods" version of the game: ONE build holding every code mod you downloaded, each with its own
on/off switch that the launcher sets when you press Play (no rebuild to change what is on).

What it does (run it inside the ps2-web-recomp folder, or let the launcher's BUILD button do it):
  1. looks in C:\\p3fes\\packed\\<mod>\\ for the .pnach files the launcher downloaded (or that you put there),
  2. bakes them into a copy of the boot program with a switch table (tools/p3fes_pnach_apply.py --mod),
  3. translates and builds the browser page and the Linux PC window (scripts/port.sh, which passes the table on),
  4. leaves games/p3fesmod ready; the Windows PC window is built once with tools\\p3fes_win_mod.bat.
It never changes the normal game (games/p3fes, build/web-p3fes). Mod files are read, never uploaded or copied into the repository.

usage: python3 tools/p3fes_packed_build.py [--packed DIR] [--prepare-only]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NAME, MOD = "p3fes", "p3fesmod"


def find_registry():
    for p in (os.path.join(HERE, "launcher", "packed_mods.json"), "/mnt/c/p3fes/launcher/packed_mods.json"):
        if os.path.isfile(p):
            return json.load(open(p))
    sys.exit("packed_mods.json not found next to the launcher")


def name_ok(reg, filename):
    """Registry "match" / "exclude": a mod can own only some of the .pnach files of a download (same rule as the launcher)."""
    low = filename.lower()
    if reg.get("match") and not any(t in low for t in reg["match"]):
        return False
    return not any(t in low for t in (reg.get("exclude") or []))


def pnach_files(folder):
    out = []
    for dp, _dn, fn in os.walk(folder):
        out += [os.path.join(dp, f) for f in sorted(fn) if f.lower().endswith(".pnach")]
    return sorted(out)


def run(cmd, **kw):
    print("$ " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd, **kw)
    if r.returncode:
        sys.exit("STOPPED: %s failed (exit %d)" % (cmd[0], r.returncode))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packed", default="/mnt/c/p3fes/packed")
    ap.add_argument("--prepare-only", action="store_true", help="write the patched program and switch table, do not translate or build")
    args = ap.parse_args()
    root = os.getcwd()
    if not os.path.isdir(os.path.join(root, "scripts")) or not os.path.isdir(os.path.join(root, "games", NAME)):
        sys.exit("STOPPED: run this inside the ps2-web-recomp folder (the one with scripts and games).")
    vanilla = os.path.join(root, "games", NAME, "disc", "SLUS_216.21")
    if not os.path.isfile(vanilla):
        sys.exit("STOPPED: the game's boot file is missing (games/p3fes/disc/SLUS_216.21). Finish setup first.")
    if "ps2-modswitch" not in open(os.path.join(root, "recomp", "codegen.cpp")).read():
        sys.exit("STOPPED: the project does not have the mod switch patch yet. Run p3fes_install.sh first (Setup > GET THE TOOLS).")

    mods, names = [], []
    for m in find_registry():
        if m.get("kind") != "code":
            continue
        files = [f for f in pnach_files(os.path.join(args.packed, m.get("source") or m["id"])) if name_ok(m, os.path.basename(f))]
        if files:
            mods.append((m, files))
            names.append(m["name"])
    if not mods:
        sys.exit("STOPPED: no mod files found in %s. Download or add at least one code mod first." % args.packed)
    print("Mods in this build: " + ", ".join(names), flush=True)

    game = os.path.join(root, "games", MOD)
    os.makedirs(game, exist_ok=True)
    for i, (m, files) in enumerate(mods):   # "skip_addrs": lines that write these addresses are left out (data values the PC window sets itself)
        if m.get("skip_addrs"):
            skip = {a.lower().lstrip("0") for a in m["skip_addrs"]}
            outs = []
            for j, f in enumerate(files):
                kept = []
                for ln in open(f, errors="replace").read().splitlines():
                    t = ln.split("//")[0].strip().split(",")
                    if len(t) >= 4 and t[0].strip().lower().startswith("patch") and t[2].strip().lower().lstrip("0") in skip:
                        continue
                    kept.append(ln)
                out = os.path.join(game, "skip_%s_%d.pnach" % (m["id"], j))
                open(out, "w").write("\n".join(kept) + "\n")
                outs.append(out)
            mods[i] = (m, outs)
    new_entries = os.path.join(game, "entries_new.txt")
    cmd = [sys.executable, os.path.join(HERE, "p3fes_pnach_apply.py"), vanilla]
    for m, files in mods:
        cmd += ["--mod", "%s:%d=%s" % (m["id"], m["bit"], ",".join(files))]
    cmd += ["-o", os.path.join(game, "core.elf"), "--entries", new_entries, "--variants", os.path.join(game, "variants.txt")]
    run(cmd)
    shutil.copyfile(vanilla, os.path.join(game, "vanilla.elf"))

    # entry points: the normal game's, plus the ones the patches add, plus the few that were found by playing
    seen, merged = set(), []
    extra = [e for m, _f in mods for e in m.get("extra_entries", [])]
    for p in (os.path.join(root, "games", NAME, "entries.txt"), os.path.join(game, "entries.txt"), new_entries):
        if os.path.isfile(p):
            for tok in open(p).read().split():
                if tok not in seen:
                    seen.add(tok)
                    merged.append(tok)
    for tok in extra:
        if tok not in seen:
            seen.add(tok)
            merged.append(tok)
    open(os.path.join(game, "entries.txt"), "w").write("\n".join(merged) + "\n")
    iso = os.path.join(game, "disc.iso")
    if not os.path.exists(iso):
        src = os.path.join(root, "games", NAME, "disc.iso")
        if os.path.exists(src):
            os.symlink(os.path.realpath(src), iso)
    if args.prepare_only:
        print("Prepared. (--prepare-only: nothing translated or built.)")
        return

    for d in (os.path.join(root, "generated", MOD), os.path.join(root, "build", "native-" + MOD)):
        shutil.rmtree(d, ignore_errors=True)
    # the translator must know --variants: rebuild it if it is older than the patch
    eer = os.path.join(root, "build", "tools", "eerecomp")
    src = os.path.join(root, "recomp", "codegen.cpp")
    if not os.path.isfile(eer) or os.path.getmtime(eer) < os.path.getmtime(src):
        run(["ninja", "-C", os.path.join(root, "build", "tools"), "eerecomp"])
    run(["bash", os.path.join(root, "scripts", "port.sh"), MOD, os.path.join(root, "games", NAME, "disc.iso"), "--no-explore"])
    print("\nDONE. Built: " + ", ".join(names) + ".\nIn the launcher: Mods > Packed-In Mods. Turn mods on or off there, then press Play.", flush=True)


if __name__ == "__main__":
    main()
