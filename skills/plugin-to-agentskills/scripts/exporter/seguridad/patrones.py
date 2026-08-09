"""Aplica las reglas de `reglas.json` sobre el texto del paquete.

Los patrones viven en datos y no en codigo por la misma razon que los
perfiles de destino: anadir uno nuevo no deberia exigir editar Python. Lo que
NO cabe aqui —interpretar un package.json, decidir si un binario esta
documentado— vive en estructural.py, y es honesto que asi sea.

La deteccion es por expresion regular y da falsos positivos. Por eso cada
regla declara su `confianza`, cada hallazgo cita `fichero:linea` con una
muestra del texto, y el gate exige confianza al menos media para bloquear.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from exporter.modelo import Hallazgo

RUTA_REGLAS = Path(__file__).resolve().parent / "reglas.json"

# El catalogo NO se analiza a si mismo. reglas.json es, por definicion, un
# fichero lleno de los patrones que el motor caza: comprobado que las lineas
# que declaran SEC-PROMPT-IGNORA-001 y SEC-PROMPT-REVELA-001 casan con sus
# propios patrones. Como el fichero vive dentro de la skill publicada, su
# ambito es `exportado` y el gate se negaria a exportar la herramienta. Se
# compara por sufijo de ruta y no por igualdad con RUTA_REGLAS para que la
# exclusion valga tambien al auditar una COPIA de este repositorio, que es lo
# que hacen el CI y `tests/test_seg_golden.EsteRepositorio`.
SUFIJO_CATALOGO = "exporter/seguridad/reglas.json"


def _es_el_catalogo(ruta_relativa: str) -> bool:
    return ruta_relativa == SUFIJO_CATALOGO or ruta_relativa.endswith("/" + SUFIJO_CATALOGO)


CLAVES = ("id", "familia", "dimension", "severidad", "confianza",
          "patron", "titulo", "detalle", "mitigacion", "extensiones")


class ReglaInvalida(Exception):
    """El fichero de reglas no se puede usar."""


def cargar_reglas(ruta=None) -> list:
    """Lee reglas.json y compila cada patron.

    La validacion de aqui es la minima para no romperse. La validacion contra
    el JSON Schema completo la hace el CI, donde si se puede instalar
    `jsonschema`.
    """
    ruta = Path(ruta) if ruta else RUTA_REGLAS
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ReglaInvalida("{}: JSON malformado en linea {}, columna {}: {}".format(
            ruta.name, e.lineno, e.colno, e.msg))
    if not isinstance(datos.get("reglas"), list) or not datos["reglas"]:
        raise ReglaInvalida("{}: falta la lista 'reglas' o esta vacia".format(ruta.name))

    reglas = []
    vistos = set()
    for r in datos["reglas"]:
        faltan = [k for k in CLAVES if k not in r]
        if faltan:
            raise ReglaInvalida("{}: la regla '{}' no trae {}".format(
                ruta.name, r.get("id", "(sin id)"), ", ".join(faltan)))
        if r["id"] in vistos:
            raise ReglaInvalida("{}: identificador repetido: {}".format(ruta.name, r["id"]))
        vistos.add(r["id"])
        try:
            r = dict(r, _rx=re.compile(r["patron"]))
        except re.error as e:
            raise ReglaInvalida("{}: el patron de '{}' no compila: {}".format(
                ruta.name, r["id"], e))
        reglas.append(r)
    return reglas


def analizar(ficheros, reglas) -> list:
    """Un Hallazgo por cada (regla, fichero, linea) que coincida.

    Una linea con dos coincidencias de la misma regla produce UNO: lo que el
    lector necesita es donde mirar, y la linea ya se lo dice.
    """
    salida = []
    for f in ficheros:
        if f.binario:
            continue
        if _es_el_catalogo(f.ruta):
            continue
        ext = os.path.splitext(f.ruta)[1].lower()
        aplicables = [r for r in reglas if ext in r["extensiones"]]
        if not aplicables:
            continue
        try:
            texto = f.absoluta.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for numero, linea in enumerate(texto.splitlines(), start=1):
            for r in aplicables:
                m = r["_rx"].search(linea)
                if not m:
                    continue
                salida.append(Hallazgo(
                    id=r["id"], familia=r["familia"], dimension=r["dimension"],
                    severidad=r["severidad"], confianza=r["confianza"],
                    ambito=f.ambito,
                    ubicacion="{}:{}".format(f.ruta, numero),
                    muestra=m.group(0).strip()[:120],
                    titulo=r["titulo"], mitigacion=r["mitigacion"]))
    return salida
