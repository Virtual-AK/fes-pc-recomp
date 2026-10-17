"""Experiment: make PATH3 respect the VIF1 MSKPATH3 command (PS2 Web Recomp runtime).

Before: DMA channel 2 (PATH3) data reached the GS at once, whatever the mask said, so a game that
queues all its texture uploads on channel 2 and lets VIF1 release them between draws had every upload
land before any draw.
After: while PATH3 is masked its data waits in a queue. A mask-off followed by a mask-on (the pulse the
game uses) releases exactly one GIF packet (up to the next end-of-packet tag). Any other GIF data that
arrives after a mask-off (or the next vertical blank) releases everything that waits.
Run in the ps2-web-recomp folder: python3 ps2run_fix_path3_mask.py   (idempotent; refuses unknown source)
The last step ("threaded build") routes PATH3 data, vertical-blank flushes and chain ends through the VU thread's queue so the rule also holds in the window build; the first window run crashed with the EE and VU threads sharing the queue, so the last stage ("VU-thread mask") gives the VU thread its own mask and queue.
With PS2_TRACE_M3=1 it also prints [p3] queued/release lines. When VIF1's chain ends with PATH3 left unmasked, everything still queued is released (the GIF had the rest of the frame to drain it). Running the script again on a tree patched by an older version adds whatever is missing.
"""
import sys, os
d = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src'

def load(rel):
    return open(os.path.join(d, rel)).read()
def save(rel, s):
    open(os.path.join(d, rel), 'w').write(s)
def need(s, old, what):
    if s.count(old) != 1:
        print("PATCH NOT APPLIED:", what); raise SystemExit(1)

gif = load('gs/gif.cpp'); hpp = load('gs/gif.hpp'); sysc = load('system.cpp'); dmac = load('dmac.cpp')
done = []

hdr = 'void transfer(int path, const std::uint8_t *data, std::uint32_t qwc) {\n'
setm = 'void set_path3_masked(bool masked) { g_stat = (g_stat & ~2u) | (masked ? 2u : 0u); }'

if 'g_pend3' not in gif:
    need(gif, hdr, 'gif.cpp transfer()'); need(gif, setm, 'gif.cpp set_path3_masked()')
    need(hpp, 'void set_path3_masked(bool masked);', 'gif.hpp')
    need(sysc, 'void vblank() {\n', 'system.cpp vblank()')
    block = r"""void transfer_direct(int path, const std::uint8_t *data, std::uint32_t qwc);

namespace {
std::vector<std::uint8_t> g_pend3;
bool g_released = false;

// Length in qwords of the GIF packet (tags up to and including the next one with EOP) at the front of the queue.
std::uint32_t packet_qwords(const std::vector<std::uint8_t> &q) {
    const std::uint32_t total = static_cast<std::uint32_t>(q.size() / 16);
    std::uint32_t at = 0;
    while (at < total) {
        std::uint64_t tag;
        std::memcpy(&tag, q.data() + static_cast<std::size_t>(at) * 16, 8);
        const std::uint32_t nloop = static_cast<std::uint32_t>(tag) & 0x7FFFu, flg = static_cast<std::uint32_t>(tag >> 58) & 3u;
        std::uint32_t nreg = static_cast<std::uint32_t>(tag >> 60) & 0xFu;
        if (!nreg) nreg = 16;
        const bool eop = (tag >> 15) & 1u;
        const std::uint32_t body = flg == 0 ? nloop * nreg : flg == 1 ? (nloop * nreg + 1) / 2 : nloop;
        at += 1 + body;
        if (eop) break;
    }
    return std::min(at, total);
}

void release(bool everything) {
    while (!g_pend3.empty()) {
        const std::uint32_t n = everything ? static_cast<std::uint32_t>(g_pend3.size() / 16) : packet_qwords(g_pend3);
        if (!n) break;
        std::vector<std::uint8_t> chunk(g_pend3.begin(), g_pend3.begin() + static_cast<std::size_t>(n) * 16);
        g_pend3.erase(g_pend3.begin(), g_pend3.begin() + static_cast<std::ptrdiff_t>(n) * 16);
        transfer_direct(3, chunk.data(), n);
        if (!everything) break;
    }
}
}

void flush_path3() {
    static int shown = 0;
    if (!g_pend3.empty() && shown++ < 20)
        std::fprintf(stderr, "[path3] %zu qwords still waiting at vblank (masked %u, released %u)\n", g_pend3.size() / 16, (g_stat >> 1) & 1u, g_released ? 1u : 0u);
    if (g_released || !(g_stat & 2u)) {
        release(true);
        g_released = false;
    }
}

void transfer(int path, const std::uint8_t *data, std::uint32_t qwc) {
    if (g_released) {
        release(true);
        g_released = false;
    }
    if (path == 3 && ((g_stat & 2u) || !g_pend3.empty())) {
        g_pend3.insert(g_pend3.end(), data, data + static_cast<std::size_t>(qwc) * 16);
        return;
    }
    transfer_direct(path, data, qwc);
}

"""
    gif = gif.replace(hdr, block + hdr.replace('void transfer(', 'void transfer_direct('))
    gif = gif.replace(setm, """void set_path3_masked(bool masked) {
    if (!masked) {
        if (g_stat & 2u) g_released = true;
        g_stat &= ~2u;
        return;
    }
    if (g_released) {
        release(false);
        g_released = false;
    }
    g_stat |= 2u;
}""")
    if '#include <vector>' not in gif:
        gif = gif.replace('#include <cstring>\n', '#include <cstring>\n#include <vector>\n', 1)
    hpp = hpp.replace('void set_path3_masked(bool masked);', 'void set_path3_masked(bool masked);\n// Release everything still waiting behind the PATH3 mask when it is off (called at vertical blank)\nvoid flush_path3();')
    sysc = sysc.replace('void vblank() {\n', 'void vblank() {\n    gif::flush_path3();\n', 1)
    if '"gs/gif.hpp"' not in sysc and '"gif.hpp"' not in sysc:
        sysc = '#include "gs/gif.hpp"\n' + sysc
    done.append("base fix")

