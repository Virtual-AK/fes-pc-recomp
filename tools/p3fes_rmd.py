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


def _batch_one(job):
    path, out_dir, mirror, textures = job
    import io
    import contextlib
    rec = {"file": path}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            r = export_model(path, out_dir, mirror, textures, verbose=False)
        rec.update(status="ok" if r["vertices"] else "empty", vertices=r["vertices"], skipped=r["skipped"],
                   textures=len(r["textures"]))
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
        jobs.append((f, os.path.join(a.out, rel, base), a.mirror_x, not a.no_textures))
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
    p = sub.add_parser("batch", help="export every .RMD in a folder (one subfolder per model) and write a report")
    p.add_argument("folder", help="folder to search, including subfolders (e.g. the MODEL folder)")
    p.add_argument("-o", "--out", required=True, help="output folder")
    p.add_argument("--no-textures", action="store_true", help="geometry only (much faster, far less disk space)")
    p.add_argument("--mirror-x", action="store_true")
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
