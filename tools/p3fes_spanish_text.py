#!/usr/bin/env python3
"""Spanish battle / boss dialogue lines shortened by hand to fit the room the English line had.

The translation's lines (MSG.TBL, AICALC.TBL) are often longer than the English slots, and the slots cannot grow (the game walks from one
message to the next by the size field). Where the Spanish does not fit, a shorter wording from SHORT_TEXT is used.

Readable form: plain text with the Spanish letters, "\\n" for a line break and {hex} for a control byte kept as it is (for example
{f2030101} is a character name). The game has two sets of accented letters: the battle help lines (jyokyohelp_*) and the dialogue
lines (MSG_*) use different font codes.
"""
import re

HELP_SET = {"á": b"\x81\x84", "é": b"\x81\x8c", "í": b"\x81\x90", "ñ": b"\x81\x94", "ó": b"\x81\x96", "ú": b"\x81\x9c", "¿": b"\x80\xe0"}
DLG_SET = {"á": b"\x82\x04", "é": b"\x82\x0c", "í": b"\x82\x10", "ñ": b"\x82\x14", "ó": b"\x82\x16", "ú": b"\x82\x1c", "¿": b"\x81`"}
INV = {"help": {v: c for c, v in HELP_SET.items()}, "dlg": {v: c for c, v in DLG_SET.items()}}
TAIL = re.compile(rb"\n?(?:\xf2...|\xf1\x04|\xf3....)*$", re.S)


def kind_of(label):
    """"help" for the battle help lines, "dlg" for the dialogue."""
    return "help" if label.startswith(b"jyokyohelp") else "dlg"


def split(en, es):
    """(prefix, suffix): the control bytes before the English text and after it. The prefix is what English and Spanish share at the start,
    cut back to its last control byte; the suffix is the English line's end (a line break and codes), which the Spanish line must share.
    None when the Spanish line does not agree."""
    n = 0
    while n < min(len(en), len(es)) and en[n] == es[n]:
        n += 1
    while n > 0 and 0x20 <= en[n - 1] < 0x80:
        n -= 1
    suf = TAIL.search(en).group(0)
    if not es.endswith(suf) or n + len(suf) > len(en):
        return None
    return en[:n], suf


def decode(b, kind):
    """Readable form of message text bytes."""
    inv = INV[kind]
    out = []
    i = 0
    while i < len(b):
        if b[i:i + 2] in inv:
            out.append(inv[b[i:i + 2]])
            i += 2
        elif b[i] == 0x7f:
            out.append("¡")
            i += 1
        elif b[i] == 0x0a:
            out.append("\n")
            i += 1
        elif 0x20 <= b[i] < 0x7f and b[i] not in b"{}":
            out.append(chr(b[i]))
            i += 1
        else:
            out.append("{%02x}" % b[i])
            i += 1
    return "".join(out)


def encode(t, kind):
    """The game's bytes for a readable text."""
    s = HELP_SET if kind == "help" else DLG_SET
    out = bytearray()
    i = 0
    while i < len(t):
        c = t[i]
        if c == "{":
            j = t.index("}", i)
            out += bytes.fromhex(t[i + 1:j])
            i = j + 1
            continue
        if c in s:
            out += s[c]
        elif c == "¡":
            out += b"\x7f"
        elif c == "\n" or 0x20 <= ord(c) < 0x7f:
            out += c.encode()
        else:
            raise ValueError("character not in the font: %r" % c)
        i += 1
    return bytes(out)


def key_of(en, es, label):
    """(readable English text, prefix, suffix) of a line, or None when the Spanish line does not agree with the English one."""
    r = split(en, es)
    if r is None:
        return None
    pre, suf = r
    return decode(en[len(pre):len(en) - len(suf)], kind_of(label)), pre, suf


def shorter(en, es, label):
    """The hand-shortened Spanish message for the English line en, built on the control bytes of the line; None when there is no
    shortened wording or the control bytes do not agree."""
    k = key_of(en, es, label)
    if k is None:
        return None
    t = SHORT_TEXT.get(k[0])
    if t is None:
        return None
    return k[1] + encode(t, kind_of(label)) + k[2]

