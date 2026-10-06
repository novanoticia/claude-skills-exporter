"""Textos visibles en varios idiomas.

Un catalogo JSON por idioma en este mismo directorio: `clave -> plantilla`,
con campos `{nombre}` de `str.format`. El idioma activo es estado de modulo,
fijado una sola vez al arrancar `main()`: el programa es de un solo proceso
y de un solo hilo, y pasar el idioma como parametro tocaria decenas de
firmas por poco beneficio.

Anadir un idioma es soltar aqui un `xx.json` con su `_meta`; se descubre
solo, igual que los perfiles de `exporter/targets/`.

Solo biblioteca estandar y solo lectura de ficheros propios: este modulo no
ejecuta nada de lo que analiza.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

IDIOMA_BASE = "es"
DIRECTORIO = Path(__file__).resolve().parent

_activo = IDIOMA_BASE
_cache: dict = {}


class IdiomaDesconocido(Exception):
    def __init__(self, codigo: str, disponibles: dict):
        super().__init__(codigo)
        self.codigo = codigo
        self.disponibles = disponibles


def normalizar_codigo(codigo: str) -> str:
    """`FR_fr.UTF-8` -> `fr`; `en-US` -> `en`."""
    return re.split(r"[-_.@]", codigo.strip().lower())[0]


def _cargar(codigo: str) -> dict:
    if codigo not in _cache:
        ruta = DIRECTORIO / (codigo + ".json")
        _cache[codigo] = json.loads(ruta.read_text(encoding="utf-8"))
    return _cache[codigo]


def idiomas_disponibles() -> dict:
    """`{codigo: nombre en su propia lengua}` de los catalogos legibles."""
    salida = {}
    for ruta in sorted(DIRECTORIO.glob("*.json")):
        try:
            meta = json.loads(ruta.read_text(encoding="utf-8"))["_meta"]
            salida[ruta.stem] = meta["nombre"]
        except (OSError, ValueError, KeyError, TypeError):
            # Un catalogo roto no se ofrece. Quien lo rompa lo ve en CI:
            # validar_idiomas.py lo comprueba fichero a fichero.
            continue
    return salida


def fijar_idioma(codigo: str) -> str:
    global _activo
    normalizado = normalizar_codigo(codigo)
    disponibles = idiomas_disponibles()
    if normalizado not in disponibles:
        raise IdiomaDesconocido(codigo, disponibles)
    _activo = normalizado
    return normalizado


def idioma_activo() -> str:
    return _activo


def t(clave: str, **datos) -> str:
    """Texto de `clave` en el idioma activo.

    Si falta en ese idioma cae al espanol, para que un catalogo incompleto
    degrade en vez de romper; si falta tambien en espanol es un error de
    programacion y se lanza KeyError. Solo se formatea la PLANTILLA: los
    datos se insertan como valores y no se reinterpretan.
    """
    plantilla = _cargar(_activo).get(clave)
    if plantilla is None:
        plantilla = _cargar(IDIOMA_BASE)[clave]
    return plantilla.format(**datos)


def t_opcional(clave: str, defecto: str) -> str:
    """La sobrescritura de `clave` en el idioma activo, o `defecto`.

    Para los textos que viven en espanol en reglas.json y en los perfiles de
    destino: ahi `defecto` es el espanol de origen, y los catalogos de otros
    idiomas lo sobrescriben. No cae a `es` (su catalogo no los lleva) y no
    formatea, porque esos textos no son plantillas.
    """
    return _cargar(_activo).get(clave, defecto)


VARIABLES_DE_LOCALE = ("LC_ALL", "LC_MESSAGES", "LANG")


def detectar_del_entorno(entorno=None) -> str:
    """El idioma del locale del entorno, o el base si no hay catalogo.

    Respeta la precedencia POSIX (LC_ALL, LC_MESSAGES, LANG). La primera
    variable con valor decide, salvo `C` y `POSIX`, que significan «sin
    idioma» y se saltan. Si el idioma que dice no tiene catalogo, gana el
    base: no se salta a la siguiente variable, porque eso mezclaria idiomas.
    """
    entorno = os.environ if entorno is None else entorno
    for variable in VARIABLES_DE_LOCALE:
        valor = (entorno.get(variable) or "").strip()
        if not valor or valor.upper() in ("C", "POSIX") or valor.upper().startswith("C."):
            continue
        codigo = normalizar_codigo(valor)
        return codigo if codigo in idiomas_disponibles() else IDIOMA_BASE
    return IDIOMA_BASE


def idioma_pedido(flag, entorno=None) -> str:
    """Que idioma se pidio: el flag, si no CSE_LANG, si no el base.

    `auto` se resuelve aqui contra el entorno. Una variable vacia cuenta
    como ausente. No valida: eso lo hace fijar_idioma.
    """
    entorno = os.environ if entorno is None else entorno
    pedido = flag or entorno.get("CSE_LANG") or IDIOMA_BASE
    if pedido.strip().lower() == "auto":
        return detectar_del_entorno(entorno)
    return pedido
