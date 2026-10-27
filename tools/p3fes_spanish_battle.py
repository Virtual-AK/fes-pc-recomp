#!/usr/bin/env python3
"""
p3fes_spanish_battle.py - put the Spanish translation's battle text and battle pictures into the ORIGINAL disc's own files,
without changing any file's size or layout.

Why: the translation's own copies of these files are laid out differently (they move things around and match the translated game
program), and using them whole breaks the game (missing portraits, freezes). Here the original file is kept byte for byte except for
exactly the parts that hold Spanish text or Spanish artwork, so everything else keeps working.

What it writes (under OUT/files/BTL.CVM/..., a mod folder the launcher can switch on):
  BATTLE/MSG.TBL                       skill / passive / item names, All-Out Attack prompt, and every battle message that fits
  SND_BENC/PANEL/BP_ALL.BIN            the command wheel's help text and its pictures (Skill, RUSH, SELECTION, 1 MORE, Critical, STATUS ...)
  SND_BENC/PANEL/AGS_BP_ALL.BIN        the same for the two The Answer versions
  SND_BENC/PANEL/AGS2_BP_ALL.BIN
  BATTLE/PANEL/BS_INIT.BIN             the battle HUD pictures: PLAYER ADVANTAGE, the idle RUSH label
  BATTLE/RESULT/BR_*.BIN               the RESULT and level-up screen pictures (STATUS, EXP, LV ...)
and, under OUT/files/DATA.CVM/: the Persona fusion room's result files and OPED/OP_TITLE.BIN (the title screen menu).

Text is replaced where the Spanish line is not longer than the room the English line had (the game stores every line in a fixed slot);
longer lines stay English and are listed in the report. Pictures are replaced one texture at a time, only where the Spanish texture has
exactly the size of the original.

If a "button prompts" mod is given (--prompts FOLDER, the folder that holds BTL/SND_BENC/PANEL/BP_ALL.BIN), the key icons it drew are
drawn again on top of the Spanish pictures, so the keyboard / controller prompts survive.

Usage:
    py p3fes_spanish_battle.py ORIGINAL.iso TRANSLATED.iso OUT_FOLDER [--prompts FOLDER]

Needs p3fes_modmap.py next to it (and numpy + p3fes_prompts.py only when --prompts is used). Standard library otherwise.
"""

import argparse
import os
import re
import struct
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PANEL = "/BTL.CVM/SND_BENC/PANEL/"
VARIANTS = ("BP_ALL.BIN", "AGS_BP_ALL.BIN", "AGS2_BP_ALL.BIN")
MSG_TBL = "/BTL.CVM/BATTLE/MSG.TBL"
# containers whose pictures are replaced (the battle HUD with the Advantage banners and RUSH, the RESULT screens, the level-up screens)
PICTURE_FILES = ("/BTL.CVM/BATTLE/PANEL/BS_INIT.BIN",
                 "/BTL.CVM/BATTLE/RESULT/BR_BASE.BIN", "/BTL.CVM/BATTLE/RESULT/AGS_BR_BASE.BIN", "/BTL.CVM/BATTLE/RESULT/AGS2_BR_BASE.BIN",
                 "/BTL.CVM/BATTLE/RESULT/BR_LEVEL.BIN",
                 "/BTL.CVM/BATTLE/RESULT/BR_LVH.BIN", "/BTL.CVM/BATTLE/RESULT/AGS_BR_LVH.BIN", "/BTL.CVM/BATTLE/RESULT/AGS2_BR_LVH.BIN")

# lines that are too long in Spanish for their English slot, shortened by hand (keys are the English text as stored)
SHORT = {
    b"Member(s) will target\nthe designated enemy.\n": b"Atacar al enemigo\nque designes.\n",
    b"Member(s) will wait\non standby.\x82\x89\n": b"Esperar sin actuar.\n",
    b"Use an item.\n": b"Usar objeto.\n",
    b"Ask Mitsuru to analyze\nthe enemy.\n": b"Que Mitsuru analice\nal enemigo.\n",
    b"Ask Fuuka to analyze\nthe enemy.\n": b"Que F\x81\xb1ka analice\nal enemigo.\n",
    b"Ask Fuuka to use Oracle.\n": b"Que F\x81\xb1ka use\nel Or\x81\x84culo.\n",
}
RELENT = b"Desistir\n"        # the All-Out Attack "Relent" button: the translation's word does not fit its slot

