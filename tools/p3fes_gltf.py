#!/usr/bin/env python3
"""Write a Persona 3 FES .RMD model as glTF: mesh, skeleton, skin weights and animations.

Usage:   py p3fes_rmd.py gltf MODEL.RMD -o OUTFOLDER
Result:  OUTFOLDER/NAME.gltf + NAME.bin (+ texture PNGs). Blender: File > Import > glTF 2.0.

Needs nothing but Python. Reads the user's own data only; never ship the output.
Formats are described in docs/formats.md (skeleton, skin and animation section).
"""
import json
import math
import os
import struct

import p3fes_rmd as r


def transpose(m):
    return [[m[j][i] for j in range(3)] for i in range(3)]


def det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
            m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def inv3(m):
    d = det3(m)
    if abs(d) < 1e-12:
        return [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]
    c = [[m[(j + 1) % 3][(i + 1) % 3] * m[(j + 2) % 3][(i + 2) % 3] - m[(j + 1) % 3][(i + 2) % 3] * m[(j + 2) % 3][(i + 1) % 3]
          for j in range(3)] for i in range(3)]
    return [[c[i][j] / d for j in range(3)] for i in range(3)]


def inverse_rows(R, t):
    """Inverse of the row-vector transform p' = p*R + t, as a 4x4 (rows)."""
    Ri = inv3(R)
    ti = [-sum(t[k] * Ri[k][j] for k in range(3)) for j in range(3)]
    return mat4_rows(Ri, ti)


def decompose_rows(R):
    """Split a row-vector rotation-and-scale matrix (p' = p*R) into a glTF rotation quaternion (x, y, z, w) and a
    scale (sx, sy, sz). A mirrored matrix (negative determinant) gets a negative x scale."""
    lens = [math.sqrt(sum(c * c for c in row)) or 1.0 for row in R]
    Rn = [[c / lens[i] for c in R[i]] for i in range(3)]
    scale = list(lens)
    if det3(Rn) < 0:
        Rn[0] = [-c for c in Rn[0]]
        scale[0] = -scale[0]
    q = r.normalise(r.quat_from_matrix(transpose(Rn)))
    return q, scale


def mat4_rows(R, t):
    """Row-vector 4x4 (p' = p*M) from a 3x3 and a translation."""
    return [list(R[0]) + [0.0], list(R[1]) + [0.0], list(R[2]) + [0.0], list(t) + [1.0]]


