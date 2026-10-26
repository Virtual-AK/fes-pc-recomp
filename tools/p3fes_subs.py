#!/usr/bin/env python3
"""
p3fes_subs.py - helpers for the video subtitles of the PC window (ps2run_subs_patch.py, docs/subtitles.md).

The PC window draws subtitles over the game's movies from plain .srt text files. To know which movie is playing it needs to know where
each movie lies on the disc, so this tool reads your own disc image and writes a small list:

    movies.txt:   NAME  FIRST_SECTOR  SECTOR_COUNT        (one movie per line, NAME without .SFD, upper case, sectors of the whole disc image)

Usage:
    py p3fes_subs.py movies "game.iso" -o SUBS_FOLDER      write SUBS_FOLDER/movies.txt
    py p3fes_subs.py check  FILE.srt                       say how many lines an .srt has and where it looks wrong
    py p3fes_subs.py polish FOLDER                         tidy the .srt files of a folder (originals kept in FOLDER/raw)
    py p3fes_subs.py transcribe "game.iso" -o FOLDER       listen to the movies and write timed .srt text of what is said (needs faster-whisper)

It only READS the disc image. Subtitle packs are folders of  NAME.srt  (UTF-8), for example P3CTOP.srt, P3CT001_01.srt.
"""
import argparse
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3fes_unpack as U

SECTOR = 2048