# message (.BMD) files inside containers where the Spanish messages replace the English ones (each file keeps its size)
# (BP_TUTORIAL.BIN, the tutorials, and SHUFFLE/SFL_BASE.BIN, the Shuffle Time messages, work the same way but are not rewritten here:
# Shuffle Time is already Spanish through the translation itself, and the freeze once suspected does not happen.)
MESSAGE_FILES = ("/BTL.CVM/BATTLE/RESULT/BR_LEVEL.BIN",)     # level-up messages, Fuuka's new-ability lines, Persona messages
MESSAGE_ALONE = ("/BTL.CVM/BATTLE/RESULT/BRP_SYSMSG.BMD",)    # a message file that is a disc file of its own
# Spanish messages shortened by hand where the translation's wording does not fit the room the English message had (the Persona
# result screen has no spare bytes). Keys are the message names; {N} and {S} stand for the two name codes the messages use.
NAME_CODE = b"\xf2\x02\x02\x01\xf2\x03\x01\x01\xf2\x02\x01\x01"
SKILL_CODE = b"\xf2\x02\x02\x01\xf2\x03\x02\x01\xf2\x02\x01\x01"
HEAD = b"\xf2\x08\xff\xff\xf1?> "
BMD_SHORT = {
    "BRP_START": [HEAD + b"\x7f{N} sube de nivel!\n\xf1\x04"],
    "BRP_PARAMUP": [HEAD + b"\x7f{N} aumenta en {S}!\n\xf1\x04"],
    "BRP_GETSKILL": [HEAD + b"\x7f{N} aprende {S}!\n\xf1\x04"],
    "BRP_RMSKILL": [HEAD + b"Esta Persona no puede recordar\nm\x81\x84s habilidades. Elige una\npara olvidar.\n\xf1\x04"],
    "BRP_RMSKILL_Q": [HEAD + b"\x80\xe0Olvidar {S}?\n\xf1\x04"],
    "BRP_SKILLSHIFTCANSEL": [HEAD + b"{N} lanza un grito agudo.\n\xf1\x04"],
}
# message files inside a file with the small table "count, then (offset, size) pairs" (the Persona result screen)
BRP_BASE = "/BTL.CVM/BATTLE/RESULT/BRP_BASE.BIN"
AICALC = ("/BTL.CVM/BATTLE/AICALC.TBL", "/BTL.CVM/BATTLE/AICALC_F.TBL")
BRP_IN_PAKS = ("/DATA.CVM/FACILITY/FCL_COMBINE.PAK", "/DATA.CVM/FACILITY/AGS_FCL_COMBINE.PAK")   # the Persona fusion room has a copy
# The Spanish pictures are wider than the English ones (e.g. "SUBIDA DE NIVEL"); the sprite says how much of the picture to show.
# (offset in the sprite, English value, Spanish value) - checked against the original byte before it is changed.
GEOMETRY = {
    "DATA/I_NEW_ALL_STATUS_UPUP02.SPR": ((0x164, 154, 255), (0x264, 154, 255)),
    "DATA/I_LVUP_CURSOR01.SPR": ((0x124, 81, 136),),
}

# a help line in BP_ALL.BIN: [size u32 = text length + 7] f2 08 ff ff f1 3f TEXT 00 (00 padding)
HELP = re.compile(rb"\xf2\x08\xff\xff\xf1\?([^\x00]*)\x00(\x00*)")
# an entry of MSG.TBL: LABEL 00.. 01 00 ff ff [offset u32] [size u32 = text length + 7] f2 08 ff ff f1 3f TEXT 00 (00 padding)
ENTRY = re.compile(rb"([A-Za-z][A-Za-z_0-9]{3,30})\x00*\x01\x00\xff\xff(....)(....)\xf2\x08\xff\xff\xf1\?([^\x00]*)\x00(\x00*)", re.S)
# an entry of AICALC.TBL (boss and enemy dialogue): the same, with another number in the header
ENTRY_AI = re.compile(rb"([A-Za-z][A-Za-z_0-9]{3,30})\x00+\x01\x00.\x00(....)(....)\xf2\x08\xff\xff\xf1\?([^\x00]*)\x00(\x00*)", re.S)
CODES = re.compile(rb"\xf2...|\xf1\x04|\xf3....", re.S)
NAME = re.compile(rb"([ -~\x81-\x9f\xe0-\xef]+)\x00+")
JUNK = re.compile(rb"^(UNUSED|blank|SOBRAS|0x|0D|\W)", re.I)


