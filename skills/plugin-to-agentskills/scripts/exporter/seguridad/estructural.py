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
from exporter.seguridad.recorrido import leer_para_analisis

HOOKS_NPM = ("preinstall", "install", "postinstall")

EXTENSIONES_ARCHIVO = {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar", ".bz2", ".xz"}

# Nombres que casi nunca deberian estar versionados. `.env.example` y
# similares quedan fuera a proposito: son plantillas, no secretos.
NOMBRES_SECRETO = {".env", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
                   "credentials.json", ".npmrc", ".pypirc"}
SUFIJOS_SECRETO = (".pem", ".p12", ".pfx", ".keystore")

# Sufijos de `.env.<algo>` que son PLANTILLA y no secreto. La lista es corta
# a proposito: marcar un `.env.example` es el falso positivo que ensena a la
# gente a ignorar los avisos, y ese coste es peor que el hallazgo que se
# gana. Todo lo demas -.env.local, .env.production- se trata como un .env,
# porque eso es lo que es: un fichero de entorno con valores de verdad.
ENV_PLANTILLA = {"example", "sample", "template", "dist", "defaults", "tpl"}

# Un valor de dependencia npm que NO fija una version. Ademas de los rangos
# clasicos, cualquier especificador con protocolo -github:, file:, link:,
# workspace:, npm:...- y la forma corta `usuario/repo`: todos ellos traen lo
# que haya en el otro extremo en el momento de instalar, que es exactamente
# lo que "sin fijar" significa. Ni `:` ni `/` aparecen nunca en un semver,
# asi que las dos alternativas nuevas no pueden tocar una version fijada.
RANGO_NPM = re.compile(r"^\s*[\^~*]|^\s*$|latest|^\s*(git\+|https?://)|\|\||\s-\s|[<>]"
                       r"|^\s*[a-z][\w+.-]*:|^\s*[\w.-]+/[\w.-]+")

PIN_PYTHON = re.compile(r"==\s*[0-9]")

# Una linea de dependencia de Python: el nombre del paquete, sus extras
# opcionales, y despues un operador de version, un marcador de entorno, o
# NADA EN ABSOLUTO. Antes se exigia el operador, asi que `requests` a secas
# -el caso mas suelto que existe, porque acepta cualquier version publicada
# hoy y manana- era el unico que se escapaba limpio.
LINEA_PYTHON = re.compile(r"^\s*[A-Za-z0-9._-]+\s*(\[[^\]]*\]\s*)?([<>=!~;].*)?$")

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


def _es_env_con_valores(nombre: str) -> bool:
    """True para `.env` y sus variantes reales, False para las plantillas.

    NOMBRES_SECRETO comparaba por igualdad exacta, asi que `.env.local` y
    `.env.production` -que son justo los que llevan valores de verdad, no
    los huecos- no contaban como credencial.
    """
    if nombre == ".env":
        return True
    if not nombre.startswith(".env."):
        return False
    return nombre.rsplit(".", 1)[-1].lower() not in ENV_PLANTILLA


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
                "Ejecuta código con solo instalar la dependencia",
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
                "Dependencias npm sin versión fijada",
                "Fijar la versión exacta, y acompañarla de un lockfile versionado."))
    return salida


def _python(f) -> list:
    try:
        texto = f.absoluta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    sueltas = []
    for numero, linea in enumerate(texto.splitlines(), start=1):
        # Las lineas que empiezan por `-` no son dependencias sino opciones
        # del propio fichero (`-r otro.txt`, `--index-url ...`, `-e .`).
        # Hay que saltarlas explicitamente desde que LINEA_PYTHON acepta un
        # nombre suelto: `-` esta en su clase de caracteres, asi que un
        # `--index-url` casaria y se reportaria como dependencia sin fijar.
        if not linea.strip() or linea.lstrip().startswith(("#", "-")):
            continue
        if LINEA_PYTHON.match(linea) and not PIN_PYTHON.search(linea):
            sueltas.append((numero, linea.strip()))
    if not sueltas:
        return []
    numero, muestra = sueltas[0]
    return [_h("SEC-DEP-SIN-FIJAR-002", "cadena_de_suministro", "cadena_de_suministro",
               "media", "alta", f.ambito, "{}:{}".format(f.ruta, numero),
               muestra[:120],
               "Dependencias de Python sin versión fijada",
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
                       "Dependencias de Python sin versión fijada",
                       "Fijar con `==` y, si se puede, con hash.")]
        if en_array and cruda.endswith("]"):
            en_array = False
    return []