def movies(iso):
    """[(NAME, first sector of the disc image, sector count)] for every .SFD movie on the disc."""
    out = []
    with open(iso, "rb") as f:
        size = os.fstat(f.fileno()).st_size
        outer = U.Window(f, 0, size)
        for e in U.list_files(outer):
            p = e["path"]
            if p.upper().endswith(".SFD"):
                out.append((os.path.basename(p)[:-4].upper(), e["lba"], (e["size"] + SECTOR - 1) // SECTOR))
            elif p.upper().endswith(".CVM"):
                opened = U.open_cvm(f, e)
                if opened is None:
                    continue
                inner, files = opened
                for x in files:
                    if x["path"].upper().endswith(".SFD"):
                        first = (inner.base + x["lba"] * SECTOR) // SECTOR
                        out.append((os.path.basename(x["path"])[:-4].upper(), first, (x["size"] + SECTOR - 1) // SECTOR))
    return out


def write_movies(iso, folder):
    os.makedirs(folder, exist_ok=True)
    lst = movies(iso)
    with open(os.path.join(folder, "movies.txt"), "w") as f:      # two movies can share a name (the sound copy of P3CT003): both lines stay
        for name, first, count in sorted(lst, key=lambda r: r[1]):
            f.write("%s %d %d\n" % (name, first, count))
    return len(lst)


TIME = re.compile(r"(\d+):(\d\d):(\d\d)[,.](\d{1,3})\s*-->\s*(\d+):(\d\d):(\d\d)[,.](\d{1,3})")


def parse_srt(text):
    """[(start s, end s, text)] from SubRip text. Same rules as the PC window: index lines are optional, tags like <i> are dropped."""
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l for l in block.split("\n")]
        k = next((i for i, l in enumerate(lines) if TIME.search(l)), None)
        if k is None:
            continue
        m = TIME.search(lines[k])
        h1, m1, s1, ms1, h2, m2, s2, ms2 = m.groups()
        a = int(h1) * 3600 + int(m1) * 60 + int(s1) + int((ms1 + "00")[:3]) / 1000.0
        b = int(h2) * 3600 + int(m2) * 60 + int(s2) + int((ms2 + "00")[:3]) / 1000.0
        body = "\n".join(re.sub(r"<[^>]*>|\{\\[^}]*\}", "", l).strip() for l in lines[k + 1:] if l.strip())
        if body:
            cues.append((a, b, body))
    return cues


def check(path):
    cues = parse_srt(open(path, encoding="utf-8-sig").read())
    problems = []
    last = -1
    for i, (a, b, t) in enumerate(cues, 1):
        if b <= a:
            problems.append("line %d ends before it starts" % i)
        if a < last - 0.001:
            problems.append("line %d starts before the one before it ends" % i)
        if len(max(t.split("\n"), key=len)) > 60:
            problems.append("line %d has a very long row (the window wraps it)" % i)
        last = b
    return cues, problems


def srt_time(t):
    ms = int(round(t * 1000))
    return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)


def write_srt(path, cues):
    """cues: [(start s, end s, text)] -> SubRip file (UTF-8)."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for i, (a, b, t) in enumerate(cues, 1):
            f.write("%d\n%s --> %s\n%s\n\n" % (i, srt_time(a), srt_time(max(b, a + 0.4)), t.strip()))


def ffmpeg_exe():
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise SystemExit("ffmpeg was not found. Install it (sudo apt install ffmpeg) or run: pip install --break-system-packages imageio-ffmpeg")


def extract_audio(src, wav):
    """The sound track of a movie file (.SFD) as 16 kHz mono wav. Returns True when there is sound."""
    import subprocess
    r = subprocess.run([ffmpeg_exe(), "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", wav], capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(wav) and os.path.getsize(wav) > 1000


def read_wav(path):
    """16-bit mono wav -> float samples (-1..1) as faster-whisper wants them."""
    import array
    import wave
    try:
        import numpy as np
    except ImportError:
        np = None
    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
    if np is not None:
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    a = array.array("h")
    a.frombytes(raw)
    return [x / 32768.0 for x in a]


NAMES = ("Gekkoukan High School, Iwatodai Dormitory, Specialized Extracurricular Execution Squad, S.E.E.S., Tartarus, the Dark Hour, Persona, Shadows, "
         "the Velvet Room, Igor, Elizabeth, Theodore, Makoto Yuki, Minato, Yukari Takeba, Junpei Iori, Mitsuru Kirijo, Akihiko Sanada, Fuuka Yamagishi, "
         "Aigis, Ken Amada, Koromaru, Shinjiro Aragaki, Ryoji Mochizuki, Chidori, Strega, Takaya, Jin, Ikutsuki, Kirijo Group, Tatsumi Port Island, Nyx, Death.")
# the recogniser spells names by ear; these are the usual slips, fixed after the fact (whole words, any case)
FIXES = {"GeckoCon": "Gekkoukan", "Geckoukan": "Gekkoukan", "Gekokan": "Gekkoukan", "Gecko Con": "Gekkoukan", "Gecko-kan": "Gekkoukan",
         "Yukari Takeba": "Yukari Takeba", "Junpei Iori": "Junpei Iori", "Fuka": "Fuuka", "Akihiko Sinada": "Akihiko Sanada", "Metrus": "Mitsuru", "Mitsuro": "Mitsuru", "Rijo": "Kirijo", "your Kirijo": "Kirijo", "Kijo": "Kirijo", "Kirio": "Kirijo", "Kiriyo": "Kirijo", "Takeba": "Takeba", "Yukari Takebe": "Yukari Takeba"}


def fix_names(text):
    import re
    for bad, good in FIXES.items():
        text = re.sub(r"\b" + re.escape(bad) + r"\b", good, text, flags=re.I)
    return text


def group_words(words, max_chars=80, gap=0.8, tail=0.25):
    """Word timings [(start, end, text)] -> subtitle lines [(start, end, text)]: a new line at a pause of `gap` seconds, at the end of a sentence once
    the line is longish, or when it gets too long. Each line stays on screen from its first word to just after its last, and rows are 42 characters at most."""
    cues, cur = [], []

    def flush():
        if not cur:
            return
        text = " ".join(w[2].strip() for w in cur).replace("  ", " ").strip()
        if len(text) > 42:   # two rows, split at the space nearest the middle
            mid = len(text) // 2
            spaces = [i for i, c in enumerate(text) if c == " "]
            if spaces:
                k = min(spaces, key=lambda i: abs(i - mid))
                text = text[:k] + "\n" + text[k + 1:]
        cues.append([cur[0][0], cur[-1][1] + tail, fix_names(text)])
        cur.clear()

    for w in words:
        t = w[2].strip()
        if not t:
            continue
        if cur and (w[0] - cur[-1][1] > gap or sum(len(x[2].strip()) + 1 for x in cur) + len(t) > max_chars):
            flush()
        cur.append((w[0], w[1], t))
        if t[-1] in ".?!" and sum(len(x[2].strip()) + 1 for x in cur) >= 35:
            flush()
    flush()
    for i in range(len(cues) - 1):   # never overlap the next line
        cues[i][1] = min(cues[i][1], cues[i + 1][0] - 0.02)
    return [(a, max(b, a + 0.5), t) for a, b, t in cues]


HALLUCINATIONS = ("thank you for watching", "thanks for watching", "subtitles by", "please subscribe", "amara.org")   # what speech recognisers invent on music and silence


def polish(cues, max_chars=84, join_gap=2.5):
    """Tidy lines from the recogniser: drop invented sign-offs, fix usual name slips, and join a line that stopped mid-sentence with the next one
    (when they are close in time and the result is not too long). Returns new cues [(start, end, text)]."""
    out = []
    for a, b, t in cues:
        t = fix_names(" ".join(t.split("\n"))).strip()
        if not t or any(h in t.lower() for h in HALLUCINATIONS):
            continue
        if out:
            pa, pb, pt = out[-1]
            if pt[-1] not in ".?!\u2026\"" and a - pb < join_gap and len(pt) + 1 + len(t) <= max_chars:
                out[-1] = (pa, b, pt + " " + t)
                continue
        out.append((a, b, t))
    res = []
    for a, b, t in out:
        if len(t) > 42:
            mid = len(t) // 2
            spaces = [i for i, c in enumerate(t) if c == " "]
            if spaces:
                k = min(spaces, key=lambda i: abs(i - mid))
                t = t[:k] + "\n" + t[k + 1:]
        res.append((a, b, t))
    return res


def polish_folder(folder):
    """Polish every .srt in FOLDER; the untouched originals go to FOLDER/raw."""
    raw = os.path.join(folder, "raw")
    os.makedirs(raw, exist_ok=True)
    for fn in sorted(os.listdir(folder)):
        if not fn.lower().endswith(".srt"):
            continue
        p = os.path.join(folder, fn)
        keep = os.path.join(raw, fn)
        if not os.path.exists(keep):
            with open(p, "rb") as f, open(keep, "wb") as g:
                g.write(f.read())
        src = open(keep, encoding="utf-8-sig").read()
        new = polish(parse_srt(src))
        write_srt(p, new)
        print("%s: %d -> %d lines" % (fn, len(parse_srt(src)), len(new)))


def transcribe(iso, folder, model="small", language="en", only=None, redo=False, device="cpu", sensitive=False, novad=False):
    """Listen to every movie of the disc and write FOLDER/NAME.srt with what is said and when (time zero = start of the movie).
    Uses faster-whisper (pip install faster-whisper). The first run downloads the speech model (small: about 500 MB). Your disc is only read."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit("faster-whisper is not installed. Run:  pip install --break-system-packages faster-whisper imageio-ffmpeg")
    import tempfile
    os.makedirs(folder, exist_ok=True)
    wm = None
    done = 0
    with open(iso, "rb") as f, tempfile.TemporaryDirectory() as tmp:
        for name, first, count in sorted(movies(iso), key=lambda r: r[1]):
            out = os.path.join(folder, name + ".srt")
            if only and name not in only:
                continue
            if os.path.exists(out) and not redo:
                print("%s: already there" % name)
                continue
            src, wav = os.path.join(tmp, name + ".sfd"), os.path.join(tmp, name + ".wav")
            f.seek(first * SECTOR)
            with open(src, "wb") as g:
                left = count * SECTOR
                while left > 0:
                    b = f.read(min(left, 1 << 22))
                    if not b:
                        break
                    g.write(b)
                    left -= len(b)
            if not extract_audio(src, wav):
                print("%s: no sound found" % name)
                os.remove(src)
                continue
            if wm is None:
                print("loading the speech model (%s) ..." % model)
                wm = WhisperModel(model, device=device, compute_type="int8" if device == "cpu" else "float16")
            vad = dict(threshold=0.25, min_speech_duration_ms=80, min_silence_duration_ms=400, speech_pad_ms=600) if sensitive else dict(speech_pad_ms=500, min_silence_duration_ms=700)   # sensitive: catches short shouts, may also hear noise
            segs, _ = wm.transcribe(read_wav(wav), language=language, vad_filter=not novad, vad_parameters=vad, beam_size=5, word_timestamps=True, initial_prompt=NAMES, condition_on_previous_text=False, **(dict(no_speech_threshold=0.9, log_prob_threshold=-1.5) if sensitive else {}))   # the samples themselves: avoids faster-whisper's own audio reader (it clashes with new versions of av)
            words = [(w.start, w.end, w.word) for s in segs for w in (s.words or [])]
            cues = group_words(words)
            write_srt(out, cues)
            done += 1
            print("%s: %d lines" % (name, len(cues)))
            os.remove(src)
            os.remove(wav)
    print("done: %d movies written to %s (check them: the speech recogniser makes mistakes, especially with names)" % (done, folder))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("movies")
    m.add_argument("iso")
    m.add_argument("-o", "--out", required=True)
    c = sub.add_parser("check")
    c.add_argument("srt")
    pl = sub.add_parser("polish")
    pl.add_argument("folder")
    t = sub.add_parser("transcribe")
    t.add_argument("iso")
    t.add_argument("-o", "--out", required=True)
    t.add_argument("--model", default="small", help="tiny, base, small (default), medium: bigger is slower and better")
    t.add_argument("--lang", default="en", help="language spoken in the movies (en or ja)")
    t.add_argument("--only", nargs="*", help="only these movies, e.g. --only P3CTOP P3CT001_01")
    t.add_argument("--device", default="cpu", help="cpu (default, works everywhere) or cuda (a graphics card with the CUDA libraries installed)")
    t.add_argument("--sensitive", action="store_true", help="also catch very short lines (shouts like \"Wait!\"); write to a separate folder and compare, it can add noise")
    t.add_argument("--novad", action="store_true", help="do not cut out the silence first (finds very short lines, but music can turn into invented words): use on one movie and compare")
    t.add_argument("--redo", action="store_true", help="redo movies that already have a file")
    a = ap.parse_args()
    if a.cmd == "polish":
        polish_folder(a.folder)
        return 0
    if a.cmd == "transcribe":
        transcribe(a.iso, a.out, a.model, a.lang, set(a.only or []) or None, a.redo, a.device, a.sensitive, a.novad)
        return 0
    if a.cmd == "movies":
        n = write_movies(a.iso, a.out)
        print("%d movies written to %s" % (n, os.path.join(a.out, "movies.txt")))
    else:
        cues, problems = check(a.srt)
        print("%d subtitle lines" % len(cues))
        for p in problems[:20]:
            print("  " + p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
