import math, os, struct, sys, tempfile, wave
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools"))
import p3fes_wavstat as ws
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "a.wav")
    with wave.open(p, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
        frames = []
        for i in range(48000 * 2):
            v = int(8000 * math.sin(i / 20.0)) if i < 48000 else 0
            frames.append(struct.pack("<hh", v, v))
        w.writeframes(b"".join(frames))
    s = ws.stats(p)
    assert s["rate"] == 48000 and abs(s["seconds"] - 2.0) < 1e-6
    assert 7900 < s["peak"] <= 8000
    assert len(s["rows"]) == 2 and s["silent_seconds"] == 1 and s["rows"][0][1] > 1000
print("ok   wavstat reports length, peak, loudness per second and silent seconds")
