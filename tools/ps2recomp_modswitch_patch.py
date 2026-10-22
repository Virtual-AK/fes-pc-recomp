"""Live on/off switches for packed-in mods. Patches recomp/ (the translator) and runtime/src/system.cpp.

What it adds
  * eerecomp --variants FILE --vanilla ELF : FILE is the table written by p3fes_pnach_apply.py --variants. For every code word a mod
    changes, the translator writes BOTH versions of that instruction into the C++ and picks one while the game runs, from the
    number in the PS2_MODS setting (bit k set = mod k on). The original code of a hooked place is kept, so a mod that is off costs
    nothing but one check at the few hooked places.
  * a start-up step (generated file modsw.cpp) that reads PS2_MODS, and writes the data changes of the mods that are on into memory.
Without --variants nothing changes, so the normal build is untouched (it only gets an empty modsw.cpp).

Usage (in the ps2-web-recomp folder): python3 ps2recomp_modswitch_patch.py
Safe to run twice. Rebuild the translator afterwards (scripts/setup.sh), then recompile the game.
"""
import os
import re
import sys

MARK = 'ps2-modswitch'


def rd(p):
    s = open(p, newline='').read()
    return s.replace('\r\n', '\n'), '\r\n' in s


def wr(p, s, crlf):
    open(p, 'w', newline='').write(s.replace('\n', '\r\n') if crlf else s)


def sub(s, old, new, what, count=1):
    if s.count(old) != count:
        print("PATCH NOT APPLIED: %s does not look like the expected source (%s)" % (what, old.strip()[:60]))
        raise SystemExit(1)
    return s.replace(old, new)


def between(s, start, end, new, what):
    i = s.find(start)
    j = s.find(end, i + 1)
    if i < 0 or j < 0:
        print("PATCH NOT APPLIED: %s does not look like the expected source (%s)" % (what, start.strip()[:60]))
        raise SystemExit(1)
    return s[:i] + new + s[j:]


# ---------------------------------------------------------------------------------------------------------------- codegen.hpp
HPP = 'recomp/codegen.hpp'
CPP = 'recomp/codegen.cpp'
MAIN = 'recomp/main.cpp'
SYS = 'runtime/src/system.cpp'

if not all(os.path.exists(p) for p in (HPP, CPP, MAIN, SYS)):
    print("PATCH NOT APPLIED: run this in the ps2-web-recomp folder")
    raise SystemExit(1)

s, crlf = rd(HPP)
if MARK in s:
    print("already patched")
    raise SystemExit
s = sub(s, '#include <cstdint>\n', '#include <cstdint>\n#include <map>\n', HPP)
s = sub(s, '    std::set<std::uint32_t> probes;\n};\n', '''    std::set<std::uint32_t> probes;
    // ps2-modswitch: code words that differ per mod (address -> mask of the mod bits, original word, patched word)
    struct Variant { std::uint32_t mask, orig, patched; };
    std::map<std::uint32_t, Variant> variants;
    // data written into memory at start-up when (PS2_MODS & mask) != 0
    struct DataWrite { std::uint32_t address, size, value, mask; };
    std::vector<DataWrite> data;
};
''', HPP)
wr(HPP, s, crlf)

# ---------------------------------------------------------------------------------------------------------------- codegen.cpp
s, crlf = rd(CPP)
s = sub(s, 'layout_(*t.program, options.unit_bits) {}',
        'layout_(*t.program, options.unit_bits) {\n        if (!t.relocatable) variants_ = options.variants;\n    }', CPP)

