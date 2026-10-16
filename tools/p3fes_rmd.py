#!/usr/bin/env python3
"""
p3fes_rmd.py - reads Persona 3 FES model files (.RMD) and exports their geometry to .OBJ.

An .RMD is a RenderWare 3.x stream (a texture dictionary, then a clump) with Atlus's own
chunks around it (see docs/formats.md). This tool understands the standard parts:

    py p3fes_rmd.py info   MODEL.RMD                 what is inside: frames, meshes, materials, textures
    py p3fes_rmd.py export MODEL.RMD -o OUTFOLDER    writes MODEL.obj, MODEL.mtl and the texture PNGs
    py p3fes_rmd.py textures MODEL.RMD -o OUTFOLDER  writes only the textures as PNG files
    py p3fes_rmd.py batch  MODELFOLDER -o OUTFOLDER  exports every .RMD under a folder, one subfolder each,
                                                     and writes batch_report.txt (add --no-textures for a fast trial)

Notes:
  * Meshes are placed using the model's frame hierarchy (bone/node transforms), so parts
    that the game positions with frames appear where they belong.
  * Coordinates are written as stored. If a model looks mirrored in your 3D viewer, add
    --mirror-x.
  * Textures (PS2 native format) are converted to PNG next to the .obj; the .mtl uses them.
  * Models using the PS2's native mesh format (no vertex data in the geometry) are reported
    and skipped.

It only reads your files and writes new ones; it never changes the game files.
Standard library only, Python 3.8+.
"""

import argparse
import os
import struct
import sys

ATLUS = 0x40000000
CONTAINERS = {0x10, 0x0E, 0x1A, 0x0F, 0x08, 0x07, 0x06, 0x14, 0x03, 0x16, 0x15}
NAMES = {1: "Struct", 2: "String", 3: "Extension", 6: "Texture", 7: "Material", 8: "MaterialList",
         0x0E: "FrameList", 0x0F: "Geometry", 0x10: "Clump", 0x14: "Atomic", 0x15: "TextureNative",
         0x16: "TexDictionary", 0x1A: "GeometryList", 0x1B: "AnimAnimation", 0x11E: "HAnim"}

GEO_TRISTRIP, GEO_POSITIONS, GEO_TEXTURED, GEO_PRELIT, GEO_NORMALS = 1, 2, 4, 8, 0x10
GEO_NATIVE = 0x01000000


class ToolError(Exception):
    pass


class Chunk:
    def __init__(self, ctype, size, ver, start):
        self.type, self.size, self.ver, self.start = ctype, size, ver, start
        self.kids = []

    @property
    def data_start(self):
        return self.start + 12

    @property
    def end(self):
        return self.start + 12 + self.size

    def find(self, ctype):
        return [k for k in self.kids if k.type == ctype]

    def first(self, ctype):
        k = self.find(ctype)
        return k[0] if k else None


def plausible(ver):
    return ver == ATLUS or (ver >> 16) in (0x1C02, 0x1C03, 0x0C02, 0x1803, 0x1400, 0x0800, 0x1000)


def parse_chunks(data, pos, end, depth=0):
    out = []
    while pos + 12 <= end:
        ctype, size, ver = struct.unpack_from("<III", data, pos)
        if ctype == 0 or size > end - pos - 12 or not plausible(ver):
            break
        c = Chunk(ctype, size, ver, pos)
        if ctype in CONTAINERS and depth < 8:
            c.kids = parse_chunks(data, pos + 12, pos + 12 + size, depth + 1)
        out.append(c)
        pos += 12 + size
    return out


def skip_atlus_chunks(data):
    """Offset just after the run of game-specific chunks (type F0F0xxxx) at the start of a file.
    Up to 15 padding bytes (alignment) can sit between two of these chunks."""
    def chunk_at(o):
        if o + 12 > len(data):
            return None
        ctype, size, ver = struct.unpack_from("<III", data, o)
        if (ctype >> 16) == 0xF0F0 and ver == 0x40000000 and size <= len(data) - o - 12:
            return size
        return None
    off = 0
    while True:
        size = chunk_at(off)
        if size is None:
            for pad in range(1, 16):
                size = chunk_at(off + pad)
                if size is not None:
                    off += pad
                    break
        if size is None:
            return off
        off += 12 + size


def find_stream(data):
    best = None
    offsets = list(range(0, min(0x40, len(data) - 12) + 1))
    after = skip_atlus_chunks(data)
    for o in range(after, after + 17):          # the RenderWare data can follow after a few padding bytes
        if o not in offsets and o + 12 <= len(data):
            offsets.append(o)
    for off in offsets:
        ctype, size, ver = struct.unpack_from("<III", data, off)
        if ctype in (0x16, 0x10) and size <= len(data) - off - 12 and plausible(ver):
            top = parse_chunks(data, off, len(data))
            if top and (best is None or len(top) > len(best[1])):
                best = (off, top)
    if not best:
        raise ToolError("no RenderWare chunk list found in this file")
    return best


def read_string(data, chunk):
    raw = data[chunk.data_start:chunk.data_start + chunk.size]
    return raw.split(b"\0")[0].decode("latin-1")


# ----------------------------------------------------------------- frames, geometry, materials

def read_frames(data, flist):
    st = flist.first(1)
    n = struct.unpack_from("<I", data, st.data_start)[0]
    if st.size < 4 + 56 * n:
        raise ToolError("frame list is smaller than its frame count says")
    frames = []
    for i in range(n):
        v = struct.unpack_from("<12f", data, st.data_start + 4 + 56 * i)
        parent, flags = struct.unpack_from("<iI", data, st.data_start + 4 + 56 * i + 48)
        frames.append({"rot": [v[0:3], v[3:6], v[6:9]], "pos": v[9:12], "parent": parent})
    return frames


