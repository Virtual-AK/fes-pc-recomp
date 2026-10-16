#!/usr/bin/env python3
"""Sound bank decoding: Vagi sample table and PlayStation 2 ADPCM blocks become .wav files."""
import os, struct, subprocess, sys, tempfile, wave
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'tools', 'p3fes_bed.py')

def block(flag, nib):
    return bytes([12, flag]) + bytes((nib << 4) | nib for _ in range(14))

# body: sample 0 = 2 blocks (second marked last), sample 1 starts at 48 and is 1 block marked last
bd = block(0, 1) + block(1, 2) + block(0, 3) + block(1, 4)
vagi = b'IECSigaV' + struct.pack('<III', 0x28, 1, 0x18) + struct.pack('<I', 0x20) + struct.pack('<IHBB', 0, 44100, 0, 255) + struct.pack("<IHBB", 48, 22050, 0, 255)
hd = b'IECSsreV' + struct.pack('<4I', 0x10, 0, 0, 0)[:8] + vagi
with tempfile.TemporaryDirectory() as d:
    sd = os.path.join(d, 'A', 'x.SE.d'); os.makedirs(sd)
    open(os.path.join(sd, 'x.hd'), 'wb').write(hd); open(os.path.join(sd, 'x.bd'), 'wb').write(bd)
    r = subprocess.run([sys.executable, TOOL, 'banks', d, '-o', os.path.join(d, 'r.txt')], capture_output=True, text=True)
    print(r.stdout[-300:], r.stderr)
    ok = r.returncode == 0
    try:
        w0 = wave.open(os.path.join(sd, 'wav', 's000.wav')); w1 = wave.open(os.path.join(sd, 'wav', 's001.wav'))
        ok = ok and w0.getnframes() == 56 and w0.getframerate() == 44100 and w1.getnframes() == 28 and w1.getframerate() == 22050
        f = struct.unpack('<2h', w0.readframes(2)); ok = ok and f[0] == 1
    except Exception as e:
        print(e); ok = False
    c = subprocess.run([sys.executable, TOOL, 'chunks', d, '-o', os.path.join(d, 'c.txt')], capture_output=True, text=True)
    ok = ok and c.returncode == 0 and 'SCEIVagi' in open(os.path.join(d, 'c.txt')).read()
print('ok   sound banks decode to wav' if ok else 'FAIL sound banks')
sys.exit(0 if ok else 1)
