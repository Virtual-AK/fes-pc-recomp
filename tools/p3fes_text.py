#!/usr/bin/env python3
"""
p3fes_text.py - get the game's text out of the .BMD message files (and the message data inside .BF scripts), and put edited text back.

EXTRACT  (read-only on your extracted folder):
    py p3fes_text.py extract "C:\\p3fes\\extracted"
  Writes one plain-text file per message file under <input>_text, e.g.
  C:\\p3fes\\extracted_text\\BTL.CVM\\BATTLE\\PANEL\\BP_TUTORIAL.BIN.d\\bp_tutorial1.bmd.txt
  Scripts (.BF) carry their own message data; it is written to <name>.bf.txt and repacked into the script.
  (21 scripts list their messages out of order; those are read-only for now.)
  It also checks every file: it rebuilds each one from what it read and compares it with
  the original, byte for byte. The summary tells you how many matched exactly.
  If the text folder already exists, extract stops instead of overwriting your edits; use
  -o for another folder, or --overwrite when you really want to start over.

REPACK  (builds modified .BMD files; never touches your extracted folder):
    py p3fes_text.py repack "C:\\p3fes\\extracted_text" "C:\\p3fes\\extracted" -o "C:\\p3fes\\mod_files"
  Reads your edited text files and writes new .BMD files (only the ones you changed) under
  the output folder, in the same folder layout as the extracted files.

How to read a text file:
    @msg 0 BTUT_11T type=0 speaker=FFFF pad=1     one message: its name and settings
    @speaker 1 Aigis                               a speaker name shown with the message (editable)
    @tail 0a0b...                                  unknown extra data after a message (kept as is)
    @line 1                                        the start of a line of the message
    The first time an enemy is analyzed,           readable text
    {F2 08 FF FF F1 3F}                            a control code (colour, pause, voice...)
  A real line break inside the text is a line break in the file. Edit the readable text
  and keep every {..} code unless you know what it does. Do not add or remove @msg or
  @line markers (that is not supported yet). Messages the tool does not understand yet
  appear as "@raw" lines and are kept unchanged. A line that ends in {NOEND} has no
  normal end code; leave that marker in place.

The text is the game's own. Keep these files on your computer; never upload them.
Standard library only, Python 3.8+.
"""
import argparse
import collections, os, struct, sys

BASE = 0x20          # all pointers inside a message file count from here
NAME_LEN = 24
END = b"\xF1\x04"    # every line ends with this code


class ToolError(Exception):
    pass


WHY = []   # (reason, detail) collected while parsing, used by the diagnostics report


# ----------------------------------------------------------------- text <-> bytes

def bytes_to_text(b):
    """Bytes -> editable text. Plain characters stay as they are. Everything else is shown
    as {hex} tokens, one token per game code, so each can be seen and moved as a unit:
      F1..FF   a control code. The code takes 2 * (second hex digit) bytes in total
               (F1 = 2 bytes, F2 = 4, F3 = 6, F4 = 8, F5 = 10 ...), and its parameters can
               look like letters, which is why the whole code is always shown as hex.
      80..EF   the first half of a two-byte character (font symbol); shown with its pair.
    Other bytes that are not plain text are shown as single {hex} tokens."""
    out, run = [], []
    def flush():
        if run:
            out.append("{" + " ".join("%02X" % x for x in run) + "}")
            run.clear()
    i, n = 0, len(b)
    while i < n:
        x = b[i]
        if x >= 0xF1 and i + 2 * (x & 15) <= n:
            flush()
            k = 2 * (x & 15)
            out.append("{" + " ".join("%02X" % y for y in b[i:i + k]) + "}")
            i += k
        elif 0x80 <= x <= 0xEF and i + 1 < n:
            run.extend(b[i:i + 2])
            i += 2
        elif x == 0x0A:
            flush(); out.append("\n"); i += 1
        elif 0x20 <= x < 0x7F and x not in (0x7B, 0x7D):
            flush(); out.append(chr(x)); i += 1
        else:
            run.append(x); i += 1
    flush()
    return "".join(out)


def text_to_bytes(t):
    out = bytearray()
    i = 0
    while i < len(t):
        c = t[i]
        if c == "{":
            j = t.find("}", i)
            if j < 0:
                raise ToolError("a '{' has no closing '}'")
            try:
                out.extend(bytes.fromhex(t[i + 1:j]))
            except ValueError:
                raise ToolError("bad code {%s}: use pairs of hex digits like {F2 08}" % t[i + 1:j])
            i = j + 1
        elif c == "\n":
            out.append(0x0A); i += 1
        elif c == "\r":
            i += 1
        elif 0x20 <= ord(c) < 0x7F and c != "}":
            out.append(ord(c)); i += 1
        else:
            raise ToolError("character %r cannot be stored; use a {hex} code" % c)
    return bytes(out)


