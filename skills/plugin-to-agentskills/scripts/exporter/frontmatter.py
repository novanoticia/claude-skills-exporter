"""Parseo y serializacion del frontmatter YAML minimo de un SKILL.md.

Parser de nivel superior, sin PyYAML: soporta `clave: valor`, escalares en
bloque (| >), listas y mapas anidados de un nivel. No pretende cubrir YAML
entero, sino exactamente lo que aparece en un SKILL.md real.
"""

from __future__ import annotations

import re


def split_frontmatter(text: str):
    """Devuelve (dict_frontmatter, texto_frontmatter_bruto, cuerpo)."""
    if not text.startswith("---"):
        return {}, "", text
    lines = text.splitlines(keepends=True)
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return {}, "", text
    raw = "".join(lines[1:end])
    body = "".join(lines[end + 1:])
    return parse_simple_yaml(raw), raw, body


def parse_simple_yaml(raw: str) -> dict:
    """Parser de nivel superior: clave: valor, escalares en bloque (| >) y listas."""
    data, key, buf, mode, indent = {}, None, [], None, 0

    def flush():
        nonlocal key, buf, mode
        if key is None:
            return
        if mode == "block":
            data[key] = "\n".join(buf).strip()
        elif mode == "nested":
            # Una clave sin valor puede abrir una lista (`- item`) o un mapa
            # (`clave: valor`). Se decide aquí, con las líneas ya recogidas:
            # antes se asumía lista siempre y un `metadata:` con claves dentro
            # se perdía entero, que es justo donde la spec manda guardar los
            # datos propios del autor.
            items = [x for _, x in buf if x]
            if items and items[0].startswith("- "):
                data[key] = [unquote(x[2:].strip()) for x in items
                             if x.startswith("- ")]
            else:
                data[key] = _mapa_anidado(buf)
        key, buf, mode = None, [], None

    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            if mode == "block":
                buf.append("")
            continue
        stripped = line.strip()
        cur_indent = len(line) - len(line.lstrip())

        if mode in ("block", "nested") and cur_indent > indent:
            # En modo `nested` se guarda la línea CRUDA: aún no se sabe si el
            # bloque es una lista o un mapa, y flush() necesita el prefijo.
            # En `nested` va con su sangria: un `- item` cuelga de la subclave
            # anterior, no del mapa.
            buf.append((cur_indent, stripped) if mode == "nested" else stripped)
            continue
        if mode == "nested" and stripped.startswith("- ") and cur_indent >= indent:
            buf.append((cur_indent, stripped))
            continue
        flush()

        m = re.match(r"^([A-Za-z0-9_\-.]+)\s*:\s*(.*)$", stripped)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        indent = cur_indent
        if v in ("|", "|-", ">", ">-", "|+", ">+"):
            key, mode, buf = k, "block", []
        elif v == "":
            key, mode, buf = k, "nested", []
        else:
            data[k] = unquote(v)
    flush()
    return data


def _mapa_anidado(lineas) -> dict:
    """Mapa de un nivel bajo una clave sin valor, con listas por subclave.

    `lineas` son pares (sangria, texto). Una subclave sin valor recoge los
    `- item` que la siguen: `metadata:` / `deps:` / `- a` da
    {"deps": ["a"]}. Antes esa lista convertia el mapa entero en lista y las
    claves hermanas se perdian. Lo que no encaja (mapas mas hondos) se ignora,
    como el resto del subconjunto.
    """
    mapa, abierta, base = {}, None, None
    for sangria, texto in lineas:
        if texto.startswith("- "):
            if abierta is not None:
                if not isinstance(mapa[abierta], list):
                    mapa[abierta] = []
                mapa[abierta].append(unquote(texto[2:].strip()))
            continue
        if base is None:
            base = sangria
        if sangria > base:
            continue
        m = re.match(r"^([A-Za-z0-9_\-.]+)\s*:\s*(.*)$", texto)
        if not m:
            abierta = None
            continue
        valor = m.group(2).strip()
        if valor:
            mapa[m.group(1)] = unquote(valor)
            abierta = None
        else:
            mapa[m.group(1)] = ""
            abierta = m.group(1)
    return mapa


