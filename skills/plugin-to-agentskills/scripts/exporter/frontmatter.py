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


def unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def yaml_escape(v: str) -> str:
    """Serializa un escalar en una sola línea de forma segura."""
    v = " ".join(str(v).split())
    if re.search(r'[:#\[\]{}&*!|>%@`"\']', v) or v == "":
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return v
