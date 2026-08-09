"""Comprobaciones que exigen interpretar un fichero, no buscar un patron.

Una dependencia sin version fijada no se detecta con una regex sobre el
texto: hay que leer el manifiesto y mirar el valor. Un binario "no
documentado" exige saber si algun otro fichero lo menciona. Nada de eso cabe
en reglas.json sin inventar un lenguaje de reglas, que es un proyecto en si
mismo.

Los archivos comprimidos SE SENALAN Y NO SE ABREN. No conocer su contenido es
informacion: alimenta el nivel `no_evaluable`.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from exporter.modelo import Hallazgo

HOOKS_NPM = ("preinstall", "install", "postinstall")

EXTENSIONES_ARCHIVO = {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar", ".bz2", ".xz"}

# Nombres que casi nunca deberian estar versionados. `.env.example` y
# similares quedan fuera a proposito: son plantillas, no secretos.
NOMBRES_SECRETO = {".env", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
                   "credentials.json", ".npmrc", ".pypirc"}
SUFIJOS_SECRETO = (".pem", ".p12", ".pfx", ".keystore")

RANGO_NPM = re.compile(r"^\s*[\^~*]|^\s*$|latest|^\s*(git\+|https?://)|\|\||\s-\s|[<>]")
PIN_PYTHON = re.compile(r"==\s*[0-9]")
LINEA_PYTHON = re.compile(r"^\s*[A-Za-z0-9._-]+\s*[<>=!~]")

# `pyproject.toml` se analiza por lineas y no con un parser TOML: Python 3.8
# no trae `tomllib` y la restriccion de solo-stdlib es innegociable. Es un
# parseo tolerante que puede quedarse corto pero nunca inventa.
#
# Estas dos tablas son de dependencias ENTERAS: toda linea suya es una
# dependencia. `[project]` NO esta aqui a proposito. En PEP 621 no es una
# tabla de dependencias sino la de metadatos, y `dependencies` es una clave
# mas entre `name`, `version`, `description` o `requires-python`; tratarla
# entera hacia que `name = "x"` se declarara dependencia sin fijar.
TABLAS_DEPS_ENTERAS = ("[tool.poetry.dependencies]", "[project.optional-dependencies]")

# Bajo `[project]` solo interesa el array `dependencies` (o el de extras).
CLAVES_ARRAY_DEPS = ("dependencies", "optional-dependencies")

DEP_TOML = re.compile(r"^\s*[\"']?([A-Za-z0-9._-]+)[\"']?\s*[=:]")

# Dentro de un array de dependencias la gramatica es otra: no `clave = valor`
# sino la cadena de requisito `"paquete>=version"`. DEP_TOML no la reconoce
# porque exige `=` o `:` justo tras el nombre, y ahi lo que hay es `>`.
CADENA_DEP = re.compile(r"^\s*[\"']([A-Za-z0-9._-]+)\s*[<>=!~]")


def _h(hid, familia, dimension, severidad, confianza, ambito,
       ubicacion, muestra, titulo, mitigacion) -> Hallazgo:
    return Hallazgo(id=hid, familia=familia, dimension=dimension,
                    severidad=severidad, confianza=confianza, ambito=ambito,
                    ubicacion=ubicacion, muestra=muestra,
                    titulo=titulo, mitigacion=mitigacion)


def _leer_json(f):
    try:
        return json.loads(f.absoluta.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def _npm(f) -> list:
    datos = _leer_json(f)
    if not isinstance(datos, dict):
        return []
    salida = []
    scripts = datos.get("scripts")
    if isinstance(scripts, dict):
        presentes = [h for h in HOOKS_NPM if h in scripts]
        if presentes:
            salida.append(_h(
                "SEC-POSTINSTALL-001", "cadena_de_suministro", "cadena_de_suministro",
                "alta", "alta", f.ambito, f.ruta + ":1",
                ", ".join(presentes),
                "Ejecuta codigo con solo instalar la dependencia",
                "Retirar el hook. Lo que deba correr, que lo lance el usuario a conciencia."))
    for clave in ("dependencies", "devDependencies", "optionalDependencies"):
        deps = datos.get(clave)
        if not isinstance(deps, dict):
            continue
        sueltas = sorted(n for n, v in deps.items()
                         if isinstance(v, str) and RANGO_NPM.search(v))
        if sueltas:
            salida.append(_h(
                "SEC-DEP-SIN-FIJAR-001", "cadena_de_suministro", "cadena_de_suministro",
                "media", "alta", f.ambito, f.ruta + ":1",
                ", ".join(sueltas[:6]),
                "Dependencias npm sin version fijada",
                "Fijar la version exacta, y acompanarla de un lockfile versionado."))
    return salida


def _python(f) -> list:
    try:
        texto = f.absoluta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    sueltas = []
    for numero, linea in enumerate(texto.splitlines(), start=1):
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        if LINEA_PYTHON.match(linea) and not PIN_PYTHON.search(linea):
            sueltas.append((numero, linea.strip()))
    if not sueltas:
        return []
    numero, muestra = sueltas[0]
    return [_h("SEC-DEP-SIN-FIJAR-002", "cadena_de_suministro", "cadena_de_suministro",
               "media", "alta", f.ambito, "{}:{}".format(f.ruta, numero),
               muestra[:120],
               "Dependencias de Python sin version fijada",
               "Fijar con `==` y, si se puede, con hash.")]


def _pyproject(f) -> list:
    try:
        texto = f.absoluta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    dentro = False       # tabla de dependencias entera
    en_array = False     # array `dependencies` bajo [project]
    for numero, linea in enumerate(texto.splitlines(), start=1):
        cruda = linea.strip()
        if cruda.startswith("["):
            dentro = cruda in TABLAS_DEPS_ENTERAS
            en_array = False
            continue
        if cruda.startswith(CLAVES_ARRAY_DEPS):
            en_array = True
            # `dependencies = [` a secas es la CABECERA del array, no una
            # dependencia: lo que hay que mirar viene en las lineas
            # siguientes. Sin esta guarda, un array multilinea con todo
            # fijado se marcaria por su propia cabecera, que no lleva `==`.
            if cruda.endswith("["):
                continue
        if not (dentro or en_array) or not cruda or cruda.startswith("#"):
            continue
        casa = DEP_TOML.match(linea) or (en_array and CADENA_DEP.match(linea))
        if casa and not PIN_PYTHON.search(linea):
            return [_h("SEC-DEP-SIN-FIJAR-002", "cadena_de_suministro",
                       "cadena_de_suministro", "media", "media", f.ambito,
                       "{}:{}".format(f.ruta, numero), cruda[:120],
                       "Dependencias de Python sin version fijada",
                       "Fijar con `==` y, si se puede, con hash.")]
        if en_array and cruda.endswith("]"):
            en_array = False
    return []


def analizar(raiz, ficheros) -> list:
    raiz = Path(raiz)
    salida = []
    textos = []
    for f in ficheros:
        if not f.binario:
            try:
                textos.append(f.absoluta.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass

    for f in ficheros:
        nombre = os.path.basename(f.ruta)
        ext = os.path.splitext(nombre)[1].lower()

        if nombre == "package.json":
            salida.extend(_npm(f))
        elif nombre in ("requirements.txt", "requirements-dev.txt"):
            salida.extend(_python(f))
        elif nombre == "pyproject.toml":
            salida.extend(_pyproject(f))

        if ext in EXTENSIONES_ARCHIVO:
            salida.append(_h(
                "SEC-ARCHIVO-ANIDADO-001", "cadena_de_suministro", "cadena_de_suministro",
                "media", "alta", f.ambito, f.ruta + ":1", nombre,
                "Archivo comprimido dentro del repositorio",
                "No se abre: su contenido no se ha analizado. Descomprimirlo y "
                "versionar los ficheros, o justificar por que viaja comprimido."))

        if nombre in NOMBRES_SECRETO or nombre.endswith(SUFIJOS_SECRETO):
            salida.append(_h(
                "SEC-SECRETO-EN-REPO-001", "permisos_y_acciones", "tecnico",
                "alta", "alta", f.ambito, f.ruta + ":1", nombre,
                "Fichero con nombre de credencial versionado en el repositorio",
                "Retirarlo del control de versiones, rotar lo que contuviera y "
                "anadirlo a .gitignore."))

        if f.binario and ext not in EXTENSIONES_ARCHIVO:
            if not any(nombre in t or f.ruta in t for t in textos):
                salida.append(_h(
                    "SEC-BINARIO-NO-DOCUMENTADO-001", "cadena_de_suministro",
                    "cadena_de_suministro", "media", "media", f.ambito,
                    f.ruta + ":1", nombre,
                    "Fichero binario que ningun texto del repositorio menciona",
                    "Documentar que es, de donde sale y como reproducirlo; o retirarlo."))

    return salida