def mul4(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def dot4(a, b):
    return abs(sum(x * y for x, y in zip(a, b)))


class Buffer:
    """Collects binary data and the bufferViews / accessors that describe it."""

    def __init__(self):
        self.blob = bytearray()
        self.views = []
        self.accessors = []

    def add(self, raw, ctype, count, atype, target=None, minmax=None):
        while len(self.blob) % 4:
            self.blob.append(0)
        view = {"buffer": 0, "byteOffset": len(self.blob), "byteLength": len(raw)}
        if target:
            view["target"] = target
        self.blob += raw
        self.views.append(view)
        acc = {"bufferView": len(self.views) - 1, "componentType": ctype, "count": count, "type": atype}
        if minmax:
            acc["min"], acc["max"] = minmax
        self.accessors.append(acc)
        return len(self.accessors) - 1

    def floats(self, flat, atype, comps, target=None, minmax=False):
        n = len(flat) // comps
        mm = None
        if minmax and n:
            cols = [flat[i::comps] for i in range(comps)]
            mm = ([min(c) for c in cols], [max(c) for c in cols])
        return self.add(struct.pack("<%df" % len(flat), *flat), 5126, n, atype, target, mm)


EFFECT_TYPE = 0x44A07195


def read_keyframes(data, ch, nbones):
    """Per bone: sorted list of (time, quaternion xyzw, translation) from one animation chunk.
    Type 2: 22-byte compressed keyframes (+ a 24-byte offset/scale block). Type 1: 36-byte plain keyframes
    (float time, 4 float quaternion, 3 float position, u32 back pointer)."""
    p = ch.data_start
    ver, itype, n, flags, dur = struct.unpack_from("<4If", data, p)
    body = p + 20
    if itype == 2:
        size, unit = 22, 24
        if body + 22 * n + 24 > ch.end:
            raise r.ToolError("animation is shorter than its keyframe count says")
        off = struct.unpack_from("<3f", data, body + 22 * n)
        sc = struct.unpack_from("<3f", data, body + 22 * n + 12)
    elif itype == 1:
        size, unit = 36, 36
        if body + 36 * n > ch.end:
            raise r.ToolError("animation is shorter than its keyframe count says")
    elif itype == EFFECT_TYPE:
        size, unit = 52, 52
        if body + 52 * n > ch.end:
            raise r.ToolError("animation is shorter than its keyframe count says")
    else:
        raise r.ToolError("animation type %d is not understood" % itype)
    owner = [None] * n
    tracks = [[] for _ in range(nbones)]
    for i in range(n):
        o = body + size * i
        t = struct.unpack_from("<f", data, o)[0]
        if itype == 2:
            rot = struct.unpack_from("<4H", data, o + 4)
            tr = struct.unpack_from("<3H", data, o + 12)
            prev = struct.unpack_from("<I", data, o + 18)[0]
            q = r.normalise(tuple(r.unpack16(h) for h in rot))
            pos = tuple(off[a] + sc[a] * r.unpack16(tr[a]) for a in range(3))
        elif itype == 1:
            q = r.normalise(struct.unpack_from("<4f", data, o + 4))
            pos = struct.unpack_from("<3f", data, o + 20)
            prev = struct.unpack_from("<I", data, o + 32)[0]
        else:                                     # effect layout: quaternion is NaN when the bone has no rotation
            raw = struct.unpack_from("<4f", data, o + 4)
            q = None if any(c != c or abs(c) > 1e6 for c in raw) else r.normalise(raw)
            pos = struct.unpack_from("<3f", data, o + 20)
            prev = struct.unpack_from("<I", data, o + 48)[0]
        if i < nbones:
            owner[i] = i
        else:
            pi = prev // unit
            if prev % unit or pi >= i or owner[pi] is None:
                raise r.ToolError("keyframe %d points at an impossible previous keyframe" % i)
            owner[i] = owner[pi]
        tracks[owner[i]].append((t, q, tuple(pos)))
    for tr in tracks:
        tr.sort(key=lambda k: k[0])
        last = None
        for i in range(len(tr)):                  # keep neighbouring quaternions in one hemisphere
            if tr[i][1] is None:
                continue
            if last is not None and sum(a * b for a, b in zip(tr[i][1], tr[last][1])) < 0:
                tr[i] = (tr[i][0], tuple(-c for c in tr[i][1]), tr[i][2])
            last = i
    return {"duration": dur, "tracks": tracks, "keyframes": n, "type": itype}


def export_gltf(model_path, out_dir, mirror_x=False, textures=True, verbose=True):
    with open(model_path, "rb") as fh:
        data = fh.read()
    sc = r.read_scene(data)
    frames = sc["frames"]
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(model_path))[0]
    flist = sc["clump"].first(0x0E)
    exts = r.frame_extensions(data, flist) if flist else []
    hanims = [(i, h) for i, (n, h) in enumerate(exts) if h]
    roots = [(i, h) for i, h in hanims if h["count"] > 0]
    notes = []
    diag = []
    # bone index -> frame
    bone_frame = []
    if roots:
        by_id = {h["node_id"]: i for i, h in hanims}
        slots = {}
        for nid, idx, fl in roots[0][1]["nodes"]:
            if nid in by_id:
                slots[idx] = by_id[nid]
        bone_frame = [slots[i] for i in range(len(roots[0][1]["nodes"])) if i in slots]
        if len(bone_frame) != roots[0][1]["count"]:
            notes.append("only %d of %d bones could be matched to frames" % (len(bone_frame), roots[0][1]["count"]))
    nb = len(bone_frame)

    buf = Buffer()
    nodes = []
    # one glTF node per RenderWare frame, same index
    mirrored = 0
    rest_q = []
    for i, f in enumerate(frames):
        q, scl = decompose_rows(f["rot"])
        rest_q.append(q)
        node = {"name": "frame%d" % i if i not in bone_frame else "bone%d" % bone_frame.index(i),
                "rotation": list(q), "translation": list(f["pos"])}
        if any(abs(abs(v) - 1.0) > 1e-4 or v < 0 for v in scl):
            node["scale"] = scl
        if scl[0] < 0:
            mirrored += 1
        nodes.append(node)
    if mirrored:
        diag.append("%d frames are mirrored; exported with a negative scale" % mirrored)
    for i, f in enumerate(frames):
        p = f["parent"]
        if 0 <= p < len(frames) and p != i:
            nodes[p].setdefault("children", []).append(i)
    top = [i for i, f in enumerate(frames) if not (0 <= f["parent"] < len(frames)) or f["parent"] == i]
    world = r.world_transforms(frames) if frames else []

    materials, mat_index, images, gltf_textures, samplers = [], {}, [], {}, []
    tex_files = []
    if textures:
        tex_files = r.export_textures(data, sc["texdict"], out_dir, verbose=verbose)

    def material(geo_i, mats, m):
        key = (geo_i, m)
        if key in mat_index:
            return mat_index[key]
        info = mats[m] if m < len(mats) else {"color": (200, 200, 200, 255), "texture": None}
        c = info["color"]
        mat = {"name": "mat_%d_%d" % key, "doubleSided": True,
               "pbrMetallicRoughness": {"baseColorFactor": [c[0] / 255, c[1] / 255, c[2] / 255, 1.0],
                                        "metallicFactor": 0.0, "roughnessFactor": 1.0}}
        tex = info.get("texture")
        if tex and textures:
            if tex not in gltf_textures:
                images.append({"uri": "%s.png" % tex})
                gltf_textures[tex] = len(images) - 1
            mat["pbrMetallicRoughness"]["baseColorTexture"] = {"index": gltf_textures[tex]}
            mat["pbrMetallicRoughness"]["baseColorFactor"] = [1, 1, 1, 1]
            mat["alphaMode"] = "MASK"
            mat["alphaCutoff"] = 0.5
        materials.append(mat)
        mat_index[key] = len(materials) - 1
        return mat_index[key]

    meshes, skins = [], []
    scene_nodes = list(top)
    skinned_count = 0
    shared_skin = None
    skipped = []
    for ai, (fi, gi, fl) in enumerate(sc["atomics"]):
        if gi >= len(sc["geos"]):
            skipped.append("atomic %d: geometry index out of range" % ai)
            continue
        geo = sc["geos"][gi]
        try:
            info = r.read_geometry(data, geo)
        except (r.ToolError, struct.error) as e:
            skipped.append("geometry %d: %s" % (gi, e))
            continue
        if info.get("native"):
            skipped.append("geometry %d: PS2 native format" % gi)
            continue
        try:
            sk = r.geometry_skin(data, geo, info["nvert"]) if nb else None
        except (r.ToolError, struct.error):
            sk = None
        if sk and len(sk["matrices"]) != sk["bones"]:
            notes.append("geometry %d: inverse bind matrices could not be read: exported without skin" % gi)
            sk = None
        if sk and sk["bones"] != nb:
            notes.append("geometry %d: skin has %d bones, skeleton %d: exported without skin" % (gi, sk["bones"], nb))
            sk = None
        R, T = world[fi] if fi < len(world) else ([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 0])
        pos, nor = [], []
        for (x, y, z) in info["verts"]:       # world space, like the .obj export (this is the bind pose)
            pos += [x * R[0][0] + y * R[1][0] + z * R[2][0] + T[0], x * R[0][1] + y * R[1][1] + z * R[2][1] + T[1],
                    x * R[0][2] + y * R[1][2] + z * R[2][2] + T[2]]
        for (x, y, z) in info["normals"]:
            nor += [x * R[0][0] + y * R[1][0] + z * R[2][0], x * R[0][1] + y * R[1][1] + z * R[2][1],
                    x * R[0][2] + y * R[1][2] + z * R[2][2]]
        attrs = {"POSITION": buf.floats(pos, "VEC3", 3, 34962, minmax=True)}
        if nor:
            attrs["NORMAL"] = buf.floats(nor, "VEC3", 3, 34962)
        if info["uvs"]:
            attrs["TEXCOORD_0"] = buf.floats([c for uv in info["uvs"][0] for c in (uv[0], uv[1])], "VEC2", 2, 34962)
        if sk:
            j, w = [], []
            for ix, wt in zip(sk["indices"], sk["weights"]):
                j += [min(i, 255) for i in ix[:4]] + [0] * (4 - len(ix[:4]))
                w += list(wt[:4]) + [0.0] * (4 - len(wt[:4]))
            attrs["JOINTS_0"] = buf.add(bytes(j), 5121, info["nvert"], "VEC4", 34962)
            attrs["WEIGHTS_0"] = buf.floats(w, "VEC4", 4, 34962)
        mats = r.read_materials(data, geo)
        groups = {}
        for (v1, v2, v3, m) in info["tris"]:
            groups.setdefault(m, []).extend((v1, v3, v2) if mirror_x else (v1, v2, v3))
        prims = []
        for m, idx in sorted(groups.items()):
            if info["nvert"] < 65536:
                acc = buf.add(struct.pack("<%dH" % len(idx), *idx), 5123, len(idx), "SCALAR", 34963)
            else:
                acc = buf.add(struct.pack("<%dI" % len(idx), *idx), 5125, len(idx), "SCALAR", 34963)
            prims.append({"attributes": attrs, "indices": acc, "material": material(gi, mats, m), "mode": 4})
        meshes.append({"name": "%s_%d" % (base, ai), "primitives": prims})
        node = {"name": "%s_mesh%d" % (base, ai), "mesh": len(meshes) - 1}
        if sk:
            skinned_count += 1
            if shared_skin is None:       # one skin for the whole character: inverse bind = inverse of the rest world matrix
                ibm = []
                for f in bone_frame:
                    M = inverse_rows(*world[f])
                    ibm += M[0] + M[1] + M[2] + M[3]
                skins.append({"name": base + "_skin", "joints": list(bone_frame),
                              "inverseBindMatrices": buf.floats(ibm, "MAT4", 16), "skeleton": bone_frame[0]})
                shared_skin = len(skins) - 1
            node["skin"] = shared_skin
            # information only: how well the matrices stored in the file agree with the skeleton's rest pose
            dev = 0.0
            for b in sk["used"]:
                m = sk["matrices"][b]
                ibm_f = [list(m[0:3]) + [0.0], list(m[4:7]) + [0.0], list(m[8:11]) + [0.0], list(m[12:15]) + [1.0]]
                prod = mul4(ibm_f, mat4_rows(*world[bone_frame[b]]))
                dev = max(dev, max(abs(prod[i][j] - (1.0 if i == j else 0.0)) for i in range(4) for j in range(4)))
            diag.append("geometry %d: file bind matrices times rest world matrices, largest difference from identity over %d used bones: %.4f"
                        " (info only, not used)" % (gi, len(sk["used"]), dev))
        nodes.append(node)
        scene_nodes.append(len(nodes) - 1)

    # animations
    animations = []
    pose_dots = {}
    if nb:
        rest_q = [rest_q[f] for f in bone_frame]
        anim_no = -1
        for ch in sc["top"]:
            if ch.type != r.ANIM:
                continue
            anim_no += 1
            try:
                kf = read_keyframes(data, ch, nb)
            except (r.ToolError, struct.error) as e:
                notes.append("animation %d skipped: %s" % (anim_no, e))
                continue
            samplers_a, channels = [], []
            if kf["type"] not in pose_dots:
                pose_dots[kf["type"]] = [dot4(t[0][1], q) for t, q in zip(kf["tracks"], rest_q) if t and t[0][1] is not None]
            for b, tr in enumerate(kf["tracks"]):
                if len(tr) < 1:
                    continue
                times = buf.floats([k[0] for k in tr], "SCALAR", 1, minmax=True)
                trn = buf.floats([c for k in tr for c in k[2]], "VEC3", 3)
                rk = [k for k in tr if k[1] is not None]
                if rk:
                    rtimes = times if len(rk) == len(tr) else buf.floats([k[0] for k in rk], "SCALAR", 1, minmax=True)
                    rot = buf.floats([c for k in rk for c in k[1]], "VEC4", 4)
                    samplers_a.append({"input": rtimes, "output": rot, "interpolation": "LINEAR"})
                    channels.append({"sampler": len(samplers_a) - 1, "target": {"node": bone_frame[b], "path": "rotation"}})
                samplers_a.append({"input": times, "output": trn, "interpolation": "LINEAR"})
                channels.append({"sampler": len(samplers_a) - 1, "target": {"node": bone_frame[b], "path": "translation"}})
            animations.append({"name": "anim_%02d_%.2fs" % (len(animations), kf["duration"]), "samplers": samplers_a, "channels": channels})
    for kind, dots in sorted(pose_dots.items()):
        if not dots:
            continue
        diag.append("first %s animation, first pose against the frame-list rest pose: mean |dot| %.4f, %d of %d bones above 0.99" % (
            "effect-layout" if kind == EFFECT_TYPE else "type %d" % kind, sum(dots) / len(dots), sum(1 for d in dots if d > 0.99), len(dots)))
        worst = sorted(range(len(dots)), key=lambda i: dots[i])[:5]
        diag.append("  least similar bones: " + ", ".join("%d (%.3f)" % (i, dots[i]) for i in worst))

    if mirror_x:
        nodes.append({"name": "mirror", "scale": [-1.0, 1.0, 1.0], "children": scene_nodes})
        scene_nodes = [len(nodes) - 1]
    doc = {"asset": {"version": "2.0", "generator": "p3fes_gltf.py"},
           "scene": 0, "scenes": [{"nodes": scene_nodes}], "nodes": nodes, "meshes": meshes,
           "buffers": [{"uri": base + ".bin", "byteLength": len(buf.blob)}], "bufferViews": buf.views, "accessors": buf.accessors}
    if materials:
        doc["materials"] = materials
    if images:
        doc["images"] = images
        doc["textures"] = [{"source": i} for i in range(len(images))]
        # texture index == image index; material refs use the image index
    if skins:
        doc["skins"] = skins
    if animations:
        doc["animations"] = animations
    with open(os.path.join(out_dir, base + ".bin"), "wb") as fh:
        fh.write(bytes(buf.blob))
    with open(os.path.join(out_dir, base + ".gltf"), "w") as fh:
        json.dump(doc, fh, separators=(",", ":"))
    return {"base": base, "meshes": len(meshes), "skins": len(skins), "bones": nb, "animations": len(animations),
            "frames": len(frames), "skipped": skipped, "notes": notes, "diagnostics": diag, "textures": tex_files,
            "bytes": len(buf.blob)}