TITLE_BIN = "/DATA.CVM/OPED/OP_TITLE.BIN"          # the title screen: its menu pictures are one sprite file inside this container
TITLE_SPR = "DATA/AGS_I_TITLE_SPR01.SPR"
STAFF_BINS = (("/DATA.CVM/OPED/ED_SR.BIN", "ED_STAFF.BIN"), ("/DATA.CVM/OPED/ED_SR_F.BIN", "ED_STAFF_F.BIN"))   # the staff roll (The Journey, The Answer)
LOGO_BIN = "/DATA.CVM/OPED/OP_LOGO.BIN"            # the start-up logos (Atlus, CRI/ADX); the Spanish one adds the translators' credits


class ToolError(Exception):
    pass


def _read(iso, entry):
    with open(iso, "rb") as f:
        f.seek(entry[0])
        return f.read(entry[1])


def _patch_entries(out, orig, esp, entry_re, start, report, what):
    """Labelled messages (LABEL, header, offset, size, text in a fixed slot): the Spanish text goes into the original's slot when it fits
    and has the same control codes. out is a bytearray the size of orig. Returns (replaced, too long)."""
    def parse(b):
        r = defaultdict(list)
        for m in entry_re.finditer(b, start):
            r[m.group(1)].append(m)
        return r
    po, ps = parse(orig), parse(esp)
    done = tall = 0
    for lab, lst in po.items():
        sl = ps.get(lab, [])
        for k, m in enumerate(lst):
            if k >= len(sl):
                continue
            t, new = m.group(4), sl[k].group(4)
            if lab.startswith(b"jyokyohelp_SOUKOUGEKI") and t == b"Relent\n":
                new = RELENT
            elif t in SHORT:
                new = SHORT[t]
            if t == new or CODES.findall(t) != CODES.findall(new):
                continue
            slot = len(t) + 1 + len(m.group(5))
            if struct.unpack("<I", m.group(3))[0] != len(t) + 7:
                continue
            if len(new) + 1 > slot:
                import p3fes_spanish_text as ST
                new = ST.shorter(t, new, lab)      # a wording shortened by hand for the English line
                if new is None or len(new) + 1 > slot:
                    tall += 1
                    report.append("%s message too long, stays English: %s %r" % (what, lab.decode(), t))
                    continue
            # the size field stays as it was: the game walks from one message to the next by it (a Spanish message of another
            # length made the All-Out Attack "Attack" label of Yukari blank), and the text itself ends at its own zero byte
            p = m.start(4)
            out[p:p + slot] = new + b"\0" * (slot - len(new))
            done += 1
    return done, tall


# ---------------------------------------------------------------- MSG.TBL
def patch_msg(orig, esp, report):
    """orig / esp: bytes of MSG.TBL. Returns the original with Spanish text put in place (same size)."""
    out = bytearray(orig)
    start = orig.find(b"jyokyohelp_")
    if start < 0 or esp.find(b"jyokyohelp_") != start:
        raise ToolError("MSG.TBL has an unexpected layout")
    # 1. names in fixed-width slots (before the help text): the same offset in both files is the same name
    # (the names end where the message table's header ("MSG1") begins; after it come the message pointers, which must stay as they are)
    end = orig.find(b"MSG1") - 8
    if end < 0 or esp.find(b"MSG1") - 8 != end or end > start:
        raise ToolError("MSG.TBL has an unexpected layout")
    mo = {m.start(): (m.group(1), len(m.group())) for m in NAME.finditer(orig[:end])}
    ms = {m.start(): m.group(1) for m in NAME.finditer(esp[:end])}
    n = long_ = 0
    for a, (t, slot) in sorted(mo.items()):
        new = ms.get(a)
        if new is None or new == t or JUNK.match(new) or JUNK.match(t):
            continue
        if len(new) + 1 > slot:
            long_ += 1
            report.append("MSG.TBL name too long, stays English: %r" % t)
            continue
        out[a:a + slot] = new + b"\0" * (slot - len(new))
        n += 1
    report.append("MSG.TBL: %d names in Spanish, %d too long" % (n, long_))
    # 2. battle messages: the same label (and the same number of times it appears) in both files
    done, tall = _patch_entries(out, orig, esp, ENTRY, start - 100, report, "MSG.TBL")
    report.append("MSG.TBL: %d battle messages in Spanish, %d too long" % (done, tall))
    return bytes(out)


