#!/usr/bin/env python3
"""
p3fes_sfd.py - look inside the game's .SFD movies and put a new picture into one.

    python3 p3fes_sfd.py info MOVIE.SFD
    python3 p3fes_sfd.py remux ORIGINAL.SFD NEW_VIDEO.m2v -o OUT.SFD [--size 1280x896]

An SFD is a stream of 2048-byte sectors, one MPEG pack each (MPEG-1 style pack header, 12 bytes):
  - the first sectors are a header (system header, padding, and private-stream-2 sectors that hold the CRI "SofdecStream" description:
    the name of the video and audio parts and, for the video, the picture size as three bytes "WWW HHH" in the same 12-bit packing as
    an MPEG sequence header, for example 28 01 c0 = 640 x 448);
  - then video sectors (stream e0: 12 bytes of PES header, 2018 bytes of MPEG-2 video; the sector that holds the start of a picture
    carries its PTS and DTS, the others are stuffed with 0xFF) and audio sectors (stream c0: ADX audio) mixed in time order;
  - then a last sector with the end code 00 00 01 b9.
The pack header's time stamp (SCR) goes up by 201 ticks (of 90 kHz) a sector; the mux rate is 917,500 bytes/s.

`remux` keeps the original header sectors and every audio sector, replaces all video sectors with the ones made from NEW_VIDEO.m2v
(an MPEG-2 elementary stream with no B-frames, like the game's own: I-frame then 11 P-frames) and mixes the audio back in by time.
`--size` rewrites the picture size in the header. Make the stream for example with
    ffmpeg -i in.SFD -vf scale=1280:896:flags=lanczos -c:v mpeg2video -g 12 -bf 0 -b:v 6000k -maxrate 6500k -bufsize 3000k -flags +cgop -sc_threshold 1000000000 -aspect 4:3 -f mpeg2video out.m2v
Keep video and audio together under the mux rate (about 7.3 Mbit/s), or the time stamps stop matching the pack times.
"""
import argparse
import struct
import sys

SECTOR = 2048
TICK = 201          # SCR ticks a sector
FRAME = 3003        # 90 kHz ticks a frame at 29.97 fps
PAYLOAD = 2018      # video bytes in a full video sector
AUDIO_LEAD = 6000   # an audio sector is placed once the picture time reaches its time minus this


def pes_list(sec):
    """[(stream id, offset of its start code, length field)] for the packets of one sector."""
    pos = 12
    out = []
    while pos + 6 <= SECTOR and sec[pos:pos + 3] == b"\0\0\1":
        c = sec[pos + 3]
        ln = struct.unpack(">H", sec[pos + 4:pos + 6])[0]
        out.append((c, pos, ln))
        pos += 6 + ln
    return out


def read_pts(b):
    return (((b[0] >> 1) & 7) << 30) | (b[1] << 22) | ((b[2] >> 1) << 15) | (b[3] << 7) | (b[4] >> 1)


def put_ts(marker, t):
    return bytes([(marker << 4) | (((t >> 30) & 7) << 1) | 1, (t >> 22) & 0xFF, (((t >> 15) & 0x7F) << 1) | 1, (t >> 7) & 0xFF, ((t & 0x7F) << 1) | 1])


def pack_header(k, rate=b"\x80\x8f\x5d"):
    scr = k * TICK + 1
    return b"\0\0\1\xba" + put_ts(2, scr) + rate


def parse(data):
    n = len(data) // SECTOR
    header, audio = [], []
    first_media = None
    for k in range(n):
        sec = data[k * SECTOR:(k + 1) * SECTOR]
        ids = [p[0] for p in pes_list(sec)]
        if first_media is None and (0xE0 in ids or 0xC0 in ids):
            first_media = k
        if first_media is None:
            header.append(sec)
        elif 0xC0 in ids:
            p = [x for x in pes_list(sec) if x[0] == 0xC0][0]
            h = sec[p[1] + 6:p[1] + 6 + 20]
            i = 0
            while h[i] == 0xFF:
                i += 1
            if h[i] >> 6 == 1:      # STD buffer field
                i += 2
            pts = read_pts(h[i:i + 5]) if h[i] >> 4 in (2, 3) else None
            audio.append((pts, sec))
    return header, audio, n