s = sub(s, '    Insn at(std::uint32_t a) const { return decode(*image_.word(a), a); }\n', '''    // ps2-modswitch: the word of an address as the variant being written sees it
    Insn at(std::uint32_t a) const {
        std::uint32_t word = *image_.word(a);
        if (!view_.empty()) {
            const auto it = view_.find(a);
            if (it != view_.end()) word = it->second;
        }
        return decode(word, a);
    }

    // every version an instruction can have (the mods-on word first, then the original)
    std::vector<Insn> views_of(std::uint32_t a) const {
        std::vector<Insn> out{decode(*image_.word(a), a)};
        const auto it = variants_.find(a);
        if (it != variants_.end()) out.push_back(decode(it->second.orig, a));
        return out;
    }

    bool group_start(std::uint32_t a) const {
        if (variants_.empty() || !p_.is_code(a)) return false;
        if (variants_.count(a)) return true;
        if (!variants_.count(a + 4)) return false;
        for (const Insn &i : views_of(a))
            if (has_delay_slot(i.op)) return true;
        return false;
    }

    void next_step(std::uint32_t t) {
        if (in_unit(t) && p_.is_code(t)) line("goto " + label(t) + ";");
        else exit_to(t);
    }

    // one instruction (and its delay slot) in several versions, chosen at run time by the PS2_MODS bits
    void emit_group(std::uint32_t a) {
        std::vector<std::pair<std::uint32_t, std::uint32_t>> parts;   // address, mask
        const auto add = [&](std::uint32_t x) {
            const auto it = variants_.find(x);
            if (it != variants_.end()) parts.emplace_back(x, it->second.mask);
        };
        add(a);
        bool slot = false;
        for (const Insn &i : views_of(a)) slot = slot || has_delay_slot(i.op);
        if (slot) add(a + 4);
        std::vector<std::uint32_t> masks;
        for (const auto &[x, m] : parts)
            if (std::find(masks.begin(), masks.end(), m) == masks.end()) masks.push_back(m);
        flush();
        std::string select = "0u";
        for (std::size_t k = 0; k < masks.size(); ++k)
            select += std::format(" | ((ps2_mods & {}u) ? {}u : 0u)", masks[k], 1u << k);
        line("switch (" + select + ") {");
        const std::uint32_t count = 1u << masks.size();
        for (std::uint32_t v = 0; v < count; ++v) line(std::format("case {}u: goto {}_v{};", v, label(a), v));
        line(std::format("default: goto {}_v0;", label(a)));
        line("}");
        for (std::uint32_t v = 0; v < count; ++v) {
            out_ << label(a) << "_v" << v << ":\\n";
            view_.clear();
            for (const auto &[x, m] : parts) {
                const std::size_t k = std::find(masks.begin(), masks.end(), m) - masks.begin();
                const auto &var = variants_.at(x);
                view_[x] = (v >> k) & 1u ? var.patched : var.orig;
            }
            const Insn i = at(a);
            const Flow fl = flow(i.op);
            if (options_.probes.count(a)) line(std::format("probe(c, {});", pc(a)));
            if (fl == Flow::None) {
                simple(i);
                ++pending_;
                flush();
                next_step(a + 4);
            } else if (i.op == Eret) {
                flush();
                line("{ const std::uint32_t t = eret(c); c.pc = t; [[clang::musttail]] return dispatch(c, 0u, depth); }");
            } else if (fl == Flow::Stop) {
                flush();
                line(std::format("stop(c, {}, \\"{}\\"); return;", pc(a), name(i.op)));
            } else {
                const Insn ds = p_.is_code(a + 4) ? at(a + 4) : Insn{a + 4, 0, Invalid};
                control(i, ds);
                if (fl != Flow::Jump && fl != Flow::JumpRegister) next_step(a + 8);
            }
            view_.clear();
        }
    }
''', CPP)

s = between(s, '    void add_required_entries() {', '    void assign_ids() {', '''    void add_required_entries() {
        for (std::uint32_t a = p_.base; a < p_.end; a += 4) {
            if (!p_.is_code(a)) continue;
            for (const Insn &i : views_of(a)) {
                const Flow fl = flow(i.op);
                if ((fl == Flow::Branch || fl == Flow::BranchLikely || fl == Flow::Jump || i.op == Jal) && !dynamic_jump(a)) {
                    const std::uint32_t t = i.branch_target_of();
                    if (p_.is_code(t) && layout_.unit_of(t) != layout_.unit_of(a)) p_.entries.insert(t);
                }
                const std::uint32_t next = a + 4;
                if (layout_.unit_of(next) != layout_.unit_of(a) && p_.is_code(next)) p_.entries.insert(next);
                if (has_delay_slot(i.op) && layout_.unit_of(a + 8) != layout_.unit_of(a) && p_.is_code(a + 8))
                    p_.entries.insert(a + 8);
            }
        }
    }

''', CPP)

s = between(s, '        for (std::uint32_t a = base_; a < end; a += 4) {\n            if (!p_.is_code(a)) continue;\n            const Insn i = at(a);',
            '        out_.str({});', '''        for (std::uint32_t a = base_; a < end; a += 4) {
            if (!p_.is_code(a)) continue;
            for (const Insn &i : views_of(a)) {
                const Flow fl = flow(i.op);
                if ((fl == Flow::Branch || fl == Flow::BranchLikely || fl == Flow::Jump) && !dynamic_jump(a)) {
                    const std::uint32_t t = i.branch_target_of();
                    if (in_unit(t) && p_.is_code(t)) labels_.insert(t);
                }
                if (has_delay_slot(i.op) && labels_.count(a + 4) && in_unit(a + 8)) labels_.insert(a + 8);
            }
            if (group_start(a)) {
                if (in_unit(a + 4)) labels_.insert(a + 4);
                if (in_unit(a + 8)) labels_.insert(a + 8);
            }
        }

''', CPP)

