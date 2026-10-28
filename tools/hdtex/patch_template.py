"""HD textures for the PC window of PS2 Web Recomp: draws a high-resolution picture instead of the game's own texture.

How it works: the game uploads every texture to the graphics chip. With PS2_HDTEX=<table file> set, the window hashes each upload (the same
hash as p3fes_texhash.py), looks it up in the table and, for a known texture, decodes the HD picture (DDS: BC1, BC2, BC3, BC7) on a second
thread and draws it instead, smoothed. Anything that goes wrong (no table, a missing file, too little graphics memory, a texture that was
overwritten) leaves the game's own picture, so the game looks as before. Nothing changes when PS2_HDTEX is not set.

  PS2_HDTEX=<file>       the table (the launcher writes it)
  PS2_HDTEX_MAX=1024     longest side kept for an HD picture (256 to 2048; larger pictures are halved)
  PS2_HDTEX_MB=192       graphics memory for HD pictures (16 to 2048, limited by what the card allows)

Run in the ps2-web-recomp folder:  python3 ps2run_hdtex_patch.py [folder]
(patches runtime/src/gs/gpu/gpu.cpp and gs.wgsl, adds runtime/src/gs/gpu/hdtex.hpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
GPU = 'runtime/src/gs/gpu/gpu.cpp'
WGSL = 'runtime/src/gs/gpu/gs.wgsl'
HPP = 'runtime/src/gs/gpu/hdtex.hpp'
TAG = 'ps2run_hdtex_patch.py'

HDTEX_HPP = @@HPP@@

GLUE = @@GLUE@@
GLUE_V1 = @@GLUE_V1@@
GLUE_V2 = @@GLUE_V2@@
GLUE_V3 = @@GLUE_V3@@
GLUE_V4 = @@GLUE_V4@@

WGSL_HD = '''const HD_BASE: u32 = 4194304u;   // ps2run_hdtex_patch.py: HD pictures live in `decoded` from here on (kDecodedWords in gpu.cpp)

fn hd_texel(base: u32, w: u32, h: u32, x: i32, y: i32) -> u32 {
    let xx = u32(clamp(x, 0, i32(w) - 1));
    let yy = u32(clamp(y, 0, i32(h) - 1));
    return decoded[base + 8u + yy * w + xx];
}

fn sample_hd(s: Setup, uin: f32, vin: f32) -> u32 {
    let base = s.dec;
    let w = decoded[base];
    let h = decoded[base + 1u];
    let sx = bitcast<f32>(decoded[base + 2u]);
    let sy = bitcast<f32>(decoded[base + 3u]);
    let ox = bitcast<f32>(decoded[base + 4u]);
    let oy = bitcast<f32>(decoded[base + 5u]);
    var u = uin / f32(1u << s.tw);
    var v = vin / f32(1u << s.th);
    if (mode(s, 24u, 2u) == 0u) {
        u = u - floor(u);
    } else {
        u = clamp(u, 0.0, 1.0);
    }
    if (mode(s, 26u, 2u) == 0u) {
        v = v - floor(v);
    } else {
        v = clamp(v, 0.0, 1.0);
    }
    let px = (u * sx + ox) * f32(w) - 0.5;
    let py = (v * sy + oy) * f32(h) - 0.5;
    let x0 = i32(floor(px));
    let y0 = i32(floor(py));
    return blend4(hd_texel(base, w, h, x0, y0), hd_texel(base, w, h, x0 + 1, y0), hd_texel(base, w, h, x0, y0 + 1), hd_texel(base, w, h, x0 + 1, y0 + 1), px - f32(x0), py - f32(y0));
}

'''

SAMPLE_OLD = 'fn sample(s: Setup, uin: f32, vin: f32, k: u32) -> u32 {\n    if (!has(s, F_BILINEAR)) {\n'
SAMPLE_NEW = ('fn sample(s: Setup, uin: f32, vin: f32, k: u32) -> u32 {\n    if (s.dec != 0xFFFFFFFFu && s.dec >= HD_BASE) {   // ps2run_hdtex_patch.py\n'
              '        return sample_hd(s, uin, vin);\n    }\n    if (!has(s, F_BILINEAR)) {\n')

GPU_EDITS = [
    # include
    ('#include <unordered_map>\n', '#include <unordered_map>\n#include <vector>\n#include "hdtex.hpp"   // ' + TAG + '\n'),
    # globals
    ('bool g_rendered[512] = {};\n',
     'bool g_rendered[512] = {};\nstd::uint32_t g_hd_epoch[512] = {};   // ' + TAG + ': counts writes to each memory page\nstruct HdLast {\n    std::uint64_t lo = 0, hi = 0;\n    int kind = 0;   // 1 upload, 2 draw\n};\nHdLast g_hd_last[512];   // who wrote each page last (for the log when a picture is dropped)\nstd::uint64_t g_hd_max_binding = 0;\n'),
    # every write bumps the page counters
    ('    for (std::uint64_t at = r.lo; at < r.hi; at += 8192) g_rendered[(at >> 13) & 511u] = true;\n',
     '    for (std::uint64_t at = r.lo; at < r.hi; at += 8192) {\n        const std::uint32_t pg = (at >> 13) & 511u;\n        g_rendered[pg] = true;\n        ++g_hd_epoch[pg];\n        g_hd_last[pg] = HdLast{r.lo, r.hi, 2};\n    }\n'),
    # the glue goes before the per-batch decode planner
    ('struct Decode {\n    std::uint32_t setup, offset, words;\n};\n', GLUE + 'struct Decode {\n    std::uint32_t setup, offset, words;\n};\n'),
    # apply
    ('    plan_decodes(prims);\n    const std::uint32_t prim_offset', '    plan_decodes(prims);\n    hd_apply(prims);   // ' + TAG + '\n    const std::uint32_t prim_offset'),
    # uploads
    ('    op.image = im.id;\n', '    op.image = im.id;\n    hd_note_write(op.range);   // ' + TAG + '\n'),
    ('    if (im.done < im.total) return;\n', '    if (im.done < im.total) return;\n    hd_image_done(im);   // ' + TAG + '\n'),
    ('    im.active = im.total != 0;\n', '    im.active = im.total != 0;\n    hd_begin(im);   // ' + TAG + '\n'),
    ('    if (im.pending.empty() && !im.lead_bits) {\n        const std::uint64_t used = queue_upload(data, bytes, 0);\n',
     '    hd_feed(data, bytes);   // ' + TAG + '\n    if (im.pending.empty() && !im.lead_bits) {\n        const std::uint64_t used = queue_upload(data, bytes, 0);\n'),
    # limits and the buffer
    ('    wgpuAdapterGetLimits(adapter, &supported);\n', '    wgpuAdapterGetLimits(adapter, &supported);\n    g_hd_max_binding = supported.maxStorageBufferBindingSize;   // ' + TAG + '\n'),
    ('    g_decoded = make_buffer(static_cast<std::uint64_t>(kDecodedWords) * 4, WGPUBufferUsage_Storage);\n',
     '    g_decoded = make_buffer(hd_setup(), WGPUBufferUsage_Storage | WGPUBufferUsage_CopyDst);   // ' + TAG + '\n'),
    # a loaded save state puts new memory in place
    ('void write_state(const std::vector<std::uint32_t> &vram, std::uint32_t scale, const std::vector<std::uint32_t> &clut) {\n    wait_idle();\n',
     'void write_state(const std::vector<std::uint32_t> &vram, std::uint32_t scale, const std::vector<std::uint32_t> &clut) {\n    wait_idle();\n    hd_forget_all();   // ' + TAG + '\n'),
]


def read(path):
    try:
        with open(root + '/' + path, newline='') as f:
            return f.read()
    except OSError:
        print("PATCH NOT APPLIED: cannot read " + path)
        raise SystemExit(1)


def write(path, text, crlf):
    with open(root + '/' + path, 'w', newline='') as f:
        f.write(text.replace('\n', '\r\n') if crlf else text)


# in-place upgrade of a tree that has the first version of this patch (no drop log)
_V1_GLOBALS = 'std::uint32_t g_hd_epoch[512] = {};   // ' + TAG + ': counts writes to each memory page\nstd::uint64_t g_hd_max_binding = 0;\n'
_V2_GLOBALS = ('std::uint32_t g_hd_epoch[512] = {};   // ' + TAG + ': counts writes to each memory page\nstruct HdLast {\n    std::uint64_t lo = 0, hi = 0;\n    int kind = 0;   // 1 upload, 2 draw\n};\n'
               'HdLast g_hd_last[512];   // who wrote each page last (for the log when a picture is dropped)\nstd::uint64_t g_hd_max_binding = 0;\n')
_V1_MARK = '    for (std::uint64_t at = r.lo; at < r.hi; at += 8192) g_rendered[(at >> 13) & 511u] = true, ++g_hd_epoch[(at >> 13) & 511u];\n'
_V2_MARK = ('    for (std::uint64_t at = r.lo; at < r.hi; at += 8192) {\n        const std::uint32_t pg = (at >> 13) & 511u;\n        g_rendered[pg] = true;\n        ++g_hd_epoch[pg];\n'
            '        g_hd_last[pg] = HdLast{r.lo, r.hi, 2};\n    }\n')
UPGRADE_V1 = [(_V1_GLOBALS, _V2_GLOBALS), (_V1_MARK, _V2_MARK), (GLUE_V1, GLUE)]
UPGRADE_V2 = [(GLUE_V2, GLUE)]
UPGRADE_V3 = [(GLUE_V3, GLUE)]
UPGRADE_V4 = [(GLUE_V4, GLUE)]


gpu = read(GPU)
wgsl = read(WGSL)
crlf_gpu = '\r\n' in gpu
crlf_wgsl = '\r\n' in wgsl
gpu = gpu.replace('\r\n', '\n')
wgsl = wgsl.replace('\r\n', '\n')
if TAG in gpu and TAG in wgsl:
    if 'hd_refreshing' in gpu:
        print("already patched")
        raise SystemExit
    # an earlier version of this patch is in: bring it up to date in place
    steps = UPGRADE_V4 if 'wait_budget_ms' in gpu else UPGRADE_V3 if 'g_hd_want' in gpu else UPGRADE_V2 if 'g_hd_last' in gpu else UPGRADE_V1
    for old, _ in steps:
        if gpu.count(old) != 1:
            print("PATCH NOT UPGRADED: " + GPU + " has an older HD texture patch that was changed by hand")
            print("  (could not place: %r)" % old[:70])
            raise SystemExit(1)
    for old, new in steps:
        gpu = gpu.replace(old, new)
    write(GPU, gpu, crlf_gpu)
    with open(root + '/' + HPP, 'w', newline='') as f:
        f.write(HDTEX_HPP)
    print("upgraded the HD texture patch (keeps pictures during re-uploads, %d edits + hdtex.hpp)" % len(steps))
    raise SystemExit
for old, _ in GPU_EDITS:
    if gpu.count(old) != 1:
        print("PATCH NOT APPLIED: " + GPU + " does not look like the expected source")
        print("  (could not place: %r)" % old[:70])
        raise SystemExit(1)
if wgsl.count(SAMPLE_OLD) != 1:
    print("PATCH NOT APPLIED: " + WGSL + " does not look like the expected source")
    raise SystemExit(1)
for old, new in GPU_EDITS:
    gpu = gpu.replace(old, new)
wgsl = wgsl.replace(SAMPLE_OLD, WGSL_HD + SAMPLE_NEW)
write(GPU, gpu, crlf_gpu)
write(WGSL, wgsl, crlf_wgsl)
with open(root + '/' + HPP, 'w', newline='') as f:
    f.write(HDTEX_HPP)
print("patched (%d edits + shader + hdtex.hpp)" % len(GPU_EDITS))