# ---------------------------------------------------------------- BP_ALL.BIN
def _textures(spr):
    """[(offset, size)] of every TMX in a sprite file."""
    import p3fes_tmx as T
    out = []
    for m in re.finditer(b"TMX0", spr):
        o = m.start() - 8
        try:
            w, h, _rgba, info = T.decode_tmx(spr[o:])
        except Exception:
            continue
        out.append((o, info["expected_size"], w, h))
    return out


def _text_pairs(orig, esp):
    """{English line: Spanish line} for the help lines of the wheel (lines in the same order in both files)."""
    mo, ms = list(HELP.finditer(orig)), list(HELP.finditer(esp))
    if len(mo) != len(ms):
        raise ToolError("BP_ALL.BIN: %d help lines against %d" % (len(mo), len(ms)))
    out = {}
    for a, b in zip(mo, ms):
        t = a.group(1)
        if CODES.search(t) or len(t) < 8:
            continue
        out[t] = b.group(1)
    out.update(SHORT)
    return out


def _pictures(out, orig, esp, o_entries, s_entries, prompts, report, name):
    """Puts the Spanish textures into out (a bytearray the size of orig), one texture at a time, only where the size is the same.
    Entries are the sprites (.SPR, several textures) and single textures (.TMX) of a container. Returns how many textures were replaced."""
    sd = {e[0]: e for e in s_entries}
    replaced = 0
    for ename, off, size in o_entries:
        up = ename.upper()
        if not (up.endswith(".SPR") or up.endswith(".TMX")) or ename not in sd:
            continue
        _n, so, ss = sd[ename]
        o_spr, s_spr = orig[off:off + size], esp[so:so + ss]
        ot, st = _textures(o_spr), _textures(s_spr)
        if len(ot) != len(st):
            report.append("%s %s: %d textures against %d, skipped" % (name, ename, len(ot), len(st)))
            continue
        spr = bytearray(o_spr)
        p_spr = prompts[off:off + size] if prompts is not None else None
        for i, ((oo, osz, ow, oh), (so2, ssz, sw, sh)) in enumerate(zip(ot, st)):
            if (osz, ow, oh) != (ssz, sw, sh):
                report.append("%s %s texture %d: size %d against %d, stays English" % (name, ename, i, osz, ssz))
                continue
            if o_spr[oo:oo + osz] == s_spr[so2:so2 + ssz]:
                continue
            new = bytearray(s_spr[so2:so2 + ssz])
            if p_spr is not None and p_spr[oo:oo + osz] != o_spr[oo:oo + osz]:
                new = _restamp(o_spr, p_spr, bytes(new), oo, osz, report, "%s %s texture %d" % (name, ename, i))
            spr[oo:oo + osz] = new
            replaced += 1
        if bytes(spr) != o_spr:
            for goff, old, new in GEOMETRY.get(ename, ()):
                if spr[goff] == old:
                    spr[goff] = new
        if p_spr is not None:      # textures the prompts mod changed that the translation did not touch keep the prompts version
            for oo, osz, _w, _h in ot:
                if p_spr[oo:oo + osz] != o_spr[oo:oo + osz] and spr[oo:oo + osz] == o_spr[oo:oo + osz]:
                    spr[oo:oo + osz] = p_spr[oo:oo + osz]
        out[off:off + size] = spr
    return replaced