s = sub(s, '''            if (options_.probes.count(a)) line(std::format("probe(c, {});", pc(a)));
            const Insn i = at(a);
            const Flow fl = flow(i.op);
            if (fl == Flow::None) {
                simple(i);
                ++pending_;
                falls = true;''', '''            if (group_start(a)) {
                emit_group(a);
                falls = skip = false;
                continue;
            }
            if (options_.probes.count(a)) line(std::format("probe(c, {});", pc(a)));
            const Insn i = at(a);
            const Flow fl = flow(i.op);
            if (fl == Flow::None) {
                simple(i);
                ++pending_;
                falls = true;''', CPP)

s = sub(s, '    std::uint32_t pending_{};\n    std::ostringstream out_;\n',
        '    std::uint32_t pending_{};\n    std::map<std::uint32_t, CodegenOptions::Variant> variants_;\n    std::map<std::uint32_t, std::uint32_t> view_;\n    std::ostringstream out_;\n', CPP)

s = sub(s, '#include "codegen.hpp"\n\n#include <bit>', '#include "codegen.hpp"\n\n#include <algorithm>\n#include <bit>', CPP)

s = sub(s, '#include \\"ps2/generated.hpp\\"\\n\\nnamespace gen {\\n";', '#include \\"ps2/generated.hpp\\"\\n\\nextern std::uint32_t ps2_mods;\\nextern void (*ps2_apply_mods_hook)(std::uint8_t *);\\nvoid ps2_apply_mods(std::uint8_t *);\\n\\nnamespace gen {\\n";', CPP)

s = sub(s, '    table << "}\\n\\nvoid register_generated_code() { ps2::register_units(gen::kUnits, " << main_units << "u);";', '    table << "}\\n\\nvoid register_generated_code() { ps2_apply_mods_hook = ps2_apply_mods; ps2::register_units(gen::kUnits, " << main_units << "u);";', CPP)
s = sub(s, '    std::printf("%zu units written to %s\\n", written, options.output.c_str());\n', '''    {
        std::ostringstream sw;
        sw << "// " << "''' + MARK + '''" << ": which mods are on, and the data they write at start-up\\n#include <cstdint>\\n#include <cstdlib>\\n#include <cstring>\\n\\n";
        sw << "std::uint32_t ps2_mods = 0;\\n\\nnamespace {\\nstruct DataWrite { std::uint32_t address, size, value, mask; };\\nconst DataWrite kData[] = {\\n";
        for (const auto &d : options.data) sw << std::format("    {{{}, {}u, {}, {}u}},\\n", hex(d.address), d.size, hex(d.value), d.mask);
        sw << "    {0u, 0u, 0u, 0u},\\n};\\n}\\n\\n";
        sw << "void ps2_apply_mods(std::uint8_t *ram) {\\n    const char *text = std::getenv(\\"PS2_MODS\\");\\n";
        sw << "    ps2_mods = text ? static_cast<std::uint32_t>(std::strtoul(text, nullptr, 0)) : 0u;\\n";
        sw << "    for (const DataWrite &d : kData)\\n        if (d.size && (ps2_mods & d.mask)) std::memcpy(ram + (d.address & 0x1FFFFFFFu), &d.value, d.size);\\n}\\n";
        write_if_changed(fs::path(options.output) / "modsw.cpp", sw.str());
    }
    std::printf("%zu units written to %s\\n", written, options.output.c_str());
''', CPP)
wr(CPP, s, crlf)

