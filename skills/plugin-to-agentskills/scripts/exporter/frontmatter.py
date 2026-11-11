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
            items = [x for x in buf if x]
            pares = [re.match(r"^([A-Za-z0-9_\-.]+)\s*:\s*(.+)$", x)
                     for x in items if not x.startswith("- ")]
            if items and all(x.startswith("- ") for x in items):
                data[key] = [unquote(x[2:].strip()) for x in items]
            elif items and all(pares):
                data[key] = {m.group(1): unquote(m.group(2).strip())
                             for m in pares}
            else:
                data[key] = [unquote(x[2:].strip()) for x in items
                             if x.startswith("- ")]
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
            buf.append(stripped)
            continue
        if mode == "nested" and stripped.startswith("- ") and cur_indent >= indent:
            buf.append(stripped)
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
    | [-+]?\.(?:inf|Inf|INF) | \.(?:nan|NaN|NAN)
    | y|Y|yes|Yes|YES|n|N|no|No|NO
    | true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF
    | ~|null|Null|NULL
    | [0-9]{4}-[0-9]{1,2}-[0-9]{1,2}(?:[Tt\ ].*)?         # fecha o marca de tiempo
    | =|<<
)$""", re.VERBOSE)


def yaml_escape(v: str) -> str:
    """Serializa un escalar en una sola línea de forma segura.

    Entrecomilla lo que YAML leeria como otra cosa que una cadena: caracteres
    con significado propio, un indicador de lista o de clave al principio, y
    los escalares de tipado implicito.
    """
    v = " ".join(str(v).split())
    if (v == "" or re.search(r'[:#\[\]{}&*!|>%@`"\']', v)
            or v in ("-", "?") or v.startswith(("- ", "? "))
            or _TIPADO_IMPLICITO_RX.match(v)):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return v
