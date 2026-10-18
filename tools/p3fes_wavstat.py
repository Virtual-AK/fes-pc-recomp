"""Summarise a 16-bit WAV file written by PS2_DUMP_AUDIO: length, peak, loudness per second and how much is silent.
Numbers only, so it is safe to share; the WAV itself is game audio and stays on your PC.
Usage: python3 p3fes_wavstat.py audio.wav [--seconds 20]
"""
import struct
import sys
import wave


def stats(path, max_rows=20):
    with wave.open(path, "rb") as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if width != 2:
            raise SystemExit("only 16-bit WAV files are supported")
        data = w.readframes(n)
    samples = struct.unpack("<%dh" % (len(data) // 2), data)
    secs = n / float(rate) if rate else 0.0
    peak = max((abs(s) for s in samples), default=0)
    rows = []
    per = rate * ch
    for i in range(0, len(samples), per):
        chunk = samples[i:i + per]
        if not chunk:
            break
        rms = (sum(s * s for s in chunk) / float(len(chunk))) ** 0.5
        rows.append((i // per, rms, max(abs(s) for s in chunk)))
    silent = sum(1 for r in rows if r[2] < 16)
    return dict(channels=ch, rate=rate, frames=n, seconds=secs, peak=peak, rows=rows, silent_seconds=silent)


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    show = 20
    if "--seconds" in argv:
        show = int(argv[argv.index("--seconds") + 1])
    s = stats(argv[0], show)
    print("channels %d, rate %d Hz, %.1f s, peak %d of 32767" % (s["channels"], s["rate"], s["seconds"], s["peak"]))
    print("silent seconds: %d of %d" % (s["silent_seconds"], len(s["rows"])))
    for sec, rms, pk in s["rows"][:show]:
        print("  second %3d  loudness %7.1f  peak %5d" % (sec, rms, pk))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
