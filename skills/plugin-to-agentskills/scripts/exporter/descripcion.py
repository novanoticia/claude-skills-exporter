"""La description es el unico campo que el destino lee para decidir si carga
la skill, y lo paga en tokens en cada sesion.

Este modulo hace tres cosas en orden: adelanta las frases que dicen CUANDO
cargar la skill, poda los ejemplos entrecomillados sobrantes y recorta al
presupuesto del destino. El orden importa: si hay que cortar, se pierde lo
prescindible y sobrevive el criterio de activacion.
"""

from __future__ import annotations

import re

# Frases que marcan CUÁNDO cargar la skill. Es lo que el destino lee para decidir
# si la activa, así que va delante de todo lo demás.
ACTIVATION_RX = re.compile(
    r"c[áa]rgal[ao]s?\s+cuando|act[íi]val[ao]s?\s+cuando|[úu]sal[ao]s?\s+cuando|"
    r"inv[óo]cal[ao]s?\s+cuando|utiliza(?:l[ao]s?)?\s+cuando|empl[ée]al[ao]s?\s+cuando|"
    r"se\s+activa\s+(?:con|cuando|ante)|se\s+dispara\s+(?:con|cuando)|"
    r"cuando\s+el\s+usuario|si\s+el\s+usuario\s+(?:pide|dice|pregunta)|"
    r"trigger\w*\s+(?:on|when|obligatorio)|"
    r"use\s+(?:this\s+skill\s+)?when|used?\s+when|load\s+(?:this\s+)?when|"
    r"this\s+skill\s+should\s+be\s+used\s+when|apply\s+when|invoke\s+when|"
    r"when\s+the\s+user",
    re.I)

# Abreviaturas tras las que un punto NO cierra frase.
ABBREV = {"etc", "ej", "p", "vs", "aprox", "sr", "sra", "srta", "dr", "dra", "prof",
          "ee", "uu", "cf", "vgr", "i.e", "e.g", "núm", "num", "pág", "pag", "fig"}


def split_sentences(text: str) -> list:
    """Parte en frases sin romper dentro de comillas ni de paréntesis.

    Necesario porque estas descripciones están llenas de disparadores entrecomillados
    del tipo "¿es importante?", cuyo signo no cierra la frase.
    """
    out, buf, paren, quote = [], [], 0, False
    n, i = len(text), 0
    while i < n:
        ch = text[i]
        buf.append(ch)
        i += 1
        if ch == '"':
            quote = not quote
            continue
        if ch in "“«":
            quote = True
            continue
        if ch in "”»":
            quote = False
            continue
        if ch in "([":
            paren += 1
            continue
        if ch in ")]":
            paren = max(0, paren - 1)
            continue
        if ch not in ".!?…" or quote or paren:
            continue
        # ¿Punto de abreviatura o de inicial?
        prev = "".join(buf[:-1]).split()
        word = prev[-1].lower().strip("(«“\"") if prev else ""
        if ch == "." and (word in ABBREV or len(word) == 1):
            continue
        # Arrastra los cierres pegados al signo: ...decisión."»)
        while i < n and text[i] in "\"”»)]":
            buf.append(text[i])
            i += 1
        # Cierra frase sólo si lo siguiente empieza algo nuevo.
        k = i
        while k < n and text[k].isspace():
            k += 1
        if k >= n or text[k].isupper() or text[k] in "¿¡«“":
            out.append("".join(buf).strip())
            buf = []
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return [s for s in out if s]


def reorder_description(desc: str):
    """Pone delante las frases que dicen CUÁNDO cargar la skill.

    Devuelve (texto, se_movio). No inventa nada: si no hay ninguna frase de
    activación reconocible, deja la descripción intacta y el aviso lo dirá.
    """
    sents = split_sentences(desc)
    if len(sents) < 2:
        return desc, False
    act_idx = [i for i, s in enumerate(sents) if ACTIVATION_RX.search(s)]
    if not act_idx:
        return desc, False
    if act_idx == list(range(len(act_idx))):
        return desc, False  # ya están agrupadas al principio
    act = [sents[i] for i in act_idx]
    rest = [s for i, s in enumerate(sents) if i not in set(act_idx)]
    return " ".join(act + rest), True


