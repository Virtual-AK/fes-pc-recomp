"""PC runner key remapping from a text file. Patches host/window.cpp (run ps2run_controls_patch.py first).
The runner reads keys.txt from the folder it is started in (or the file named in the PS2_KEYS environment variable).
Each line is  name = key  and a # starts a comment. Names: up down left right cross circle square triangle l1 r1 l2 r2 l3 r3
start select, and lup ldown lleft lright rup rdown rleft rright for the two sticks. Key names are SDL's: A to Z, 0 to 9,
Up, Down, Left, Right, Return, Backspace, Space, Left Shift, Right Shift, Left Ctrl, Tab, Keypad 1, and so on.
Use "none" to leave a button without a key. Lines you leave out keep the default key.
Example lines:   cross = Z     circle = X     lup = Up
Usage (in the ps2-web-recomp folder): python3 ps2run_keyremap_patch.py [host/window.cpp]
Safe to run twice. Rebuild afterwards (scripts/build_native.sh p3fes, or the build command you normally use)
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'host/window.cpp'
s = open(p).read()
if 'ps2-key-config' in s:
    print("already patched"); raise SystemExit

I_OLD = "#include <cstdlib>\n"
I_NEW = "#include <cctype>\n#include <cstdlib>\n#include <cstring>\n"

T_OLD = "struct PadBinding {\n"
T_NEW = r'''// ps2-key-config: the keys can be changed with a keys.txt file (see docs/controls.md)
struct StickKey {
    SDL_Scancode key;
    int axis;  // 0 left x, 1 left y, 2 right x, 3 right y
    std::uint8_t value;
};

struct KeyName {
    const char *name;
    std::uint16_t button;  // 0 for a stick direction
    int axis;
    std::uint8_t value;
};

const KeyName kKeyNames[] = {
    {"up", kUp, -1, 0},           {"down", kDown, -1, 0},         {"left", kLeft, -1, 0},
    {"right", kRight, -1, 0},     {"cross", kCross, -1, 0},       {"circle", kCircle, -1, 0},
    {"square", kSquare, -1, 0},   {"triangle", kTriangle, -1, 0}, {"l1", kL1, -1, 0},
    {"r1", kR1, -1, 0},           {"l2", kL2, -1, 0},             {"r2", kR2, -1, 0},
    {"l3", kL3, -1, 0},           {"r3", kR3, -1, 0},             {"start", kStart, -1, 0},
    {"select", kSelect, -1, 0},   {"lup", 0, 1, 0x00},            {"ldown", 0, 1, 0xFF},
    {"lleft", 0, 0, 0x00},        {"lright", 0, 0, 0xFF},         {"rup", 0, 3, 0x00},
    {"rdown", 0, 3, 0xFF},        {"rleft", 0, 2, 0x00},          {"rright", 0, 2, 0xFF},
};

std::vector<KeyBinding> g_keys(kKeys, kKeys + sizeof(kKeys) / sizeof(kKeys[0]));
std::vector<StickKey> g_sticks = {
    {SDL_SCANCODE_W, 1, 0x00}, {SDL_SCANCODE_S, 1, 0xFF}, {SDL_SCANCODE_A, 0, 0x00}, {SDL_SCANCODE_D, 0, 0xFF},
    {SDL_SCANCODE_T, 3, 0x00}, {SDL_SCANCODE_G, 3, 0xFF}, {SDL_SCANCODE_F, 2, 0x00}, {SDL_SCANCODE_H, 2, 0xFF},
};

std::string trim_text(std::string t) {
    while (!t.empty() && std::isspace(static_cast<unsigned char>(t.back()))) t.pop_back();
    std::size_t i = 0;
    while (i < t.size() && std::isspace(static_cast<unsigned char>(t[i]))) ++i;
    return t.substr(i);
}

void load_key_file() {
    const char *env = std::getenv("PS2_KEYS");
    const std::string path = env && *env ? env : "keys.txt";
    std::FILE *f = std::fopen(path.c_str(), "r");
    if (!f) return;
    std::fprintf(stderr, "[keys] reading %s\n", path.c_str());
    char line[256];
    int number = 0;
    while (std::fgets(line, sizeof line, f)) {
        ++number;
        std::string text = line;
        const std::size_t hash = text.find('#');
        if (hash != std::string::npos) text.erase(hash);
        const std::size_t eq = text.find('=');
        if (eq == std::string::npos) {
            if (!trim_text(text).empty()) std::fprintf(stderr, "[keys] line %d: expected name = key\n", number);
            continue;
        }
        std::string name = trim_text(text.substr(0, eq));
        const std::string keyText = trim_text(text.substr(eq + 1));
        for (char &c : name) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
        const KeyName *entry = nullptr;
        for (const KeyName &n : kKeyNames)
            if (name == n.name) entry = &n;
        if (!entry) {
            std::fprintf(stderr, "[keys] line %d: unknown name '%s'\n", number, name.c_str());
            continue;
        }
        SDL_Scancode code = SDL_SCANCODE_UNKNOWN;
        std::string lower = keyText;
        for (char &c : lower) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
        if (lower != "none") {
            code = SDL_GetScancodeFromName(keyText.c_str());
            if (code == SDL_SCANCODE_UNKNOWN) {
                std::fprintf(stderr, "[keys] line %d: unknown key '%s'\n", number, keyText.c_str());
                continue;
            }
        }
        if (entry->axis < 0) {
            for (KeyBinding &b : g_keys)
                if (b.button == entry->button) b.key = code;
        } else {
            for (StickKey &st : g_sticks)
                if (st.axis == entry->axis && st.value == entry->value) st.key = code;
        }
    }
    std::fclose(f);
    // a key given to one row is taken away from the others, so one press never does two things
    for (const KeyName &n : kKeyNames) {
        SDL_Scancode key = SDL_SCANCODE_UNKNOWN;
        for (const KeyBinding &b : g_keys)
            if (n.axis < 0 && b.button == n.button) key = b.key;
        for (const StickKey &st : g_sticks)
            if (n.axis >= 0 && st.axis == n.axis && st.value == n.value) key = st.key;
        if (key == SDL_SCANCODE_UNKNOWN) continue;
        int uses = 0;
        for (const KeyBinding &b : g_keys) uses += b.key == key;
        for (const StickKey &st : g_sticks) uses += st.key == key;
        if (uses > 1) std::fprintf(stderr, "[keys] %s is used more than once (%s)\n", SDL_GetScancodeName(key), n.name);
    }
}

struct PadBinding {
'''

P_OLD = """        for (const KeyBinding &b : kKeys)
            if (keys[b.key]) pressed |= b.button;
        if (keys[SDL_SCANCODE_A]) lx = 0x00;
        if (keys[SDL_SCANCODE_D]) lx = 0xFF;
        if (keys[SDL_SCANCODE_W]) ly = 0x00;
        if (keys[SDL_SCANCODE_S]) ly = 0xFF;
        if (keys[SDL_SCANCODE_F]) rx = 0x00;
        if (keys[SDL_SCANCODE_H]) rx = 0xFF;
        if (keys[SDL_SCANCODE_T]) ry = 0x00;
        if (keys[SDL_SCANCODE_G]) ry = 0xFF;
"""
P_NEW = """        static bool keysLoaded = false;
        if (!keysLoaded) {
            keysLoaded = true;
            load_key_file();
        }
        for (const KeyBinding &b : g_keys)
            if (keys[b.key]) pressed |= b.button;
        for (const StickKey &st : g_sticks) {
            if (!keys[st.key]) continue;
            if (st.axis == 0) lx = st.value;
            else if (st.axis == 1) ly = st.value;
            else if (st.axis == 2) rx = st.value;
            else ry = st.value;
        }
"""
for o in [I_OLD, T_OLD, P_OLD]:
    if s.count(o) != 1:
        print("PATCH NOT APPLIED: host/window.cpp does not look like the expected source (run ps2run_controls_patch.py first)")
        raise SystemExit(1)
s = s.replace(I_OLD, I_NEW, 1).replace(T_OLD, T_NEW, 1).replace(P_OLD, P_NEW, 1)
open(p, 'w').write(s)
print("patched (keys.txt remapping for the PC runner)")