def patch_panel(orig, esp, o_entries, s_entries, pairs, report, name, prompts=None):
    """orig / esp: whole BP_ALL files. o_entries / s_entries: [(entry name, offset inside the file, size)]. prompts: the same file after
    the button-prompts mod, or None. Returns new bytes with the size of orig."""
    out = bytearray(orig)
    # help lines
    n = 0
    for m in HELP.finditer(orig):
        t = m.group(1)
        new = pairs.get(t)
        slot = len(t) + 1 + len(m.group(2))
        if new is None or new == t:
            continue
        hdr = struct.unpack("<I", orig[m.start() - 4:m.start()])[0]
        if hdr != len(t) + 7 or len(new) + 1 > slot:
            continue
        out[m.start() - 4:m.start()] = struct.pack("<I", len(new) + 7)
        out[m.start(1):m.start(1) + slot] = new + b"\0" * (slot - len(new))
        n += 1
    report.append("%s: %d help lines in Spanish" % (name, n))
    replaced = _pictures(out, orig, esp, o_entries, s_entries, prompts, report, name)
    report.append("%s: %d pictures in Spanish" % (name, replaced))
    _messages(out, orig, esp, o_entries, s_entries, report, name, only=("BP_MIXMSG0.BMD", "BP_MIXMSG1.BMD"))   # the Persona combination messages
    return bytes(out)


def _restamp(o_spr, p_spr, new, off, size, report, what):
    """The prompts mod redrew some pixels of the original texture; draw those same pixels on the Spanish texture."""
    import numpy as np
    import p3fes_prompts as P
    ot, pt = P.Tex(o_spr, off), P.Tex(p_spr, off)
    holder = bytearray(max(len(o_spr), off + size))
    holder[off:off + size] = new
    st = P.Tex(bytes(holder), off)
    mask = (ot.rgba != pt.rgba).any(axis=2)
    if not mask.any():
        return new
    st.rgba[mask] = pt.rgba[mask]
    st.dirty = True
    report.append("%s: %d pixels of the button prompts redrawn on it" % (what, int(mask.sum())))
    return st.encode()


def patch_title(iso, patched, fo, co, fs, cs, report):
    """OP_TITLE.BIN of the original disc with the title menu sprite (LOAD GAME / NEW GAME / CONFIG, PRESS ANY BUTTON, The Journey / The Answer)
    replaced by the translation's: the sprite is smaller there, it is written at the start of the old one's room and the rest is zero.
    The container keeps its size and layout. -> bytes or None."""
    if TITLE_BIN not in fo or TITLE_BIN not in fs or TITLE_BIN not in co or TITLE_BIN not in cs:
        report.append("OP_TITLE.BIN not found in both discs")
        return None
    oe = [e for e in co[TITLE_BIN] if e[0].upper() == TITLE_SPR]
    se = [e for e in cs[TITLE_BIN] if e[0].upper() == TITLE_SPR]
    if not oe or not se:
        report.append("OP_TITLE.BIN: the title sprite was not found")
        return None
    spr = _read(patched, (se[0][1], se[0][2]))
    if len(spr) > oe[0][2]:
        report.append("OP_TITLE.BIN: the Spanish title sprite is larger than the original, stays English")
        return None
    out = bytearray(_read(iso, fo[TITLE_BIN]))
    a = oe[0][1] - fo[TITLE_BIN][0]
    out[a:a + oe[0][2]] = spr + bytes(oe[0][2] - len(spr))
    report.append("OP_TITLE.BIN: title menu in Spanish")
    return bytes(out)


def patch_logo(iso, patched, fo, co, fs, cs, report):
    """OP_LOGO.BIN of the original disc with the logo pictures the translation changed (the one with the translators' credits) put in.
    Same sizes only, the container keeps its size and layout. -> bytes or None."""
    if LOGO_BIN not in fo or LOGO_BIN not in fs or LOGO_BIN not in co or LOGO_BIN not in cs:
        report.append("OP_LOGO.BIN not found in both discs")
        return None
    sp = {e[0].upper(): e for e in cs[LOGO_BIN]}
    out = bytearray(_read(iso, fo[LOGO_BIN]))
    n = 0
    for name, a0, ln in co[LOGO_BIN]:
        e = sp.get(name.upper())
        if e is None or e[2] != ln:
            continue
        spr = _read(patched, (e[1], e[2]))
        a = a0 - fo[LOGO_BIN][0]
        if bytes(out[a:a + ln]) != spr:
            out[a:a + ln] = spr
            n += 1
    if not n:
        return None
    report.append("OP_LOGO.BIN: %d logo picture(s) with the translation credits" % n)
    return bytes(out)


