#!/usr/bin/env python3
"""
p3fes_audio.py - get the game's sound out of the extracted files.

Run this on the folder that p3fes_unpack.py made. It does two things:

  1. Splits the .AFS voice archives into the individual sound files inside them
     (these are ADX files, written under <output>/adx/).
  2. With --wav, converts ADX sound files (music from BGM.CVM, the voice clips
     from the .AFS files, and any other .ADX) to ordinary .WAV files you can play
     in any media player (written under <output>/wav/).

The sound files are the game's own audio. They are for your own use. Never upload
them anywhere, including to the project's GitHub repository.

It only READS the extracted folder. Standard library only, Python 3.8+.
Converting to WAV is slow in plain Python (about 1-2 minutes per 100 MB of ADX), so
the first time use --limit or --only to try a few files.

Usage (from a Command Prompt in the folder that holds this script):
    py p3fes_audio.py "C:\\p3fes\\extracted"                      split the .AFS files only
    py p3fes_audio.py "C:\\p3fes\\extracted" --wav --limit 5      convert 5 files to WAV
    py p3fes_audio.py "C:\\p3fes\\extracted" --wav --only BGM     all the music
    py p3fes_audio.py "C:\\p3fes\\extracted" --wav                everything (large, slow)

Options:
    --inspect PATH  show header details and loudness of an ADX file or folder of them
    -o FOLDER     where to write (default: <input>_audio next to the input)
    --wav         also convert ADX files to WAV
    --only TEXT   only files whose path contains TEXT (repeatable)
    --limit N     only process the first N files of each kind
    --no-split    do not split the .AFS archives
"""

import argparse
import array
import math
import os
import struct
import sys
import time
import wave


class ToolError(Exception):
    pass


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0


# --------------------------------------------------------------------------- AFS

def split_afs(data):
    """Return a list of (name, bytes) for the entries of an AFS archive."""
    if len(data) < 8 or data[:4] != b"AFS\x00":
        raise ToolError("not an AFS archive")
    count = struct.unpack_from("<I", data, 4)[0]
    if count == 0 or count > 100000 or 8 + count * 8 + 8 > len(data):
        raise ToolError("odd AFS entry count")
    table = [struct.unpack_from("<II", data, 8 + i * 8) for i in range(count)]
    if any(o + s > len(data) for o, s in table):
        raise ToolError("AFS entry runs past the end of the file")
    names = [None] * count
    name_off, name_len = struct.unpack_from("<II", data, 8 + count * 8)
    if 0 < name_off and name_len == count * 48 and name_off + name_len <= len(data):
        for i in range(count):
            raw = data[name_off + i * 48: name_off + i * 48 + 32]
            end = raw.find(b"\0")
            raw = raw if end < 0 else raw[:end]
            if raw and all(32 <= c < 127 for c in raw):
                names[i] = raw.decode("ascii")
    out = []
    for i, (o, s) in enumerate(table):
        blob = data[o:o + s]
        name = names[i] or ("%04d" % i)
        if not os.path.splitext(name)[1] and blob[:2] == b"\x80\x00":
            name += ".adx"
        out.append((name, blob))
    return out


# --------------------------------------------------------------------------- ADX