# Proporcion maxima de caracteres "no texto" que se tolera antes de dejar de
# considerar que el contenido decodificado es texto. Se mide sobre el texto
# YA sin bytes nulos: lo que cuenta como no-texto es el caracter de
# reemplazo -es decir, bytes que no son UTF-8 valido- y los de control que no
# sean tabulador ni salto de linea.
UMBRAL_NO_TEXTO = 0.05


def _texto_con_nulos(f) -> list:
    """Un fichero marcado binario cuyo contenido es casi todo texto.

    `es_binario` decide por un unico byte nulo en los primeros 8 KB. Eso
    convierte a un `.sh` perfectamente ejecutable con un \\x00 dentro de un
    comentario en "binario", y antes eso lo sacaba del motor entero. Un
    fichero de TEXTO con bytes nulos no tiene explicacion inocente: o esta
    ofuscado para esquivar el analisis, o esta en una codificacion (UTF-16)
    que impide leerlo. En los dos casos el motor no ha podido analizarlo
    como lo que es, y eso hay que decirlo.

    La medida NO puede ser `str.isprintable()` sobre el texto decodificado:
    con errors="replace" cada byte indecodificable se convierte en U+FFFD, y
    U+FFFD ES imprimible, asi que un ELF puntuaria como "casi todo texto".
    Se cuenta al reves: los caracteres de reemplazo son la evidencia de que
    era binario de verdad. Un texto con nulos decodifica limpio -el nulo es
    un punto de codigo valido- y un binario de verdad produce una avalancha
    de U+FFFD.
    """
    datos = leer_para_analisis(f.absoluta)
    if not datos or b"\x00" not in datos:
        return []
    sin_nulos = datos.replace(b"\x00", b"")
    if not sin_nulos:
        return []
    texto = sin_nulos.decode("utf-8", errors="replace")
    if not texto:
        return []
    no_texto = sum(1 for c in texto
                   if c == "�" or (not c.isprintable() and c not in "\t\n\r"))
    if no_texto / len(texto) > UMBRAL_NO_TEXTO:
        return []

    muestra = next((l.strip() for l in texto.splitlines() if l.strip()), "")
    return [_h("SEC-OFUSCA-NULOS-001", "ofuscacion", "tecnico", "alta", "alta",
               f.ambito, f.ruta + ":1", muestra[:120],
               "Fichero de texto con bytes nulos",
               "Un fichero de texto no debería contener bytes nulos: o se han "
               "puesto para que el análisis lo tome por binario y no lo mire, o "
               "está en una codificación como UTF-16 que impide leerlo. Guardarlo "
               "en UTF-8 sin bytes nulos y volver a auditarlo.")]


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
                "versionar los ficheros, o justificar por qué viaja comprimido."))

        if (nombre in NOMBRES_SECRETO or nombre.endswith(SUFIJOS_SECRETO)
                or _es_env_con_valores(nombre)):
            salida.append(_h(
                "SEC-SECRETO-EN-REPO-001", "permisos_y_acciones", "tecnico",
                "alta", "alta", f.ambito, f.ruta + ":1", nombre,
                "Fichero con nombre de credencial versionado en el repositorio",
                "Retirarlo del control de versiones, rotar lo que contuviera y "
                "añadirlo a .gitignore."))

        # Un fichero que no se pudo abrir es el caso mas puro de contenido
        # opaco: no se sabe nada de el, ni siquiera si es texto. Antes se
        # colaba disfrazado de binario -es_binario devolvia True ante un
        # OSError-, asi que el paquete acababa acusado de traer un "binario
        # no documentado", que afirma algo sobre un contenido que nadie ha
        # visto. El motor tiene que decir lo que le pasa, no inventarse una
        # categoria que encaje.
        if not f.legible:
            salida.append(_h(
                "SEC-ILEGIBLE-001", "cadena_de_suministro", "cadena_de_suministro",
                "media", "alta", f.ambito, f.ruta + ":1", nombre,
                "Fichero que no se ha podido leer",
                "El análisis no ha podido abrirlo, así que no dice nada sobre su "
                "contenido. Corregir sus permisos y volver a auditar, o retirarlo "
                "del paquete."))
            continue

        if f.binario and ext not in EXTENSIONES_ARCHIVO:
            salida.extend(_texto_con_nulos(f))
            if not any(nombre in t or f.ruta in t for t in textos):
                salida.append(_h(
                    "SEC-BINARIO-NO-DOCUMENTADO-001", "cadena_de_suministro",
                    "cadena_de_suministro", "media", "media", f.ambito,
                    f.ruta + ":1", nombre,
                    "Fichero binario que ningún texto del repositorio menciona",
                    "Documentar qué es, de dónde sale y cómo reproducirlo; o retirarlo."))

    return salida