# ----------------------------------------------------------------- parse / build

def end_code(mtype):
    return END if mtype == 0 else b"\0"      # menu (type 1) lines end with a zero byte


def line_to_text(b, mtype=0):
    """A stored line (including its end code) as readable text."""
    e = end_code(mtype)
    if b.endswith(e):
        return bytes_to_text(b[:-len(e)])
    return bytes_to_text(b) + "{NOEND}"


def text_to_line(t, mtype=0):
    if t.endswith("{NOEND}"):
        return text_to_bytes(t[:-7])
    return text_to_bytes(t) + end_code(mtype)


def msg_head(m):
    """Bytes between the name and the line positions."""
    if m["type"] == 1:
        return struct.pack("<HHI", m["a"], len(m["lines"]), m["b"])
    return struct.pack("<HH", len(m["lines"]), m["speaker"])


def build_dialog(m, start):
    """Bytes of a type-0 message that begins at absolute offset `start`."""
    lines = m["lines"]                      # each line keeps its own end code
    n = len(lines)
    head = msg_head(m)
    hdr_end = start + NAME_LEN + len(head) + 4 * n + 4
    offs, pos = [], hdr_end
    for l in lines:
        offs.append(pos - BASE)
        pos += len(l)
    body = b"".join(lines)
    textsize = len(body) + m["pad"]
    out = bytearray(m["name"].encode("ascii").ljust(NAME_LEN, b"\0"))
    out += head
    for o in offs:
        out += struct.pack("<I", o)
    out += struct.pack("<I", textsize)
    out += body + b"\0" * m["pad"]
    names = m.get("names")
    if names is not None:
        while len(out) % 4:
            out += b"\0"
        ptr = start + len(out) + 4 * len(names)
        table, strings = bytearray(), bytearray()
        for nm in names:
            table += struct.pack("<I", ptr + len(strings) - BASE)
            strings += nm + b"\0"
        out += table + strings
    out += m.get("tail", b"")
    while len(out) % 4:
        out += b"\0"
    return bytes(out)


def msg_pointers(m, start):
    """File positions of every pointer field inside a parsed type-0/1 message, or None if unknown."""
    if m["kind"] != "dialog":
        return None
    n = len(m["lines"])
    hl = 8 if m["type"] == 1 else 4
    pos = [start + NAME_LEN + hl + 4 * k for k in range(n)]
    names = m.get("names")
    if names:
        core = NAME_LEN + hl + 4 * n + 4 + len(b"".join(m["lines"])) + m["pad"]
        ts = start + ((core + 3) & ~3)
        pos += [ts + 4 * j for j in range(len(names))]
    elif m.get("tail"):
        return None                      # unknown extra data may hold pointers we cannot see
    return pos


def all_pointers(msgs, starts):
    count = len(msgs)
    pos = [BASE + 8 * i + 4 for i in range(count)] + [BASE + 8 * count]
    for m, s0 in zip(msgs, starts):
        p = msg_pointers(m, s0)
        if p is None:
            return None
        pos += p
    return sorted(pos)