def patch_staff(iso, fo, co, report):
    """The staff roll containers of the original disc with the job titles in Spanish (p3fes_spanish_staff): only the script inside changes, in
    its own room, so the containers keep their size and layout and the original fonts stay. -> {container path: bytes}."""
    import p3fes_spanish_staff as ST
    res = {}
    for key, name in STAFF_BINS:
        if key not in fo or key not in co:
            report.append("%s not found" % key.split("/")[-1])
            continue
        ent = [e for e in co[key] if e[0].upper() == name]
        if not ent:
            report.append("%s: the staff script was not found" % key.split("/")[-1])
            continue
        out = bytearray(_read(iso, fo[key]))
        a = ent[0][1] - fo[key][0]
        try:
            new = ST.translate(bytes(out[a:a + ent[0][2]]))
        except ValueError as e:
            report.append("%s: %s, stays English" % (key.split("/")[-1], e))
            continue
        if len(new) > ent[0][2]:
            report.append("%s: the Spanish staff script is too long, stays English" % key.split("/")[-1])
            continue
        out[a:a + ent[0][2]] = new + bytes(ent[0][2] - len(new))
        res[key] = bytes(out)
        report.append("%s: job titles in Spanish" % key.split("/")[-1])
    return res


# ---------------------------------------------------------------- everything
# ---------------------------------------------------------------- message (.BMD) files
def fit_bmd(orig, esp, report, name):
    """The original message file with the Spanish messages put in, never longer than the original file.
    Messages are matched by name. When everything in Spanish would be too long, the messages that grew most stay English.
    Returns bytes (the original size, zero padded) or None when nothing changes."""
    import p3fes_text as T
    try:
        fo, fs = T.parse_bmd(orig), T.parse_bmd(esp)
    except Exception as e:
        report.append("%s: cannot read the messages (%s)" % (name, e))
        return None
    sm = {m["name"]: m for m in fs["msgs"] if m["kind"] == "dialog"}
    for nm, lines in BMD_SHORT.items():
        if nm in sm and len(sm[nm]["lines"]) == len(lines):
            sm[nm] = dict(sm[nm], lines=[l.replace(b"{N}", NAME_CODE).replace(b"{S}", SKILL_CODE) for l in lines])
    mo = fo["msgs"]
    fo["regen_reloc"] = True

    def size(m):
        return len(T.build_dialog(m, 0)) + m.get("zpad", 0)

    def build(sel):
        f = dict(fo)
        f["msgs"] = [sm[m["name"]] if i in sel else m for i, m in enumerate(mo)]
        return T.build_bmd(f)[0]

    sel = set()
    for i, m in enumerate(mo):
        if m["kind"] != "dialog" or m["name"] not in sm or sm[m["name"]]["type"] != m["type"]:
            continue
        try:
            build({i})
        except Exception:
            report.append("%s: message %s stays English (cannot be rebuilt)" % (name, m["name"]))
            continue
        sel.add(i)
    english = []
    while sel:
        try:
            data = build(sel)
        except Exception:
            data = None
        if data is not None and len(data) <= len(orig):
            break
        worst = max(sel, key=lambda i: size(sm[mo[i]["name"]]) - size(mo[i]))
        sel.discard(worst)
        english.append(mo[worst]["name"])
    if not sel:
        report.append("%s: no message fits, stays English" % name)
        return None
    for n in sorted(english, key=lambda n: size(sm[n]) - size(mo[[m["name"] for m in mo].index(n)])):    # the dropped ones that still fit
        i = [m["name"] for m in mo].index(n)
        try:
            ok = len(build(sel | {i})) <= len(orig)
        except Exception:
            ok = False
        if ok:
            sel.add(i)
            english.remove(n)
    data = build(sel)
    slack = len(orig) - len(data)
    if slack >= 4:      # keep the file exactly as long as the original: the spare room goes before the pointer table
        fo["endpad"] = fo.get("endpad", 0) + slack - slack % 4
        data = build(sel)
    for n in english:
        report.append("%s: message %s too long, stays English" % (name, n))
    report.append("%s: %d messages in Spanish" % (name, len(sel)))
    return data + b"\0" * (len(orig) - len(data))


