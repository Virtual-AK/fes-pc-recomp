"""Fifth trace step: PS2_TRACE_M3=1 prints a line for every VIF1 MSKPATH3 command ("[m3] mask=0|1") and for
every GIF transfer ("[gifx] path=N qwc=Q"). Combine with PS2_TRACE_TEX and PS2_TRACE_DMA to see how the
game interleaves its texture uploads (PATH3) and draws. Numbers only.
Usage: python3 ps2run_trace_patch5.py [runtime/src] (the runtime source folder; default runtime/src)
"""
import sys, os
d = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src'
def patch(rel, old, new, marker):
    p = os.path.join(d, rel)
    s = open(p).read()
    if marker in s:
        print(rel, "already patched"); return
    if s.count(old) != 1:
        print("PATCH NOT APPLIED:", rel, old.strip()[:60]); raise SystemExit(1)
    open(p, 'w').write(s.replace(old, new))
    print(rel, "patched")
patch('vif.cpp', '    case 0x06: gif::set_path3_masked((imm >> 15) & 1u); break;',
      '    case 0x06:\n        { static const bool t = std::getenv("PS2_TRACE_M3") != nullptr; if (t) std::fprintf(stderr, "[m3] mask=%u\\n", (imm >> 15) & 1u); }\n        gif::set_path3_masked((imm >> 15) & 1u);\n        break;',
      'PS2_TRACE_M3')
patch('gs/gif.cpp', 'void transfer(int path, const std::uint8_t *data, std::uint32_t qwc) {\n',
      'void transfer(int path, const std::uint8_t *data, std::uint32_t qwc) {\n    { static const bool t = std::getenv("PS2_TRACE_M3") != nullptr; if (t) std::fprintf(stderr, "[gifx] path=%d qwc=%u\\n", path, qwc); }\n',
      'PS2_TRACE_M3')
