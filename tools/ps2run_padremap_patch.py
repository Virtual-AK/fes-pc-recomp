"""PC runner controller remapping from the keys file. Patches host/window.cpp (run ps2run_keyremap_patch.py first).
The keys file (keys.txt, or the file named in PS2_KEYS) may now also hold lines  pad.NAME = BUTTON  where NAME is one of
up down left right cross circle square triangle l1 r1 l2 r2 l3 r3 start select, and BUTTON is an SDL controller button name:
a b x y back start leftstick rightstick leftshoulder rightshoulder dpup dpdown dpleft dpright guide misc1 touchpad
(a, b, x, y are the bottom, right, left and top face buttons whatever the controller is called), or lefttrigger / righttrigger
for a trigger, or none. Rows you leave out keep the default (cross = a, circle = b, square = x, triangle = y, l1 = leftshoulder,
r1 = rightshoulder, l2 = lefttrigger, r2 = righttrigger, l3 = leftstick, r3 = rightstick, start = start, select = back, the
D-pad on the D-pad). The sticks are not remappable. A trigger bound to a row presses it with the trigger's pressure.
Example:   pad.cross = b     pad.circle = a
Usage (in the ps2-web-recomp folder): python3 ps2run_padremap_patch.py [host/window.cpp]
Safe to run twice. Rebuild afterwards (scripts/build_native.sh p3fes, or p3fes_win_mod.bat for the Windows PC window).
"""
import sys
p = sys.argv[1] if len(sys.argv) > 1 else 'host/window.cpp'
try:
    s = open(p, newline='').read()
except OSError:
    print("PATCH NOT APPLIED: cannot read " + p); raise SystemExit(1)
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')
if 'ps2-pad-config' in s:
    print("already patched"); raise SystemExit

