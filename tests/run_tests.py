#!/usr/bin/env python3
"""
Runs every tool on a synthetic test disc (no game data needed) and checks the results.
Usage:  python tests/run_tests.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), "tools")


def run(*args):
    r = subprocess.run([sys.executable, "-I", *args], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit(f"FAILED: {' '.join(args)}")
    return r.stdout


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        raise SystemExit(1)


def cleanup_reports():
    """The tools write their reports next to themselves; remove the ones the test made."""
    for name in os.listdir(TOOLS):
        if name.startswith("test.") and name.endswith(".json"):
            os.remove(os.path.join(TOOLS, name))


def main():
    try:
        run_all()
    finally:
        cleanup_reports()


def run_all():
    with tempfile.TemporaryDirectory() as tmp:
        iso = os.path.join(tmp, "test.iso")
        ext = os.path.join(tmp, "extracted")
        run(os.path.join(HERE, "make_test_disc.py"), iso)
        out = run(os.path.join(TOOLS, "p3fes_inspect.py"), iso, "--no-hash")
        check("SLUS_000.00" in out, "inspect finds the boot file")
        out = run(os.path.join(TOOLS, "p3fes_formats.py"), iso, "--no-video")
        check("fit the PAK theory" in out, "formats tool analyses the containers")
        run(os.path.join(TOOLS, "p3fes_unpack.py"), iso, "-o", ext, "--containers")
        check(os.path.isfile(os.path.join(ext, "DATA.CVM", "MODEL", "PACK", "HERO.PAC.d", "hero.rmd")),
              "unpack splits a container")
        check(os.path.isfile(os.path.join(ext, "manifest.csv")), "unpack writes a manifest")
        png = os.path.join(tmp, "png")
        out = run(os.path.join(TOOLS, "p3fes_tmx.py"), ext, "-o", png, "--gallery")
        check("Converted 2 of 2 textures" in out, "tmx tool converts the textures")
        check(os.path.isfile(os.path.join(png, "index.html")), "tmx tool writes the gallery")
        aud = os.path.join(tmp, "audio")
        out = run(os.path.join(TOOLS, "p3fes_audio.py"), ext, "-o", aud, "--wav")
        check("Wrote 2 sound files" in out, "audio tool splits the AFS archive")
        wavs = [f for _, _, fs in os.walk(os.path.join(aud, "wav")) for f in fs if f.endswith(".wav")]
        check(len(wavs) == 3, "audio tool converts all ADX files to WAV (%d)" % len(wavs))

        # --- disc patching: change a container entry and a loose file, check the new image
        mod = os.path.join(tmp, "mod")
        entry_dir = os.path.join(mod, "DATA.CVM", "BUSTUP", "PORTRAIT.BIN.d")
        os.makedirs(entry_dir)
        with open(os.path.join(ext, "DATA.CVM", "BUSTUP", "PORTRAIT.BIN.d", "portrait_a.tmx"), "rb") as fh:
            tmx_bytes = fh.read()
        with open(os.path.join(entry_dir, "portrait_a.tmx"), "wb") as fh:
            fh.write(tmx_bytes[:-50] + bytes(range(50)) + b"MORE")
        with open(os.path.join(ext, "DATA.CVM", "TABLE.BIN"), "rb") as fh:
            tbl = fh.read()
        with open(os.path.join(mod, "DATA.CVM", "TABLE.BIN"), "wb") as fh:
            fh.write(tbl[:20] + b"CHANGED" + tbl[27:])
        new_iso = os.path.join(tmp, "new.iso")
        r = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "p3fes_patch.py"), iso, mod, "-o", new_iso],
                           capture_output=True, text=True)
        check(r.returncode == 1 and "cannot tell the alignment" in r.stdout, "patch tool refuses an ambiguous container alignment")
        out = run(os.path.join(TOOLS, "p3fes_patch.py"), iso, mod, "-o", new_iso, "--align", "64")
        check("Verified" in out, "patch tool writes and verifies a new image")
        ext2 = os.path.join(tmp, "extracted2")
        run(os.path.join(TOOLS, "p3fes_unpack.py"), new_iso, "-o", ext2, "--containers")
        with open(os.path.join(ext2, "DATA.CVM", "BUSTUP", "PORTRAIT.BIN.d", "portrait_a.tmx"), "rb") as fh:
            check(fh.read() == tmx_bytes[:-50] + bytes(range(50)) + b"MORE", "patched container entry reads back")
        with open(os.path.join(ext2, "DATA.CVM", "BUSTUP", "PORTRAIT.BIN.d", "portrait_b.tmx"), "rb") as fh:
            with open(os.path.join(ext, "DATA.CVM", "BUSTUP", "PORTRAIT.BIN.d", "portrait_b.tmx"), "rb") as fh2:
                check(fh.read() == fh2.read(), "the other entry in the container is unchanged")
        with open(os.path.join(ext2, "DATA.CVM", "MODEL", "PACK", "HERO.PAC.d", "hero.rmd"), "rb") as fh:
            with open(os.path.join(ext, "DATA.CVM", "MODEL", "PACK", "HERO.PAC.d", "hero.rmd"), "rb") as fh2:
                check(fh.read() == fh2.read(), "an untouched container is unchanged")
        with open(os.path.join(entry_dir, "portrait_a.tmx"), "wb") as fh:
            fh.write(tmx_bytes + os.urandom(20000))
        r = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "p3fes_patch.py"), iso, mod, "--dry-run", "--align", "64"],
                           capture_output=True, text=True)
        check(r.returncode == 1 and "does not fit" in r.stdout, "patch tool refuses a file that does not fit")

        # --- message-file pointer list: must reproduce two real tables (known answers) and survive a move
        sys.path.insert(0, TOOLS)
        import importlib
        tt = importlib.import_module("p3fes_text")
        check(tt.encode_reloc([0x24, 0x28, 0x54, 0x58, 0x5C, 0x60]).hex(" ") == "07 16 0f", "pointer list matches a real table (1)")
        pos = [0x24 + 8 * i for i in range(15)] + [0x98] + [0xC4, 0x120, 0x17C, 0x1D8, 0x23C, 0x298, 0x2F8, 0x368, 0x36C,
                                                          0x3AC, 0x408, 0x46C, 0x4D0, 0x550, 0x5A4, 0x600]
        check(tt.encode_reloc(sorted(pos)).hex(" ") == "02 04 04 04 04 04 04 04 04 04 04 04 04 04 04 02 16 2e 2e 2e 32 2e 30 38 02 20 2e 32 32 40 2a 2e",
              "pointer list matches a real table (2)")
        # four real tables from the game (gaps between pointers, table bytes); long jumps and long runs
        real = [
            ("02 04 04 04 04 04 04 04 04 02 16 02 60 02 28 27 a1 02 02 2a 42 36 2f 91 02 54 07 ae 02",
             "4 8 8 8 8 8 8 8 8 4 44 4 192 4 80 4 4 4 4 4 4 672 4 84 132 108 4 4 4 4 4 4 4 656 168 4 4 348 4"),
            ("02 04 04 04 04 04 04 04 04 04 04 04 04 04 04 04 04 04 04 04 04 02 16 02 70 02 28 1f 65 02 02 26 50 02 6a 02 2a 1f c1 02 26 02 24 4a 07 88 02 2c 4f 69 04 02 26 48 02 7e 02 28 27 cd 02 02 24 0f c6",
             "4 8 8 8 8 8 8 8 8 8 8 8 8 8 8 8 8 8 8 8 8 4 44 4 224 4 80 4 4 4 4 4 612 4 76 160 4 212 4 84 4 4 4 4 4 704 76 4 72 148 4 4 272 4 88 4 4 4 4 4 4 4 4 4 4 4 1128 4 76 144 4 252 4 80 4 4 4 4 4 4 716 4 72 4 4 4 396"),
            ("02 04 04 04 04 04 04 04 04 02 16 07 78 0f a6 02 5c 17 ce 07 7a 22 28 02 5c 07 6a 02",
             "4 8 8 8 8 8 8 8 8 4 44 4 4 240 4 4 4 332 4 184 4 4 4 4 412 4 4 244 68 80 4 184 4 4 212 4"),
        ]
        for n, (tab, gaps) in enumerate(real):
            cur, ps = tt.BASE, []
            for d in map(int, gaps.split()):
                cur += d
                ps.append(cur)
            raw = bytes.fromhex(tab.replace(" ", ""))
            check(tt.encode_reloc(ps) == raw and tt.decode_reloc(raw) == ps, "real pointer table %d (long forms) round-trips" % (n + 3))
    # every tests/test_*.py is a self-contained test that prints "ok ..." as its last line
    for name in sorted(os.listdir(HERE)):
        if name.startswith("test_") and name.endswith(".py"):
            out = run(os.path.join(HERE, name))
            print(out.strip().splitlines()[-1] if out.strip() else "ok   %s (unittest, no output)" % name)
    print("All tests passed.")


if __name__ == "__main__":
    main()