if '[p3] queued' not in gif:
    a = '        transfer_direct(3, chunk.data(), n);\n'
    b = '        g_pend3.insert(g_pend3.end(), data, data + static_cast<std::size_t>(qwc) * 16);\n'
    need(gif, a, 'release()'); need(gif, b, 'transfer()')
    gif = gif.replace(a, '        { static const bool t = std::getenv("PS2_TRACE_M3") != nullptr; if (t) std::fprintf(stderr, "[p3] release %u qwords (%s), %zu left\\n", n, everything ? "all" : "one packet", g_pend3.size() / 16); }\n' + a)
    gif = gif.replace(b, b + '        { static const bool t = std::getenv("PS2_TRACE_M3") != nullptr; if (t) std::fprintf(stderr, "[p3] queued %u qwords, %zu waiting\\n", qwc, g_pend3.size() / 16); }\n')
    done.append("trace lines")

if 'chain_end' not in gif:
    anchor = 'void transfer(int path, const std::uint8_t *data, std::uint32_t qwc) {\n    if (g_released) {'
    need(gif, anchor, 'transfer()')
    gif = gif.replace(anchor, '// The VIF1 chain ended while PATH3 was left unmasked: the GIF had the rest of the frame to drain its queue.\nvoid chain_end() {\n    if (g_released) {\n        release(true);\n        g_released = false;\n    }\n}\n\n' + anchor)
    need(hpp, 'void flush_path3();', 'gif.hpp flush_path3')
    hpp = hpp.replace('void flush_path3();', 'void flush_path3();\n// Called when a VIF1 DMA chain finishes\nvoid chain_end();')
    fin = '    c.chcr &= ~0x100u;\n    hw::dmac_raise(static_cast<unsigned>(ch));'
    need(dmac, fin, 'dmac.cpp finish()')
    dmac = dmac.replace(fin, '    if (ch == 1) gif::chain_end();\n' + fin)
    done.append("chain-end release")

