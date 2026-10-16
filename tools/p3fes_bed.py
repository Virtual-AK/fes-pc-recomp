#!/usr/bin/env python3
"""Survey of the game's sound sequence files (.BED, .SE, magic "BED4") and related audio data.

Reads only your own extracted files and writes a report with sizes, header numbers and short hex dumps of the
first bytes of a few files. Nothing else from the files is copied into the report.

  py p3fes_bed.py survey extracted          write bed_survey.txt
  py p3fes_bed.py hex extracted\\path\\X.BED   dump one file's start and its 16-bit and 32-bit words
  py p3fes_bed.py split extracted           split every .SE file (a container of sound banks) into a .SE.d folder
  py p3fes_bed.py samples extracted         write bed_samples.txt: header tables of a few .BED files
  py p3fes_bed.py banks extracted           decode the sound banks inside the .SE.d folders to .wav files
  py p3fes_bed.py chunks extracted          write se_chunks.txt: the SCEI chunks of every .hd and .sq in the .SE.d folders
  py p3fes_bed.py seq extracted             check every bank's sequences and render a few to WAV (seq_report.txt)
"""
import argparse, collections, os, struct, sys, wave

EXTS = {"bed", "se"}
HEADER_WORDS = 24


def hex_dump(data, n=128):
    out = []
    for i in range(0, min(n, len(data)), 16):
        c = data[i:i + 16]
        out.append("%06X  %-47s  %s" % (i, " ".join("%02X" % b for b in c), "".join(chr(b) if 32 <= b < 127 else "." for b in c)))
    return "\n".join(out)