def encode_reloc(pos):
    """Relocation table: the compressed list of where the pointers are.

    Starting at 0x20, each entry moves forward to the next pointer:
      even byte v          -> next pointer is 2*v bytes ahead (4 .. 508)
      byte with low bits 111 -> a run of n pointers, each one word (4 bytes) after the last,
                              n = (byte >> 3) + 2  (2 .. 33)
      byte with low bits 01  -> long jump: this byte and the next form a 16-bit little-endian
                              number v, the jump is v - 1 bytes
    Worked out from the real tables of the game (see docs/formats.md). Anything else raises
    ToolError."""
    out = bytearray()
    cur, i, n = BASE, 0, len(pos)
    while i < n:
        p = pos[i]
        d = p - cur
        if d == 4:
            r = 1
            while i + r < n and r < 33 and pos[i + r] == p + 4 * r:
                r += 1
            if r >= 2:
                out.append(7 | ((r - 2) << 3))
                cur = pos[i + r - 1]
                i += r
                continue
        if d <= 0 or d % 4:
            raise ToolError("relocation jump of %d bytes cannot be encoded" % d)
        if d // 2 <= 0xFE:
            out.append(d // 2)
        elif d + 1 <= 0xFFFF:
            out += struct.pack("<H", d + 1)
        else:
            raise ToolError("relocation jump of %d bytes cannot be encoded yet" % d)
        cur = p
        i += 1
    return bytes(out)


def decode_reloc(data):
    """Inverse of encode_reloc; returns the pointer positions, or None if the bytes use a form
    that is not understood."""
    pos, cur, i = [], BASE, 0
    while i < len(data):
        b = data[i]
        if b & 1 == 0:
            cur += 2 * b
            i += 1
            pos.append(cur)
        elif b & 7 == 7:
            for _ in range((b >> 3) + 2):
                cur += 4
                pos.append(cur)
            i += 1
        elif b & 3 == 1 and i + 1 < len(data):
            cur += (b | data[i + 1] << 8) - 1
            i += 2
            pos.append(cur)
        else:
            return None
    return pos


def parse_names(region, ts):
    """After a message's text there can be a table of speaker names: pointers, then the names."""
    if len(region) < 8:
        return None
    p0 = struct.unpack_from("<I", region, 0)[0]
    d = p0 + BASE - ts
    if d < 4 or d % 4 or d // 4 > 32 or d > len(region):
        return None
    k = d // 4
    ptrs = struct.unpack_from("<%dI" % k, region, 0)
    names, pos = [], d
    for i in range(k):
        if ptrs[i] != ts + pos - BASE:
            return None
        end = region.find(b"\0", pos)
        if end < 0:
            return None
        names.append(bytes(region[pos:end]))
        pos = end + 1
    if any(region[pos:]):
        return None
    return names


def parse_dialog(data, s, e, mtype=0):
    def no(reason, detail=""):
        WHY.append((reason, detail, data[s:min(e, s + 72)].hex(" ")))
        return None
    try:
        name = data[s:s + NAME_LEN].split(b"\0")[0]
        if not name or any(not 32 <= c < 127 for c in name):
            return no("name is not plain text")
        if mtype == 1:
            a_, n, b_ = struct.unpack_from("<HHI", data, s + NAME_LEN)
            speaker, hl = a_, 8
        else:
            n, speaker = struct.unpack_from("<HH", data, s + NAME_LEN)
            a_ = b_ = 0
            hl = 4
        if n == 0 or s + NAME_LEN + hl + 4 * n + 4 > e:
            return no("line count %d does not fit" % n, "type=%d speaker=%04X" % (mtype, speaker))
        offs = list(struct.unpack_from("<%dI" % n, data, s + NAME_LEN + hl))
        textsize = struct.unpack_from("<I", data, s + NAME_LEN + hl + 4 * n)[0]
        hdr_end = s + NAME_LEN + hl + 4 * n + 4
        if offs[0] + BASE != hdr_end or hdr_end + textsize > e:
            return no("first line position wrong" if offs[0] + BASE != hdr_end else "text size runs past message",
                      "speaker=%04X lines=%d first=0x%X expected=0x%X" % (speaker, n, offs[0] + BASE, hdr_end))
        if any(offs[i] >= offs[i + 1] for i in range(n - 1)):
            return no("line positions out of order")
        ends = [o + BASE for o in offs[1:]] + [None]
        lines = []
        for i in range(n):
            a = offs[i] + BASE
            if ends[i] is None:
                chunk = data[a:hdr_end + textsize]
                stripped = chunk.rstrip(b"\0")
                pad = len(chunk) - len(stripped)
                if mtype == 1 and pad >= 1:          # the first zero is the line's own end code
                    stripped += b"\0"
                    pad -= 1
                chunk = stripped
            else:
                chunk = data[a:ends[i]]
                pad = 0
            lines.append(chunk)
        m = {"kind": "dialog", "name": name.decode("ascii"), "speaker": speaker, "type": mtype, "a": a_, "b": b_,
             "lines": lines, "pad": pad, "tail": b""}
        core = len(build_dialog(m, s))            # without any tail, aligned
        raw_core = NAME_LEN + hl + 4 * n + 4 + textsize
        actual = data[s:e]
        if actual[:raw_core] != build_dialog(m, s)[:raw_core]:
            return no("rebuilt message differs", "speaker=%04X" % speaker)
        rest = actual[raw_core:]
        ts = (s + raw_core + 3) & ~3
        names = parse_names(data[ts:e], ts) if not any(data[s + raw_core:ts]) else None
        tail = b"" if names is not None else rest.rstrip(b"\0")
        if names is not None:
            m["names"] = names
        elif tail:
            m["tail"] = tail
            WHY.append(("message has extra bytes after its text", "speaker=%04X tail=%d bytes" % (speaker, len(tail)),
                        tail[:72].hex(" ")))
        built = build_dialog(m, s)
        if actual[:len(built)] != built or any(actual[len(built):]):
            return no("rebuilt message differs after tail", "speaker=%04X" % speaker)
        return m
    except (struct.error, IndexError):
        return no("read error")


def parse_bmd(data):
    if len(data) < 48 or data[8:12] != b"MSG1":
        raise ToolError("not an MSG1 message file")
    ftype, size = struct.unpack_from("<II", data, 0)
    reloc_off, reloc_size, count = struct.unpack_from("<III", data, 16)
    word = struct.unpack_from("<I", data, 28)[0]
    if size != len(data) or reloc_off + reloc_size != len(data) or count == 0 \
            or BASE + 8 * count + 16 > len(data):
        raise ToolError("unexpected header values")
    entries = [struct.unpack_from("<II", data, BASE + 8 * i) for i in range(count)]
    starts = [off + BASE for _, off in entries]
    ordered = starts == sorted(starts)
    if max(starts) >= reloc_off:
        raise ToolError("message positions are out of order")
    # Some files (a few scripts) list messages out of order, or point two entries at one message. They are read
    # with each message ending where the next one in file order begins; such files cannot be rebuilt (read-only).
    file_order = sorted(set(starts))
    first = BASE + 8 * count + 16
    msgs = []
    for i, (t, off) in enumerate(entries):
        s = starts[i]
        if ordered:
            e = starts[i + 1] if i + 1 < count else reloc_off
        else:
            k = file_order.index(s)
            e = file_order[k + 1] if k + 1 < len(file_order) else reloc_off
        m = parse_dialog(data, s, e, t) if t in (0, 1) else None
        if m is None:
            m = {"kind": "raw", "name": data[s:s + NAME_LEN].split(b"\0")[0].decode("ascii", "replace"),
                 "blob": data[s:e]}
        m["type"] = t
        if m["kind"] == "dialog":
            # zero bytes after a message that the builder would not write again are kept with the message
            try:
                rb = build_dialog(m, s)
                tailz = data[s:e][len(rb):]
                if len(rb) < e - s and data[s:s + len(rb)] == rb and not any(tailz):
                    m["zpad"] = len(tailz)
            except (KeyError, struct.error, ValueError):
                pass
        msgs.append(m)
    f = {"ordered": ordered, "ftype": ftype, "word": word, "first": first, "starts": starts, "reloc_off": reloc_off,
         "reloc": data[reloc_off:], "msgs": msgs, "gap": data[BASE + 8 * count: BASE + 8 * count + 16], "endpad": 0}
    # A few files keep zero bytes between the last message and the pointer table (4 in the f035 scripts).
    try:
        rebuilt_off = struct.unpack_from("<I", build_bmd(f)[0], 16)[0]
        if rebuilt_off < reloc_off and not any(data[rebuilt_off:reloc_off]):
            f["endpad"] = reloc_off - rebuilt_off
    except (ToolError, struct.error):
        pass
    return f


def build_bmd(f):
    msgs = f["msgs"]
    count = len(msgs)
    pos = BASE + 8 * count + 16
    # Messages go back in the order they have in the file. In most files that is the table order; in a few
    # the table lists them in another order, and two entries can share one message (the later one is an alias).
    loose = f.get("ordered") is False
    order = sorted(range(count), key=lambda i: (f["starts"][i], i)) if loose else list(range(count))
    starts, blobs, owner = [0] * count, [], {}
    for i in order:
        m = msgs[i]
        key = f["starts"][i] if loose else None
        if key in owner:
            j, ob = owner[key]
            if (build_dialog(m, starts[j]) + bytes(m.get("zpad", 0)) if m["kind"] == "dialog" else m["blob"]) != ob:
                raise ToolError("two entries (%s and %s) share one message and were edited differently"
                                % (msgs[j]["name"], m["name"]))
            starts[i] = starts[j]
            continue
        starts[i] = pos
        b = build_dialog(m, pos) + bytes(m.get("zpad", 0)) if m["kind"] == "dialog" else m["blob"]
        blobs.append(b)
        if key is not None:
            owner[key] = (i, b)
        pos += len(b)
    while pos % 4:
        pos += 1
    pos += f.get("endpad", 0)
    reloc_off = pos
    reloc = f["reloc"]
    if f.get("regen_reloc"):
        pts = all_pointers(msgs, starts)
        if pts is None:
            raise ToolError("a message with unknown extra data would move; its pointers cannot be rebuilt")
        reloc = encode_reloc(pts)
    out = bytearray()
    size = reloc_off + len(reloc)
    out += struct.pack("<II", f["ftype"], size) + b"MSG1" + struct.pack("<I", 0)
    out += struct.pack("<III", reloc_off, len(reloc), count) + struct.pack("<I", f["word"])
    for m, s in zip(msgs, starts):
        out += struct.pack("<II", m["type"], s - BASE)
    gap = bytearray(f["gap"])
    if f.get("reloc_off") is not None:
        old = struct.unpack_from("<I", gap, 0)[0]
        struct.pack_into("<I", gap, 0, old + reloc_off - f["reloc_off"])
    else:
        struct.pack_into("<I", gap, 0, reloc_off - BASE)
    out += gap
    for b in blobs:
        out += b
    out += b"\0" * (reloc_off - len(out))
    out += reloc
    return bytes(out), starts


# ----------------------------------------------------------------- text file I/O

def to_textfile(rel, f):
    out = ["# p3fes text v1 - edit the readable text, keep the {..} codes. See p3fes_text.py.",
           "@file " + rel.replace("\\", "/")]
    for i, m in enumerate(f["msgs"]):
        if m["kind"] == "dialog":
            if m["type"] == 1:
                out.append("@msg %d %s type=1 a=%04X b=%08X pad=%d" % (i, m["name"], m["a"], m["b"], m["pad"]))
            else:
                out.append("@msg %d %s type=%d speaker=%04X pad=%d" % (i, m["name"], m["type"], m["speaker"], m["pad"]))
            for k, l in enumerate(m["lines"]):
                out.append("@line %d" % (k + 1))
                out.append(line_to_text(l, m["type"]))
            for k, nm in enumerate(m.get("names") or []):
                out.append("@speaker %d %s" % (k + 1, bytes_to_text(nm)))
            if m["tail"]:
                out.append("@tail " + m["tail"].hex())
            out.append("@end")
        else:
            out.append("@raw %d %s type=%d hex=%s" % (i, m["name"], m["type"], m["blob"].hex()))
    return "\n".join(out) + "\n"


def parse_textfile(text):
    """Return (source path, list of messages as in parse_bmd but text-derived)."""
    src, msgs, cur, buf, line_no = None, [], None, None, 0
    def close_line():
        nonlocal buf
        if buf is not None and cur is not None:
            t = "\n".join(buf)
            cur["lines"].append(text_to_line(t, cur["type"]))
        buf = None
    for raw in text.split("\n"):
        if raw.startswith("@file "):
            src = raw[6:].strip()
        elif raw.startswith("@msg "):
            close_line()
            p = raw.split()
            kv = dict(x.split("=", 1) for x in p[3:] if "=" in x)
            cur = {"kind": "dialog", "index": int(p[1]), "name": p[2], "type": int(kv["type"]),
                   "speaker": int(kv.get("speaker", "0"), 16), "a": int(kv.get("a", "0"), 16),
                   "b": int(kv.get("b", "0"), 16), "pad": int(kv["pad"]), "lines": [], "tail": b"", "names": None}
            msgs.append(cur)
        elif raw.startswith("@line "):
            close_line()
            buf = []
        elif raw.startswith("@speaker ") and cur is not None:
            close_line()
            if cur.get("names") is None:
                cur["names"] = []
            cur["names"].append(text_to_bytes(raw.split(" ", 2)[2] if raw.count(" ") >= 2 else ""))
        elif raw.startswith("@tail ") and buf is not None:
            close_line()
            cur["tail"] = bytes.fromhex(raw[6:].strip())
        elif raw.startswith("@end"):
            close_line()
            cur = None
        elif raw.startswith("@raw "):
            p = raw.split()
            kv = dict(x.split("=", 1) for x in p[3:] if "=" in x)
            msgs.append({"kind": "raw", "index": int(p[1]), "name": p[2], "type": int(kv["type"]),
                         "blob": bytes.fromhex(kv["hex"])})
        elif raw.startswith("#") and buf is None:
            pass
        elif buf is not None:
            buf.append(raw)
    close_line()
    return src, msgs


# ----------------------------------------------------------------- messages inside .BF scripts

def bf_sections(data):
    """Section table of a .BF script (FLW0): list of [type, element size, count, start], or None."""
    if len(data) < 0x20 or data[8:12] != b"FLW0":
        return None
    n = struct.unpack_from("<I", data, 0x10)[0]
    if n > 16 or 0x20 + 16 * n > len(data):
        return None
    secs = [list(struct.unpack_from("<4I", data, 0x20 + 16 * i)) for i in range(n)]
    if any(st + es * cnt > len(data) for _, es, cnt, st in secs):
        return None
    return secs


def message_bytes(rel, data):
    """The message file for a .BMD, or the message data section inside a .BF script."""
    if not rel.lower().endswith(".bf"):
        return data
    secs = bf_sections(data)
    sec = next((x for x in secs or [] if x[0] == 3 and x[1] == 1), None)
    if sec is None or sec[2] < 48:
        raise ToolError("this script has no message data")
    return data[sec[3]:sec[3] + sec[2]]


def put_message_bytes(rel, data, new):
    """Return the file with its message data replaced (a .BF script is rebuilt around the new section)."""
    if not rel.lower().endswith(".bf"):
        return new
    secs = bf_sections(data)
    sec = next(x for x in secs if x[0] == 3)
    delta = len(new) - sec[2]
    out = bytearray(data[:sec[3]] + new + data[sec[3] + sec[2]:])
    for i, (t, es, cnt, st) in enumerate(secs):
        if t == 3:
            struct.pack_into("<I", out, 0x20 + 16 * i + 8, len(new))
        elif st > sec[3]:
            struct.pack_into("<I", out, 0x20 + 16 * i + 12, st + delta)
    # the size word at +4 is the start of the last (string) section, i.e. everything before it
    old_size = struct.unpack_from("<I", data, 4)[0]
    if old_size > sec[3]:
        struct.pack_into("<I", out, 4, old_size + delta)
    return bytes(out)


# ----------------------------------------------------------------- commands

def walk_bmds(root, only):
    found = []
    for dp, _, names in os.walk(root):
        for n in names:
            if n.lower().endswith((".bmd", ".bf")):
                rel = os.path.relpath(os.path.join(dp, n), root)
                if not only or any(o.lower() in rel.lower() for o in only):
                    found.append(rel)
    found.sort(key=str.lower)
    return found


def cmd_extract(a):
    root = os.path.abspath(a.folder)
    out = os.path.abspath(a.out) if a.out else root.rstrip("\\/") + "_text"
    if os.path.commonpath([root, out]) == root:
        sys.exit("Error: the output folder must not be inside the input folder.")
    if os.path.isdir(out) and not a.overwrite and any(
            fn.endswith(".txt") for _, _, fns in os.walk(out) for fn in fns):
        sys.exit("Error: %s already has text files in it. Extracting again would overwrite any edits you made.\n"
                 "If you want a fresh copy, either choose another folder with -o, or add --overwrite "
                 "(this replaces ALL the text files, including your edits)." % out)
    files = walk_bmds(root, a.only)
    if a.limit:
        files = files[:a.limit]
    stats = dict(files=0, exact=0, msgs=0, dialog=0, raw=0, lines=0, reloc=0)
    reloc_bad = []
    rawtypes, problems, diffs = {}, [], {}
    del WHY[:]
    for rel in files:
        try:
            with open(os.path.join(root, rel), "rb") as fh:
                data = fh.read()
            data = message_bytes(rel, data)
            f = parse_bmd(data)
        except (ToolError, OSError) as e:
            problems.append((rel, str(e)))
            continue
        stats["files"] += 1
        pts = all_pointers(f["msgs"], f["starts"])
        try:
            same = pts is not None and encode_reloc(pts) == f["reloc"]
            why = "unknown pointers" if pts is None else "different bytes"
        except ToolError as e:
            same, why = False, str(e)
        if same:
            stats["reloc"] += 1
        else:
            dec = decode_reloc(f["reloc"])
            if pts is not None and dec is None:
                why += " | table uses a byte form not understood yet"
            elif pts is not None and dec != pts:
                k = next((i for i in range(min(len(dec), len(pts))) if dec[i] != pts[i]), min(len(dec), len(pts)))
                why += " | table decodes to %d pointers, I found %d; first difference at pointer #%d (table says %s, message data says %s); original table has %d bytes, tail: %s" % (
                    len(dec), len(pts), k, dec[k] if k < len(dec) else "end", pts[k] if k < len(pts) else "end",
                    len(f["reloc"]), f["reloc"][-8:].hex(" "))
            reloc_bad.append((rel, why, f["reloc"].hex(" ")[:600],
                              " ".join(str(b - a) for a, b in zip([BASE] + (pts or [])[:-1], pts or []))[:400]))
        try:
            rebuilt, _ = build_bmd(f)
        except ToolError as e:
            problems.append((rel, str(e) + " (repack disabled for it)"))
            rebuilt = None
        if rebuilt is None:
            pass
        elif rebuilt == data:
            stats["exact"] += 1
        else:
            k = next((i for i in range(min(len(rebuilt), len(data))) if rebuilt[i] != data[i]), min(len(rebuilt), len(data)))
            where = "header" if k < 32 else "message table" if k < 32 + 8 * len(f["msgs"]) else \
                "gap after table" if k < 48 + 8 * len(f["msgs"]) else "after byte 0x%X" % k
            diffs[where] = diffs.get(where, 0) + 1
            problems.append((rel, "rebuilt file differs at 0x%X (%s): original %s, rebuilt %s; sizes %d vs %d (repack disabled for it)" % (
                k, where, data[k:k + 8].hex(" "), rebuilt[k:k + 8].hex(" "), len(data), len(rebuilt))))
        for m in f["msgs"]:
            stats["msgs"] += 1
            if m["kind"] == "dialog":
                stats["dialog"] += 1
                stats["lines"] += len(m["lines"])
            else:
                stats["raw"] += 1
                rawtypes[m["type"]] = rawtypes.get(m["type"], 0) + 1
        dest = os.path.join(out, rel + ".txt")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(to_textfile(rel, f))
    with open(os.path.join(out, "problems.txt"), "w", encoding="utf-8") as fh:
        for rel, why in problems:
            fh.write("%s\t%s\n" % (rel, why))
    print("=" * 60)
    print("Message files read: %d (%d rebuild byte-identical)" % (stats["files"], stats["exact"]))
    print("Messages: %d (%d understood with %d lines, %d kept raw)" % (stats["msgs"], stats["dialog"], stats["lines"], stats["raw"]))
    if rawtypes:
        print("Raw messages by type: " + ", ".join("type %d x%d" % kv for kv in sorted(rawtypes.items())))
    if problems:
        print("%d files had problems; see problems.txt. First few:" % len(problems))
        for rel, why in problems[:5]:
            print("  %s: %s" % (rel, why))
    print("Pointer lists I can regenerate exactly: %d of %d files" % (stats["reloc"], stats["files"]))
    if diffs:
        print("Where rebuilt files first differ: " + ", ".join("%s x%d" % kv for kv in sorted(diffs.items())))
    reasons = {}
    for r, d, _ in WHY:
        reasons[r] = reasons.get(r, 0) + 1
    if reasons:
        print("Notes on type-0 messages:")
        for r, c in sorted(reasons.items(), key=lambda kv: -kv[1]):
            print("  %5d  %s" % (c, r))
    with open(os.path.join(out, "diagnostics.txt"), "w", encoding="utf-8") as fh:
        seen = {}
        for r, d, hx in WHY:
            seen[r] = seen.get(r, 0) + 1
            if seen[r] <= 6:
                fh.write("%s | %s\n    first 72 bytes: %s\n" % (r, d, hx))
    with open(os.path.join(out, "diagnostics.txt"), "a", encoding="utf-8") as fh:
        for rel, why, orig, deltas in reloc_bad[:12]:
            fh.write("POINTER LIST | %s | %s\n    original: %s\n    gaps between pointers (bytes): %s\n" % (rel, why, orig, deltas))
    print("Text written to: " + out)
    print("Reminder: this is the game's own text. Keep it on your computer; never upload it.")


def cmd_repack(a):
    tdir, orig, out = (os.path.abspath(a.textfolder), os.path.abspath(a.original), os.path.abspath(a.out))
    if os.path.commonpath([orig, out]) == orig or os.path.commonpath([tdir, out]) == tdir:
        sys.exit("Error: the output folder must not be inside the input folders.")
    written, same, bad = 0, 0, []
    for dp, _, names in os.walk(tdir):
        for n in sorted(names):
            if not n.lower().endswith((".bmd.txt", ".bf.txt")):
                continue
            tp = os.path.join(dp, n)
            rel = os.path.relpath(tp, tdir)[:-4]
            try:
                with open(tp, "r", encoding="utf-8") as fh:
                    src, tmsgs = parse_textfile(fh.read())
                with open(os.path.join(orig, rel), "rb") as fh:
                    whole = fh.read()
                data = message_bytes(rel, whole)
                f = parse_bmd(data)
                if len(tmsgs) != len(f["msgs"]):
                    raise ToolError("the number of messages changed (not supported yet)")
                for m, t in zip(f["msgs"], tmsgs):
                    if m["kind"] != t["kind"] or m["type"] != t["type"]:
                        raise ToolError("message %s changed kind (not supported)" % m["name"])
                    if m["kind"] == "dialog":
                        if (m.get("names") is None) != (t.get("names") is None) or \
                                len(m.get("names") or []) != len(t.get("names") or []):
                            raise ToolError("message %s: the number of @speaker lines changed (not supported yet)" % m["name"])
                        if m["tail"] != t["tail"]:
                            raise ToolError("message %s: the extra data (@tail) was changed" % m["name"])
                        if len(m["lines"]) != len(t["lines"]):
                            raise ToolError("message %s: the number of lines changed (not supported yet)" % m["name"])
                        m["lines"] = t["lines"]
                        m["tail"] = t["tail"]
                        m["names"] = t["names"]
                        m["pad"] = t["pad"]
                        m["speaker"] = t["speaker"]
                        m["a"], m["b"] = t["a"], t["b"]
                old_pts = all_pointers(parse_bmd(data)["msgs"], parse_bmd(data)["starts"])
                try:
                    verified = old_pts is not None and encode_reloc(old_pts) == f["reloc"]
                except ToolError:
                    verified = False
                f["regen_reloc"] = verified
                new, starts = build_bmd(f)
                if not verified and starts != parse_bmd(data)["starts"]:
                    raise ToolError("message positions would move, and the pointer list of this file cannot be "
                                    "regenerated yet; keep each message's size (rounded to 4 bytes) unchanged")
                new_pts = all_pointers(f["msgs"], starts)
                if new == data:
                    same += 1
                    continue
                if any(m["kind"] == "raw" for m in f["msgs"]) and starts != parse_bmd(data)["starts"]:
                    raise ToolError("a raw message would move; this file's text must keep its length for now")
                dest = os.path.join(out, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as fh:
                    fh.write(put_message_bytes(rel, whole, new))
                written += 1
            except (ToolError, OSError, KeyError, ValueError) as e:
                bad.append((rel, str(e)))
    print("=" * 60)
    print("Changed files written: %d; unchanged: %d; problems: %d" % (written, same, len(bad)))
    for rel, why in bad[:10]:
        print("  %s: %s" % (rel, why))
    print("Output folder: " + out)


def cmd_diag(a):
    """Numbers-only report on why one message file cannot be rebuilt (no game text is printed)."""
    root = os.path.abspath(a.folder)
    L = []
    for rel in a.files:
        L.append("=" * 60)
        L.append(rel)
        try:
            with open(os.path.join(root, rel), "rb") as fh:
                data = message_bytes(rel, fh.read())
            f = parse_bmd(data)
        except (ToolError, OSError) as e:
            L.append("  cannot read: %s" % e)
            continue
        count = len(f["msgs"])
        L.append("  message data %d bytes; header words: type %d, size %d, reloc at %d (size %d), count %d, word 0x%X"
                 % (len(data), f["ftype"], len(data), f["reloc_off"], len(f["reloc"]), count, f["word"]))
        L.append("  first message at %d (table end + 16 = %d); reloc offset %% 4 = %d, %% 16 = %d"
                 % (min(f["starts"]), f["first"], f["reloc_off"] % 4, f["reloc_off"] % 16))
        L.append("  gap bytes after the table: " + f["gap"].hex(" ") + "; zero bytes kept before the pointer table: %d" % f["endpad"])
        starts = f["starts"]
        dup = count - len(set(starts))
        L.append("  messages in file order: %s; entries sharing a start with another: %d" % (f["ordered"], dup))
        if not f["ordered"]:
            order = sorted(range(count), key=lambda i: starts[i])
            pos = {i: k for k, i in enumerate(order)}
            moved = [i for i in range(count) if pos[i] != i]
            L.append("  entries not at their file-order position: %d of %d (first 30 as index:position)" % (len(moved), count))
            L.append("    " + " ".join("%d:%d" % (i, pos[i]) for i in moved[:30]))
            L.append("  table order of start offsets (first 40): " + " ".join(str(s) for s in starts[:40]))
            L.append("  types of the moved entries: " + ", ".join(
                "%d x%d" % kv for kv in sorted(collections.Counter(f["msgs"][i]["type"] for i in moved).items())))
        pts = all_pointers(f["msgs"], f["starts"])
        dec = decode_reloc(f["reloc"])
        L.append("  pointer table: %d bytes decode to %s pointers; found in the messages: %s"
                 % (len(f["reloc"]), "?" if dec is None else len(dec), "?" if pts is None else len(pts)))
        if True:
            try:
                new, _ = build_bmd(f)
            except ToolError as e:
                L.append("  rebuild failed: %s" % e)
                new = None
            if new is not None:
                L.append("  rebuilt %d bytes against original %d" % (len(new), len(data)))
                ranges, i, n = [], 0, min(len(new), len(data))
                while i < n and len(ranges) < 12:
                    if new[i] != data[i]:
                        j = i
                        while j < n and new[j] != data[j]:
                            j += 1
                        ranges.append((i, j - i))
                        i = j
                    else:
                        i += 1
                for off, ln in ranges:
                    place = "header" if off < 32 else "message table" if off < 32 + 8 * count else \
                        "gap" if off < 48 + 8 * count else "message data" if off < f["reloc_off"] else "pointer table"
                    L.append("    differs at %d (%s), %d bytes: original %s | rebuilt %s" % (
                        off, place, ln, data[off:off + min(ln, 16)].hex(" "), new[off:off + min(ln, 16)].hex(" ")))
                if len(new) != len(data):
                    L.append("    sizes differ by %d; original tail: %s | rebuilt tail: %s" % (
                        len(data) - len(new), data[-12:].hex(" "), new[-12:].hex(" ")))
    text = "\n".join(L) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("Report: " + a.out)
    else:
        print(text)


def main():
    ap = argparse.ArgumentParser(description="Extract and repack the game's .BMD text.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="write text files from the extracted folder")
    e.add_argument("folder")
    e.add_argument("-o", "--out")
    e.add_argument("--only", action="append", default=[])
    e.add_argument("--limit", type=int, default=0)
    e.add_argument("--overwrite", action="store_true", help="replace existing text files (including any edits you made)")
    r = sub.add_parser("repack", help="build modified .BMD files from edited text")
    r.add_argument("textfolder")
    r.add_argument("original")
    r.add_argument("-o", "--out", required=True)
    d = sub.add_parser("diag", help="numbers-only report on why a message file cannot be rebuilt")
    d.add_argument("folder")
    d.add_argument("files", nargs="+", help="paths relative to the folder")
    d.add_argument("-o", "--out")
    a = ap.parse_args()
    {"extract": cmd_extract, "repack": cmd_repack, "diag": cmd_diag}[a.cmd](a)


if __name__ == "__main__":
    main()