# The wordings, one per English line (the key is the English text as the module decodes it). Built from the translation's lines.
SHORT_TEXT = {
    'Cannot proceed.': 'No se puede.',
    'Missed!': '¡Fallo!',
    'Attack dodged!': '¡Esquivado!',
    '{f2}{03}{01}{01} has been charmed!': '¡{f2}{03}{01}{01} está hechizado!',
    "{f2}{03}{01}{01} can't move!": '¡{f2}{03}{01}{01} inmóvil!',
    '{f2}{03}{01}{01} is enraged!': '¡{f2}{03}{01}{01} se enfada!',
    '{f2}{03}{01}{01} has overheated!': '¡{f2}{03}{01}{01} recalentado!',
    'Attack reverted!': '¡Ataque normal!',
    'Hit/Evasion Rate reverted!': '¡Precisión/evasión normal!',
    'Critical Rate reverted!': '¡Prob. crítico normal!',
    '{f2}{03}{01}{01} has recovered!': '¡{f2}{03}{01}{01} se recupera!',
    'Orgia Mode suspended.': '{80}{ee}xtasis suspendido.',
    'Cooled down!': '¡Enfriado!',
    'Insufficient HP!': '¡Faltan PS!',
    'Insufficient SP!': '¡Faltan PE!',
    "Can't concentrate!": '¡No se concentra!',
    'Moonless Gown activated!': '¡Novilunio activo!',
    'Moonless Gown lifted!': '¡Novilunio disipado!',
    'Attack up!': '¡Ataque +!',
    'Hit/Evasion Rate up!': '¡Precis./evas. +!',
    'Defense up!': '¡Defensa +!',
    'Critical Rate up!': '¡Prob. crítico +!',
    'Critical Rate way up!': '¡Prob. crítico ++!',
    'Ailment Susceptibility up!': '¡Más sensible a males!',
    'Fire affinity reverted!': '¡Afin.: fuego normal!',
    'Ice affinity reverted!': '¡Afin.: hielo normal!',
    'Wind affinity reverted!': '¡Afin.: viento normal!',
    'No effect!': '¡Sin efecto!',
    'All enemies knocked down!': '¡Enemigos derribados!',
    'Enemy knocked down!': '¡Enemigo derribado!',
    'Ally knocked down!': '¡Aliado derribado!',
    'Everyone knocked down!': '¡Todos derribados!',
    'Turned into a bomb!': '¡Ahora es una bomba!',
    'Attack down!': '¡Ataque -!',
    'Hit/Evasion Rate down!': '¡Precis./evas. -!',
    'Defense down!': '¡Defensa -!',
    'HP fully restored!': '¡PS al máximo!',
    'SP fully restored!': '¡PE al máximo!',
    'HP/SP fully restored!': '¡PS y PE al máximo!',
    'All ailments cured!': '¡Males curados!',
    'HP reduced to 1!': '¡PS a 1!',
    '{f2}{03}{01}{01} has charged up!': '¡{f2}{03}{01}{01} se carga!',
    '{f2}{03}{01}{01} is focused now!': '¡{f2}{03}{01}{01} se concentra!',
    'Fire resistance nullified!': '¡Resist. al fuego anulada!',
    'Ice resistance nullified!': '¡Resist. al hielo anulada!',
    'Wind resistance nullified!': '¡Resist. al viento anulada!',
    "Enemy's Attack up!": '¡Ataque enemigo +!',
    "Party's Attack up!": '¡Ataque equipo +!',
    "Enemy's Attack down!": '¡Ataque enemigo -!',
    "Party's Attack down!": '¡Ataque equipo -!',
    "Enemy's Defense up!": '¡Defensa enemiga +!',
    "Party's Defense up!": '¡Defensa equipo +!',
    "Enemy's Defense down!": '¡Defensa enemiga -!',
    "Party's Defense down!": '¡Defensa equipo -!',
    'Enemy is in a panic!': '¡Pánico enemigo!',
    'Party is in a panic!': '¡Pánico del equipo!',
    'Enemy is enraged!': '¡Enemigo furioso!',
    'Party is enraged!': '¡Equipo furioso!',
    'Enemy is distressed!': '¡Enemigo agobiado!',
    'Party is distressed!': '¡Equipo agobiado!',
    'Enemy is fear-stricken!': '¡Enemigo aterrado!',
    'Party is fear-stricken!': '¡Equipo aterrado!',
    'Light damage to the enemy!': '¡Daño leve al enemigo!',
    'Light damage to the party!': '¡Daño leve al equipo!',
    'Moderate damage to the enemy!': '¡Daño moderado al enemigo!',
    'Moderate damage to the party!': '¡Daño moderado al equipo!',
    'Heavy damage to the enemy!': '¡Daño grave al enemigo!',
    'Heavy damage to the party!': '¡Daño grave al equipo!',
    'HP restored!': '¡PS curados!',
    'No target available.': 'Sin objetivos.',
    'Already in effect.': 'Ya está activo.',
    'Limit reached.': 'Tope alcanzado.',
    'Not necessary.': 'No hace falta.',
    "Can't be used right now!": '¡No se puede usar ahora!',
    "Frozen! Can't move.": '¡Helado e inmóvil!',
    "Shocked! Can't move.": '¡Paralizado!',
    'No skills for use in battle!': '¡Sin habilidades de combate!',
    'Too panicked to use a skill!': '¡Pánico: sin habilidades!',
    'All items gone!': '¡Sin objetos!',
    'No one to give orders to!': '¡Nadie a quien ordenar!',
    " can't move.": ' inmóvil.',
    'Relent': 'Desistir',
    "Let us strike while\nthe iron's hot!": '¡Ataquemos ahora,\nes el momento!',
    "The enemy's down!\nLet's finish this!": '¡Enemigo caído!\n¡Acabemos ya!',
    "I've been waiting for\nthis!": '¡Esperaba este\nmomento!',
    "Here's our chance!\nLet's do it!": '¡Es nuestra ocasión!\n¡Vamos!',
    'Heavy damage sustained.\nMay I withdraw?': 'Daños graves.\n¿Puedo retirarme?',
    "I'm in no condition to\nfight. Can you handle this?": 'Estoy muy débil para\nluchar. ¿Puedes seguir tú?',
    "I can't hold out much\nlonger. Can you manage?": 'No aguanto más.\n¿Puedes seguir tú?',
    '*whine*\n> Koromaru wants to go...': 'Iiih...\n> Koromaru quiere irse...',
    '"Stay!"': '¡Quieto!',
    '"Alright."': 'De acuerdo.',
    "Why am I sensing two entities...?\nIt doesn't make sense!": '¿Por qué percibo dos\nentidades...? ¡No tiene sentido!',
    "I see now. The vehicle and turret are\ndifferent types: one's Chariot and\nthe other's Justice.": 'Ya entiendo: vehículo y torreta\nson de tipos distintos: uno es\nel Carro y el otro, la Justicia.',
    "That wheel's effects depend on\nwhere it stops.": 'Sus efectos dependen de\ndónde se detenga.',
    'I never imagined that your power\nwould rival ours...': 'Jamás creí que vuestro\npoder nos igualara...',
    'Astonishing... Perhaps I misjudged\nyour strength.': 'Asombroso... ¿Habré subestimado\nvuestra fuerza?',
    'Ugh... So, this is the power of those\nwhose Persona awakened naturally...': 'Agh... Este es el poder de quienes\ndespertaron su Persona\nnaturalmente...',
    'Son of a bitch...!': '¡Maldita sea...!',
    "*gasp* It's using those other\nShadows as bombs!": '¡Ah...! ¡Usa a las otras\nSombras como bombas!',
    "Takaya was right... You're a nuisance!": 'Takaya acertó... ¡Sois\nun estorbo!',
    "Why!? Why won't you leave me alone!?": '¡¿Por qué no me dejáis\nen paz?!',
    "This is it... I ain't holdin' back!": 'Esto es todo... ¡Voy a\nir con todo!',
    "I've improved since our last fight.\nYou can't hide your weaknesses\nfrom me!": 'He mejorado desde la última\nvez. ¡No podréis ocultarme\nvuestras debilidades!',
    'I excel at data analysis.': 'Los datos se me dan bien.',
    "I don't need no Persona to find\nyour weaknesses!": '¡Sin Personas veo\nvuestras debilidades!',
    "Tch, you think you're tough?\nI won't lose this time!": 'Tch, ¿os creéis fuertes?\n¡Esta vez no perderé!',
    'Dammit...!': '¡Rayos...!',
    "You needn't hurry. The moment we await\nis predestined.": 'Sin prisa. El momento que\nesperamos ya está escrito.',
    'I pity those who cannot see it for\nwhat it truly is... a blessing.': 'Me dan pena quienes no ven\nlo que es: una bendición.',
    'We are mere mortals; we cannot\nchange our fate.': 'Somos mortales y no podemos\ncambiar el destino.',
    'Ha... Hahaha... It seems we are\ndestined to be in opposition...': 'Ja... Ja, ja... Parece que\nnuestros destinos chocan...',
    'How can you summon such power...\neven in the face of death...?': '¿Cómo invocáis tal poder...\nincluso ante la muerte...?',
    "Nyx's Arcana changed to the Magician!?": '¡¿Cambia el arcano de Nix\na Mago?!',
    "I sense... Death! Nyx's true Arcana\nis Death!": 'Percibo... ¡la Muerte!\n¡Es el arcano de Nix!',
    'The moment man devoured the fruit\nof knowledge, he sealed his fate...': 'La humanidad selló su destino\nal probar el fruto del\nconocimiento...',
    'Entrusting his future to the cards,\nman clings to a dim hope.': 'y se aferra a una leve esperanza\nal fiar su futuro a las cartas.',
    "Attaining one's dream requires a stern\nwill and unfailing determination.": 'Cumplir un sueño exige\nvoluntad firme y determinación.',
    "Celebrate life's grandeur... its brilliance...\nits magnificence...": 'Celebra la grandeza de la vida,\nsu brillo, su magnificencia...',
    'Only courage in the face of doubt\ncan lead one to the answer...': 'Solo el valor ante la duda\nlleva a la respuesta...',
    'It is indeed a precious gift to\nunderstand the forces that guide\noneself...': 'Entender las fuerzas que nos guían\nes un don muy valioso...',
    'To find the one true path, one must seek\nguidance amidst uncertainty...': 'Para hallar el camino verdadero\nhay que guiarse entre dudas...',
    "It requires great courage to look at\noneself honestly, and forge one's\nown path...": 'Hace falta valor para mirarse\ncon sinceridad y abrir\nsu propio camino...',
    'Alongside time exists fate,\nthe bearer of cruelty.': 'El tiempo trae consigo al\ncruel destino.',
    'Only with strength can one endure\nsuffering and torment.': 'Solo la fortaleza permite\nsoportar el sufrimiento.',
    'Beyond the beaten path lies\nthe absolute end.': 'El camino más trillado\nsolo lleva al final.',
    'What!? Her power is unbelievable!\n...Who IS she!?': '¡¿Qué?! ¡Qué poder!\n¡¿Quién es ella?!',
    'But, the curtain has just risen...\nShow me your best performance!': 'El telón acaba de subir...\n¡Muéstrame tu mejor actuación!',
    'Marvelous... You wield such power.': 'Maravilloso... Tienes mucho poder.',
    'Now, I give you the grand finale!': '¡Ahora, el gran final!',
    "Don't resist, and I won't hurt you...!": '¡No te resistas, no te\nharé daño!',
    "Please... Don't resist...": 'Por favor... No luches...',
    "Why's it using Io...!?": '¡¿Por qué usa a Io?!',
    "Why's it using Isis...!?": '¡¿Por qué usa a Isis?!',
    'No... Artemisia!?': '¡¿Artemisia?!',
    'Hey! Nobody copies my Hermes!!': '¡Eh! ¡Nadie copia a Hermes!',
    'How can he use Kala-Nemi...?': '¿Cómo usa a Kalanemi...?',
    'Hmph... That was nothing.': 'Hmph... No ha sido nada.',
    "Tch... Not bad... But I'm\nnot going down!": 'Tch... No está mal...\n¡Pero no caeré!',
    "All right... it's time to\nget serious!": 'Muy bien... ¡Voy en serio!',
    "I won't give up!": '¡No me rendiré!',
    "Get ready, 'cause here I come!": 'Prepárate, ¡allá voy!',
    "I can't lose... I WILL NOT LOSE!": '¡No puedo perder!\n¡No perderé!',
    "I won't hold back!": '¡No me contendré!',
    'Show me your resolve!': '¡Mostrad temple!',
    'Is the attack getting stronger...!?': '¡¿El ataque se refuerza?!',
    'The enemy is gathering power...!': '¡El enemigo acumula poder!',
    'We must find some way to stop it...': 'Hay que pararlo como\nsea...',
    "It must be guarding this area...\nIt's strong, so be careful!": 'Debe de vigilar la zona...\n¡Es fuerte, ten cuidado!',
    "A guardian... I'm afraid you'll have\nto defeat it to proceed.": 'Un guardián... Me temo que\ntendrás que vencerlo.',
    "Its Arcana is the Empress. It's\na guardian, so it'll be a difficult\nfight!": 'Su arcano es la Emperatriz.\n¡Es un guardián, será\nun combate difícil!',
    "It seems to be protecting this area.\nIt's strong, so don't let your guard\ndown!": 'Parece que protege la zona.\n¡Es muy fuerte, así que\nno bajes la guardia!',
    "It's a strong one; be careful!\nI sense the Emperor Arcana.": 'Es fuerte, ten cuidado.\nPercibo al Emperador.',
    "Its Arcana is the Lovers.\nIt's strong, so be ready!": 'Su arcano: los Enamorados.\n¡Es fuerte, prepárate!',
    'I sense the Strength Arcana.\nThis Shadow is more powerful\nthan most.': 'Percibo el arcano de la Fuerza.\nEsta Sombra es muy fuerte.',
    'I sense the Hermit Arcana...\nThis foe is very powerful!': 'Percibo al Ermitaño...\n¡Este enemigo es fuerte!',
    "This guardian's Arcana is Fortune,\nbut the battle won't be won by luck!": 'El arcano del guardián es la Fortuna,\n¡pero no es cuestión de suerte!',
    "This is an important battle...\nYour opponent's Arcana is Justice.": 'Este combate es importante...\nSu arcano es la Justicia.',
    'The enemy is a Chariot. Ordinary\nShadows pale in comparison!': 'Es un Carro. ¡Las Sombras\nnormales no se le comparan!',
    "Be ready! I sense it's a strong one!": '¡Prepárate! ¡Es de las fuertes!',
    "Its Arcana is the Lovers.\nIt's a strong foe!": 'Su arcano: los Enamorados.\n¡Es fuerte!',
    "This is no ordinary enemy.\nDon't let your guard down!": 'No es un enemigo normal.\n¡No bajes la guardia!',
    "Its Arcana is Strength! This won't\nbe easy!": '¡Su arcano es la Fuerza!\n¡No será fácil!',
    'This Shadow is a formidable foe!\nIts Arcana is Justice.': '¡Esta Sombra es temible!\nSu arcano es la Justicia.',
    "The Hanged Man... That's this\nguardian's Arcana!": 'El Colgado... ¡Es el arcano\nde este guardián!',
}