def world_transforms(frames):
    """Each frame's world matrix as (3x3 rows, position). Row-vector convention: p' = p*R + t."""
    cache = {}

    def mul(a, b):
        ra, ta = a
        rb, tb = b
        r = [[sum(ra[i][k] * rb[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        t = [sum(ta[k] * rb[k][j] for k in range(3)) + tb[j] for j in range(3)]
        return r, t

    def get(i, depth=0):
        if i in cache:
            return cache[i]
        f = frames[i]
        local = ([list(r) for r in f["rot"]], list(f["pos"]))
        if f["parent"] < 0 or f["parent"] >= len(frames) or f["parent"] == i or depth > 200:
            cache[i] = local
        else:
            cache[i] = mul(local, get(f["parent"], depth + 1))
        return cache[i]

    return [get(i) for i in range(len(frames))]


def read_materials(data, geo):
    """List of materials: dict(color, texture name, mask name)."""
    mats = []
    ml = geo.first(8)
    if not ml:
        return mats
    for m in ml.find(7):
        st = m.first(1)
        info = {"color": (255, 255, 255, 255), "texture": None, "mask": None}
        if st and st.size >= 16:
            flags, col, _, textured = struct.unpack_from("<IIII", data, st.data_start)
            info["color"] = (col & 255, (col >> 8) & 255, (col >> 16) & 255, (col >> 24) & 255)
            if textured:
                tex = m.first(6)
                if tex:
                    strs = tex.find(2)
                    if strs:
                        info["texture"] = read_string(data, strs[0])
                    if len(strs) > 1:
                        info["mask"] = read_string(data, strs[1])
        mats.append(info)
    return mats


def read_geometry(data, geo):
    """Returns dict with verts, normals, uvs, tris [(a,b,c,mat)], or {'native': True}."""
    st = geo.first(1)
    if not st or st.size < 16:
        raise ToolError("geometry has no data block")
    p = st.data_start
    flags, ntri, nvert, nmorph = struct.unpack_from("<IIII", data, p)
    p += 16
    if geo.ver < 0x1C020000 and (geo.ver >> 16) < 0x1C02:      # old versions carry 3 floats
        p += 12
    info = {"flags": flags, "ntri": ntri, "nvert": nvert, "nmorph": nmorph,
            "ntex": (flags >> 16) & 0xFF}
    if flags & GEO_NATIVE:
        info["native"] = True
        return info
    ntex = info["ntex"] or (1 if flags & GEO_TEXTURED else 0)
    if flags & 0x80 and not info["ntex"]:
        ntex = 2
    info["ntex"] = ntex
    if flags & GEO_PRELIT:
        p += 4 * nvert
    uvs = []
    for t in range(ntex):
        layer = [struct.unpack_from("<2f", data, p + 8 * i) for i in range(nvert)]
        p += 8 * nvert
        uvs.append(layer)
    tris = []
    for i in range(ntri):
        v2, v1, mat, v3 = struct.unpack_from("<4H", data, p + 8 * i)
        tris.append((v1, v2, v3, mat))
    p += 8 * ntri
    if nmorph < 1:
        raise ToolError("geometry has no morph target")
    cx, cy, cz, cr, hasv, hasn = struct.unpack_from("<4f2I", data, p)
    p += 24
    if not hasv:
        raise ToolError("geometry has no vertex positions")
    verts = [struct.unpack_from("<3f", data, p + 12 * i) for i in range(nvert)]
    p += 12 * nvert
    normals = []
    if hasn:
        normals = [struct.unpack_from("<3f", data, p + 12 * i) for i in range(nvert)]
        p += 12 * nvert
    info.update(verts=verts, normals=normals, uvs=uvs, tris=tris, used=p - st.data_start, block=st.size)
    return info


def read_scene(data):
    off, top = find_stream(data)
    clump = next((c for c in top if c.type == 0x10), None)
    if not clump:
        raise ToolError("no clump (model) in this file")
    st = clump.first(1)
    natoms = struct.unpack_from("<I", data, st.data_start)[0]
    frames = read_frames(data, clump.first(0x0E))
    glist = clump.first(0x1A)
    geos = glist.find(0x0F) if glist else []
    atomics = []
    for a in clump.find(0x14):
        ast = a.first(1)
        fi, gi, fl, _ = struct.unpack_from("<4I", data, ast.data_start)
        atomics.append((fi, gi, fl))
    texdict = next((c for c in top if c.type == 0x16), None)
    return {"offset": off, "top": top, "clump": clump, "frames": frames, "geos": geos,
            "atomics": atomics, "texdict": texdict, "natoms": natoms}


def texture_summaries(data, texdict):
    out = []
    if not texdict:
        return out
    for t in texdict.find(0x15):
        strs = t.find(2)
        structs = t.find(1)
        name = read_string(data, strs[0]) if strs else "?"
        mask = read_string(data, strs[1]) if len(strs) > 1 else ""
        words = ()
        if len(structs) > 1 and structs[1].size >= 64:
            words = struct.unpack_from("<16I", data, structs[1].data_start)
        out.append({"name": name, "mask": mask, "data_size": structs[1].size if len(structs) > 1 else 0, "words": words})
    return out



# ----------------------------------------------------------------- PS2 native textures

import zlib

# PS2 graphics-chip (GS) memory layout. A "native" texture stores its pixels as an upload
# packet: 8-bit and 4-bit pictures are scrambled into the chip's memory order and sent as
# 32-bit pixels. To read the picture back we replay the upload, then read it as 8/4-bit.
BLOCK32 = [[0, 1, 4, 5, 16, 17, 20, 21], [2, 3, 6, 7, 18, 19, 22, 23],
           [8, 9, 12, 13, 24, 25, 28, 29], [10, 11, 14, 15, 26, 27, 30, 31]]
BLOCK4 = [[0, 2, 8, 10], [1, 3, 9, 11], [4, 6, 12, 14], [5, 7, 13, 15],
          [16, 18, 24, 26], [17, 19, 25, 27], [20, 22, 28, 30], [21, 23, 29, 31]]
WORDS = [[0, 1, 4, 5, 8, 9, 12, 13], [2, 3, 6, 7, 10, 11, 14, 15],
         [8, 9, 12, 13, 0, 1, 4, 5], [10, 11, 14, 15, 2, 3, 6, 7]]


def ct32_word(x, y, tbw):
    page = (y // 32) * tbw + (x // 64)
    blk = BLOCK32[(y % 32) // 8][(x % 64) // 8]
    return page * 2048 + blk * 64 + (y % 8 // 2) * 16 + (x % 8 // 2) * 4 + (y % 2) * 2 + (x % 2)


def t8_index(x, y, tbw):
    """Byte position of 8-bit pixel (x, y) in GS memory."""
    page = (y // 64) * max(1, (tbw + 1) // 2) + (x // 128)
    blk = BLOCK32[(y % 64) // 16][(x % 128) // 16]
    xi, yi = x % 16, y % 16
    c, r = yi // 4, yi % 4
    word = WORDS[(r + 2 * (c % 2)) % 4][xi % 8]
    lane = 2 * (xi // 8) + (1 if r >= 2 else 0)
    return page * 8192 + blk * 256 + c * 64 + word * 4 + lane


def t4_index(x, y, tbw):
    """Nibble position of 4-bit pixel (x, y) in GS memory."""
    page = (y // 128) * max(1, (tbw + 1) // 2) + (x // 128)
    blk = BLOCK4[(y % 128) // 16][(x % 128) // 32]
    xi, yi = x % 32, y % 16
    c, r = yi // 4, yi % 4
    word = WORDS[(r + 2 * (c % 2)) % 4][xi % 8]
    lane = 2 * (xi // 8) + (1 if r >= 2 else 0)
    return page * 16384 + blk * 512 + c * 128 + word * 8 + lane


def parse_packet(blob, off):
    """One GS upload packet: a GIF tag with register writes (we need TRXREG), then an image tag.
    Returns (rrw, rrh, pixel bytes, offset after the packet)."""
    nloop = struct.unpack_from("<I", blob, off)[0] & 0x7FFF
    rrw = rrh = None
    for i in range(nloop):
        data, addr = struct.unpack_from("<QQ", blob, off + 16 + 16 * i)
        if addr & 0xFF == 0x52:
            rrw, rrh = data & 0xFFFFFFFF, data >> 32
    t = off + 16 + 16 * nloop
    nq = struct.unpack_from("<I", blob, t)[0] & 0x7FFF
    start = t + 16
    return rrw, rrh, blob[start:start + nq * 16], start + nq * 16


def replay_upload(stream, rrw):
    """Put the uploaded 32-bit pixels where the GS would put them; returns the memory bytes."""
    n = len(stream) // 4
    tbw_up = max(1, (rrw + 63) // 64)
    rows = (n + rrw - 1) // rrw
    size = ((rows + 31) // 32) * tbw_up * 8192
    mem = bytearray(max(size, len(stream)))
    for k in range(n):
        a = ct32_word(k % rrw, k // rrw, tbw_up) * 4
        mem[a:a + 4] = stream[4 * k:4 * k + 4]
    return mem


def texture_parts(data, tex):
    """Pull the pieces out of a TextureNative chunk."""
    structs = tex.find(1)
    if len(structs) < 2:
        raise ToolError("texture has no raster data")
    blob = data[structs[1].data_start:structs[1].data_start + structs[1].size]
    if len(blob) < 88 or struct.unpack_from("<I", blob, 0)[0] != 1:
        raise ToolError("unexpected texture layout")
    w, h, depth, fmt = struct.unpack_from("<4I", blob, 12)
    tex0 = struct.unpack_from("<Q", blob, 28)[0]
    texel_size, pal_size = struct.unpack_from("<2I", blob, 60)
    if depth not in (4, 8):
        raise ToolError("%d-bit textures are not supported yet" % depth)
    rrw, rrh, stream, _ = parse_packet(blob, 88)
    if not rrw:
        raise ToolError("upload packet has no size")
    prrw, prrh, pstream, _ = parse_packet(blob, 88 + texel_size)
    # Palette entries are in file order; 8-bit palettes have entries 8-15 and 16-23 swapped in
    # every group of 32 (the GS "CSM1" palette layout). Confirmed on a face and a uniform texture.
    ncol = 256 if depth == 8 else 16
    pal = []
    for i in range(ncol):
        j = ((i & ~0x18) | ((i & 8) << 1) | ((i & 16) >> 1)) if depth == 8 else i
        r, g, b, a = pstream[4 * j:4 * j + 4]
        pal.append((r, g, b, min(255, a * 2)))
    return {"w": w, "h": h, "depth": depth, "tbw": (tex0 >> 14) & 0x3F, "stream": stream,
            "rrw": rrw, "rrh": rrh, "pal": pal, "prrw": prrw, "prrh": prrh,
            "texel_size": texel_size, "pal_size": pal_size, "fmt": fmt, "pstream": pstream}


def paint(parts, getter):
    w, h, pal = parts["w"], parts["h"], parts["pal"]
    rgba = bytearray(w * h * 4)
    for y in range(h):
        for x in range(w):
            rgba[4 * (y * w + x):4 * (y * w + x) + 4] = bytes(pal[getter(x, y) % len(pal)])
    return bytes(rgba)


def decode_native_texture(data, tex):
    """tex: a TextureNative chunk. Returns (width, height, RGBA bytes) or raises ToolError."""
    t = texture_parts(data, tex)
    mem = replay_upload(t["stream"], t["rrw"])
    tbw = t["tbw"]
    if t["depth"] == 8:
        return t["w"], t["h"], paint(t, lambda x, y: mem[t8_index(x, y, tbw)])

    # 4-bit layout is NOT fully pinned down (see docs/formats.md): this is reading A, unverified.
    return t["w"], t["h"], variants_4bit(data, tex)[0][1]


def variants_8bit(data, tex):
    """Four palette orderings for an 8-bit texture (the picture layout is the same in each)."""
    t = texture_parts(data, tex)
    mem = replay_upload(t["stream"], t["rrw"])
    tbw = t["tbw"]
    raw = t["pstream"]

    def pal_from(buf, swap):
        out = []
        for i in range(256):
            j = ((i & ~0x18) | ((i & 8) << 1) | ((i & 16) >> 1)) if swap else i
            r, g, b, a = buf[4 * j:4 * j + 4]
            out.append((r, g, b, min(255, a * 2)))
        return out
    pmem = replay_upload(raw, t["prrw"])
    out = []
    for label, buf, swap in (("A: file order, swap entries 8-15 with 16-23 (used)", raw, True),
                             ("B: file order", raw, False),
                             ("C: after GS replay", pmem, False),
                             ("D: after GS replay, swap 8-15 with 16-23", pmem, True)):
        tt = dict(t)
        tt["pal"] = pal_from(buf, swap)
        out.append((label, paint(tt, lambda x, y: mem[t8_index(x, y, tbw)])))
    return out


def variants_4bit(data, tex):
    """Several ways of reading a 4-bit texture, for working out which one the game uses."""
    t = texture_parts(data, tex)
    w, h, tbw, stream = t["w"], t["h"], t["tbw"], t["stream"]
    out = []
    mem = replay_upload(stream, t["rrw"])

    def get4(m):
        def f(x, y):
            n = t4_index(x, y, tbw)
            return (m[n >> 1] >> ((n & 1) * 4)) & 15 if (n >> 1) < len(m) else 0
        return f
    out.append(("A: replay with the packet's size, GS 4-bit layout", paint(t, get4(mem))))
    out.append(("B: plain rows, low nibble first", paint(t, lambda x, y: (stream[(y * w + x) // 2] >> (((y * w + x) & 1) * 4)) & 15)))
    out.append(("C: plain rows, high nibble first", paint(t, lambda x, y: (stream[(y * w + x) // 2] >> ((1 - ((y * w + x) & 1)) * 4)) & 15)))
    mem2 = replay_upload(stream, max(1, w // 4))
    out.append(("D: replay as (w/4 x h/2), GS 4-bit layout", paint(t, get4(mem2))))
    raw = bytearray(stream) + bytearray(1 << 16)
    out.append(("E: stream already in GS memory order, GS 4-bit layout", paint(t, get4(raw))))
    mem3 = replay_upload(stream, t["rrw"])
    half = w // 2

    def get8split(x, y):
        k = t8_index(x // 2, y, max(1, half // 64))
        b = mem3[k] if k < len(mem3) else 0
        return (b >> ((x & 1) * 4)) & 15
    out.append(("F: read as 8-bit picture (w/2 wide), split nibbles", paint(t, get8split)))
    memg = replay_upload(stream, t["rrw"] * 2)
    out.append(("G: replay with twice the width, GS 4-bit layout", paint(t, get4(memg))))
    mem16 = replay_upload(stream, max(1, w // 4))

    def get4_ct32order(x, y):                       # blocks laid out like 32-bit blocks
        xi, yi = x % 32, y % 16
        c, r = yi // 4, yi % 4
        word = WORDS[(r + 2 * (c % 2)) % 4][xi % 8]
        lane = 2 * (xi // 8) + (1 if r >= 2 else 0)
        blk = BLOCK32[(y // 16) % 4][(x // 32) % 8]
        n = blk * 512 + c * 128 + word * 8 + lane
        return (mem16[n >> 1] >> ((n & 1) * 4)) & 15 if (n >> 1) < len(mem16) else 0
    out.append(("H: replay (w/4 x h/2), 4-bit blocks in 32-bit block order", paint(t, get4_ct32order)))

    def get8split_hi(x, y):
        k = t8_index(x // 2, y, max(1, half // 64))
        b = mem3[k] if k < len(mem3) else 0
        return (b >> ((1 - (x & 1)) * 4)) & 15
    out.append(("I: read as 8-bit picture (w/2 wide), high nibble first", paint(t, get8split_hi)))
    return out


def grey_smoothness(rgba, w, h, tol=12):
    """Share of horizontally and vertically neighbouring pixel pairs whose grey levels are within tol."""
    g = [(rgba[4 * i] + rgba[4 * i + 1] + rgba[4 * i + 2]) // 3 for i in range(w * h)]
    close = tot = 0
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if x + 1 < w:
                tot += 1
                close += abs(g[i] - g[i + 1]) <= tol
            if y + 1 < h:
                tot += 1
                close += abs(g[i] - g[i + w]) <= tol
    return close / tot if tot else 0.0


def contact_sheet(variants, w, h, scale=4, cols=2):
    """Tile the variants into one RGBA picture (nearest-neighbour enlarged)."""
    gap = 8
    cw, ch = w * scale, h * scale
    rows = (len(variants) + cols - 1) // cols
    W, H = cols * (cw + gap) + gap, rows * (ch + gap) + gap
    img = bytearray(b"\x30\x30\x30\xff" * (W * H))
    for i, (_, rgba) in enumerate(variants):
        ox, oy = gap + (i % cols) * (cw + gap), gap + (i // cols) * (ch + gap)
        for y in range(h * scale):
            sy = y // scale
            for x in range(w * scale):
                sx = x // scale
                px = rgba[4 * (sy * w + sx):4 * (sy * w + sx) + 4]
                o = 4 * ((oy + y) * W + ox + x)
                img[o:o + 4] = px
    return W, H, bytes(img)


def write_png(path, w, h, rgba):
    raw = b"".join(b"\0" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def smoothness(rgba, w, h):
    """Share of neighbouring pixels that are identical; a scrambled picture scores low."""
    same = tot = 0
    for y in range(h):
        row = rgba[y * w * 4:(y + 1) * w * 4]
        for x in range(w - 1):
            tot += 1
            if row[4 * x:4 * x + 4] == row[4 * x + 4:4 * x + 8]:
                same += 1
    return same / tot if tot else 0.0


def export_textures(data, texdict, out_dir, verbose=True, variants=False):
    done = []
    if not texdict:
        return done
    for t in texdict.find(0x15):
        strs = t.find(2)
        name = read_string(data, strs[0]) if strs else "texture%d" % len(done)
        try:
            w, h, rgba = decode_native_texture(data, t)
        except (ToolError, struct.error, IndexError) as e:
            if verbose:
                print("  texture %s: cannot decode (%s)" % (name, e))
            continue
        write_png(os.path.join(out_dir, name + ".png"), w, h, rgba)
        done.append(name)
        if verbose:
            parts = texture_parts(data, t)
            print("  texture %s: %dx%d, %d-bit, neighbouring pixels equal %.0f%%; upload %dx%d (%d bytes), palette upload %dx%d" % (
                name, w, h, parts["depth"], 100 * smoothness(rgba, w, h), parts["rrw"], parts["rrh"],
                len(parts["stream"]), parts["prrw"], parts["prrh"]))
        if variants and texture_parts(data, t)["depth"] in (4, 8):
            vs = variants_4bit(data, t) if texture_parts(data, t)["depth"] == 4 else variants_8bit(data, t)
            if verbose:
                for lab, rg in vs:
                    print("      %s" % lab)
            W, H, img = contact_sheet(vs, w, h, scale=2 if w * h >= 4096 else 4, cols=2 if len(vs) == 4 else 3)
            write_png(os.path.join(out_dir, name + "_variants.png"), W, H, img)
            if verbose:
                print("    wrote %s_variants.png, three per row, left to right then top to bottom, in the order A, B, C, ..." % name)
    return done


# ----------------------------------------------------------------- commands

def cmd_info(a):
    with open(a.model, "rb") as fh:
        data = fh.read()
    sc = read_scene(data)
    print("%s: %d bytes, RenderWare stream at 0x%X" % (a.model, len(data), sc["offset"]))
    print("Top-level chunks: " + " ".join("%X" % c.type for c in sc["top"]))
    print("Frames: %d; geometries: %d; atomics: %d" % (len(sc["frames"]), len(sc["geos"]), len(sc["atomics"])))
    for i, g in enumerate(sc["geos"]):
        try:
            info = read_geometry(data, g)
        except (ToolError, struct.error) as e:
            print("  geometry %d: cannot read (%s)" % (i, e))
            continue
        if info.get("native"):
            print("  geometry %d: PS2 native format (flags %08X), skipped" % (i, info["flags"]))
            continue
        mats = read_materials(data, g)
        used = ", ".join(sorted(set(m["texture"] or "(none)" for m in mats)))
        print("  geometry %d: %d vertices, %d triangles, flags %08X, %d texture sets, normals %s; "
              "data used %d of %d bytes; materials %d (%s)" % (
                  i, info["nvert"], info["ntri"], info["flags"], info["ntex"],
                  "yes" if info["normals"] else "no", info["used"], info["block"], len(mats), used))
    for fi, gi, fl in sc["atomics"]:
        print("  atomic: frame %d, geometry %d, flags %X" % (fi, gi, fl))
    tex = texture_summaries(data, sc["texdict"])
    print("Textures in the dictionary: %d" % len(tex))
    for t in tex:
        w = t["words"]
        print("  %-16s mask %-10s data %d bytes%s" % (t["name"], t["mask"] or "-", t["data_size"],
              ("  header words: " + " ".join("%X" % x for x in w[:16])) if w else ""))


def cmd_texhex(a):
    with open(a.model, "rb") as fh:
        data = fh.read()
    sc = read_scene(data)
    found = False
    for t in sc["texdict"].find(0x15) if sc["texdict"] else []:
        strs = t.find(2)
        name = read_string(data, strs[0]) if strs else "?"
        if a.name and name != a.name:
            continue
        found = True
        structs = t.find(1)
        st = structs[1]
        blob = data[st.data_start:st.data_start + st.size]
        print("%s: data struct %d bytes" % (name, st.size))
        print("words: " + " ".join("%X" % w for w in struct.unpack_from("<%dI" % min(24, len(blob) // 4), blob, 0)))
        for label, lo, hi in (("start", 0, 224), ("end", max(0, len(blob) - 224), len(blob))):
            print("-- %s (offset 0x%X) --" % (label, lo))
            for i in range(lo, hi, 16):
                row = blob[i:i + 16]
                print("%05X  %s" % (i, " ".join("%02X" % b for b in row)))
        if not a.all:
            break
    if not found:
        raise ToolError("no texture with that name")


def cmd_textures(a):
    with open(a.model, "rb") as fh:
        data = fh.read()
    sc = read_scene(data)
    os.makedirs(a.out, exist_ok=True)
    done = export_textures(data, sc["texdict"], a.out, variants=a.variants)
    print("Wrote %d texture file(s) to %s" % (len(done), a.out))


def cmd_export(a):
    r = export_model(a.model, a.out, a.mirror_x, not a.no_textures)
    print("Wrote %s.obj and %s.mtl in %s" % (r["base"], r["base"], a.out))
    print("Vertices: %d, materials: %d" % (r["vertices"], r["materials"]))
    for s in r["skipped"]:
        print("Skipped: " + s)


def cmd_gltf(a):
    import p3fes_gltf
    res = p3fes_gltf.export_gltf(a.model, a.out, a.mirror_x, not a.no_textures)
    print("Wrote %s.gltf and %s.bin in %s" % (res["base"], res["base"], a.out))
    print("Meshes: %d, skins: %d, bones: %d, animations: %d" % (res["meshes"], res["skins"], res["bones"], res["animations"]))
    for line in res["diagnostics"] + res["notes"]:
        print(line)
    for s in res["skipped"]:
        print("Skipped: " + s)


def export_model(model_path, out_dir, mirror_x=False, textures=True, verbose=True):
    """Write one model as .obj/.mtl (+ textures). Returns a dict describing what happened."""
    class A:
        pass
    a = A()
    a.model, a.out, a.mirror_x, a.no_textures = model_path, out_dir, mirror_x, not textures
    with open(a.model, "rb") as fh:
        data = fh.read()
    sc = read_scene(data)
    os.makedirs(a.out, exist_ok=True)
    base = os.path.splitext(os.path.basename(a.model))[0]
    world = world_transforms(sc["frames"]) if sc["frames"] else []
    obj_lines = ["# exported by p3fes_rmd.py", "mtllib %s.mtl" % base]
    mtl = {}
    vcount = tcount = ncount = 0
    skipped = []
    for ai, (fi, gi, fl) in enumerate(sc["atomics"]):
        if gi >= len(sc["geos"]):
            skipped.append("atomic %d: geometry index out of range" % ai)
            continue
        geo = sc["geos"][gi]
        try:
            info = read_geometry(data, geo)
        except (ToolError, struct.error) as e:
            skipped.append("geometry %d: %s" % (gi, e))
            continue
        if info.get("native"):
            skipped.append("geometry %d: PS2 native format" % gi)
            continue
        mats = read_materials(data, geo)
        R, T = world[fi] if fi < len(world) else ([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 0])
        sign = -1.0 if a.mirror_x else 1.0
        obj_lines.append("o %s_%d" % (base, ai))
        for (x, y, z) in info["verts"]:
            wx = x * R[0][0] + y * R[1][0] + z * R[2][0] + T[0]
            wy = x * R[0][1] + y * R[1][1] + z * R[2][1] + T[1]
            wz = x * R[0][2] + y * R[1][2] + z * R[2][2] + T[2]
            obj_lines.append("v %.6f %.6f %.6f" % (sign * wx, wy, wz))
        has_uv = bool(info["uvs"])
        if has_uv:
            for (u, v) in info["uvs"][0]:
                obj_lines.append("vt %.6f %.6f" % (u, 1.0 - v))
        has_n = bool(info["normals"])
        if has_n:
            for (x, y, z) in info["normals"]:
                wx = x * R[0][0] + y * R[1][0] + z * R[2][0]
                wy = x * R[0][1] + y * R[1][1] + z * R[2][1]
                wz = x * R[0][2] + y * R[1][2] + z * R[2][2]
                obj_lines.append("vn %.5f %.5f %.5f" % (sign * wx, wy, wz))
        cur_mat = None
        for (v1, v2, v3, m) in info["tris"]:
            if m != cur_mat:
                cur_mat = m
                name = "mat_%d_%d" % (gi, m)
                mtl[name] = mats[m] if m < len(mats) else {"color": (200, 200, 200, 255), "texture": None}
                obj_lines.append("usemtl " + name)
            idx = (v1, v2, v3) if not a.mirror_x else (v1, v3, v2)
            parts = []
            for v in idx:
                s = str(vcount + v + 1)
                if has_uv:
                    s += "/%d" % (tcount + v + 1)
                elif has_n:
                    s += "/"
                if has_n:
                    s += "/%d" % (ncount + v + 1)
                parts.append(s)
            obj_lines.append("f " + " ".join(parts))
        vcount += info["nvert"]
        tcount += info["nvert"] if has_uv else 0
        ncount += info["nvert"] if has_n else 0
    with open(os.path.join(a.out, base + ".obj"), "w") as fh:
        fh.write("\n".join(obj_lines) + "\n")
    with open(os.path.join(a.out, base + ".mtl"), "w") as fh:
        for name, m in mtl.items():
            c = m["color"]
            fh.write("newmtl %s\nKd %.3f %.3f %.3f\n" % (name, c[0] / 255, c[1] / 255, c[2] / 255))
            if m.get("texture"):
                fh.write("map_Kd %s.png\n" % m["texture"])
            fh.write("\n")
    tex_done = []
    if not a.no_textures:
        tex_done = export_textures(data, sc["texdict"], a.out, verbose=verbose)
    return {"base": base, "vertices": vcount, "materials": len(mtl), "skipped": skipped,
            "textures": tex_done, "geometries": len(sc["geos"]), "atomics": len(sc["atomics"]),
            "frames": len(sc["frames"])}


def cmd_chunks(a):
    """Debug view for files the reader cannot open: the game's own chunks, then where RenderWare data might be."""
    with open(a.model, "rb") as fh:
        data = fh.read()
    print("%s: %d bytes" % (a.model, len(data)))
    off = 0
    n = 0
    while off + 12 <= len(data):
        ctype, size, ver = struct.unpack_from("<III", data, off)
        ok = (ctype >> 16) == 0xF0F0 and size <= len(data) - off - 12
        print("  at 0x%06X: type %08X, size %d, version %08X%s" % (off, ctype, size, ver, "" if ok else "   <- not a game chunk, stop"))
        if not ok:
            break
        off += 12 + size
        n += 1
        if n >= 40:
            print("  ... (stopping after 40 chunks)")
            break
    print("Bytes at 0x%X: %s" % (off, data[off:off + 48].hex(" ")))
    hits = []
    for o in range(0, len(data) - 12):
        ctype, size, ver = struct.unpack_from("<III", data, o)
        if ctype in (0x16, 0x10, 0x0B, 0x0C) and size <= len(data) - o - 12 and plausible(ver):
            hits.append((o, ctype, size, ver))
    print("Places that look like RenderWare chunks (type 0x16, 0x10, 0x0B, 0x0C): %d" % len(hits))
    for o, ctype, size, ver in hits[:12]:
        print("  at 0x%06X: type %X, size %d, version %08X" % (o, ctype, size, ver))
    try:
        find_stream(data)
        print("find_stream: OK (this version of the tool can open the file)")
    except ToolError as e:
        print("find_stream: " + str(e))


# ----------------------------------------------------------------- skeleton, skin, animation

HANIM, SKIN, NODE_NAME, ANIM = 0x11E, 0x116, 0x253F2FE, 0x1B


def read_hanim(data, ch):
    """RenderWare HAnim plugin chunk: bone id, and for the root the list of bones in depth-first order."""
    p = ch.data_start
    ver, node_id, n = struct.unpack_from("<3I", data, p)
    info = {"version": ver, "node_id": node_id, "count": n, "flags": 0, "keyframe_size": 0, "nodes": []}
    if n > 0:
        info["flags"], info["keyframe_size"] = struct.unpack_from("<2I", data, p + 12)
        for i in range(n):
            nid, idx, fl = struct.unpack_from("<3I", data, p + 20 + 12 * i)
            info["nodes"].append((nid, idx, fl))
    return info


def matrix_sane(m):
    """A 4x4 bone matrix whose three rotation rows are about unit length and whose position is finite.
    The fourth number of each row is padding and is ignored."""
    for r in (0, 4, 8):
        ln = (m[r] ** 2 + m[r + 1] ** 2 + m[r + 2] ** 2) ** 0.5
        if not (0.9 < ln < 1.1):
            return False
    return all(abs(m[i]) < 1e5 for i in (12, 13, 14))


def find_matrix_block(data, start, end, nb):
    """Search the bytes from start to end for nb consecutive bone matrices; returns the best
    (offset, stride, number of sane matrices) found."""
    best = (0, 64, 0)
    for stride in (64, 68, 72):
        for off in range(0, max(0, end - start - nb * stride) + 1):
            c = 0
            for b in range(nb):
                q = start + off + b * stride
                if q + 64 > end:
                    break
                if matrix_sane(struct.unpack_from("<16f", data, q)):
                    c += 1
            if c > best[2]:
                best = (off, stride, c)
    return best


def read_skin(data, ch, nvert):
    """RenderWare skin plugin chunk for ordinary (non-native) geometry: per-vertex bone indices and
    weights, and one inverse bone matrix per bone. The layout of the tail varies between versions, so
    the possible layouts are tried and the one that fits the chunk size exactly is used."""
    p = ch.data_start
    end = ch.end
    nb, nused, maxw, _pad = struct.unpack_from("<4B", data, p)
    p += 4
    used = list(data[p:p + nused])
    p += nused
    need = nvert * 4 + nvert * 16
    if p + need > end:
        raise ToolError("skin data is smaller than its vertex count says")
    idx = [tuple(data[p + 4 * i:p + 4 * i + 4]) for i in range(nvert)]
    p += nvert * 4
    wts = [struct.unpack_from("<4f", data, p + 16 * i) for i in range(nvert)]
    p += nvert * 16
    rest = end - p

    def matrices(prefix):
        out = []
        for b in range(nb):
            q = p + b * (64 + prefix) + prefix
            if q + 64 > end:
                break
            out.append(struct.unpack_from("<16f", data, q))
        return out

    def sane_count(ms):
        return sum(1 for m in ms if matrix_sane(m))
    # Layout found on a real character: nb matrices of 64 bytes, then "split skin" data:
    # u32 boneLimit, u32 numMeshes, u32 numRLE, nb bytes (bone remap, 0xFF = unused), numRLE pairs of bytes.
    split = None
    q = p + nb * 64
    if rest >= nb * 64 + 12 + nb and sane_count(matrices(0)) == nb:
        h1, h2, h3 = struct.unpack_from("<3I", data, q)
        pairs = rest - nb * 64 - 12 - nb          # bytes after the remap table
        split = {"header": (h1, h2, h3), "bone_limit": h1, "meshes": h2, "rle_count": pairs // 2,
                 "remap": list(data[q + 12:q + 12 + nb]),
                 "rle": [tuple(data[q + 12 + nb + 2 * i:q + 14 + nb + 2 * i]) for i in range(pairs // 2)]}
    if split:
        layout = (0, rest - nb * 64)
        fits = [layout]
    else:
        # older layouts that fit the chunk size exactly; sizes alone can be ambiguous, so prefer the layout
        # whose matrices look like real matrices, and on a tie the simplest layout
        fits = [(prefix, extra) for prefix, extra in ((0, 0), (0, 12), (4, 0), (4, 12)) if rest == nb * (64 + prefix) + extra]
        layout = max(fits, key=lambda le: (sane_count(matrices(le[0])), -fits.index(le))) if fits else None
    exact = layout is not None
    prefix = layout[0] if layout else 0
    mats = matrices(prefix)
    sane = sane_count(mats)
    return {"split": split, "tail_start": p, "end": end, "bones": nb, "used": used, "max_weights": maxw, "indices": idx, "weights": wts, "matrices": mats,
            "layout_exact": exact, "layout": layout, "rest_bytes": rest, "sane_matrices": sane}


def read_anim(data, ch):
    """Header of a RenderWare animation chunk (0x1B) and a size check for its keyframes."""
    p = ch.data_start
    ver, itype, nframes, flags, dur = struct.unpack_from("<4If", data, p)
    body = ch.size - 20
    expect = {1: 36 * nframes, 2: 22 * nframes + 24}
    return {"version": ver, "type": itype, "frames": nframes, "flags": flags, "duration": dur,
            "body_bytes": body, "expected_bytes": expect.get(itype), "size": ch.size}


def frame_extensions(data, flist):
    """Per frame: (name, hanim) read from the extension chunks that follow the frame-list struct."""
    exts = flist.find(3)
    out = []
    for e in exts:
        name = None
        hanim = None
        # plugin chunks inside an extension are leaves, so walk them directly
        q = e.data_start
        while q + 12 <= e.end:
            t, sz, ver = struct.unpack_from("<III", data, q)
            if sz > e.end - q - 12:
                break
            if t == NODE_NAME:
                name = data[q + 12:q + 12 + sz].split(b"\0")[0].decode("latin-1")
            elif t == HANIM and sz >= 12:
                fake = Chunk(t, sz, ver, q)
                hanim = read_hanim(data, fake)
            q += 12 + sz
        out.append((name, hanim))
    return out


def geometry_skin(data, geo, nvert):
    ext = geo.first(3)
    if not ext:
        return None
    q = ext.data_start
    while q + 12 <= ext.end:
        t, sz, ver = struct.unpack_from("<III", data, q)
        if sz > ext.end - q - 12:
            break
        if t == SKIN:
            return read_skin(data, Chunk(t, sz, ver, q), nvert)
        q += 12 + sz
    return None


def hexline(b):
    return " ".join("%02x" % x for x in b)


def skin_detail(data, sk):
    t, e = sk["tail_start"], sk["end"]
    print("    --- bytes after the weights: %d ---" % (e - t))
    for o in range(0, min(112, e - t), 16):
        print("      +%4d: %s" % (o, hexline(data[t + o:t + o + 16])))
    print("      ... last 48 bytes:")
    for o in range(max(0, e - t - 48), e - t, 16):
        print("      +%4d: %s" % (o, hexline(data[t + o:min(t + o + 16, e)])))
    off, stride, cnt = find_matrix_block(data, t, e, sk["bones"])
    print("    best place for %d consecutive bone matrices: offset +%d, stride %d bytes, %d of %d look like matrices" % (
        sk["bones"], off, stride, cnt, sk["bones"]))
    print("    (so there are %d bytes before them and %d bytes after them)" % (off, e - t - off - sk["bones"] * stride))
    if cnt:
        m = struct.unpack_from("<16f", data, t + off)
        print("    first matrix: " + " ".join("%.3f" % x for x in m))


def anim_detail(data, ch, limit):
    p = ch.data_start
    ver, itype, n, flags, dur = struct.unpack_from("<4If", data, p)
    body = p + 20
    print("      raw first %d keyframes (22 bytes each):" % limit)
    for i in range(min(limit, n)):
        print("        %3d: %s" % (i, hexline(data[body + 22 * i:body + 22 * i + 22])))
    tail = body + 22 * n
    if tail + 24 <= ch.end:
        print("      block after the keyframes: %s" % hexline(data[tail:tail + 24]))
        print("        as 6 floats: " + " ".join("%.5g" % x for x in struct.unpack_from("<6f", data, tail)))
    print("      last 3 keyframes:")
    for i in range(max(0, n - 3), n):
        print("        %3d: %s" % (i, hexline(data[body + 22 * i:body + 22 * i + 22])))


def half(h):
    return struct.unpack("<e", struct.pack("<H", h))[0]


def unpack16(h):
    """Decode the 16-bit animation value: sign bit, 5-bit exponent, 10-bit mantissa, except that the low bit of
    the exponent counts as an extra top mantissa bit (so each doubling of the value takes two exponent steps).
    0x7800 is 1.0, 0x7400 is 0.75, 0x7000 is 0.5. Verified against the translation rest poses of N00001A."""
    mag = h & 0x7FFF
    if mag == 0:
        return 0.0
    e = mag >> 10
    m = ((e & 1) << 10) | (mag & 0x3FF)
    v = 2.0 ** ((e >> 1) - 15) * (1 + m / 2048.0)
    return -v if h & 0x8000 else v


def quat_from_matrix(m):
    """Unit quaternion (x, y, z, w) from a 3x3 rotation matrix given as rows."""
    t = m[0][0] + m[1][1] + m[2][2]
    if t > 0:
        r = (1 + t) ** 0.5
        w = r / 2
        x, y, z = (m[2][1] - m[1][2]) / (2 * r), (m[0][2] - m[2][0]) / (2 * r), (m[1][0] - m[0][1]) / (2 * r)
    elif m[0][0] >= m[1][1] and m[0][0] >= m[2][2]:
        r = (1 + m[0][0] - m[1][1] - m[2][2]) ** 0.5
        x = r / 2
        y, z, w = (m[0][1] + m[1][0]) / (2 * r), (m[0][2] + m[2][0]) / (2 * r), (m[2][1] - m[1][2]) / (2 * r)
    elif m[1][1] >= m[2][2]:
        r = (1 + m[1][1] - m[0][0] - m[2][2]) ** 0.5
        y = r / 2
        x, z, w = (m[0][1] + m[1][0]) / (2 * r), (m[1][2] + m[2][1]) / (2 * r), (m[0][2] - m[2][0]) / (2 * r)
    else:
        r = (1 + m[2][2] - m[0][0] - m[1][1]) ** 0.5
        z = r / 2
        x, y, w = (m[0][2] + m[2][0]) / (2 * r), (m[1][2] + m[2][1]) / (2 * r), (m[1][0] - m[0][1]) / (2 * r)
    return (x, y, z, w)


def normalise(q):
    n = sum(c * c for c in q) ** 0.5
    return tuple(c / n for c in q) if n else (0, 0, 0, 1)


def linfit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return 0, my, 0
    sl = sxy / sxx
    return sl, my - sl * mx, (sxy * sxy) / (sxx * syy)


def anim_fit(data, ch, frames, bone_frames):
    """Compare the first keyframe of each bone with the bone's rest pose from the frame list, to work out
    how rotation and translation are stored."""
    p = ch.data_start
    n = struct.unpack_from("<I", data, p + 8)[0]
    body = p + 20
    nb = len(bone_frames)
    if n < nb:
        print("      too few keyframes for a fit")
        return
    kfs = []
    for i in range(nb):
        o = body + 22 * i
        t = struct.unpack_from("<f", data, o)[0]
        rot = struct.unpack_from("<4H", data, o + 4)
        tr = struct.unpack_from("<3H", data, o + 12)
        kfs.append((t, rot, tr))
    print("      fit of the first %d keyframes against the rest pose (frame list):" % nb)
    print("        keyframes with time 0: %d of %d" % (sum(1 for k in kfs if abs(k[0]) < 1e-6), nb))
    # rotation
    best = None
    for conv in ("rows", "columns"):
        rest_q = []
        for fi in bone_frames:
            R = frames[fi]["rot"]
            if conv == "columns":
                R = [[R[j][i] for j in range(3)] for i in range(3)]
            rest_q.append(quat_from_matrix(R))
        for name, dec in (("folded 16-bit", unpack16), ("half floats", lambda h: half(h)), ("int16 / 32768", lambda h: (h - 65536 if h > 32767 else h) / 32768)):
            for order in ("xyzw", "wxyz"):
                tot = 0
                for (t, rot, tr), rq in zip(kfs, rest_q):
                    v = [dec(h) for h in rot]
                    q = normalise(tuple(v) if order == "xyzw" else (v[1], v[2], v[3], v[0]))
                    tot += abs(sum(a * b for a, b in zip(q, rq)))
                score = tot / nb
                if best is None or score > best[0]:
                    best = (score, conv, name, order)
                print("        rotation, rest matrix as %s, %-13s, order %s: mean |dot| with rest pose %.3f" % (conv, name, order, score))
    print("        best rotation reading: %s, %s, %s (%.3f)" % (best[1], best[2], best[3], best[0]))
    # translation
    for name, dec in (("int16", lambda h: h - 65536 if h > 32767 else h), ("half floats", half)):
        parts = []
        for ax in range(3):
            xs = [dec(k[2][ax]) for k in kfs]
            ys = [frames[fi]["pos"][ax] for fi in bone_frames]
            parts.append((ax, linfit(xs, ys)))
        print("        translation as %-11s: %s" % (name, "; ".join(
            "%s = %.6g * raw + %.6g (r2 %.3f)" % ("xyz"[ax], sl, ic, r2) for ax, (sl, ic, r2) in parts)))
    tail = body + 22 * n
    if tail + 24 <= ch.end:
        blk = struct.unpack_from("<6f", data, tail)
        print("        the 24-byte block as 6 floats: " + " ".join("%.6g" % x for x in blk))
        # test the block as offset (first three) and scalar (last three) under several ways of scaling the raw value
        s16 = lambda h: h - 65536 if h > 32767 else h
        hyps = [("offset + scalar * folded 16-bit", unpack16),
                ("offset + scalar * half / 32768", lambda h: half(h) / 32768),
                ("offset + scalar * half", lambda h: half(h)),
                ("offset + scalar * int16 / 32768", lambda h: s16(h) / 32768),
                ("offset + scalar * uint16 / 65535", lambda h: h / 65535),
                ("offset + scalar * half / 16384", lambda h: half(h) / 16384),
                ("offset + scalar * half / 65536", lambda h: half(h) / 65536)]
        print("        translation from the block, median absolute error against the rest pose (x, y, z):")
        for name, dec in hyps:
            errs = []
            for ax in range(3):
                e = sorted(abs(blk[ax] + blk[3 + ax] * dec(k[2][ax]) - frames[fi]["pos"][ax]) for k, fi in zip(kfs, bone_frames))
                errs.append(e[len(e) // 2])
            print("          %-34s %9.4g %9.4g %9.4g" % (name, errs[0], errs[1], errs[2]))
    print("        per bone: first keyframe raw (rotation 4, translation 3 as hex) and the rest pose (position x y z):")
    for i, (k, fi) in enumerate(zip(kfs, bone_frames)):
        pos = frames[fi]["pos"]
        print("          bone %3d: %s | %s | %9.4f %9.4f %9.4f" % (
            i, " ".join("%04x" % h for h in k[1]), " ".join("%04x" % h for h in k[2]), pos[0], pos[1], pos[2]))


def cmd_skeleton(a):
    with open(a.model, "rb") as fh:
        data = fh.read()
    sc = read_scene(data)
    flist = sc["clump"].first(0x0E)
    frames = sc["frames"]
    exts = frame_extensions(data, flist) if flist else []
    print("%s" % a.model)
    print("Frames: %d (extension chunks found: %d)" % (len(frames), len(exts)))
    named = sum(1 for n, _ in exts if n)
    hanims = [(i, h) for i, (n, h) in enumerate(exts) if h]
    print("Frames with a name: %d; frames with bone (HAnim) data: %d" % (named, len(hanims)))
    roots = [(i, h) for i, h in hanims if h["count"] > 0]
    for i, h in roots:
        print("  skeleton root: frame %d, bone id %d, %d bones, flags %d, keyframe size %d" % (
            i, h["node_id"], h["count"], h["flags"], h["keyframe_size"]))
        by_id = {hh["node_id"]: ii for ii, hh in hanims}
        for k, (nid, idx, fl) in enumerate(h["nodes"][:a.max_bones]):
            fi = by_id.get(nid)
            par = frames[fi]["parent"] if fi is not None and fi < len(frames) else None
            nm = exts[fi][0] if fi is not None and fi < len(exts) else None
            print("    bone %3d: id %4d, frame %s, parent frame %s, flags %d%s" % (
                idx, nid, fi, par, fl, ("  name " + nm) if nm else ""))
        if len(h["nodes"]) > a.max_bones:
            print("    ... %d more bones (use --max-bones to show more)" % (len(h["nodes"]) - a.max_bones))
    if not hanims:
        print("  no skeleton data in this model")
    print()
    for gi, geo in enumerate(sc["geos"]):
        try:
            info = read_geometry(data, geo)
            nvert = info["nvert"]
        except (ToolError, struct.error):
            continue
        try:
            sk = geometry_skin(data, geo, nvert)
        except (ToolError, struct.error) as e:
            print("geometry %d: skin data could not be read (%s)" % (gi, e))
            continue
        if not sk:
            print("geometry %d: %d vertices, no skin data" % (gi, nvert))
            continue
        wsum = sum(1 for w in sk["weights"] if abs(sum(w) - 1.0) < 0.02)
        used = sum(1 for ix, w in zip(sk["indices"], sk["weights"]) for i, x in zip(ix, w) if x > 0 and i >= sk["bones"])
        print("geometry %d: %d vertices, skin: %d bones (%d used), up to %d weights per vertex" % (
            gi, nvert, sk["bones"], len(sk["used"]), sk["max_weights"]))
        print("    weights sum to 1 on %d of %d vertices; bone indices out of range: %d" % (wsum, nvert, used))
        print("    inverse matrices: layout %s, %d bytes left after the weights, %d of %d matrices look sane" % (
            ("exact (matrices, then %d trailing bytes)" % sk["layout"][1]) if sk["layout_exact"] else "NOT recognised",
            sk["rest_bytes"], sk["sane_matrices"], len(sk["matrices"])))
        if sk["split"]:
            sp = sk["split"]
            print("    split-skin data: header numbers %s, %d range pairs, %d of %d bones used by the remap table" % (
                sp["header"], sp["rle_count"], sum(1 for x in sp["remap"] if x != 0xFF), sk["bones"]))
        if a.detail:
            skin_detail(data, sk)
    print()
    anims = [c for c in sc["top"] if c.type == ANIM]
    print("Animation chunks (0x1B) at the top level: %d" % len(anims))
    types = {}
    for c in anims:
        try:
            an = read_anim(data, c)
        except struct.error:
            continue
        types.setdefault(an["type"], []).append(an)
    for t, lst in sorted(types.items()):
        ok = sum(1 for x in lst if x["expected_bytes"] is not None and x["body_bytes"] == x["expected_bytes"])
        print("  type %d: %d animations; keyframe counts %s; sizes consistent with %s bytes per keyframe: %d of %d" % (
            t, len(lst), sorted({x["frames"] for x in lst})[:8], {1: "36", 2: "22 (+24 once)"}.get(t, "?"), ok, len(lst)))
        for x in lst[:a.max_anims]:
            print("      version 0x%X, %d keyframes, duration %.3f s, flags %d, body %d bytes (expected %s)" % (
                x["version"], x["frames"], x["duration"], x["flags"], x["body_bytes"], x["expected_bytes"]))
        if a.detail and t not in (1, 2):
            c = next(c for c in anims if read_anim(data, c)["type"] == t)
            an = read_anim(data, c)
            print("      unknown type 0x%08X: header bytes %s" % (t, hexline(data[c.data_start:c.data_start + 20])))
            if an["frames"] and an["body_bytes"] % an["frames"] == 0:
                size = an["body_bytes"] // an["frames"]
                print("      body is %d bytes per keyframe; first 6 and last 3 keyframes:" % size)
                body = c.data_start + 20
                for i in list(range(min(6, an["frames"]))) + list(range(max(6, an["frames"] - 3), an["frames"])):
                    print("        %3d: %s" % (i, hexline(data[body + size * i:body + size * i + size])))
                print("      bytes after the keyframes: %s" % hexline(data[body + size * an["frames"]:c.end][:48]))
            else:
                print("      body (%d bytes) does not divide evenly by %d keyframes; first 96 bytes: %s" % (
                    an["body_bytes"], an["frames"], hexline(data[c.data_start + 20:c.data_start + 116])))
        if a.detail and t == 2:
            first = next(c for c in anims if read_anim(data, c)["type"] == 2)
            anim_detail(data, first, 8)
            if roots:
                by_id = {hh["node_id"]: ii for ii, hh in hanims}
                bone_frames = [by_id[nid] for nid, idx, fl in sorted(roots[0][1]["nodes"], key=lambda n: n[1]) if nid in by_id]
                if len(bone_frames) == len(roots[0][1]["nodes"]):
                    anim_fit(data, first, frames, bone_frames)


def _batch_one(job):
    path, out_dir, mirror, textures, as_gltf = job
    import io
    import contextlib
    rec = {"file": path}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            if as_gltf:
                import p3fes_gltf
                r = p3fes_gltf.export_gltf(path, out_dir, mirror, textures, verbose=False)
                r["vertices"] = r["meshes"]
            else:
                r = export_model(path, out_dir, mirror, textures, verbose=False)
        rec.update(status="ok" if r["vertices"] else "empty", vertices=r["vertices"], skipped=r["skipped"],
                   textures=len(r["textures"]))
        if as_gltf:
            rec.update(bones=r["bones"], animations=r["animations"], notes=r["notes"])
        if r["skipped"]:
            rec["status"] = "partial" if r["vertices"] else "empty"
    except BaseException as e:             # one bad file must never stop the batch
        rec.update(status="failed", error="%s: %s" % (type(e).__name__, e))
        try:
            with open(path, "rb") as fh:
                rec["head"] = fh.read(16).hex(" ")
        except OSError:
            pass
    return rec


def cmd_batch(a):
    import concurrent.futures
    import json
    want = a.match.lower() if a.match else None
    files = []
    for dp, _, fns in os.walk(a.folder):
        for fn in sorted(fns):
            if fn.lower().endswith(".rmd") and (not want or want in fn.lower()):
                files.append(os.path.join(dp, fn))
    files.sort()
    if a.limit:
        files = files[:a.limit]
    if not files:
        sys.exit("No .RMD files found in " + a.folder)
    jobs = []
    for f in files:
        rel = os.path.relpath(os.path.dirname(f), a.folder)
        base = os.path.splitext(os.path.basename(f))[0]
        jobs.append((f, os.path.join(a.out, rel, base), a.mirror_x, not a.no_textures, a.gltf))
    print("Exporting %d models to %s using %d worker(s). This can take a while; progress is shown every 100 files." % (len(jobs), a.out, a.jobs))
    results = []
    if a.jobs > 1:
        with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as ex:
            for i, rec in enumerate(ex.map(_batch_one, jobs, chunksize=8), 1):
                results.append(rec)
                if i % 100 == 0:
                    print("  %d / %d" % (i, len(jobs)))
    else:
        for i, j in enumerate(jobs, 1):
            results.append(_batch_one(j))
            if i % 100 == 0:
                print("  %d / %d" % (i, len(jobs)))
    os.makedirs(a.out, exist_ok=True)
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    reasons = {}
    for r in results:
        if r["status"] == "failed":
            reasons.setdefault(r["error"], []).append(r)
        elif r["status"] in ("partial", "empty"):
            for sk in r["skipped"] or ["no geometry written"]:
                key = "skipped: " + sk.split(":", 1)[-1].strip()
                reasons.setdefault(key, []).append(r)
    import re
    for r in results:                      # warnings from the glTF exporter, grouped with the numbers blanked out
        for note in r.get("notes") or []:
            key = "note: " + re.sub(r"\d+", "N", note)
            reasons.setdefault(key, []).append(r)
    with open(os.path.join(a.out, "batch_report.json"), "w") as fh:
        json.dump(results, fh, indent=1)
    lines = ["Models: %d" % len(results)]
    lines += ["  %-8s %d" % (k, v) for k, v in sorted(counts.items())]
    lines.append("")
    lines.append("Problems grouped by reason (count, then up to 3 example files):")
    for k, v in sorted(reasons.items(), key=lambda kv: -len(kv[1])):
        lines.append("  %5d  %s" % (len(v), k))
        for r in v[:3]:
            lines.append("           %s%s" % (os.path.relpath(r["file"], a.folder), ("   starts: " + r["head"]) if r.get("head") else ""))
    lines.append("")
    if a.gltf:
        lines.append("Totals: %d meshes exported, %d textures written; %d models have a skeleton, %d animations written." % (
            sum(r.get("vertices", 0) for r in results), sum(r.get("textures", 0) for r in results),
            sum(1 for r in results if r.get("bones")), sum(r.get("animations", 0) for r in results)))
    else:
        lines.append("Totals: %d vertices exported, %d textures written." % (
            sum(r.get("vertices", 0) for r in results), sum(r.get("textures", 0) for r in results)))
    text = "\n".join(lines)
    with open(os.path.join(a.out, "batch_report.txt"), "w") as fh:
        fh.write(text + "\n")
    print()
    print(text)
    print("\nFull list written to " + os.path.join(a.out, "batch_report.json"))


def main():
    ap = argparse.ArgumentParser(description="Read Persona 3 FES .RMD model files.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("info", help="show what is inside a model")
    p.add_argument("model")
    p.set_defaults(fn=cmd_info)
    p = sub.add_parser("skeleton", help="show the bones, skin weights and animation headers in a model")
    p.add_argument("model")
    p.add_argument("--max-bones", type=int, default=40)
    p.add_argument("--max-anims", type=int, default=6)
    p.add_argument("--detail", action="store_true", help="also dump raw bytes of the skin tail and the first animation (for format work)")
    p.set_defaults(fn=cmd_skeleton)
    p = sub.add_parser("chunks", help="debug: show the game's own chunks and where RenderWare data might start")
    p.add_argument("model")
    p.set_defaults(fn=cmd_chunks)
    p = sub.add_parser("texhex", help="print the raw bytes of a texture (for format research)")
    p.add_argument("model")
    p.add_argument("--name", help="texture name (default: the first one)")
    p.add_argument("--all", action="store_true")
    p.set_defaults(fn=cmd_texhex)
    p = sub.add_parser("textures", help="write the model's textures as PNG files")
    p.add_argument("model")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--variants", action="store_true", help="for 4-bit textures also write a sheet of alternative readings")
    p.set_defaults(fn=cmd_textures)
    p = sub.add_parser("export", help="write the geometry as .obj and .mtl")
    p.add_argument("model")
    p.add_argument("-o", "--out", required=True, help="output folder")
    p.add_argument("--no-textures", action="store_true", help="do not write the texture PNG files")
    p.add_argument("--mirror-x", action="store_true", help="mirror the model left-right (for viewers that show it flipped)")
    p.set_defaults(fn=cmd_export)
    p = sub.add_parser("gltf", help="write mesh, skeleton, skin weights and animations as glTF (opens in Blender)")
    p.add_argument("model")
    p.add_argument("-o", "--out", required=True, help="output folder")
    p.add_argument("--no-textures", action="store_true")
    p.add_argument("--mirror-x", action="store_true", help="mirror the model left-right")
    p.set_defaults(fn=cmd_gltf)
    p = sub.add_parser("batch", help="export every .RMD in a folder (one subfolder per model) and write a report")
    p.add_argument("folder", help="folder to search, including subfolders (e.g. the MODEL folder)")
    p.add_argument("-o", "--out", required=True, help="output folder")
    p.add_argument("--no-textures", action="store_true", help="geometry only (much faster, far less disk space)")
    p.add_argument("--mirror-x", action="store_true")
    p.add_argument("--gltf", action="store_true", help="write glTF (skeleton, skin, animations) instead of .obj")
    p.add_argument("--match", help="only files whose name contains this text (e.g. N000)")
    p.add_argument("--limit", type=int, help="stop after this many files (for a quick trial)")
    p.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1), help="parallel workers")
    p.set_defaults(fn=cmd_batch)
    a = ap.parse_args()
    try:
        a.fn(a)
    except (ToolError, OSError, struct.error) as e:
        sys.exit("Error: %s" % e)


if __name__ == "__main__":
    main()
