"""Carga de los perfiles de destino.

Los perfiles son datos, no codigo: un JSON por destino en targets/. Anadir un
destino es escribir un fichero, no editar Python.

La validacion de aqui es la minima que el programa necesita para no romperse.
La validacion contra el JSON Schema completo la hace el CI, donde si se puede
instalar `jsonschema`.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

CLAVES_OBLIGATORIAS = ("id", "label", "instalacion", "formato",
                       "capacidades", "peligros", "evidencia")

DIRECTORIO_POR_DEFECTO = Path(__file__).resolve().parent / "targets"


class PerfilInvalido(Exception):
    """Un fichero de targets/ no se puede usar."""


class Perfil:

    def __init__(self, datos: dict):
        self.datos = datos
        self.id = datos["id"]
        self.label = datos["label"]

    def capacidad(self, nombre: str) -> str:
        """Nivel declarado, o 'desconocido' si el perfil no dice nada.

        Callar no es negar: una capacidad sin declarar produce no_verificable,
        nunca una conjetura.
        """
        return self.datos["capacidades"].get(nombre, "desconocido")

    def presupuesto(self) -> int:
        return int(self.datos["formato"]["presupuesto_description_bytes"])

    def modos(self) -> list:
        return list(self.datos["instalacion"]["modos"])

    def peligros_para(self, senal_id: str) -> list:
        return [p for p in self.datos["peligros"] if senal_id in p.get("dispara_con", [])]

    def limite(self, nombre: str):
        return self.datos.get("limites_paquete", {}).get(nombre)

    def caducado(self, hoy: datetime.date) -> bool:
        return datetime.date.fromisoformat(
            self.datos["evidencia"]["revisar_tras"]) < hoy

    def __repr__(self) -> str:
        return "<Perfil {}>".format(self.id)


def cargar_perfil(ruta: Path) -> Perfil:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PerfilInvalido("{}: JSON malformado en linea {}, columna {}: {}".format(
            ruta.name, e.lineno, e.colno, e.msg))
    faltan = [k for k in CLAVES_OBLIGATORIAS if k not in datos]
    if faltan:
        raise PerfilInvalido("{}: faltan claves obligatorias: {}".format(
            ruta.name, ", ".join(faltan)))
    return Perfil(datos)


def cargar_perfiles(directorio=None) -> dict:
    """Devuelve {id: Perfil} de todos los targets/*.json, salvo _schema.json."""
    directorio = Path(directorio) if directorio else DIRECTORIO_POR_DEFECTO
    perfiles = {}
    for ruta in sorted(directorio.glob("*.json")):
        if ruta.name.startswith("_"):
            continue
        perfil = cargar_perfil(ruta)
        if perfil.id != ruta.stem:
            raise PerfilInvalido(
                "{}: el id '{}' no coincide con el nombre del fichero".format(
                    ruta.name, perfil.id))
        perfiles[perfil.id] = perfil
    return perfiles
