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
from exporter.seguridad.recorrido import leer_para_analisis

RUTA_REGLAS = Path(__file__).resolve().parent / "reglas.json"

def _es_el_catalogo(absoluta) -> bool:
    """True solo si el fichero ES el catalogo que este motor esta usando.

    El catalogo no se analiza a si mismo. reglas.json es, por definicion, un
    fichero lleno de los patrones que el motor caza -las lineas que declaran
    SEC-PROMPT-IGNORA-001 y SEC-PROMPT-REVELA-001 casan con sus propios
    patrones-, y vive dentro de la skill publicada, asi que su ambito es
    `exportado` y sin la exclusion el gate se negaria a exportar la
    herramienta.

    La comparacion es por IDENTIDAD DE FICHERO, no por sufijo de ruta. Antes
    bastaba con que la ruta terminara en "exporter/seguridad/reglas.json", y
    esa ruta la elige el repositorio auditado: crear
    `skills/x/exporter/seguridad/reglas.json` daba una exencion gratis, y en
    un .json -que declaran las once reglas, las tres de inyeccion de prompt
    incluidas- se esconde muy bien una carga. La exencion la concedia el
    auditado; ahora la concede el sistema de ficheros, que no se puede
    falsificar desde dentro del arbol auditado.

    Comprobado que los dos casos que dependen de esto auditan el MISMO
    inodo, no una copia: `tests/test_seg_golden.EsteRepositorio` ejecuta el
    convert.py de este repositorio sobre este repositorio, y el paso de CI
    "El conversor arranca desde una copia aislada" copia el arbol entero y
    ejecuta el convert.py DE LA COPIA sobre la copia, asi que RUTA_REGLAS se
    resuelve dentro de esa misma copia.

    El unico caso que pierde la exencion es auditar una copia AJENA de este
    repositorio con un conversor instalado en otro sitio. Y ahi perderla es
    lo correcto: el motor no puede distinguir una copia legitima del
    catalogo de un fichero que un tercero ha puesto en esa ruta con ese
    contenido. Decirlo es mas honesto que callarlo, y para el humano que
    sabe lo que esta auditando esta --anular-revision-seguridad.
    """
    try:
        return os.path.samefile(str(absoluta), str(RUTA_REGLAS))
    except OSError:
        # El catalogo puede no existir donde se espera, o el fichero
        # auditado haber desaparecido entre el recorrido y este momento.
        return False


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


def reglas_aplicables(ext: str, reglas, conocidas) -> list:
    """Que reglas se aplican a un fichero con esa extension.

    `extensiones` era de facto una LISTA BLANCA: si ninguna regla declaraba
    la extension, el fichero no se analizaba con ninguna. Como el nombre del
    fichero lo elige el repositorio auditado, eso dejaba al auditado decidir
    si se le audita: un `scripts/instalar` -la forma idiomatica de un script
    ejecutable, sin extension- pasaba entero por delante del motor sin que
    ninguna regla lo mirase.

    Ahora la lista es un VETO, no un permiso. Se analiza todo texto, y la
    lista solo sirve para NO aplicar una regla donde no tiene sentido:

      - extension que alguna regla declara -> solo las que la declaran, que
        es el comportamiento de siempre y lo que evita, por ejemplo, buscar
        conducta_de_prompt dentro de un .py;
      - extension ausente o que ninguna regla declara -> TODAS las reglas.

    No hay lista de extensiones "inertes" exentas, y es deliberado: una lista
    asi seria, por construccion, una lista de evasion. El defecto que esto
    corrige es exactamente "el atacante elige un nombre que el motor no mira",
    y reservar un conjunto de extensiones no miradas solo lo hace mas pequeno.

    El coste en falsos positivos es bajo porque los patrones del catalogo son
    frases muy concretas -un gestor de paquetes instalando desde una URL, una
    descarga entubada a un interprete, una orden de desatender las
    instrucciones previas- y no formas genericas. Los literales no se
    escriben aqui: este fichero viaja dentro de la skill publicada, asi que
    su ambito es `exportado` y escribirlos en claro haria que el motor se
    delatase a si mismo (§4 del diseno). Viven en reglas.json, que el motor
    se salta, y en tests/fixtures/, que esta fuera de toda skill.
    """
    if ext in conocidas:
        return [r for r in reglas if ext in r["extensiones"]]
    return list(reglas)


def analizar(ficheros, reglas) -> list:
    """Un Hallazgo por cada (regla, fichero, linea) que coincida.

    Una linea con dos coincidencias de la misma regla produce UNO: lo que el
    lector necesita es donde mirar, y la linea ya se lo dice.
    """
    salida = []
    # La union de lo que el catalogo declara. Distingue "extension que alguna
    # regla conoce" de "extension que ninguna conoce", que es lo unico que
    # necesita reglas_aplicables para decidir.
    conocidas = {e.lower() for r in reglas for e in r["extensiones"]}
    for f in ficheros:
        if _es_el_catalogo(f.absoluta):
            continue
        ext = os.path.splitext(f.ruta)[1].lower()
        aplicables = reglas_aplicables(ext, reglas, conocidas)
        # Los marcados como binarios TAMBIEN se analizan. `es_binario` solo
        # mira si hay un byte nulo en los primeros 8 KB, asi que un .sh
        # perfectamente ejecutable con un \x00 dentro de un comentario
        # quedaba fuera del motor entero: un unico byte bastaba para que
        # ninguna regla lo mirase. Decodificando con errors="replace", un
        # payload en texto plano sigue casando; lo que de verdad sea binario
        # produce caracteres de reemplazo que no casan con nada.
        if f.binario:
            datos = leer_para_analisis(f.absoluta)
            if datos is None:
                continue
            texto = datos.decode("utf-8", errors="replace")
        else:
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