def _messages(out, orig, esp, o_entries, s_entries, report, name, only=None):
    """Spanish messages for every .BMD entry of a container (out is a bytearray the size of orig). Returns how many files changed."""
    sd = {e[0]: e for e in s_entries}
    changed = 0
    for ename, off, size in o_entries:
        if not ename.upper().endswith(".BMD") or ename not in sd or (only is not None and ename not in only):
            continue
        _n, so, ss = sd[ename]
        new = fit_bmd(orig[off:off + size], esp[so:so + ss], report, "%s %s" % (name, ename))
        if new is not None and new != orig[off:off + size]:
            out[off:off + size] = new
            changed += 1
    return changed


def patch_aicalc(orig, esp, report, name):
    """AICALC.TBL / AICALC_F.TBL: the enemy AI tables, with the boss and enemy dialogue at the end. Only that dialogue changes."""
    out = bytearray(orig)
    done, tall = _patch_entries(out, orig, esp, ENTRY_AI, 0, report, name)
    report.append("%s: %d dialogue messages in Spanish, %d too long" % (name, done, tall))
    return bytes(out)


def _table_entries(data):
    """[(name, offset, size)] of a file that starts with: u32 first, u32 count, then count (offset, size) pairs."""
    n = struct.unpack_from("<I", data, 4)[0]
    if not 0 < n < 64 or 8 + 8 * n > len(data):
        raise ToolError("unexpected table")
    out = []
    for i in range(n):
        off, size = struct.unpack_from("<II", data, 8 + 8 * i)
        if off + size > len(data):
            raise ToolError("unexpected table")
        kind = data[off + 8:off + 12]
        out.append(("E%d.%s" % (i, "BMD" if kind == b"MSG1" else "SPR" if kind == b"SPR0" else "BIN"), off, size))
    return out


def patch_brp_base(orig, esp, report, name):
    """The Persona result screen file with Spanish messages and pictures; same size, same layout."""
    try:
        o_entries, s_entries = _table_entries(orig), _table_entries(esp)
    except ToolError as e:
        report.append("%s: %s, skipped" % (name, e))
        return orig
    out = bytearray(orig)
    n = _pictures(out, orig, esp, o_entries, s_entries, None, report, name)
    m = _messages(out, orig, esp, o_entries, s_entries, report, name)
    report.append("%s: %d pictures, %d message files in Spanish" % (name, n, m))
    return bytes(out)