def words32(data, n=HEADER_WORDS):
    k = min(n, len(data) // 4)
    return struct.unpack_from("<%dI" % k, data, 0) if k else ()


def walk(root):
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            yield os.path.join(dp, fn)


def survey(root, report_path):
    magic_by_ext = collections.Counter()        # (extension, first 4 bytes) -> count
    beds = []                                   # (path, data) for files with the BED4 magic or a .bed/.se extension
    total = 0
    for path in walk(root):
        total += 1
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        try:
            with open(path, "rb") as fh:
                head = fh.read(4)
        except OSError:
            continue
        magic = head if all(32 <= b < 127 for b in head) and len(head) == 4 else None
        if magic == b"BED4" or ext in EXTS:
            magic_by_ext[(ext, head.decode("latin-1") if magic else head.hex())] += 1
            with open(path, "rb") as fh:
                beds.append((path, fh.read()))
        elif magic and ext not in ("rmd", "tmx", "bmd", "bf"):
            magic_by_ext[(ext, magic.decode("latin-1"))] += 0   # keep the table small: only note unusual audio-like magics
    L = []
    L.append("Sound sequence survey: %d files scanned, %d sequence files found" % (total, len(beds)))
    if not beds:
        L.append("No .BED/.SE files or BED4 magic found. Run p3fes_unpack.py first.")
    else:
        L.append("\nExtension and first four bytes (count)")
        for (ext, mg), c in sorted(magic_by_ext.items(), key=lambda kv: -kv[1]):
            if c:
                L.append("  .%-4s %-10s %d" % (ext, mg, c))
        per_folder = collections.Counter(os.path.relpath(os.path.dirname(p), root).split(os.sep)[0:3].__str__() for p, _ in beds)
        L.append("\nFiles per top folders")
        for k, c in per_folder.most_common(12):
            L.append("  %6d  %s" % (c, k))
        sizes = sorted(len(d) for _, d in beds)
        L.append("\nSizes: min %d, median %d, max %d, total %d bytes" % (sizes[0], sizes[len(sizes) // 2], sizes[-1], sum(sizes)))
        # header words, per position
        L.append("\nFirst %d 32-bit words across files: distinct values, most common (value x count), and how often the word"
                 "\nequals the file size, is below the file size (offset-like), or is a multiple of 4" % HEADER_WORDS)
        cols = [collections.Counter() for _ in range(HEADER_WORDS)]
        eq_size = [0] * HEADER_WORDS
        below = [0] * HEADER_WORDS
        mult4 = [0] * HEADER_WORDS
        for _, d in beds:
            for i, w in enumerate(words32(d)):
                cols[i][w] += 1
                eq_size[i] += w == len(d)
                below[i] += 0 < w < len(d)
                mult4[i] += w % 4 == 0
        for i, c in enumerate(cols):
            if not c:
                break
            top = ", ".join("%X x%d" % kv for kv in c.most_common(4))
            L.append("  w%02d  %5d distinct  size-equal %4d  below-size %4d  mult4 %4d  | %s" % (
                i, len(c), eq_size[i], below[i], mult4[i], top))
        # strongest guess at a table: words after the header that rise steadily
        L.append("\nExamples (smallest, median, largest): first 128 bytes")
        by_size = sorted(beds, key=lambda pd: len(pd[1]))
        for label, (p, d) in (("smallest", by_size[0]), ("median", by_size[len(by_size) // 2]), ("largest", by_size[-1])):
            L.append("\n%s: %s, %d bytes" % (label, os.path.basename(p), len(d)))
            L.append(hex_dump(d))
        # trailing zero padding and zero runs
        pads = collections.Counter(len(d) % 16 for _, d in beds)
        L.append("\nFile size mod 16: " + ", ".join("%d x%d" % kv for kv in sorted(pads.items())))
        # does the file end with a block of zeros
        tails = sum(1 for _, d in beds if d[-16:] == bytes(16))
        L.append("Files ending in 16 zero bytes: %d" % tails)
    text = "\n".join(L)
    with open(report_path, "w") as fh:
        fh.write(text + "\n")
    print(text[:3000])
    print("\nFull report written to %s" % report_path)


# ---------------------------------------------------------------- sound banks (.hd + .bd)
# .hd: Sony "SCEI" chunks, each with an 8 byte name written backwards by the little-endian words (IECSigaV = SCEIVagi).
# The Vagi chunk lists the samples: after the chunk name, u32 chunk size, u32 highest index, then u32 offsets (from the
# start of the chunk) of each entry; an entry is u32 offset into the .bd, u16 sample rate, 2 more bytes.
# .bd: PlayStation 2 ADPCM, 16-byte blocks: shift/filter byte, flag byte (1 = last block, 2 = loops, 4 = loop start), 14 data bytes.
ADPCM_K = ((0, 0), (60, 0), (115, -52), (98, -55), (122, -60))


def read_vagi(hd):
    at = hd.find(b"IECSigaV")
    if at < 0:
        return []
    size, top = struct.unpack_from("<II", hd, at + 8)
    entries = []
    for i in range(top + 1):
        o = struct.unpack_from("<I", hd, at + 16 + 4 * i)[0]
        if o == 0xFFFFFFFF or at + o + 8 > len(hd):
            entries.append(None)
            continue
        off, rate = struct.unpack_from("<IH", hd, at + o)
        entries.append((off, rate))
    return entries


def decode_adpcm(bd, start, stop):
    """Decode blocks from start until a block marked last (flag 1) or stop. Returns (samples, loop_start_or_None, looped)."""
    h1 = h2 = 0
    out = []
    loop_start = None
    looped = False
    pos = start
    while pos + 16 <= min(stop, len(bd)):
        head, flags = bd[pos], bd[pos + 1]
        shift, filt = head & 15, min((head >> 4) & 15, 4)
        if shift > 12:
            shift = 9
        k0, k1 = ADPCM_K[filt]
        if flags & 4 and loop_start is None:
            loop_start = len(out)
        for i in range(28):
            b = bd[pos + 2 + i // 2]
            n = (b >> 4) if i & 1 else (b & 15)
            if n >= 8:
                n -= 16
            v = ((n << 12) >> shift) + ((h1 * k0 + h2 * k1 + 32) >> 6)
            v = -32768 if v < -32768 else 32767 if v > 32767 else v
            out.append(v)
            h2, h1 = h1, v
        pos += 16
        if flags & 2:
            looped = True
        if flags & 1:
            break
    return out, loop_start, looped


def decode_banks(root, report_path, limit=0):
    dirs = sorted(p for p in (os.path.join(dp, d) for dp, ds, _ in os.walk(root) for d in ds) if p.lower().endswith(".se.d"))
    if limit:
        dirs = dirs[:limit]
    if not dirs:
        sys.exit("No .SE.d folders found under %s. Run: py p3fes_bed.py split extracted" % root)
    total = bad = 0
    rates, counts, secs = collections.Counter(), collections.Counter(), []
    loops = 0
    problems = []
    for i, d in enumerate(dirs, 1):
        if i % 100 == 0:
            print("  ... %d of %d" % (i, len(dirs)), flush=True)
        names = {os.path.splitext(n)[1].lower(): os.path.join(d, n) for n in os.listdir(d)}
        if ".hd" not in names or ".bd" not in names:
            problems.append("%s: missing .hd or .bd" % os.path.basename(d))
            continue
        hd = open(names[".hd"], "rb").read()
        bd = open(names[".bd"], "rb").read()
        ents = read_vagi(hd)
        counts[len(ents)] += 1
        starts = sorted(e[0] for e in ents if e)
        out_dir = os.path.join(d, "wav")
        os.makedirs(out_dir, exist_ok=True)
        for n, e in enumerate(ents):
            if not e:
                continue
            off, rate = e
            if off >= len(bd):
                bad += 1
                problems.append("%s sample %d: offset %d beyond the %d byte body" % (os.path.basename(d), n, off, len(bd)))
                continue
            nxt = next((x for x in starts if x > off), len(bd))
            pcm, ls, lp = decode_adpcm(bd, off, nxt)
            if not pcm:
                continue
            with wave.open(os.path.join(out_dir, "s%03d.wav" % n), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate or 44100)
                w.writeframes(struct.pack("<%dh" % len(pcm), *pcm))
            total += 1
            rates[rate] += 1
            secs.append(len(pcm) / float(rate or 44100))
            loops += lp
    secs.sort()
    L = ["Decoded %d samples from %d banks (%d offsets outside the body, %d with loop flags)" % (total, len(dirs), bad, loops), "",
         "Samples per bank: " + ", ".join("%d x%d" % kv for kv in sorted(counts.items())[:15]), "",
         "Sample rates: " + ", ".join("%d Hz x%d" % kv for kv in rates.most_common(8))]
    if secs:
        L.append("Length: min %.3f s, median %.3f s, max %.3f s" % (secs[0], secs[len(secs) // 2], secs[-1]))
    L += problems[:20]
    text = "\n".join(L)
    open(report_path, "w").write(text + "\n")
    print(text)
    print("\nWAV files are in the wav folder inside each .SE.d folder. Report written to %s" % report_path)


def scei_chunks(data):
    """Yield (name, start, size) for the contiguous SCEI chunks of an .hd or .sq entry (size includes the 8-byte name)."""
    pos = 0
    while pos + 12 <= len(data):
        size = struct.unpack_from("<I", data, pos + 8)[0]
        if size < 12 or pos + size > len(data):
            yield ("??", pos, len(data) - pos)
            return
        raw = data[pos:pos + 8]
        name = raw[0:4][::-1].decode("latin-1") + raw[4:8][::-1].decode("latin-1")
        yield (name, pos, size)
        pos += size


def chunk_census(root, report_path):
    dirs = sorted(p for p in (os.path.join(dp, d) for dp, ds, _ in os.walk(root) for d in ds) if p.lower().endswith(".se.d"))
    if not dirs:
        sys.exit("No .SE.d folders found under %s. Run: py p3fes_bed.py split extracted" % root)
    stats = collections.defaultdict(list)       # (kind, chunk name) -> sizes
    examples = collections.defaultdict(list)    # (kind, chunk name) -> [(size, bytes)]
    layouts = collections.Counter()
    whole = {".hd": [], ".sq": []}
    for d in dirs:
        for fn in os.listdir(d):
            ext = os.path.splitext(fn)[1].lower()
            if ext not in (".hd", ".sq"):
                continue
            data = open(os.path.join(d, fn), "rb").read()
            whole[ext].append((len(data), data))
            seq = []
            for name, start, size in scei_chunks(data):
                seq.append(name)
                stats[(ext, name)].append(size)
                examples[(ext, name)].append((size, data[start:start + size]))
            layouts[(ext, " ".join(seq))] += 1
    L = ["SCEI chunks in %d sound banks. Names are shown the right way round (the file stores each 4 letters backwards)." % len(dirs), ""]
    L.append("Chunk order per file (count)")
    for (ext, lay), c in layouts.most_common(25):
        L.append("  %s  %5d  %s" % (ext, c, lay))
    L.append("\nChunk sizes (bytes, including the 8-byte name)")
    for (ext, name), sz in sorted(stats.items()):
        sz = sorted(sz)
        L.append("  %s %-9s x%-5d min %6d median %6d max %6d" % (ext, name, len(sz), sz[0], sz[len(sz) // 2], sz[-1]))
    L.append("\nWhole-file examples: smallest, median and largest .hd, then .sq (full hex, these are small parameter tables)")
    for ext in (".hd", ".sq"):
        lst = sorted(whole[ext], key=lambda x: x[0])
        if not lst:
            continue
        for label, (n, data) in (("smallest", lst[0]), ("median", lst[len(lst) // 2]), ("largest", lst[-1])):
            L.append("\n%s %s, %d bytes%s" % (label, ext, n, " (first 512 bytes)" if n > 512 else ""))
            L.append(hex_dump(data, 512))
    text = "\n".join(L)
    open(report_path, "w").write(text + "\n")
    print(text[:2500])
    print("\nFull report written to %s" % report_path)


# ---------------------------------------------------------------- sequences (.sq) and tones (.hd SCEISetb)
# .sq, chunk SCEISesq at c. Everything below is an offset from c unless said otherwise; 0xFFFFFFFF means "none".
#   c+0x0C  highest group number (u32), c+0x10 u32 X: the group table starts at c+0x10+X (it was 0x10)
#   group table: one u32 offset per group; a group: u32 highest block number, u32 Y, u8 volume, u8 pan, u16 tempo/resolution
#   (0x03E8), u32 none, then the block table at group+4+Y (one u32 offset per block, most "none").
#   block: u32 offset of the events from the block start (0x10), u8 volume, u8 pan, u16 resolution, u32 event bytes, u32 0.
#   events: MIDI-like. variable length delay (7 bits per byte, high bit = more), then a status byte:
#     0x90 note on  + 3 bytes (0, key, velocity);  0xA0 note off + 3 bytes (0, key, 0);  0xFF end (no data).
# .hd, chunk SCEISetb at s: the tone table starts at s+0x20: u16 record size (0x32), u8 highest tone, u8 0xFF, then the records.
#   A record: u16 sample number (index into SCEIVagi), byte 2 ?, byte 3 volume (0x7F), byte 4 pan (0x40 = middle), ...
# A note's key picks the tone with that number.
NONE = 0xFFFFFFFF


def _u32(d, o):
    if o < 0 or o + 4 > len(d):
        raise ValueError("offset 0x%X outside the file" % o)
    return struct.unpack_from("<I", d, o)[0]


def parse_sq(sq):
    """Return the event blocks of a .sq: list of dicts (group, block, volume, pan, resolution, data)."""
    ch = {n: (st, z) for n, st, z in scei_chunks(sq)}
    if "SCEISesq" not in ch:
        raise ValueError("no SCEISesq chunk")
    c, size = ch["SCEISesq"]
    blocks = []
    top = _u32(sq, c + 0x0C)
    ttab = c + 0x10 + _u32(sq, c + 0x10)
    for gi in range(top + 1):
        go = _u32(sq, ttab + 4 * gi)
        if go == NONE:
            continue
        g = c + go
        gmax = _u32(sq, g)
        gtab = g + 4 + _u32(sq, g + 4)
        for bi in range(gmax + 1):
            bo = _u32(sq, gtab + 4 * bi)
            if bo == NONE:
                continue
            b = c + bo
            start = b + _u32(sq, b)
            length = _u32(sq, b + 8)
            if start + length > len(sq):
                raise ValueError("block %d/%d runs past the end of the file" % (gi, bi))
            blocks.append({"group": gi, "block": bi, "volume": sq[b + 4], "pan": sq[b + 5],
                           "resolution": struct.unpack_from("<H", sq, b + 6)[0], "data": sq[start:start + length]})
    return blocks


def _vlq(data, pos):
    v = 0
    while True:
        if pos >= len(data):
            raise ValueError("number runs past the end")
        b = data[pos]
        pos += 1
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            return v, pos


def parse_events(data):
    """Return [(tick, status, key, velocity, set, extra)]; raises ValueError on a status byte we do not know.
    0xB0 (a control event, seen with control numbers 0x0E and 0x0F): three bytes (set, key, control, kept in the velocity
    slot), then a variable-length number and a little-endian u16, returned as extra = (number, u16)."""
    pos, tick, out = 0, 0, []
    while pos < len(data):
        delta, pos = _vlq(data, pos)
        tick += delta
        if pos >= len(data):
            raise ValueError("missing status byte")
        st = data[pos]
        pos += 1
        if st in (0x90, 0xA0):
            if pos + 3 > len(data):
                raise ValueError("note event cut short")
            out.append((tick, st, data[pos + 1], data[pos + 2], data[pos], None))
            pos += 3
        elif st == 0xB0:
            if pos + 3 > len(data):
                raise ValueError("control event cut short")
            tset, key, ctl = data[pos], data[pos + 1], data[pos + 2]
            val, pos = _vlq(data, pos + 3)
            if pos + 2 > len(data):
                raise ValueError("control event cut short")
            out.append((tick, st, key, ctl, tset, (val, struct.unpack_from("<H", data, pos)[0])))
            pos += 2
        elif st == 0xFF:
            out.append((tick, st, 0, 0, 0, None))
            break
        else:
            raise ValueError("unknown status byte 0x%02X" % st)
    return out


def parse_tones(hd):
    """Return a list of tone sets; each set is a list of tones (dicts with sample, volume, pan).
    SCEISetb at s: s+0x10 holds the offset of a directory: u32 highest set number, then one u32 offset (from s) per set.
    A set: u32 (8), u16 record size (0x32), u8 highest tone, u8 0xFF, then the 50-byte tone records."""
    ch = {n: (st, z) for n, st, z in scei_chunks(hd)}
    if "SCEISetb" not in ch:
        raise ValueError("no SCEISetb chunk")
    s, size = ch["SCEISetb"]
    dr = s + _u32(hd, s + 0x10)
    top = _u32(hd, dr)
    sets = []
    for si in range(top + 1):
        so = _u32(hd, dr + 4 + 4 * si)
        if so == NONE:
            sets.append([])
            continue
        th = s + so + 4
        if th + 4 > s + size:
            raise ValueError("tone set %d starts outside its chunk" % si)
        rec = struct.unpack_from("<H", hd, th)[0]
        n = hd[th + 2] + 1
        if rec < 5 or th + 4 + n * rec > s + size:
            raise ValueError("tone set %d does not fit in its chunk (record size %d, %d tones, chunk %d bytes)" % (si, rec, n, size))
        tones = []
        for i in range(n):
            o = th + 4 + i * rec
            tones.append({"sample": struct.unpack_from("<H", hd, o)[0], "volume": hd[o + 3], "pan": hd[o + 4]})
        sets.append(tones)
    return sets


def render_block(events, tones, pcm_of, ticks_per_second, block_volume, rate=44100):
    """Mix the note-ons of one block into mono 16-bit samples at `rate`."""
    notes = [(e[0], e[2], e[3], e[4]) for e in events if e[1] == 0x90]      # control events (0xB0) are not applied yet
    if not notes:
        return []
    mix = {}
    end = 0
    for t, key, vel, tset in notes:
        group = tones[tset] if tset < len(tones) else (tones[0] if tones else [])
        if key >= len(group):
            continue
        tone = group[key]
        pcm, srate = pcm_of(tone["sample"])
        if not pcm:
            continue
        gain = (vel / 127.0) * (tone["volume"] / 127.0) * (block_volume / 127.0)
        start = int(t / float(ticks_per_second) * rate)
        step = srate / float(rate)
        n = int(len(pcm) / step)
        for i in range(n):
            x = i * step
            j = int(x)
            f = x - j
            a = pcm[j]
            b = pcm[j + 1] if j + 1 < len(pcm) else a
            mix[start + i] = mix.get(start + i, 0.0) + (a + (b - a) * f) * gain
        end = max(end, start + n)
    out = [0] * end
    for i, v in mix.items():
        out[i] = -32768 if v < -32768 else 32767 if v > 32767 else int(v)
    return out


def sequence_check(root, report_path, wav_banks=20, tps=2000, wav_dir="seq_wav"):
    dirs = sorted(p for p in (os.path.join(dp, d) for dp, ds, _ in os.walk(root) for d in ds) if p.lower().endswith(".se.d"))
    if not dirs:
        sys.exit("No .SE.d folders found under %s. Run: py p3fes_bed.py split extracted" % root)
    status, blocks_n, events_n = collections.Counter(), 0, 0
    fails = collections.defaultdict(list)
    groups, blocks_per, tempos, vols, ends = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    keys_bad = vag_bad = tone_counts = 0
    key_use = collections.Counter()
    set_use = collections.Counter()
    ctl_use, ctl_time = collections.Counter(), collections.Counter()
    wavs = 0
    setb_example = None
    over = {}                                   # bank -> (tones, highest key used, samples, tone record size, Setb size)
    fail_hex = {}                               # failure text -> hex of the block's events
    fail_full = []
    for i, d in enumerate(dirs, 1):
        if i % 100 == 0:
            print("  ... %d of %d" % (i, len(dirs)), flush=True)
        names = {os.path.splitext(n)[1].lower(): os.path.join(d, n) for n in os.listdir(d)}
        try:
            sq = open(names[".sq"], "rb").read()
            hd = open(names[".hd"], "rb").read()
            bd = open(names[".bd"], "rb").read()
        except (KeyError, OSError):
            fails["missing .sq, .hd or .bd"].append(os.path.basename(d))
            continue
        try:
            blocks = parse_sq(sq)
        except (ValueError, struct.error) as e:
            fails["sq: %s" % e].append(os.path.basename(d))
            continue
        try:
            tones = parse_tones(hd)
        except (ValueError, struct.error) as e:
            fails["hd: %s" % str(e)[:60]].append(os.path.basename(d))
            if setb_example is None:
                st = next((x for x in scei_chunks(hd) if x[0] == "SCEISetb"), None)
                if st:
                    setb_example = (os.path.basename(d), hd[st[1]:st[1] + min(st[2], 160)])
            tones = []
        groups[len(set(b["group"] for b in blocks))] += 1
        blocks_per[len(blocks)] += 1
        ents = vagi = None
        ents = read_vagi(hd)
        cache = {}

        def pcm_of(n):
            if n not in cache:
                e = ents[n] if n < len(ents) else None
                if not e:
                    cache[n] = ([], 44100)
                else:
                    starts = sorted(x[0] for x in ents if x)
                    nxt = next((x for x in starts if x > e[0]), len(bd))
                    cache[n] = (decode_adpcm(bd, e[0], nxt)[0], e[1] or 44100)
            return cache[n]
        for b in blocks:
            blocks_n += 1
            tempos[b["resolution"]] += 1
            vols[b["volume"]] += 1
            try:
                evs = parse_events(b["data"])
            except ValueError as e:
                fails["events: %s" % e].append("%s %d/%d" % (os.path.basename(d), b["group"], b["block"]))
                fail_hex.setdefault("events: %s" % e, []).append((os.path.basename(d), b["data"][:48]))
                fail_full.append(("%s %d/%d" % (os.path.basename(d), b["group"], b["block"]), b["data"]))
                continue
            events_n += len(evs)
            ends[bool(evs) and evs[-1][1] == 0xFF] += 1
            for e in evs:
                t, st, k, v, tset = e[:5]
                status[st] += 1
                if st == 0xB0:
                    ctl_use[(v, e[5][1])] += 1
                    ctl_time[e[5][0]] += 1
                if st == 0x90:
                    key_use[k] += 1
                    set_use[tset] += 1
                    grp = tones[tset] if tset < len(tones) else []
                    if tones and k >= len(grp):
                        keys_bad += 1
                        sb = next((x for x in scei_chunks(hd) if x[0] == "SCEISetb"), (0, 0, 0))
                        old = over.get(os.path.basename(d), (len(grp), 0, len(ents), 0, sb[2]))
                        over[os.path.basename(d)] = (old[0], max(old[1], k), old[2], old[3], old[4])
                    elif tones and grp[k]["sample"] >= len(ents):
                        vag_bad += 1
            if tones and i <= wav_banks:
                pcm = render_block(evs, tones, pcm_of, tps, b["volume"])
                if pcm:
                    os.makedirs(wav_dir, exist_ok=True)
                    with wave.open(os.path.join(wav_dir, "%s_g%02d_b%02d.wav" % (os.path.basename(d)[:-5], b["group"], b["block"])), "wb") as w:
                        w.setnchannels(1)
                        w.setsampwidth(2)
                        w.setframerate(44100)
                        w.writeframes(struct.pack("<%dh" % len(pcm), *pcm))
                    wavs += 1
    L = ["Sequence check of %d banks: %d event blocks, %d events, %d WAV files written (first %d banks, %d ticks per second)" % (
        len(dirs), blocks_n, events_n, wavs, wav_banks, tps), ""]
    L.append("Event status bytes: " + ", ".join("0x%02X x%d" % kv for kv in sorted(status.items())))
    L.append("Blocks that end with 0xFF: " + ", ".join("%s x%d" % kv for kv in ends.items()))
    L.append("Note keys beyond the tone table: %d; tones pointing past the sample table: %d" % (keys_bad, vag_bad))
    L.append("Groups per bank: " + ", ".join("%d x%d" % kv for kv in sorted(groups.items())[:10]))
    L.append("Blocks per bank: " + ", ".join("%d x%d" % kv for kv in sorted(blocks_per.items())[:14]))
    L.append("Block resolution values: " + ", ".join("%d x%d" % kv for kv in tempos.most_common(6)))
    L.append("Block volumes: " + ", ".join("%d x%d" % kv for kv in vols.most_common(8)))
    if ctl_use:
        L.append("Control events (0xB0): control number and 16-bit value: " + ", ".join("0x%02X/%d x%d" % (k[0], k[1], n) for k, n in sorted(ctl_use.items())))
        L.append("  their variable-length number: " + ", ".join("%d x%d" % kv for kv in sorted(ctl_time.items())))
    L.append("Tone sets used by notes: " + ", ".join("%d x%d" % kv for kv in sorted(set_use.items())))
    L.append("Most used note keys: " + ", ".join("%d x%d" % kv for kv in key_use.most_common(12)))
    L.append("\nThings that did not parse (%d kinds)" % len(fails))
    for why, who in sorted(fails.items(), key=lambda kv: -len(kv[1]))[:12]:
        L.append("  %5d  %s   e.g. %s" % (len(who), why, ", ".join(who[:3])))
    L.append("\nBanks with note keys beyond their tone table: %d. First ones: tones, highest key used, samples, Setb chunk bytes" % len(over))
    for name, (nt, mk, ns, _, sz) in list(over.items())[:12]:
        L.append("  %-14s tones %3d  highest key %3d  samples %3d  Setb %6d bytes" % (name, nt, mk, ns, sz))
    shown = 0
    for name, (nt, mk, ns, _, sz) in over.items():
        if shown >= 2:
            break
        hdp = os.path.join(root, "x")
        for dd in dirs:
            if os.path.basename(dd) == name:
                hdd = open([os.path.join(dd, n) for n in os.listdir(dd) if n.lower().endswith(".hd")][0], "rb").read()
                st = next((x for x in scei_chunks(hdd) if x[0] == "SCEISetb"), None)
                if st:
                    L.append("\nStart of the SCEISetb chunk of %s (first 256 bytes) and the end of the chunk (last 64 bytes):" % name)
                    L.append(hex_dump(hdd[st[1]:st[1] + 256], 256))
                    L.append(hex_dump(hdd[st[1] + st[2] - 64:st[1] + st[2]], 64))
                    shown += 1
                break
    for why, lst in fail_hex.items():
        L.append("\nExamples of '%s' (first 48 bytes of the event data):" % why)
        for name, raw in lst[:3]:
            L.append("  %s: %s" % (name, raw.hex(" ")))
    full = fail_full
    if full:
        L.append("\nEvery block that failed, in full (bank, group/block, event bytes):")
        for name, raw in full[:40]:
            L.append("  %s: %s" % (name, raw.hex(" ")))
    if setb_example:
        L.append("\nFirst 160 bytes of the SCEISetb chunk of %s (a bank whose tone table did not fit):" % setb_example[0])
        L.append(hex_dump(setb_example[1], 160))
    text = "\n".join(L)
    open(report_path, "w").write(text + "\n")
    print(text)
    print("\nSequence WAV files are in the %s folder. Report written to %s" % (wav_dir, report_path))


class _View:
    def __init__(self, data):
        self.data, self.size = data, len(data)

    def read_at(self, pos, n):
        return self.data[pos:pos + n]


def split_se(root, report_path):
    """Split .SE files (repeated [252-byte name][u32 size][data] entries) next to themselves."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import p3fes_unpack as U
    files = [p for p in walk(root) if p.lower().endswith(".se")]
    if not files:
        sys.exit("No .SE files found under %s" % root)
    ext_counts, magics, sizes, fails = collections.Counter(), collections.defaultdict(collections.Counter), collections.defaultdict(list), []
    examples = {}
    entries_per = collections.Counter()
    for i, path in enumerate(files, 1):
        if i % 100 == 0:
            print("  ... %d of %d" % (i, len(files)), flush=True)
        with open(path, "rb") as fh:
            data = fh.read()
        res = U.analyse_pak(_View(data))
        if not res["ok"]:
            fails.append((os.path.basename(path), res.get("reason"), res.get("stop_offset")))
            continue
        out = path + ".d"
        os.makedirs(out, exist_ok=True)
        entries_per[len(res["entries"])] += 1
        for (name, length), off in zip(res["entries"], res["starts"]):
            body = data[off + 256: off + 256 + length]
            with open(os.path.join(out, "".join(c if c.isalnum() or c in "._-" else "_" for c in name)), "wb") as fh:
                fh.write(body)
            ext = os.path.splitext(name)[1].lower()
            ext_counts[ext] += 1
            magics[ext][body[:8].hex(" ")] += 1
            sizes[ext].append(length)
            examples.setdefault(ext, body)
    L = ["Split %d .SE files: %d could not be read as containers" % (len(files), len(fails)), "",
         "Entries per file: " + ", ".join("%d entries x%d files" % kv for kv in sorted(entries_per.items())), "", "Entry types"]
    for ext, c in ext_counts.most_common():
        sz = sorted(sizes[ext])
        L.append("  %-6s %5d entries, size min %d, median %d, max %d" % (ext or "(none)", c, sz[0], sz[len(sz) // 2], sz[-1]))
        L.append("         first 8 bytes: " + ", ".join("%s x%d" % kv for kv in magics[ext].most_common(4)))
    for ext, body in examples.items():
        if ext in (".hd", ".bd") or len(examples) <= 3:
            L.append("\nFirst 192 bytes of one %s entry" % (ext or "(none)"))
            L.append(hex_dump(body, 192))
    if fails:
        L.append("\nFiles that failed: " + "; ".join("%s (%s at %s)" % f for f in fails[:10]))
    text = "\n".join(L)
    open(report_path, "w").write(text + "\n")
    print(text[:2500])
    print("\nFull report written to %s" % report_path)


def bed_samples(root, report_path):
    beds = []
    for p in walk(root):
        if p.lower().endswith(".bed"):
            with open(p, "rb") as fh:
                d = fh.read()
            if d[:4] == b"BED4":
                beds.append((p, d))
    if not beds:
        sys.exit("No BED4 files found under %s" % root)
    by = sorted(beds, key=lambda pd: len(pd[1]))
    kind7 = [pd for pd in by if len(pd[1]) >= 28 and struct.unpack_from("<I", pd[1], 0x1C)[0] == 7]
    pick = [("smallest", by[0]), ("median", by[len(by) // 2]), ("largest", by[-1])]
    if kind7:
        pick += [("smallest with first entry type 7", kind7[0]), ("median with first entry type 7", kind7[len(kind7) // 2])]
    L = ["BED4 samples (%d files). For each: 24-byte rows from offset 4, then the next 256 bytes after the table region" % len(beds)]
    for label, (p, d) in pick:
        L.append("\n== %s: %s, %d bytes" % (label, os.path.basename(p), len(d)))
        L.append("offset  six 32-bit words")
        for r in range(40):
            o = 4 + 24 * r
            if o + 24 > len(d):
                break
            L.append("%06X  %s" % (o, " ".join("%08X" % w for w in struct.unpack_from("<6I", d, o))))
        offs = []
        for sec in (0x1C, 0x330):
            for r in range(32):
                o = sec + 24 * r
                if o + 24 <= len(d):
                    t, off, par = struct.unpack_from("<3I", d, o)
                    if t == 7:
                        offs.append((o, off, par))
        L.append("used rows (type 7): " + ", ".join("row@%X -> data 0x%X flags 0x%X" % x for x in offs))
        for o, off, par in offs:
            L.append("first 96 bytes at 0x%X:" % off)
            L.append(hex_dump(d[off:off + 96], 96))
        L.append("last 64 bytes of the file:")
        L.append(hex_dump(d[-64:], 64))
    text = "\n".join(L)
    open(report_path, "w").write(text + "\n")
    print(text[:1800])
    print("\nFull report written to %s" % report_path)


def main():
    ap = argparse.ArgumentParser(description="Survey the game's sound sequence files.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("survey", help="survey every .BED/.SE file under a folder")
    s.add_argument("folder")
    s.add_argument("-o", "--output", default="bed_survey.txt")
    sp = sub.add_parser("split", help="split .SE containers into .hd and .bd files")
    sp.add_argument("folder")
    sp.add_argument("-o", "--output", default="se_report.txt")
    sq = sub.add_parser("seq", help="check sequences and render some to WAV")
    sq.add_argument("folder")
    sq.add_argument("-o", "--output", default="seq_report.txt")
    sq.add_argument("--wav-banks", type=int, default=20, help="render WAV files for the first N banks (default 20)")
    sq.add_argument("--wav-dir", default="seq_wav", help="where the rendered WAV files go (default seq_wav)")
    sq.add_argument("--ticks-per-second", type=int, default=2000, help="timing guess (default 2000)")
    ck = sub.add_parser("chunks", help="census of the SCEI chunks in .SE.d banks")
    ck.add_argument("folder")
    ck.add_argument("-o", "--output", default="se_chunks.txt")
    bk = sub.add_parser("banks", help="decode .SE.d sound banks to .wav")
    bk.add_argument("folder")
    bk.add_argument("-o", "--output", default="bank_report.txt")
    bk.add_argument("--limit", type=int, default=0, help="only the first N banks")
    sm = sub.add_parser("samples", help="header tables of a few .BED files")
    sm.add_argument("folder")
    sm.add_argument("-o", "--output", default="bed_samples.txt")
    h = sub.add_parser("hex", help="dump the start of one file")
    h.add_argument("file")
    h.add_argument("-n", type=int, default=256)
    a = ap.parse_args()
    if a.cmd == "survey":
        survey(os.path.abspath(a.folder), a.output)
    elif a.cmd == "split":
        split_se(os.path.abspath(a.folder), a.output)
    elif a.cmd == "seq":
        sequence_check(os.path.abspath(a.folder), a.output, a.wav_banks, a.ticks_per_second, a.wav_dir)
    elif a.cmd == "chunks":
        chunk_census(os.path.abspath(a.folder), a.output)
    elif a.cmd == "banks":
        decode_banks(os.path.abspath(a.folder), a.output, a.limit)
    elif a.cmd == "samples":
        bed_samples(os.path.abspath(a.folder), a.output)
    else:
        with open(a.file, "rb") as fh:
            d = fh.read()
        print("%s: %d bytes" % (a.file, len(d)))
        print(hex_dump(d, a.n))
        print("16-bit words: " + " ".join("%04X" % w for w in struct.unpack_from("<%dH" % min(48, len(d) // 2), d, 0)))
        print("32-bit words: " + " ".join("%08X" % w for w in words32(d, 32)))


if __name__ == "__main__":
    main()
