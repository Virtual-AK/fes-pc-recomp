#!/usr/bin/env python3
"""The staff roll (ED_SR.BIN, ED_SR_F.BIN) in Spanish, on the original disc's own fonts.

The translation's staff roll cannot be used: its two fonts and its longer script do not fit in the room the original container has,
and the container cannot grow. The original fonts only have plain letters (no accents), so the job titles are put in Spanish without
accents and, where needed, abbreviated, and the script keeps the same lines in the same order (so its layout part stays valid) and
the same size. Names stay as they are.

The script (ED_STAFF.BIN / ED_STAFF_F.BIN): 28 byte header (u32 x7: lines, layout offset, layout size, entries, 0x1c, width table size,
layout offset - width table size), a table of character widths, the text lines (each ends with 00, a tab starts an indented line), and
the layout part. Only the text lines change, the layout offset and the last header number follow the new text length.
"""
import struct

# English line (as in the file, tab included) -> Spanish line
ROLES = {
    "art director": "director de arte", "composer": "compositor", "chief planner": "planificador jefe", "scenario writer": "guionista",
    "event planning leader": "lider plan. eventos", "event planner": "plan. eventos",
    "Social Link planning leader": "lider plan. vinculos", "Social Link event planner": "plan. ev. vinculos",
    "Social Link assistant planner": "ayte. plan. vinculos",
    "field planning leader": "lider plan. mundo", "field planner": "plan. mundo",
    "battle planning leader": "lider plan. combates", "battle planner": "plan. combates",
    "chief programmer": "jefe de programacion", "field program leader": "lider prog. mundo", "field sub programmer": "2o prog. mundo",
    "battle program leader": "lider prog. combates", "battle sub programmer": "2o prog. combates",
    "event programmer": "prog. eventos", "facility programmer": "prog. tiendas", "interface sub programmer": "2o prog. interfaz",
    "chief designer": "jefe de dis.", "event design leader": "lider dis. eventos", "event designer": "dis. eventos",
    "3D character design leader": "lider dis. pers. 3D", "3D character designer": "dis. pers. 3D",
    "field design leader": "lider dis. mundo", "field designer": "dis. mundo",
    "battle design leader": "lider dis. combates", "battle designer": "dis. combates",
    "interface design leader": "lider dis. interfaz", "interface designer": "dis. interfaz",
    "original demon design": "dis. orig. demonios", "character design cooperation": "colab. dis. personajes",
    "enemy design cooperation": "colab. dis. enemigos", "animation": "animacion",
    "\tproducer": "\tproductor", "\tdirector & illustration supervisor": "\tdirector y sup. ilustracion",
    "\tillustration assistance leader": "\tlider ayte. ilustracion", "\tcolor coordinator & special effects": "\tcolor y efectos especiales",
    "\tanimation check": "\trevision anim.", "\tanimation art direction": "\tdir. arte animado",
    "\tphotography supervisor": "\tsup. fotografia", "\t3D CG effects": "\tefectos CG 3D", "\tsupervisor": "\tsupervisor",
    "\trecording supervisor": "\tsup. grabacion", "casting cooperation": "colaboracion de casting", "world art establisher": "arte conceptual del mundo",
    "\tart color image board": "\tcolor de arte", "sound designer": "dis. de sonido", "sound design assistant": "ayte. dis. sonido",
    "animation sound editor": "ed. sonido anim.", "singer": "cantante", "lyrics": "letra", "MC": "MC", "theme song": "tema principal",
    "\tcomposer": "\tcompositor", "\tlyrics": "\tletra", "\tsinger": "\tcantante",
    "project support engineer": "ingeniero de soporte", "special thanks": "agradecimientos", "US localization": "localizacion EE.UU.",
    "executive producer": "productor ejecutivo", "director of production": "director de produccion", "VP sales & marketing": "VP ventas y mkt.",
    "project lead": "lider de proyecto", "project coordinator": "coordinador de proyecto", "creative designer": "dis. creativo",
    "translator": "traductor", "editor": "editor", "assistant editor": "ayte. edicion", "quality assurance": "control de calidad",
    "\tQA lead": "\tjefe CC", "\ttester": "\ttester", "voice recording": "grabacion voces", "\tproject coordinator": "\tcoordinador de proyecto",
    "\tlocalization chief programmer": "\tjefe prog. local.", "\tlocalization sub programmer": "\t2o prog. local.",
    "\tlocalization design": "\tdis. localiz.", "general manager": "director general", "producer": "productor",
    "presented by ATLUS": "presentado por ATLUS", "\tdirector,": "\tdirector,", "\tillustration supervisor & editor": "\tsup. ilustr. y edit.",
    "\tkey illustrator": "\tilustr. jefe", "\tillustrators": "\tilustradores", "\tcolor coordinates & special effects": "\tcolor y efectos especiales",
    "\tcoloring": "\tcolores", "\tanimation art": "\tarte animado", "\tphotography": "\tfotografia", "voice editor": "ed. de voces",
    "assistant voice editor": "ayte. ed. voces", "art work": "arte", "\tQA manager": "\tdir. CC",
}


def translate(script):
    """The script (bytes of ED_STAFF.BIN or ED_STAFF_F.BIN) with the job titles in Spanish; the same length or shorter (the caller pads).
    Raises ValueError when the file is not laid out as expected."""
    h = list(struct.unpack_from("<7I", script, 0))
    if h[4] != 0x1c or h[6] != h[1] - h[5] or h[1] > len(script):
        raise ValueError("unexpected staff roll script")
    t0 = h[4] + h[5]
    recs = script[t0:h[1]].split(b"\x00")
    out = []
    for r in recs:
        s = r.decode("latin1")
        out.append(ROLES.get(s, s).encode("latin1"))
    text = b"\x00".join(out)
    h[1] = t0 + len(text)
    h[6] = h[1] - h[5]
    layout = script[struct.unpack_from("<I", script, 4)[0]:]
    return struct.pack("<7I", *h) + script[28:t0] + text + layout