# Escapes de una cadena YAML entre comillas dobles que este subconjunto
# decodifica. Cualquier otro se deja como esta: no se reinterpreta lo que no
# se soporta.
_ESCAPES_DOBLES = {"\\": "\\", '"': '"', "/": "/", "n": "\n", "t": "\t", "r": "\r"}
_ESCAPE_RX = re.compile(r'\\(["\\/ntr])')


def unquote(v: str) -> str:
    """Quita las comillas de un escalar Y decodifica sus escapes.

    Antes solo quitaba los delimitadores. Una descripcion `"dice \\"hola\\""`
    se quedaba con las barras dentro, y `yaml_escape` las volvia a escapar al
    exportar: cada pasada anadia barras y el valor leido dejaba de ser el del
    autor.

    Las dos formas se decodifican como manda YAML: entre comillas simples lo
    unico especial es la comilla doblada; entre comillas dobles, la barra
    invertida. Un escalar sin comillas no se toca.
    """
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        interior = v[1:-1]
        if v[0] == "'":
            return interior.replace("''", "'")
        return _ESCAPE_RX.sub(lambda m: _ESCAPES_DOBLES[m.group(1)], interior)
    return v


# Escalares que un lector YAML NO leeria como cadena si van sin comillas:
# numeros, booleanos, nulos y fechas. El estandar Agent Skills pide cadenas
# en `name`, `description` y en los valores de `metadata`, asi que un
# `name: 123` o un `version: 4.1` cambia de tipo al llegar al destino.
# Se cubren las formas de YAML 1.1 y 1.2, porque no se sabe con cual lee
# cada plataforma.
_TIPADO_IMPLICITO_RX = re.compile(r"""^(?:
      [-+]?[0-9][0-9_]*                                   # entero, tambien 017
    | [-+]?0[xXoObB][0-9a-fA-F_]+                         # hex, octal, binario
    | [-+]?(?:\.[0-9]+|[0-9][0-9_]*(?:\.[0-9_]*)?)(?:[eE][-+]?[0-9]+)?   # decimal
    | [-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+(?:\.[0-9_]*)?     # sexagesimal (YAML 1.1): 1:30 es 90
    | [-+]?\.(?:inf|Inf|INF) | \.(?:nan|NaN|NAN)
    | y|Y|yes|Yes|YES|n|N|no|No|NO
    | true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF
    | ~|null|Null|NULL
    | [0-9]{4}-[0-9]{1,2}-[0-9]{1,2}(?:[Tt\ ].*)?         # fecha o marca de tiempo
    | =|<<
)$""", re.VERBOSE)


# Caracteres que YAML no deja abrir un escalar plano. En mitad del texto no
# significan nada: `dice "hola"` o `v1.2 [beta]` son cadenas planas validas.
_INDICADORES_INICIALES = frozenset("[]{},#&*!|>'\"%@`?:")


def _necesita_comillas(v: str) -> bool:
    return bool(v == "" or v[0] in _INDICADORES_INICIALES
                or v == "-" or v.startswith("- ")
                or ": " in v or " #" in v or v.endswith(":")
                or _TIPADO_IMPLICITO_RX.match(v))


def yaml_escape(v: str) -> str:
    """Serializa un escalar en una sola linea de forma segura.

    Entrecomilla SOLO lo que YAML exige: un indicador al principio, `: ` o
    ` #` dentro, un `:` final y los escalares de tipado implicito. Antes se
    entrecomillaba cualquier valor con una comilla o un corchete en mitad del
    texto, con las comillas interiores escapadas con barra; ChatGPT web no
    decodifica esos escapes y mostraba las barras (observado el 2026-11-17).

    Cuando hay que entrecomillar un valor con `"` o `\\`, se usan comillas
    simples, que no tienen escapes con barra: la comilla simple se dobla.
    """
    v = " ".join(str(v).split())
    if not _necesita_comillas(v):
        return v
    if '"' in v or "\\" in v:
        return "'" + v.replace("'", "''") + "'"
    return '"' + v + '"'
