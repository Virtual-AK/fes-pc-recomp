"""VIF UNPACK V2 formats (two values per entry: V2-8, V2-16, V2-32). After this patch the third and fourth lane of such an entry are
written as 0 (the old runtime repeated the first two lanes, which broke the cut-in panels). Switches for comparing: PS2_VIF_V2REPEAT=1
brings the old behaviour back; PS2_VIF_V2KEEP=1 leaves the two lanes as they were in VU1 memory (only the first two lanes are written).
Found while chasing the cut-in panel glitch: the first corner of each panel quad reads colour (467, 368, 467, 368) from entries that a
V2 UNPACK filled this way. Whether the real hardware writes 0 here is what this switch lets us test by comparing frame pictures.
Running it on a tree patched by an earlier version of this script upgrades it (keep switch added, zero fill made the default).
Usage (in the ps2-web-recomp folder): python3 ps2run_vif_v2zero_patch.py [runtime/src/vif.cpp]
Safe to run twice. Rebuild afterwards: ninja -C build/native-p3fes ps2run
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'runtime/src/vif.cpp'
s = open(p).read()
KA = '            if (v2_zero()) {\n                value[2] = value[3] = 0;\n            } else {\n'
KB = '        for (std::uint32_t j = 0; j < 4; ++j) {\n            std::uint32_t m = masked ?'
KC = '            if (m == 3) continue;\n'
KH = 'bool v2_zero() {\n    static const bool z = std::getenv("PS2_VIF_V2ZERO") != nullptr;\n    return z;\n}\n'
ZH_OLD = 'static const bool z = std::getenv("PS2_VIF_V2ZERO") != nullptr;'
ZH_NEW = 'static const bool z = std::getenv("PS2_VIF_V2REPEAT") == nullptr;'
def make_default(s):
    if s.count(ZH_OLD) != 1:
        print("PATCH NOT APPLIED: cannot change the default"); raise SystemExit(1)
    return s.replace(ZH_OLD, ZH_NEW, 1)
def add_keep(s):
    if s.count(KA) != 1 or s.count(KC) != 1 or s.count(KH) != 1:
        print("PATCH NOT APPLIED: cannot add the keep switch"); raise SystemExit(1)
    s = s.replace(KH, KH + 'bool v2_keep() {\n    static const bool k = std::getenv("PS2_VIF_V2KEEP") != nullptr;\n    return k;\n}\n', 1)
    s = s.replace(KA, '            if (v2_keep()) {\n                std::uint32_t old[4];\n                std::memcpy(old, mem + (addr & mask) * 16, 16);\n                value[2] = old[2];\n                value[3] = old[3];\n            } else if (v2_zero()) {\n                value[2] = value[3] = 0;\n            } else {\n', 1)
    s = s.replace(KC, '            if (!fill && components == 2 && j >= 2 && v2_keep()) continue;\n' + KC, 1)
    return s
if 'PS2_VIF_V2ZERO' in s or 'PS2_VIF_V2REPEAT' in s:
    if 'PS2_VIF_V2REPEAT' in s:
        print("already patched"); raise SystemExit
    if 'PS2_VIF_V2KEEP' not in s:
        s = add_keep(s)
    open(p, 'w').write(make_default(s))
    print("patched (zero fill is now the default; PS2_VIF_V2REPEAT=1 restores the old behaviour)"); raise SystemExit
A = '        } else if constexpr (Components == 2) {\n            value[2] = value[0];\n            value[3] = value[1];\n'
B = '                else if (components == 2) { value[2] = value[0]; value[3] = value[1]; }\n'
T = 'template <std::uint32_t Bits, std::uint32_t Components, bool Usn>\nvoid unpack_fast('
if s.count(A) != 1 or s.count(B) != 1 or s.count(T) != 1:
    print("PATCH NOT APPLIED: unpack code not recognised"); raise SystemExit(1)
s = s.replace(T, 'bool v2_zero() {\n    static const bool z = std::getenv("PS2_VIF_V2ZERO") != nullptr;\n    return z;\n}\n\n' + T, 1)
s = s.replace(A, '        } else if constexpr (Components == 2) {\n            if (v2_zero()) {\n                value[2] = value[3] = 0;\n            } else {\n                value[2] = value[0];\n                value[3] = value[1];\n            }\n', 1)
s = s.replace(B, '                else if (components == 2) {\n                    if (v2_zero()) { value[2] = value[3] = 0; }\n                    else { value[2] = value[0]; value[3] = value[1]; }\n                }\n', 1)
s = make_default(add_keep(s))
if '#include <cstdlib>' not in s:
    s = '#include <cstdlib>\n' + s
open(p, 'w').write(s)
print("patched (zero fill is now the default; PS2_VIF_V2REPEAT=1 restores the old behaviour; PS2_VIF_V2KEEP=1 leaves the lanes alone)")