def build(iso, patched, out_dir, prompts_dir=None, report=None):
    """Writes the mod files under out_dir/files. Returns the report lines."""
    import p3fes_modmap as M
    report = [] if report is None else report
    fo, co, _ = M.locate(iso)
    fs, cs, _ = M.locate(patched)
    dst = os.path.join(out_dir, "files", "BTL.CVM")
    # MSG.TBL
    if MSG_TBL in fo and MSG_TBL in fs:
        new = patch_msg(_read(iso, fo[MSG_TBL]), _read(patched, fs[MSG_TBL]), report)
        p = os.path.join(dst, "BATTLE", "MSG.TBL")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(new)
    else:
        report.append("MSG.TBL not found")
    # the panels
    pairs = None
    for v in VARIANTS:
        key = (PANEL + v).upper()
        if key not in fo or key not in fs:
            report.append("%s not found in both discs" % v)
            continue
        orig, esp = _read(iso, fo[key]), _read(patched, fs[key])
        base_o, base_s = fo[key][0], fs[key][0]
        o_entries = [(n, a - base_o, s) for n, a, s in co[key]]
        s_entries = [(n, a - base_s, s) for n, a, s in cs[key]]
        if pairs is None:
            pairs = _text_pairs(orig, esp)
        prompts = None
        if prompts_dir:
            pp = os.path.join(prompts_dir, "BTL", "SND_BENC", "PANEL", v)
            if os.path.isfile(pp):
                with open(pp, "rb") as f:
                    prompts = f.read()
                if len(prompts) != len(orig):
                    prompts = None
        new = patch_panel(orig, esp, o_entries, s_entries, pairs, report, v, prompts)
        p = os.path.join(dst, "SND_BENC", "PANEL", v)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(new)
    # the other containers: pictures only
    for key in tuple(PICTURE_FILES) + tuple(k for k in MESSAGE_FILES if k not in PICTURE_FILES):
        if key not in fo or key not in fs or key not in co or key not in cs:
            report.append("%s not found in both discs" % key.split("/")[-1])
            continue
        name = key.split("/")[-1]
        orig, esp = _read(iso, fo[key]), _read(patched, fs[key])
        o_entries = [(n, a - fo[key][0], s) for n, a, s in co[key]]
        s_entries = [(n, a - fs[key][0], s) for n, a, s in cs[key]]
        prompts = None
        if prompts_dir:
            pp = os.path.join(prompts_dir, *key.strip("/").replace(".CVM", "").split("/"))
            if os.path.isfile(pp):
                with open(pp, "rb") as f:
                    prompts = f.read()
                if len(prompts) != len(orig):
                    prompts = None
        out = bytearray(orig)
        n = _pictures(out, orig, esp, o_entries, s_entries, prompts, report, name) if key in PICTURE_FILES else 0
        if key in PICTURE_FILES:
            report.append("%s: %d pictures in Spanish" % (name, n))
        m = _messages(out, orig, esp, o_entries, s_entries, report, name) if key in MESSAGE_FILES else 0
        if n or m:
            p = os.path.join(dst, *key.strip("/").split("/")[1:])
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(out)
    # the enemy AI tables carry the boss and enemy dialogue
    for key in AICALC:
        if key in fo and key in fs:
            orig = _read(iso, fo[key])
            new = patch_aicalc(orig, _read(patched, fs[key]), report, key.split("/")[-1])
            if new != orig:
                p = os.path.join(dst, "BATTLE", key.split("/")[-1])
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as f:
                    f.write(new)
    # the Persona result screen, alone and inside the Persona fusion room's files
    if BRP_BASE in fo and BRP_BASE in fs:
        orig = _read(iso, fo[BRP_BASE])
        new = patch_brp_base(orig, _read(patched, fs[BRP_BASE]), report, "BRP_BASE.BIN")
        if new != orig:
            p = os.path.join(dst, "BATTLE", "RESULT", "BRP_BASE.BIN")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(new)
    for key in BRP_IN_PAKS:
        if key not in fo or key not in fs or key not in co or key not in cs:
            report.append("%s not found in both discs" % key.split("/")[-1])
            continue
        ent = "BATTLE/RESULT/BRP_BASE.BIN"
        oe = [e for e in co[key] if e[0].upper() == ent]
        se = [e for e in cs[key] if e[0].upper() == ent]
        if not oe or not se:
            report.append("%s: no Persona result screen inside" % key.split("/")[-1])
            continue
        pak = bytearray(_read(iso, fo[key]))
        a = oe[0][1] - fo[key][0]
        orig = bytes(pak[a:a + oe[0][2]])
        new = patch_brp_base(orig, _read(patched, (se[0][1], se[0][2])), report, key.split("/")[-1] + " BRP_BASE")
        if new != orig:
            pak[a:a + len(new)] = new
            p = os.path.join(os.path.dirname(dst), "DATA.CVM", *key.strip("/").split("/")[1:])
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(pak)
    # message files that are files of their own
    for key in MESSAGE_ALONE:
        if key not in fo or key not in fs:
            report.append("%s not found in both discs" % key.split("/")[-1])
            continue
        orig = _read(iso, fo[key])
        new = fit_bmd(orig, _read(patched, fs[key]), report, key.split("/")[-1])
        if new is not None and new != orig:
            p = os.path.join(dst, *key.strip("/").split("/")[1:])
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(new)
    # the title screen menu
    new = patch_title(iso, patched, fo, co, fs, cs, report)
    if new is not None:
        p = os.path.join(os.path.dirname(dst), "DATA.CVM", "OPED", "OP_TITLE.BIN")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(new)
    # the staff roll
    for key, data in patch_staff(iso, fo, co, report).items():
        p = os.path.join(os.path.dirname(dst), "DATA.CVM", "OPED", key.split("/")[-1])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
    # the start-up logo screen
    new = patch_logo(iso, patched, fo, co, fs, cs, report)
    if new is not None:
        p = os.path.join(os.path.dirname(dst), "DATA.CVM", "OPED", "OP_LOGO.BIN")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(new)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original")
    ap.add_argument("translated")
    ap.add_argument("out")
    ap.add_argument("--prompts", help="folder holding BTL/SND_BENC/PANEL/BP_ALL.BIN made by the button prompts mod")
    a = ap.parse_args()
    for line in build(a.original, a.translated, a.out, a.prompts):
        print(line)


if __name__ == "__main__":
    main()