OLD_TABLE = """struct PadBinding {
    SDL_GameControllerButton button;
    std::uint16_t mask;
};

constexpr PadBinding kPadButtons[] = {
    {SDL_CONTROLLER_BUTTON_A, kCross},          {SDL_CONTROLLER_BUTTON_B, kCircle},
    {SDL_CONTROLLER_BUTTON_X, kSquare},         {SDL_CONTROLLER_BUTTON_Y, kTriangle},
    {SDL_CONTROLLER_BUTTON_LEFTSHOULDER, kL1},  {SDL_CONTROLLER_BUTTON_RIGHTSHOULDER, kR1},
    {SDL_CONTROLLER_BUTTON_LEFTSTICK, kL3},     {SDL_CONTROLLER_BUTTON_RIGHTSTICK, kR3},
    {SDL_CONTROLLER_BUTTON_BACK, kSelect},      {SDL_CONTROLLER_BUTTON_START, kStart},
    {SDL_CONTROLLER_BUTTON_DPAD_UP, kUp},       {SDL_CONTROLLER_BUTTON_DPAD_DOWN, kDown},
    {SDL_CONTROLLER_BUTTON_DPAD_LEFT, kLeft},   {SDL_CONTROLLER_BUTTON_DPAD_RIGHT, kRight},
};

"""
OLD_READ = """        for (const PadBinding &b : kPadButtons)
            if (SDL_GameControllerGetButton(pad, b.button)) pressed |= b.mask;
        const auto trigger = [&](SDL_GameControllerAxis a, std::uint16_t bit, std::uint8_t &pressure) {
            const int v = SDL_GameControllerGetAxis(pad, a);
            if (v <= 2000 || (pressed & bit)) return;
            pressed |= bit;
            pressure = static_cast<std::uint8_t>(std::max(1, v * 255 / 32767));
        };
        trigger(SDL_CONTROLLER_AXIS_TRIGGERLEFT, kL2, l2);
        trigger(SDL_CONTROLLER_AXIS_TRIGGERRIGHT, kR2, r2);
"""
NEW_READ = """        for (const PadBinding &b : g_pad_buttons)
            if (b.button != SDL_CONTROLLER_BUTTON_INVALID && SDL_GameControllerGetButton(pad, b.button)) pressed |= b.mask;
        for (const PadBinding &b : g_pad_buttons) {  // a trigger bound to a row (L2 and R2 by default) presses it with the trigger's pressure
            if (b.axis == SDL_CONTROLLER_AXIS_INVALID) continue;
            const int v = SDL_GameControllerGetAxis(pad, b.axis);
            if (v <= 2000 || (pressed & b.mask)) continue;
            pressed |= b.mask;
            const std::uint8_t pressure = static_cast<std::uint8_t>(std::max(1, v * 255 / 32767));
            if (b.mask == kL2) l2 = pressure;
            else if (b.mask == kR2) r2 = pressure;
        }
"""
NEW_DEFS = r'''// ps2-pad-config: lines "pad.cross = a" in the keys file choose the controller button (or trigger) for a row
struct PadBinding {
    SDL_GameControllerButton button;  // SDL_CONTROLLER_BUTTON_INVALID: no button
    SDL_GameControllerAxis axis;      // SDL_CONTROLLER_AXIS_INVALID: no trigger (only the two triggers are accepted)
    std::uint16_t mask;
};

std::vector<PadBinding> g_pad_buttons = {
    {SDL_CONTROLLER_BUTTON_A, SDL_CONTROLLER_AXIS_INVALID, kCross},          {SDL_CONTROLLER_BUTTON_B, SDL_CONTROLLER_AXIS_INVALID, kCircle},
    {SDL_CONTROLLER_BUTTON_X, SDL_CONTROLLER_AXIS_INVALID, kSquare},         {SDL_CONTROLLER_BUTTON_Y, SDL_CONTROLLER_AXIS_INVALID, kTriangle},
    {SDL_CONTROLLER_BUTTON_LEFTSHOULDER, SDL_CONTROLLER_AXIS_INVALID, kL1},  {SDL_CONTROLLER_BUTTON_RIGHTSHOULDER, SDL_CONTROLLER_AXIS_INVALID, kR1},
    {SDL_CONTROLLER_BUTTON_LEFTSTICK, SDL_CONTROLLER_AXIS_INVALID, kL3},     {SDL_CONTROLLER_BUTTON_RIGHTSTICK, SDL_CONTROLLER_AXIS_INVALID, kR3},
    {SDL_CONTROLLER_BUTTON_BACK, SDL_CONTROLLER_AXIS_INVALID, kSelect},      {SDL_CONTROLLER_BUTTON_START, SDL_CONTROLLER_AXIS_INVALID, kStart},
    {SDL_CONTROLLER_BUTTON_DPAD_UP, SDL_CONTROLLER_AXIS_INVALID, kUp},       {SDL_CONTROLLER_BUTTON_DPAD_DOWN, SDL_CONTROLLER_AXIS_INVALID, kDown},
    {SDL_CONTROLLER_BUTTON_DPAD_LEFT, SDL_CONTROLLER_AXIS_INVALID, kLeft},   {SDL_CONTROLLER_BUTTON_DPAD_RIGHT, SDL_CONTROLLER_AXIS_INVALID, kRight},
    {SDL_CONTROLLER_BUTTON_INVALID, SDL_CONTROLLER_AXIS_TRIGGERLEFT, kL2},   {SDL_CONTROLLER_BUTTON_INVALID, SDL_CONTROLLER_AXIS_TRIGGERRIGHT, kR2},
};

struct PadName {
    const char *name;
    std::uint16_t mask;
};

const PadName kPadNames[] = {
    {"up", kUp},       {"down", kDown},   {"left", kLeft},       {"right", kRight},
    {"cross", kCross}, {"circle", kCircle}, {"square", kSquare}, {"triangle", kTriangle},
    {"l1", kL1},       {"r1", kR1},       {"l2", kL2},           {"r2", kR2},
    {"l3", kL3},       {"r3", kR3},       {"start", kStart},     {"select", kSelect},
};

void pad_line(int number, const std::string &name, const std::string &text) {
    const PadName *row = nullptr;
    for (const PadName &n : kPadNames)
        if (name == n.name) row = &n;
    if (!row) {
        std::fprintf(stderr, "[keys] line %d: unknown pad name '%s'\n", number, name.c_str());
        return;
    }
    std::string lower = text;
    for (char &c : lower) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    SDL_GameControllerButton button = SDL_CONTROLLER_BUTTON_INVALID;
    SDL_GameControllerAxis axis = SDL_CONTROLLER_AXIS_INVALID;
    if (lower != "none") {
        button = SDL_GameControllerGetButtonFromString(lower.c_str());
        if (button == SDL_CONTROLLER_BUTTON_INVALID) {
            axis = SDL_GameControllerGetAxisFromString(lower.c_str());
            if (axis != SDL_CONTROLLER_AXIS_TRIGGERLEFT && axis != SDL_CONTROLLER_AXIS_TRIGGERRIGHT) {
                std::fprintf(stderr, "[keys] line %d: unknown controller button '%s'\n", number, text.c_str());
                return;
            }
        }
    }
    for (PadBinding &b : g_pad_buttons)
        if (b.mask == row->mask) {
            b.button = button;
            b.axis = axis;
        }
}

'''
A_TRIM = "std::string trim_text(std::string t) {\n"
A_ENTRY = "        const KeyName *entry = nullptr;\n"
NEW_ENTRY = """        if (name.compare(0, 4, "pad.") == 0) {
            pad_line(number, name.substr(4), keyText);
            continue;
        }
"""
for what, a in (('the button table', OLD_TABLE), ('the button reading', OLD_READ), ('trim_text', A_TRIM), ('the name lookup', A_ENTRY)):
    if s.count(a) != 1:
        print("PATCH NOT APPLIED: " + what + " not found (apply ps2run_controls_patch.py and ps2run_keyremap_patch.py first)"); raise SystemExit(1)
s = s.replace(OLD_TABLE, '').replace(OLD_READ, NEW_READ).replace(A_TRIM, NEW_DEFS + A_TRIM).replace(A_ENTRY, NEW_ENTRY + A_ENTRY)
open(p, 'w', newline='').write(s.replace('\n', '\r\n') if crlf else s)
print("patched (pad.NAME = BUTTON lines in the keys file)")
