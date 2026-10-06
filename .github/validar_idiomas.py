#!/usr/bin/env python3
"""Valida los catalogos de idioma de exporter/i18n/.

Un catalogo distinto de `es` es valido si tiene las mismas claves y los
mismos marcadores que `es.json`, mas la traduccion completa de cada regla de
seguridad y de cada peligro de los perfiles de destino. Asi un idioma
incompleto rompe el CI en vez de degradar en silencio al usuario.

`es.json` NO lleva claves `regla.*` ni `peligro.*`: el espanol de reglas y
peligros vive en reglas.json y en targets/*.json, y duplicarlo aqui lo haria
divergir.

Solo biblioteca estandar: no necesita jsonschema.
"""

import json
import string
import sys
from pathlib import Path

I18N = Path("skills/plugin-to-agentskills/scripts/exporter/i18n")
TARGETS = Path("skills/plugin-to-agentskills/scripts/exporter/targets")
REGLAS = Path("skills/plugin-to-agentskills/scripts/exporter/seguridad/reglas.json")
CAMPOS = ("titulo", "detalle", "mitigacion")


def _marcadores(plantilla: str) -> set:
    return {campo for _, campo, _, _ in string.Formatter().parse(plantilla) if campo}


def _marcadores_invalidos(plantilla: str) -> list:
    """Campos que str.format(**datos) no sabe resolver: sin nombre o no identificador.

    `{}` y `{0}` se descartan al comparar conjuntos de marcadores, pero en
    ejecucion lanzan IndexError; `{a.b}` y `{a[0]}` acceden a atributos de un
    dato. Solo se admiten campos con nombre de identificador.
    """
    return sorted({campo for _, campo, _, _ in string.Formatter().parse(plantilla)
                   if campo is not None and not campo.isidentifier()})


def _leer(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


def _claves_de_reglas_y_peligros(raiz: Path) -> set:
    esperadas = set()
    for r in _leer(raiz / REGLAS)["reglas"]:
        esperadas |= {"regla.{}.{}".format(r["id"], c) for c in CAMPOS}
    for ruta in sorted((raiz / TARGETS).glob("*.json")):
        if ruta.name.startswith("_"):
            continue
        for p in _leer(ruta).get("peligros", []):
            esperadas |= {"peligro.{}.{}".format(p["id"], c) for c in CAMPOS}
    return esperadas


def comprobar(raiz: Path) -> list:
    """Devuelve la lista de errores; vacia si todos los catalogos son validos."""
    errores = []
    catalogos = {}
    for ruta in sorted((raiz / I18N).glob("*.json")):
        try:
            catalogos[ruta.stem] = _leer(ruta)
        except ValueError as e:
            errores.append("{}: JSON inválido ({})".format(ruta.name, e))
    if "es" not in catalogos:
        return errores + ["falta es.json, el catálogo de referencia"]

    extra = _claves_de_reglas_y_peligros(raiz)
    base = {k: v for k, v in catalogos["es"].items() if k != "_meta"}
    for k in sorted(base):
        if k.startswith(("regla.", "peligro.")):
            errores.append("es.json: lleva la clave {} (el español de reglas y "
                           "peligros vive en reglas.json y en targets/)".format(k))
            continue
        if not isinstance(base[k], str) or not base[k].strip():
            errores.append("es.json: la plantilla {} está vacía o no es texto".format(k))
            continue
        try:
            malos = _marcadores_invalidos(base[k])
        except ValueError as e:
            errores.append("es.json: {} no es una plantilla válida ({})".format(k, e))
            continue
        if malos:
            errores.append("es.json: {} usa marcadores sin nombre de identificador "
                           "{}: solo se admiten campos con nombre".format(k, malos))

    for codigo, datos in sorted(catalogos.items()):
        meta = datos.get("_meta")
        if (not isinstance(meta, dict) or meta.get("idioma") != codigo
                or not str(meta.get("nombre", "")).strip()):
            errores.append("{}.json: _meta debe llevar idioma='{}' y un nombre".format(
                codigo, codigo))
        if codigo == "es":
            continue

        propias = {k: v for k, v in datos.items() if k != "_meta"}
        esperadas = set(base) | extra
        for k in sorted(esperadas - set(propias)):
            errores.append("{}.json: falta la clave {}".format(codigo, k))
        for k in sorted(set(propias) - esperadas):
            errores.append("{}.json: sobra la clave {}".format(codigo, k))
        for k, v in sorted(propias.items()):
            if not isinstance(v, str) or not v.strip():
                errores.append("{}.json: la plantilla {} está vacía".format(codigo, k))
                continue
            if k in extra:
                continue    # son textos sueltos, no plantillas
            try:
                m_prop = _marcadores(v)
            except ValueError as e:
                errores.append("{}.json: {} no es una plantilla válida ({})".format(
                    codigo, k, e))
                continue
            malos = _marcadores_invalidos(v)
            if malos:
                errores.append("{}.json: {} usa marcadores sin nombre de identificador "
                               "{}: solo se admiten campos con nombre".format(
                                   codigo, k, malos))
                continue
            if k in base and isinstance(base[k], str) and m_prop != _marcadores(base[k]):
                errores.append("{}.json: los marcadores de {} no coinciden con es "
                               "({} frente a {})".format(
                                   codigo, k, sorted(m_prop),
                                   sorted(_marcadores(base[k]))))
    return errores


def main(raiz: Path) -> int:
    errores = comprobar(raiz)
    for e in errores:
        print("[error] " + e, file=sys.stderr)
    if errores:
        return 1
    n = len(list((raiz / I18N).glob("*.json")))
    print("{} catálogo(s) de idioma válidos.".format(n))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