def info(path):
    data = open(path, "rb").read()
    header, audio, n = parse(data)
    print("%s: %d sectors, %d header sectors, %d audio sectors, %d video sectors" % (path, n, len(header), len(audio), n - len(header) - len(audio) - 1))
    for k, sec in enumerate(header):
        i = sec.find(b"SofdecStream")
        if i >= 0:
            j = sec.find(b".M2V")
            print("sector %d: video entry at 0x%x, size bytes %s" % (k, j, sec[j + 13:j + 29].hex(" ")))
    if audio:
        print("first audio PTS %s, last %s" % (audio[0][0], audio[-1][0]))


def video_pictures(es):
    """Byte positions of picture start codes (00 00 01 00) in the elementary stream."""
    pos, out = 0, []
    while True:
        i = es.find(b"\0\0\1\0", pos)
        if i < 0:
            return out
        out.append(i)
        pos = i + 4


def remux(orig, m2v, out, size=None):
    data = open(orig, "rb").read()
    es = open(m2v, "rb").read()
    header, audio, _n = parse(data)
    header = [bytearray(h) for h in header]
    if size:
        w, h = [int(x) for x in size.lower().split("x")]
        seq = data.find(b"\0\0\1\xb3")
        old = data[seq + 4:seq + 7]            # width and height as the MPEG sequence header packs them
        new = bytes([(w >> 4) & 0xFF, ((w & 15) << 4) | (h >> 8), h & 0xFF])
        hit = 0
        for hs in header:
            m = hs.find(b".M2V")
            i = hs.find(old, m) if m >= 0 else -1
            if i >= 0:
                hs[i:i + 3] = new
                hit += 1
        if not hit:
            sys.exit("Error: did not find the picture size in the header sectors")
    pics = video_pictures(es)
    if not pics or pics[0] != 0 and es[:4] != b"\0\0\1\xb3":
        sys.exit("Error: %s does not look like an MPEG-2 video stream" % m2v)
    pic_at = {p: k for k, p in enumerate(pics)}        # byte position -> picture number (decode = display order, no B-frames)
    es += b"\0\0\1\xb7"
    es += b"\0" * (-len(es) % PAYLOAD)               # zero bytes after the sequence end code fill the last sector
    chunks = [es[i:i + PAYLOAD] for i in range(0, len(es), PAYLOAD)]
    sectors = [bytes(h) for h in header]
    ai = 0
    cur_t = 0
    k_out = len(sectors)

    def add(sec_body):
        nonlocal k_out
        sectors.append(pack_header(k_out) + sec_body)
        k_out += 1

    for ci, ch in enumerate(chunks):
        start = ci * PAYLOAD
        first = None
        for p in pics:
            if start <= p < start + len(ch):
                first = p
                break
            if p >= start + len(ch):
                break
        if first is not None:
            cur_t = pic_at[first] * FRAME
        while ai < len(audio) and audio[ai][0] is not None and audio[ai][0] <= cur_t + AUDIO_LEAD:
            body = audio[ai][1][12:]
            add(body)
            ai += 1
        if first is not None:
            t = pic_at[first] * FRAME
            hdr = b"\x60\x2e" + put_ts(3, t) + put_ts(1, t)
        else:
            hdr = b"\xff" * 9 + b"\x60\x2e\x0f"
        body = b"\0\0\1\xe0" + struct.pack(">H", len(hdr) + len(ch)) + hdr + ch
        add(body)
    while ai < len(audio):
        add(audio[ai][1][12:])
        ai += 1
    sectors.append(b"\0\0\1\xb9" + b"\xff" * (SECTOR - 4))
    with open(out, "wb") as f:
        for s in sectors:
            assert len(s) == SECTOR, len(s)
            f.write(s)
    print("wrote %s: %d sectors (%d MB), %d pictures, %d audio sectors" % (out, len(sectors), len(sectors) * SECTOR // 1048576, len(pics), len(audio)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["info", "remux"])
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out")
    ap.add_argument("--size")
    a = ap.parse_args()
    if a.mode == "info":
        for f in a.files:
            info(f)
    else:
        if len(a.files) != 2 or not a.out:
            sys.exit("Error: remux ORIGINAL.SFD NEW_VIDEO.m2v -o OUT.SFD")
        remux(a.files[0], a.files[1], a.out, a.size)


if __name__ == "__main__":
    main()
