#!/usr/bin/env python3
"""
p3fes_split_video.py - cut a long screen recording into pieces that are small enough to send.

    python3 p3fes_split_video.py "recording.mp4"                 pieces of 4 minutes, next to the recording: recording_part1.mp4 ...
    python3 p3fes_split_video.py "recording.mp4" --minutes 2     shorter pieces
    python3 p3fes_split_video.py "recording.mp4" --parts 2       exactly two pieces of equal length

No re-encoding (the picture is not touched), so it takes seconds. The cuts fall on the nearest key frame, so a piece can be a second longer or shorter.
Needs ffmpeg (sudo apt install ffmpeg, or pip install --break-system-packages imageio-ffmpeg).
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p3fes_subs import ffmpeg_exe


def duration(path):
    r = subprocess.run([ffmpeg_exe(), "-i", path], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise SystemExit("could not read the length of " + path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--minutes", type=float, default=4.0)
    ap.add_argument("--parts", type=int, default=0)
    a = ap.parse_args()
    total = duration(a.video)
    seg = total / a.parts if a.parts > 0 else a.minutes * 60
    base, ext = os.path.splitext(a.video)
    pattern = base + "_part%d" + ext
    n = max(1, int(total // seg + (0.01 if total % seg else 0)))
    for i in range(n):
        start = i * seg
        cmd = [ffmpeg_exe(), "-v", "error", "-y", "-ss", "%.2f" % start, "-i", a.video, "-t", "%.2f" % seg, "-c", "copy", "-avoid_negative_ts", "make_zero", pattern % (i + 1)]
        subprocess.run(cmd, check=True)
        print("%s  (%.0f MB)" % (pattern % (i + 1), os.path.getsize(pattern % (i + 1)) / 1e6))
    print("done: %d pieces" % n)


if __name__ == "__main__":
    main()
