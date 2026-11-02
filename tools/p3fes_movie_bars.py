#!/usr/bin/env python3
"""
p3fes_movie_bars.py - give a bar-free movie (640x368) the dark blue bars of the disc (640x448), keeping its quality.

    python3 p3fes_movie_bars.py IN.SFD OUT.SFD [--height 448] [--color 0E1C27] [--bitrate 6400]

Why: Simply Better FMVs shows seven cutscenes without bars (P3CT002_00, P3CT008, P3CT019_01, P3CT029, P3CT030_01, P3CT030_02, P3FCT006)
and its LetterBoxBe-Gone cheat tells the game the pictures are 368 high. In P3CT008 (the shower scene) the strip above and below the picture
then comes out white. Tested in the PC window (2 November 2026): this tool's 640x448 version of P3CT008, with the two P3CT008 lines
(flag 06 at 005D4D00, height 70 at 005D4D10) taken out of the LetterBoxBe-Gone cheat, plays in full quality with the dark blue bars.

Steps for P3CT008 (Mods > File mods, Simply Better FMVs):
  1. Rename mods\\sbfmv-eng\\files\\DATA\\SFD\\P3CT008.SFD to P3CT008.SFD.off (the backup).
  2. python3 p3fes_movie_bars.py P3CT008.SFD.off P3CT008.SFD     (run from that folder)
  3. In mods\\sbfmv-eng\\files\\cheats\\94A82AAA.LetterBoxBe-Gone.pnach delete the "Fix ID 10" comment and its two patch lines (005D4D00, 005D4D10).
  4. In the launcher switch Simply Better FMVs off and on again (that rebuilds the overlay).
The bar colour (14, 28, 39) is the game's own dark blue backdrop, measured from a recording. Needs ffmpeg (on the PATH, or pip install imageio-ffmpeg) and p3fes_sfd.py next to this file.
"""
import argparse
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3fes_sfd as F


def ffmpeg_exe():
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise SystemExit("ffmpeg was not found. Install it, or run: pip install imageio-ffmpeg")


def probe_height(src):
    r = subprocess.run([ffmpeg_exe(), "-i", src], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Video:" in line:
            for tok in line.replace(",", " ").split():
                if "x" in tok and tok.split("x")[0].isdigit() and tok.split("x")[1].isdigit() and int(tok.split("x")[0]) >= 320:
                    return int(tok.split("x")[0]), int(tok.split("x")[1])
    raise SystemExit("Error: could not read the picture size of %s" % src)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--height", type=int, default=448)
    ap.add_argument("--color", default="0E1C27")
    ap.add_argument("--bitrate", type=int, default=6400, help="video kbit/s; video plus audio must stay under about 7300")
    a = ap.parse_args()
    w, h = probe_height(a.src)
    if h >= a.height:
        sys.exit("Error: the picture is already %d high, nothing to add" % h)
    top = (a.height - h) // 2
    with tempfile.TemporaryDirectory() as d:
        m2v = os.path.join(d, "v.m2v")
        cmd = [ffmpeg_exe(), "-y", "-v", "error", "-i", a.src,
               "-vf", "pad=%d:%d:0:%d:color=0x%s,format=yuv420p" % (w, a.height, top, a.color),
               "-c:v", "mpeg2video", "-g", "12", "-bf", "0", "-b:v", "%dk" % a.bitrate, "-minrate", "%dk" % a.bitrate,
               "-maxrate", "%dk" % a.bitrate, "-bufsize", "3000k", "-mbd", "rd", "-flags", "+cgop", "-sc_threshold", "1000000000",
               "-aspect", "4:3", "-r", "30000/1001", "-f", "mpeg2video", m2v]
        subprocess.run(cmd, check=True)
        F.remux(a.src, m2v, a.out, "%dx%d" % (w, a.height))
    print("wrote %s (%dx%d, bars %d pixels top and bottom)" % (a.out, w, a.height, top))


if __name__ == "__main__":
    main()
