"""Memory pokes at start-up for the PC window of PS2 Web Recomp (file mods that need a bigger file than the disc slot).

The game keeps its own table of the files it loads (size, start sector, name), so a mod file that is larger than the original,
and therefore sits somewhere else on the disc, is still read from the old place with the old size. The launcher works out the
new values and passes them in the environment variable PS2_POKE as  ADDRESS=VALUE,ADDRESS=VALUE  (hex numbers, one 32-bit word
each). The runner writes them into memory right after the game program is loaded. Nothing happens when the variable is not set.

Run in the ps2-web-recomp folder:  python3 ps2run_poke_patch.py [folder]
(patches runtime/src/system.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'
REL = 'runtime/src/system.cpp'

OLD = ('        std::memcpy(g_ram + vaddr, data.data() + offset, filesz);\n'
       '        std::memset(g_ram + vaddr + filesz, 0, memsz - filesz);\n'
       '    }\n')
NEW = ('        std::memcpy(g_ram + vaddr, data.data() + offset, filesz);\n'
       '        std::memset(g_ram + vaddr + filesz, 0, memsz - filesz);\n'
       '    }\n'
       '    // ps2run_poke_patch.py: PS2_POKE=ADDR=VALUE,ADDR=VALUE (hex words) written after the program is loaded\n'
       '    if (const char *pk = std::getenv("PS2_POKE")) {\n'
       '        std::string s(pk);\n'
       '        std::size_t at = 0;\n'
       '        while (at < s.size()) {\n'
       '            std::size_t end = s.find(\',\', at);\n'
       '            if (end == std::string::npos) end = s.size();\n'
       '            const std::string item = s.substr(at, end - at);\n'
       '            const std::size_t eq = item.find(\'=\');\n'
       '            if (eq != std::string::npos) {\n'
       '                const std::uint32_t a = physical(static_cast<std::uint32_t>(std::strtoul(item.substr(0, eq).c_str(), nullptr, 16)));\n'
       '                const std::uint32_t v = static_cast<std::uint32_t>(std::strtoul(item.substr(eq + 1).c_str(), nullptr, 16));\n'
       '                if (a + 4 <= kRamSize) std::memcpy(g_ram + a, &v, 4);\n'
       '                std::fprintf(stderr, "[poke] %08X = %08X\\n", a, v);\n'
       '            }\n'
       '            at = end + 1;\n'
       '        }\n'
       '    }\n')

try:
    with open(root + '/' + REL, newline='') as f:
        t = f.read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + REL)
    raise SystemExit(1)
crlf = '\r\n' in t
t = t.replace('\r\n', '\n')
if '// ps2run_poke_patch.py: PS2_POKE' in t:
    print("already patched")
    raise SystemExit
if t.count(OLD) != 1:
    print("PATCH NOT APPLIED: " + REL + " does not look like the expected source")
    raise SystemExit(1)
t = t.replace(OLD, NEW)
if '#include <cstdlib>' not in t:
    t = '#include <cstdlib>\n' + t
with open(root + '/' + REL, 'w', newline='') as f:
    f.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (1 edits)")