# ---------------------------------------------------------------------------------------------------------------- main.cpp
s, crlf = rd(MAIN)
s = sub(s, '''int usage() {
    std::fprintf(stderr, "usage: eerecomp <elf> [--entries file] [--modules dir] [--probes file] [--out dir] [--stats]\\n");''', '''struct Variants {
    std::map<std::uint32_t, CodegenOptions::Variant> code;
    std::vector<CodegenOptions::DataWrite> data;
};

// ps2-modswitch: read the table written by p3fes_pnach_apply.py --variants
Variants read_variants(const std::string &path) {
    Variants v;
    std::ifstream file(path);
    if (!file) throw std::runtime_error("cannot open " + path);
    std::string kind;
    while (file >> kind) {
        if (kind == "C") {
            std::string a, m, o, n;
            file >> a >> m >> o >> n;
            v.code[static_cast<std::uint32_t>(std::stoul(a, nullptr, 16))] = {static_cast<std::uint32_t>(std::stoul(m, nullptr, 16)),
                                                                            static_cast<std::uint32_t>(std::stoul(o, nullptr, 16)),
                                                                            static_cast<std::uint32_t>(std::stoul(n, nullptr, 16))};
        } else if (kind == "D") {
            std::string a, s, val, m;
            file >> a >> s >> val >> m;
            v.data.push_back({static_cast<std::uint32_t>(std::stoul(a, nullptr, 16)), static_cast<std::uint32_t>(std::stoul(s)),
                              static_cast<std::uint32_t>(std::stoul(val, nullptr, 16)), static_cast<std::uint32_t>(std::stoul(m, nullptr, 16))});
        } else {
            std::string rest;
            std::getline(file, rest);
        }
    }
    return v;
}

// code found in either version of the game counts as code
Program merge_programs(const Program &a, const Program &b) {
    Program m;
    m.base = std::min(a.base, b.base);
    m.end = std::max(a.end, b.end);
    m.code.assign((m.end - m.base) >> 2, 0);
    for (std::uint32_t pc = m.base; pc < m.end; pc += 4) m.code[(pc - m.base) >> 2] = a.is_code(pc) || b.is_code(pc);
    for (const Program *p : {&a, &b}) {
        m.functions.insert(p->functions.begin(), p->functions.end());
        m.entries.insert(p->entries.begin(), p->entries.end());
        m.rejected.insert(p->rejected.begin(), p->rejected.end());
        m.dynamic.insert(p->dynamic.begin(), p->dynamic.end());
    }
    return m;
}

int usage() {
    std::fprintf(stderr, "usage: eerecomp <elf> [--entries file] [--modules dir] [--probes file] [--out dir] [--stats] [--variants file --vanilla elf]\\n");''', MAIN)
s = sub(s, '    std::string elf_path = argv[1], entries_path, out, probes_path, modules_dir;', '    std::string elf_path = argv[1], entries_path, out, probes_path, modules_dir, variants_path, vanilla_path;', MAIN)
s = sub(s, '        else if (arg == "--modules" && i + 1 < argc) modules_dir = argv[++i];', '''        else if (arg == "--modules" && i + 1 < argc) modules_dir = argv[++i];
        else if (arg == "--variants" && i + 1 < argc) variants_path = argv[++i];
        else if (arg == "--vanilla" && i + 1 < argc) vanilla_path = argv[++i];''', MAIN)
s = sub(s, '''        Program program = analyse(image, entries.main, dynamic_sites(imports));
''', '''        Program program = analyse(image, entries.main, dynamic_sites(imports));
        Variants variants;
        if (!variants_path.empty()) {
            // the translator sees the game with every mod on AND the original game, and keeps the code of both
            variants = read_variants(variants_path);
            if (vanilla_path.empty()) throw std::runtime_error("--variants needs --vanilla (the original program file)");
            const Image vanilla = Image::load(vanilla_path);
            const Program original = analyse(vanilla, entries.main, dynamic_sites(snr2_imports(vanilla)));
            program = merge_programs(program, original);
            // a changed word that is not code in the original game belongs to a code cave: it needs no switch of its own
            for (auto it = variants.code.begin(); it != variants.code.end();)
                it = original.is_code(it->first) ? std::next(it) : variants.code.erase(it);
            std::printf("mod switches: %zu code words with two versions, %zu start-up data writes\\n", variants.code.size(), variants.data.size());
        }
''', MAIN)
s = sub(s, '            CodegenOptions options;\n            options.output = out;\n', '            CodegenOptions options;\n            options.output = out;\n            options.variants = variants.code;\n            options.data = variants.data;\n', MAIN)
wr(MAIN, s, crlf)

# ---------------------------------------------------------------------------------------------------------------- runtime/src/system.cpp
s, crlf = rd(SYS)
s = sub(s, '#include <stdexcept>\n', '''#include <stdexcept>

// ps2-modswitch: the translated game (generated modsw.cpp) sets this; it reads PS2_MODS and writes the start-up data of the mods that are on
void (*ps2_apply_mods_hook)(std::uint8_t *) = nullptr;
''', SYS)
s = sub(s, '''        std::memset(g_ram + vaddr + filesz, 0, memsz - filesz);
    }
    return true;
}
''', '''        std::memset(g_ram + vaddr + filesz, 0, memsz - filesz);
    }
    if (ps2_apply_mods_hook) ps2_apply_mods_hook(g_ram);
    return true;
}
''', SYS)
wr(SYS, s, crlf)
print("patched (%s)" % MARK)