def decode_adx(data, max_seconds=0):
    """Decode a standard CRI ADX file. Returns (channels, sample_rate, int16 array (interleaved))."""
    if len(data) < 20 or data[0] != 0x80 or data[1] != 0x00:
        raise ToolError("not an ADX file")
    start = struct.unpack_from(">H", data, 2)[0] + 4
    enc, block, depth, channels = data[4], data[5], data[6], data[7]
    rate, total = struct.unpack_from(">II", data, 8)
    cutoff = struct.unpack_from(">H", data, 16)[0]
    if enc != 3:
        raise ToolError("ADX encoding %d is not supported (only the standard type 3)" % enc)
    if block != 18 or depth != 4 or not 1 <= channels <= 8 or rate == 0:
        raise ToolError("unusual ADX header (block %d, depth %d, channels %d)" % (block, depth, channels))
    # filter coefficients
    a = math.sqrt(2.0) - math.cos(2.0 * math.pi * cutoff / rate)
    b = math.sqrt(2.0) - 1.0
    c = (a - math.sqrt((a + b) * (a - b))) / b
    c0 = int(round(c * 2.0 * 4096))
    c1 = int(round(-(c * c) * 4096))

    frames_per_ch = (total + 31) // 32
    if max_seconds:
        frames_per_ch = min(frames_per_ch, int(max_seconds * rate) // 32 + 1)
    total = min(total, frames_per_ch * 32)
    chans = [array.array("h") for _ in range(channels)]
    hist = [[0, 0] for _ in range(channels)]
    pos = start
    end = len(data)
    for _ in range(frames_per_ch):
        if pos + 18 * channels > end:
            break
        for ch in range(channels):
            fr = data[pos:pos + 18]
            pos += 18
            scale = (fr[0] << 8) | fr[1]
            h1, h2 = hist[ch]
            out = chans[ch]
            for byte in fr[2:]:
                n = byte >> 4
                if n > 7:
                    n -= 16
                s = ((n * scale << 12) + c0 * h1 + c1 * h2) >> 12
                if s > 32767:
                    s = 32767
                elif s < -32768:
                    s = -32768
                h2 = h1
                h1 = s
                out.append(s)
                n = byte & 15
                if n > 7:
                    n -= 16
                s = ((n * scale << 12) + c0 * h1 + c1 * h2) >> 12
                if s > 32767:
                    s = 32767
                elif s < -32768:
                    s = -32768
                h2 = h1
                h1 = s
                out.append(s)
            hist[ch][0] = h1
            hist[ch][1] = h2
    n_samples = min(total, min(len(ch) for ch in chans))
    if channels == 1:
        pcm = chans[0][:n_samples]
    else:
        pcm = array.array("h", bytes(2 * n_samples * channels))
        for ch in range(channels):
            pcm[ch::channels] = chans[ch][:n_samples]
    return channels, rate, pcm


def write_wav(path, channels, rate, pcm):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if sys.byteorder == "big":
        pcm = array.array("h", pcm)
        pcm.byteswap()
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


# --------------------------------------------------------------------------- main

def inspect_adx(path):
    """Print what is inside an ADX file's header and how loud its first 30 seconds are."""
    with open(path, "rb") as fh:
        data = fh.read()
    print("-" * 70)
    print(os.path.basename(path), "- %s" % human(len(data)))
    if len(data) < 32 or data[0] != 0x80 or data[1] != 0x00:
        print("  not an ADX file; first bytes: " + data[:16].hex(" "))
        return
    start = struct.unpack_from(">H", data, 2)[0] + 4
    enc, block, depth, channels = data[4], data[5], data[6], data[7]
    rate, total = struct.unpack_from(">II", data, 8)
    cutoff = struct.unpack_from(">H", data, 16)[0]
    print("  encoding %d, block %d, depth %d, channels %d, rate %d, samples %d (%.1f s), cutoff %d, version 0x%02X, flags 0x%02X" % (
        enc, block, depth, channels, rate, total, total / float(rate or 1), cutoff, data[18], data[19]))
    print("  header: " + data[:32].hex(" "))
    scales = [(data[start + i * 18 * channels] << 8) | data[start + i * 18 * channels + 1]
              for i in range(8) if start + (i + 1) * 18 * channels <= len(data)]
    print("  first frame scales (channel 1): " + " ".join(str(x) for x in scales))
    try:
        ch, r, pcm = decode_adx(data, 30)
    except ToolError as e:
        print("  cannot decode: " + str(e))
        return
    peak = max((abs(x) for x in pcm), default=0)
    nz = sum(1 for x in pcm if x)
    sec = len(pcm) // max(ch, 1) // max(r, 1)
    per = []
    step = r * ch
    for i in range(0, min(len(pcm), step * 30), step):
        seg = pcm[i:i + step]
        per.append(max((abs(x) for x in seg), default=0))
    print("  decoded %.1f s: loudest sample %d of 32767, %d%% of samples non-zero" % (len(pcm) / float(ch * r), peak, 100 * nz // max(len(pcm), 1)))
    print("  loudest sample in each second: " + " ".join(str(x) for x in per[:30]))


def walk(root, ext, only):
    found = []
    for dirpath, _, names in os.walk(root):
        for n in names:
            if n.lower().endswith(ext):
                rel = os.path.relpath(os.path.join(dirpath, n), root)
                if not only or any(o.lower() in rel.lower() for o in only):
                    found.append(rel)
    found.sort(key=str.lower)
    return found


def safe_name(n):
    return "".join(c if c not in '<>:"|?*\\/' and ord(c) >= 32 else "_" for c in n) or "unnamed"


def main():
    ap = argparse.ArgumentParser(description="Split .AFS archives and convert .ADX audio to .WAV.")
    ap.add_argument("folder", nargs="?", help="the folder made by p3fes_unpack.py")
    ap.add_argument("--inspect", metavar="PATH", help="show header details and loudness for an ADX file or every ADX in a folder")
    ap.add_argument("-o", "--out", help="output folder")
    ap.add_argument("--wav", action="store_true", help="also convert ADX files to WAV")
    ap.add_argument("--only", action="append", default=[], help="only paths containing this text")
    ap.add_argument("--limit", type=int, default=0, help="only the first N files of each kind")
    ap.add_argument("--no-split", action="store_true", help="do not split .AFS archives")
    args = ap.parse_args()

    if args.inspect:
        target = os.path.abspath(args.inspect)
        files = [target] if os.path.isfile(target) else [os.path.join(target, r) for r in walk(target, ".adx", args.only)]
        if args.limit:
            files = files[:args.limit]
        for f in files:
            inspect_adx(f)
        return
    if not args.folder:
        ap.error("give the extracted folder, or use --inspect PATH")
    root = os.path.abspath(args.folder)
    if not os.path.isdir(root):
        sys.exit(f"Error: {root} is not a folder.")
    out_dir = os.path.abspath(args.out) if args.out else root.rstrip("\\/") + "_audio"
    try:
        inside = os.path.commonpath([root, out_dir]) == root
    except ValueError:
        inside = False
    if inside:
        sys.exit("Error: the output folder must not be inside the input folder.")
    t0 = time.time()
    split_files = []   # (rel label, path of written adx)
    n_entries = 0
    problems = []

    if not args.no_split:
        afs = walk(root, ".afs", args.only)
        if args.limit:
            afs = afs[:args.limit]
        print(f"Splitting {len(afs)} .AFS archives")
        for i, rel in enumerate(afs):
            try:
                with open(os.path.join(root, rel), "rb") as fh:
                    entries = split_afs(fh.read())
            except (ToolError, OSError) as e:
                problems.append((rel, str(e)))
                continue
            folder = os.path.join(out_dir, "adx", os.path.splitext(rel)[0])
            os.makedirs(folder, exist_ok=True)
            used = set()
            for name, blob in entries:
                name = safe_name(name)
                base, ext = os.path.splitext(name)
                k = 1
                while name.lower() in used:
                    k += 1
                    name = f"{base}__{k}{ext}"
                used.add(name.lower())
                p = os.path.join(folder, name)
                with open(p, "wb") as fh:
                    fh.write(blob)
                n_entries += 1
                split_files.append(p)
            if i % 20 == 0:
                sys.stderr.write(f"\r  {i}/{len(afs)}")
                sys.stderr.flush()
        sys.stderr.write("\r" + " " * 30 + "\r")
        print(f"Wrote {n_entries} sound files from {len(afs) - len([1 for p in problems])} archives")

    converted = 0
    if args.wav:
        jobs = [(os.path.join(root, r), r) for r in walk(root, ".adx", args.only)]
        for p in split_files:
            if p.lower().endswith(".adx"):
                jobs.append((p, os.path.relpath(p, os.path.join(out_dir, "adx"))))
        if args.limit:
            jobs = jobs[:args.limit]
        print(f"Converting {len(jobs)} ADX files to WAV")
        minutes = 0.0
        for i, (path, rel) in enumerate(jobs):
            try:
                with open(path, "rb") as fh:
                    ch, rate, pcm = decode_adx(fh.read())
                write_wav(os.path.join(out_dir, "wav", os.path.splitext(rel)[0] + ".wav"), ch, rate, pcm)
                minutes += len(pcm) / ch / rate / 60.0
                converted += 1
            except (ToolError, OSError) as e:
                problems.append((rel, str(e)))
            sys.stderr.write(f"\r  {i + 1}/{len(jobs)}")
            sys.stderr.flush()
        sys.stderr.write("\r" + " " * 30 + "\r")
        print(f"Converted {converted} files, {minutes:.1f} minutes of audio")

    with open(os.path.join(out_dir, "problems.txt"), "w", encoding="utf-8") as fh:
        for rel, why in problems:
            fh.write(f"{rel}\t{why}\n")
    print("=" * 70)
    print(f"Done in {time.time() - t0:.0f}s. Output folder: {out_dir}")
    if problems:
        print(f"{len(problems)} files had problems; see problems.txt. First few:")
        for rel, why in problems[:5]:
            print(f"  {rel}: {why}")
    print("Reminder: the audio is the game's own. Keep it on your computer; never upload it.")


if __name__ == "__main__":
    main()