QUOTED_RX = re.compile(r'[“"«][^”"»\n]{2,60}[”"»]')


def nbytes(s: str) -> int:
    return len(s.encode("utf-8"))


MAX_TRIGGER_EXAMPLES = 4   # más ejemplos no discriminan mejor; sólo alargan la lista


def trim_quoted_examples(sentence: str, budget: int,
                         max_keep: int = MAX_TRIGGER_EXAMPLES, floor_keep: int = 2) -> str:
    """Deja unos pocos disparadores entrecomillados y resume el resto con '…'.

    Una frase de activación suele ser larga por acumulación de ejemplos, no por
    complejidad: con dos o cuatro el destino ya reconoce la intención, y lo que se
    libera se invierte en decir para qué sirve la skill. Así el resultado se lee como
    un párrafo y no como una enumeración.
    """
    quotes = list(QUOTED_RX.finditer(sentence))
    if len(quotes) <= floor_keep:
        return sentence
    if len(quotes) <= max_keep and nbytes(sentence) <= budget:
        return sentence
    tail = sentence[quotes[-1].end():].lstrip(" ,;")
    best = sentence
    for keep in range(min(len(quotes) - 1, max_keep), floor_keep - 1, -1):
        cand = sentence[:quotes[keep - 1].end()] + "… " + tail
        best = cand
        if nbytes(cand) <= budget:
            return cand
    return best


def compact_description(desc: str, budget: int) -> str:
    """Reduce la descripción a `budget` bytes UTF-8 conservando el criterio de activación.

    Devuelve **un solo párrafo**: primero cuándo cargar la skill, después una mención
    breve de para qué sirve. Los ejemplos entrecomillados se podan antes que las frases,
    porque una enumeración larga de disparadores casi sinónimos no discrimina mejor que
    dos o tres y se come el presupuesto que necesita el propósito.
    """
    desc = " ".join(desc.split())          # un párrafo: sin saltos ni viñetas
    if nbytes(desc) <= budget:
        return desc
    sents = split_sentences(desc)
    act = [s for s in sents if ACTIVATION_RX.search(s)]
    if not act:
        return desc                        # sin activación no hay nada que priorizar
    rest = [s for s in sents if not ACTIVATION_RX.search(s)]

    # Se reserva un tercio del presupuesto para el propósito; la activación se poda
    # hasta caber en el resto.
    head = trim_quoted_examples(act[0], int(budget * 0.62))
    out = head
    for s in act[1:]:
        if nbytes(out) + 1 + nbytes(s) <= int(budget * 0.75):
            out += " " + s

    # Mención corta del propósito: se prueba la frase descriptiva más breve primero,
    # para maximizar la probabilidad de que quepa alguna.
    for s in sorted(rest, key=nbytes):
        if nbytes(out) + 1 + nbytes(s) <= budget:
            out += " " + s
            break
    for s in rest:
        if s in out:
            continue
        if nbytes(out) + 1 + nbytes(s) <= budget:
            out += " " + s
    return out


def clamp_description(desc: str, budget: int) -> str:
    """Garantía dura: deja la descripción por debajo de `budget` bytes UTF-8.

    Corta en el último final de frase que quepa; si no hay ninguno razonable, en el
    último espacio. Nunca a mitad de palabra: la descripción es el criterio de
    activación, y una frase partida no lo es.
    """
    if nbytes(desc) <= budget:
        return desc
    cut = desc.encode("utf-8")[:budget - 4].decode("utf-8", errors="ignore")
    while nbytes(cut) > budget - 4:
        cut = cut[:-1]
    floor = int(len(cut) * 0.6)   # no dejar un muñón de una frase suelta
    ends = list(re.finditer(r"[.!?](?=\s|$)", cut))
    if ends and ends[-1].end() >= floor:
        return cut[:ends[-1].end()]
    sp = cut.rfind(" ")
    base = cut[:sp] if sp >= floor else cut
    return base.rstrip(" ,;:—-") + "…"


def tiene_activacion(desc: str) -> bool:
    """¿Dice la descripcion en algun momento CUANDO cargar la skill?

    Si no lo dice, el destino casi nunca la activara. No se puede arreglar
    automaticamente sin inventar criterios que el autor nunca escribio.
    """
    return bool(ACTIVATION_RX.search(desc))
