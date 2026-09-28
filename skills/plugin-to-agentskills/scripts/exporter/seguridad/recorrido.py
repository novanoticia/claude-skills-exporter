"""Recorre el repositorio entero y le pone ambito a cada fichero.

Este recorrido NO es el de `discover_skills`. Aquel localiza los directorios
con un SKILL.md y corta el descenso ahi, porque su unidad de analisis es la
skill. La unidad de la seguridad es el paquete: un `postinstall` malicioso en
la raiz no pertenece a ninguna skill y hay que verlo igual.

El ambito es el campo del que cuelga todo lo demas. `exportado` significa que
el fichero acaba dentro del .zip o de la carpeta que el usuario sube a otra
plataforma, y por eso un hallazgo grave ahi bloquea la escritura. `paquete`
significa que se queda en el repositorio: avisa, pero no impide exportar unas
skills que estan limpias.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from exporter.deteccion import IGNORED_DIRS

# `.git` no se recorre: es historia, no contenido, y su tamano no representa
# lo que se instala. `__pycache__` tampoco: no es contenido del paquete sino
# un artefacto que el propio interprete escribe al arrancar la herramienta
# —comprobado sobre un checkout limpio: arrancar convert.py escribe nueve
# .pyc en exporter/__pycache__ ANTES de que empiece el recorrido—, y ademas
# `copiar_skill` lo poda al empaquetar, asi que nunca viaja a ningun sitio.
# Todo lo demas SI se recorre, node_modules incluido, que es justo donde vive
# el riesgo de cadena de suministro.
EXCLUIDOS_SIEMPRE = {".git", "__pycache__"}

CABECERA_BYTES = 8192

# Tope de lectura para analizar un fichero marcado como binario. Desde que
# "parece binario" dejo de significar "no lo mires", el motor puede toparse
# con una imagen o un ejecutable de cientos de MB, y leerlo entero para
# pasarle once expresiones regulares no compensa. Un payload en texto plano
# escondido tras un byte nulo vive, en la practica, en el primer tramo del
# fichero: el caso real es un script pequeno con un nulo en un comentario,
# no un ISO. El tope acota el coste; el precio que se paga es que un payload
# situado mas alla de 1 MiB dentro de un fichero binario no se ve.
#
# A los ficheros de texto NO se les aplica: se leian enteros desde siempre y
# recortarlos ahora perderia deteccion que hoy si funciona.
MAX_BYTES_ANALISIS = 1024 * 1024


def leer_para_analisis(ruta, tope: int = MAX_BYTES_ANALISIS):
    """Los primeros `tope` bytes del fichero, o None si no se puede leer."""
    try:
        with open(str(ruta), "rb") as fh:
            return fh.read(tope)
    except OSError:
        return None


@dataclass(frozen=True)
class Fichero:
    ruta: str          # relativa a la raiz, siempre con separadores posix
    absoluta: Path
    ambito: str
    binario: bool
    # False cuando el fichero no se pudo abrir siquiera. Es distinto de
    # `binario`: un binario se ha leido y no es texto; un ilegible no se ha
    # llegado a leer, y de su contenido no se sabe absolutamente nada. Antes
    # los dos casos se confundian -es_binario devolvia True ante un OSError-,
    # y un fichero sin permisos se contaba como "binario no documentado",
    # que dice algo que el motor no ha comprobado.
    legible: bool = True


def _cabecera(ruta: Path):
    """Los primeros bytes del fichero, o None si no se pudo abrir."""
    try:
        with open(str(ruta), "rb") as fh:
            return fh.read(CABECERA_BYTES)
    except OSError:
        return None


def es_binario(ruta: Path) -> bool:
    """Un byte nulo en la cabecera es la senal practica de que no es texto.

    Un fichero que no se puede abrir cuenta como binario para no analizarlo
    como si fuera texto, pero `recorrer` guarda aparte que era ilegible: son
    dos cosas distintas y confundirlas hacia que el motor afirmara cosas que
    no habia comprobado.
    """
    cabecera = _cabecera(ruta)
    return cabecera is None or b"\x00" in cabecera


def _ambito(rel: str, dirs_skill) -> str:
    """`exportado` solo si el fichero acaba DE VERDAD dentro del artefacto.

    No basta con colgar de un directorio de skill. `copiar_skill` poda
    IGNORED_DIRS al empaquetar, asi que un hallazgo en
    `skills/x/node_modules/...`, `skills/x/dist/...` o `skills/x/.venv/...`
    no viaja a ninguna parte: marcarlo `exportado` bloquearia la escritura de
    un artefacto que jamas contiene ese fichero. Es el falso bloqueo que la
    §7 del diseno quiere evitar.
    """
    if any(p in IGNORED_DIRS for p in rel.split("/")[:-1]):
        return "paquete"
    for d in dirs_skill:
        d = d.rstrip("/")
        # El origen puede SER el directorio de la skill: un repositorio de
        # una sola skill con el SKILL.md en la raiz. `relative_to` devuelve
        # "." y sin esta rama todo el arbol saldria `paquete`, dejando el
        # gate desactivado en silencio.
        if d in ("", "."):
            return "exportado"
        if rel == d or rel.startswith(d + "/"):
            return "exportado"
    return "paquete"


def recorrer(raiz, dirs_skill) -> list:
    """Devuelve todos los ficheros del arbol, en orden estable, con su ambito.

    No sigue enlaces simbolicos: uno que apunte a `/` haria el recorrido
    infinito, y ademas el empaquetado tampoco los sigue.
    """
    raiz = Path(raiz)
    dirs = [str(d).replace(os.sep, "/").strip("/") for d in dirs_skill]
    salida = []
    for base, subdirs, ficheros in os.walk(str(raiz)):
        subdirs[:] = sorted(
            d for d in subdirs
            if d not in EXCLUIDOS_SIEMPRE
            and not os.path.islink(os.path.join(base, d)))
        for nombre in sorted(ficheros):
            absoluta = Path(base) / nombre
            if absoluta.is_symlink():
                continue
            rel = os.path.relpath(str(absoluta), str(raiz)).replace(os.sep, "/")
            cabecera = _cabecera(absoluta)
            salida.append(Fichero(ruta=rel, absoluta=absoluta,
                                  ambito=_ambito(rel, dirs),
                                  binario=cabecera is None or b"\x00" in cabecera,
                                  legible=cabecera is not None))
    return sorted(salida, key=lambda f: f.ruta)