if 'kPath3Flush' not in gif:
    qh = load('gs/queue.hpp')
    need(qh, 'kDownloadAsync };', 'queue.hpp enum')
    qh = qh.replace('kDownloadAsync };', 'kDownloadAsync, kPath3Flush, kPath3ChainEnd };')
    save('gs/queue.hpp', qh)
    # 1. EE-thread PATH3 data goes through the VU ring unchanged, so it stays in order with the VIF1 stream;
    #    the gate runs on the VU thread (vu_path3).
    anchor = 'void transfer(int path, const std::uint8_t *data, std::uint32_t qwc) {\n    if (g_released) {'
    need(gif, anchor, 'transfer() (threaded)')
    gif = gif.replace(anchor, 'void transfer(int path, const std::uint8_t *data, std::uint32_t qwc) {\n    if (path == 3 && gs::queue::vu_active() && gs::queue::role() != gs::queue::Role::Vu) {\n        transfer_direct(path, data, qwc);\n        return;\n    }\n    if (g_released) {')
    # 2. flush and chain-end become messages on the VU thread
    need(gif, 'void flush_path3() {\n', 'flush_path3()')
    gif = gif.replace('void flush_path3() {\n', 'void flush_path3() {\n    if (gs::queue::vu_active() && gs::queue::role() != gs::queue::Role::Vu) {\n        gs::queue::post(gs::queue::kPath3Flush, 0, 0, nullptr, 0);\n        return;\n    }\n', 1)
    need(gif, 'void chain_end() {\n', 'chain_end()')
    gif = gif.replace('void chain_end() {\n', 'void chain_end() {\n    if (gs::queue::vu_active() && gs::queue::role() != gs::queue::Role::Vu) {\n        gs::queue::post(gs::queue::kPath3ChainEnd, 0, 0, nullptr, 0);\n        return;\n    }\n', 1)
    # 3. entry point used by the VU thread for PATH3 data that arrived from the EE thread
    gif = gif.replace('void transfer_direct(int path, const std::uint8_t *data, std::uint32_t qwc) {\n', 'void vu_path3(const std::uint8_t *data, std::uint32_t qwc) { transfer(3, data, qwc); }\n\nvoid transfer_direct(int path, const std::uint8_t *data, std::uint32_t qwc) {\n', 1)
    need(hpp, 'void chain_end();', 'gif.hpp chain_end')
    hpp = hpp.replace('void chain_end();', 'void chain_end();\n// VU thread: PATH3 data posted by the EE thread, passed through the mask rule\nvoid vu_path3(const std::uint8_t *data, std::uint32_t qwc);')
    vu = '            case gs::queue::kVuFence:\n'
    need(sysc, vu, 'system.cpp run_vu_thread')
    sysc = sysc.replace(vu, '            case gs::queue::kGif:\n                if (h.arg0 == 3) gif::vu_path3(payload, h.arg1);\n                else gs::queue::render().post(static_cast<gs::queue::Type>(h.type), h.arg0, h.arg1, payload, h.bytes);\n                break;\n            case gs::queue::kPath3Flush: gif::flush_path3(); break;\n            case gs::queue::kPath3ChainEnd: gif::chain_end(); break;\n' + vu, 1)
    done.append("threaded build")

if 'g_vmask' not in gif:
    # Found in the first window run (17 October 2026): in the threaded build the EE thread also runs VIF1 commands
    # (a shadow copy that keeps the status bit the CPU reads), so MSKPATH3 reached the queue code from both threads and
    # the two raced on the queue (crash in release()). The queue and its mask now belong to the VU thread alone;
    # the EE thread only updates the status bit.
    a = 'bool g_released = false;\n'
    need(gif, a, 'g_released')
    b = '    if (g_released || !(g_stat & 2u)) {\n'
    need(gif, b, 'flush_path3() mask test')
    c = 'if (path == 3 && ((g_stat & 2u) || !g_pend3.empty())) {'
    need(gif, c, 'transfer() mask test')
    e = '(g_stat >> 1) & 1u, g_released ? 1u : 0u);'
    need(gif, e, 'flush_path3() message')
    f = """void set_path3_masked(bool masked) {
    if (!masked) {
        if (g_stat & 2u) g_released = true;
        g_stat &= ~2u;
        return;
    }
    if (g_released) {
        release(false);
        g_released = false;
    }
    g_stat |= 2u;
}"""
    need(gif, f, 'set_path3_masked()')
    gif = gif.replace(a, 'bool g_released = false;\nbool g_vmask = false;  // the VU thread\'s own view of the mask (threaded build)\nbool mask_up() { return gs::queue::vu_active() ? g_vmask : (g_stat & 2u) != 0; }\n', 1)
    gif = gif.replace(b, '    if (g_released || !mask_up()) {\n', 1)
    gif = gif.replace(c, 'if (path == 3 && (mask_up() || !g_pend3.empty())) {', 1)
    gif = gif.replace(e, '(mask_up() ? 1u : 0u), g_released ? 1u : 0u);', 1)
    gif = gif.replace(f, """void set_path3_masked(bool masked) {
    if (gs::queue::vu_active()) {
        if (gs::queue::role() != gs::queue::Role::Vu) {
            g_stat = (g_stat & ~2u) | (masked ? 2u : 0u);  // EE thread: only the status bit the CPU reads
            return;
        }
        if (!masked) {
            if (g_vmask) g_released = true;
            g_vmask = false;
            return;
        }
        if (g_released) {
            release(false);
            g_released = false;
        }
        g_vmask = true;
        return;
    }
    if (!masked) {
        if (g_stat & 2u) g_released = true;
        g_stat &= ~2u;
        return;
    }
    if (g_released) {
        release(false);
        g_released = false;
    }
    g_stat |= 2u;
}""", 1)
    done.append("VU-thread mask")

if not done:
    print("already patched"); raise SystemExit
save('gs/gif.cpp', gif); save('gs/gif.hpp', hpp); save('system.cpp', sysc); save('dmac.cpp', dmac)
print("patched (" + ", ".join(done) + ")")
