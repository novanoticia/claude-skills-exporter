#!/usr/bin/env python3
"""
convert.py — Extrae las skills de un repositorio con un plugin de Claude y las
empaqueta en formato Agent Skills portable (ChatGPT / Perplexity Computer /
Mistral Vibe Work / claude.ai).

Parte de Claude Skills Exporter.
Copyright (c) 2026 Pablo Rodríguez López — https://github.com/novanoticia
Licencia MIT. Se permite usar, copiar, modificar y redistribuir este fichero,
incluso comercialmente, conservando este aviso de copyright y la licencia.

Sólo biblioteca estándar. Python 3.8+.

Uso:
    python3 convert.py inspect <repo-url-o-ruta>              # qué exige, sin destino
    python3 convert.py audit   <repo-url-o-ruta> [--target …] # matriz; no escribe nada
    python3 convert.py export  <repo-url-o-ruta> [--out DIR] [--only NOMBRE ...]
    python3 convert.py <repo-url-o-ruta> ...                  # forma corta = export

Salidas de `export` en <out>/:
    <skill>.zip                se sube tal cual a ChatGPT, claude.ai y Perplexity
    <skill>/                   se sube a Mistral Vibe Work
    INFORME-PORTABILIDAD.md    qué se adaptó y qué se romperá fuera de Claude
    resumen.json               lo mismo, en formato máquina

Los dos llevan los mismos ficheros, PERO NO SON EL MISMO ARTEFACTO: la descripción
del frontmatter se ajusta al presupuesto de cada destino (850 B en el zip, 490 B en
la carpeta). Descomprimir el zip no produce la carpeta de Mistral.

Una skill por zip — nunca un zip con varias dentro.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from exporter.compatibilidad import evaluar
from exporter.descripcion import (
    clamp_description,
    compact_description,
    nbytes,
    reorder_description,
    tiene_activacion,
)
from exporter.deteccion import (
    CLAUDE_TOOL_NAMES,
    IGNORED_DIRS,
    detectar,
    detectar_en_arbol,
)
from exporter.empaquetado import comprobar_limites, copiar_skill, zip_dir
from exporter import i18n
from exporter.i18n import t
from exporter.frontmatter import split_frontmatter, yaml_escape
from exporter.informes import informe_markdown, resumen_json
from exporter.modelo import (
    Bloqueo,
    Estado,
    Nivel,
    SkillPortatil,
    VeredictoSeguridad,
    capacidades_de,
)
from exporter.perfiles import PerfilInvalido, cargar_perfiles
from exporter.seguridad import estructural as seg_estructural
from exporter.seguridad import patrones as seg_patrones
from exporter.seguridad import riesgo as seg_riesgo
from exporter.seguridad.recorrido import recorrer

# --------------------------------------------------------------------------
# Límites y constantes del estándar Agent Skills
# --------------------------------------------------------------------------

# Tope del estándar Agent Skills, en CARACTERES. Es también el que aplican
# ChatGPT (Skills), claude.ai y la Skills API, y lo aplican como error duro.
MAX_DESCRIPTION_CHARS = 1024

# Los presupuestos POR DESTINO (en BYTES UTF-8, no en caracteres: en español un
# acento ocupa dos y una raya tres, así que contar letras engaña por un 2-3%) ya
# no son constantes de este fichero: se derivan de los perfiles de exporter/targets/
# con presupuesto_de(), el más restrictivo de los destinos que van a usar ese
# artefacto. Añadir un destino es escribir un JSON, no tocar esta lista, y añadir
# un MODO de instalación nuevo tampoco: perfiles_por_artefacto() reparte por lo
# que el perfil declara, no por una lista de modos escrita a mano.
# ChatGPT y claude.ai no necesitan presupuesto propio: su tope es el del estándar
# (1024 caracteres) y el zip ya viaja con la descripción de 850 bytes, que cabe de
# sobra. Por eso el mismo .zip de Perplexity sirve para los tres sin reexportar.
SOFT_BODY_TOKENS = 5000           # cuerpo recomendado del SKILL.md
CHARS_PER_TOKEN = 4               # estimación grosera

# Claves de frontmatter que NO son del estándar abierto y se retiran al exportar.
CLAUDE_ONLY_KEYS = {
    "allowed-tools", "allowed_tools", "disable-model-invocation",
    "model", "argument-hint", "user-invocable", "context",
}

# Claves escalares del estándar Agent Skills que se conservan tal cual.
# El conjunto del estándar es CERRADO: name, description, license,
# compatibility, metadata y allowed-tools. Cualquier otra clave al nivel
# superior hace que el destino rechace la skill con ERROR DURO —claude.ai y la
# Skills API responden "Unexpected key(s) in SKILL.md frontmatter"— en vez de
# ignorarla. `allowed-tools` es del estándar pero se retira igualmente porque su
# semántica es de Claude y no significa nada fuera (ver CLAUDE_ONLY_KEYS).
PORTABLE_KEYS = ["name", "description", "license", "compatibility"]

# Claves que NO son del estándar pero cuyo valor merece conservarse: se anidan
# bajo `metadata`, el cajón que la spec reserva para datos propios del autor.
# `version` vivía en PORTABLE_KEYS y se emitía al nivel superior, así que TODA
# skill exportada fallaba al subirse. `metadata` también estaba en la lista pero
# nunca sobrevivía: el filtro exigía valores str y un mapa no lo es.
# `depends` es una lista YAML (`depends: [- una, - otra]`), no un str: el mismo
# filtro la dejaba fuera en silencio pese a que references/portabilidad.md
# prometía que se conservaba. write_skill_md() sabe emitir listas anidadas
# bajo metadata, así que aquí basta con no descartarlas.
KEYS_A_METADATA = ["version", "depends"]


# --------------------------------------------------------------------------
# Modelo
# --------------------------------------------------------------------------

@dataclass
class Finding:
    severity: str
    code: str
    message: str


@dataclass
class SkillResult:
    src_dir: Path
    name: str
    orig_name: str
    description: str
    findings: list = field(default_factory=list)
    adaptations: list = field(default_factory=list)
    extra_files: list = field(default_factory=list)
    # Las dos variantes de la descripción: cada destino tiene su presupuesto.
    desc_folder: str = ""     # carpeta descomprimida → Mistral
    desc_zip: str = ""        # contenido del .zip → Perplexity
    body: str = ""
    fm_extra: dict = field(default_factory=dict)
    fm_meta: dict = field(default_factory=dict)
    # Señales detectadas en toda la skill (SKILL.md adaptado + resto del árbol).
    # Alimentan a_skill_portatil(), que las pasa al motor de compatibilidad.
    senales: list = field(default_factory=list)

    @property
    def worst(self) -> str:
        for s in ("alta", "media", "baja"):
            if any(f.severity == s for f in self.findings):
                return s
        return "ninguna"


# --------------------------------------------------------------------------
# Descubrimiento
# --------------------------------------------------------------------------

# IGNORED_DIRS vive en exporter.deteccion: es el mismo conjunto que
# detectar_en_arbol() debe podar para no auditar ficheros que este modulo
# nunca copia al paquete (ver copiar_skill() mas abajo).


def discover_skills(root: Path) -> list:
    """Encuentra directorios de skill (los que contienen SKILL.md), sin anidar."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        names = {f.lower(): f for f in filenames}
        if "skill.md" in names:
            found.append(Path(dirpath) / names["skill.md"])
            dirnames[:] = []  # no descender: subcarpetas pertenecen a esta skill
    return sorted(found)


def sanitize_name(raw: str) -> str:
    n = re.sub(r"[^a-z0-9\-]+", "-", str(raw).strip().lower())
    n = re.sub(r"-{2,}", "-", n).strip("-")
    return n[:64] or "skill"


def nombre_publicado(skill_md: Path) -> str:
    """El identificador con el que la skill sale al mundo.

    Sale del `name` del frontmatter, NO del nombre de la carpeta, y de el
    cuelgan el nombre del zip, el de la carpeta exportada y las claves de
    `evaluaciones` y `bloqueos`. audit_and_adapt lo vuelve a calcular igual;
    aqui hace falta antes, para poder comprobar la unicidad sin haber escrito
    todavia nada.
    """
    fm, _raw_fm, _body = split_frontmatter(
        skill_md.read_text(encoding="utf-8", errors="replace"))
    return sanitize_name(str(fm.get("name") or skill_md.parent.name))


def _relativa(ruta: Path, raiz: Path) -> str:
    try:
        return str(Path(ruta).relative_to(raiz)).replace(os.sep, "/")
    except ValueError:
        return str(ruta)


def comprobar_nombres_unicos(skill_files, raiz: Path) -> None:
    """Aborta si dos skills reclaman el mismo nombre publicado.

    Sin esto, la segunda skill machacaba los artefactos de la primera y solo
    salia UN zip, mientras el informe y resumen.json seguian declarando dos.
    Y lo mas grave no era eso: `evaluaciones` y `bloqueos` son diccionarios
    con esa clave, asi que el veredicto de seguridad de una skill se
    atribuia a la otra -una skill limpia se quedaba sin escribir porque otra,
    sucia, se llamaba igual-.

    Se aborta en vez de desambiguar sola. Renombrar en silencio produciria un
    artefacto con un nombre que el autor no eligio, y quien lo subiera a otra
    plataforma acabaria publicando una skill que no reconoce.
    """
    por_nombre = {}
    for sf in skill_files:
        por_nombre.setdefault(nombre_publicado(sf), []).append(sf.parent)
    colisiones = {n: ds for n, ds in por_nombre.items() if len(ds) > 1}
    if not colisiones:
        return

    lineas = [t("error.nombres_duplicados.cabecera")]
    for nombre, dirs in sorted(colisiones.items()):
        lineas.append(t("error.nombres_duplicados.linea", nombre=nombre,
                        directorios=", ".join(sorted(_relativa(d, raiz) for d in dirs))))
    lineas.append(
        t("error.nombres_duplicados.pie"))
    sys.exit("\n".join(lineas))


# --------------------------------------------------------------------------
# Auditoría y adaptación
# --------------------------------------------------------------------------

def audit_and_adapt(skill_md: Path, out_dir: Path, presupuesto_carpeta: int,
                    presupuesto_zip: int, reorder: bool = True) -> SkillResult:
    src_dir = skill_md.parent
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    fm, _raw_fm, body = split_frontmatter(text)

    orig_name = str(fm.get("name") or src_dir.name)
    name = sanitize_name(orig_name)
    res = SkillResult(src_dir=src_dir, name=name, orig_name=orig_name,
                      description=str(fm.get("description") or ""))

    if not fm:
        res.findings.append(Finding("alta", "sin-frontmatter",
            t("portabilidad.sin-frontmatter")))
    if not res.description:
        res.findings.append(Finding("alta", "sin-description",
            t("portabilidad.sin-description")))
        res.description = t("portabilidad.descripcion-pendiente", carpeta=src_dir.name)
    if name != orig_name:
        res.adaptations.append(t("adaptacion.nombre", original=orig_name, nuevo=name))
    if sanitize_name(src_dir.name) != name:
        res.findings.append(Finding("media", "nombre-vs-carpeta",
            t("portabilidad.nombre-vs-carpeta", nombre=name, carpeta=src_dir.name)))

    # Orden de la descripción: primero CUÁNDO cargarla, después qué hace.
    # Va ANTES del recorte a propósito: si hay que cortar, se pierde lo prescindible.
    if reorder:
        reordered, moved = reorder_description(res.description)
        if moved:
            res.description = reordered
            res.adaptations.append(
                t("adaptacion.descripcion-reordenada"))
    if not tiene_activacion(res.description):
        res.findings.append(Finding("alta", "description-sin-activacion",
            t("portabilidad.description-sin-activacion")))

    # Una descripción por destino: no comparten presupuesto, así que no comparten texto.
    origen_bytes = nbytes(res.description)
    if reorder:
        res.desc_folder = clamp_description(
            compact_description(res.description, presupuesto_carpeta), presupuesto_carpeta)
        res.desc_zip = clamp_description(
            compact_description(res.description, presupuesto_zip), presupuesto_zip)
    else:
        res.desc_folder = clamp_description(res.description, presupuesto_carpeta)
        res.desc_zip = clamp_description(res.description, presupuesto_zip)
    res.description = res.desc_zip   # la que se muestra en el informe

    if origen_bytes > presupuesto_carpeta:
        res.adaptations.append(
            t("adaptacion.descripcion-ajustada", origen_bytes=origen_bytes,
              zip_bytes=nbytes(res.desc_zip), tope_zip=presupuesto_zip,
              carpeta_bytes=nbytes(res.desc_folder), tope_carpeta=presupuesto_carpeta))
    if origen_bytes > presupuesto_zip:
        res.findings.append(Finding("media", "description-larga",
            t("portabilidad.description-larga", bytes=origen_bytes)))
    elif origen_bytes > presupuesto_carpeta:
        res.findings.append(Finding("baja", "description-densa",
            t("portabilidad.description-densa", bytes=origen_bytes,
              presupuesto=presupuesto_carpeta)))

    # Claves no portables
    dropped = [k for k in fm if k in CLAUDE_ONLY_KEYS]
    if dropped:
        res.adaptations.append(t("adaptacion.claves-retiradas",
                                 claves=", ".join(sorted(dropped))))

    # Adaptación de rutas ANTES de auditar, para no avisar de lo que ya se arregló.
    new_body = re.sub(r"\$\{?CLAUDE_PLUGIN_ROOT\}?/skills/[a-zA-Z0-9_\-]+/", "", body)
    new_body = re.sub(r"\$\{?CLAUDE_PLUGIN_ROOT\}?/", "", new_body)
    if new_body != body:
        res.adaptations.append(t("adaptacion.rutas-plugin-root"))
        body = new_body

    # Patrones problemáticos en todo el árbol de la skill (SKILL.md, references/,
    # scripts/, y cualquier otro fichero de texto), no sólo en el cuerpo.
    #
    # El SKILL.md se audita sobre el cuerpo YA ADAPTADO, y el resto del arbol
    # desde disco. La razon esta en el orden que ya seguia este fichero:
    # adaptar antes de auditar, para no avisar de lo que uno mismo acaba de
    # arreglar. La reescritura de ${CLAUDE_PLUGIN_ROOT} solo alcanza al cuerpo
    # del SKILL.md, asi que en references/ y scripts/ ese patron SI es un
    # riesgo real y debe seguir avisando.
    #
    # `body` ya no empieza en la linea 1 del fichero real: split_frontmatter()
    # se lo quito. detectar() numera desde 1 salvo que se le diga cuanto se
    # quito, o cada senal del SKILL.md sale con un numero de linea que no es
    # el que tiene el fichero de verdad -el offset se mide por diferencia de
    # lineas totales porque sobrevive a las reescrituras de arriba, que
    # cambian texto DENTRO de una linea pero nunca el numero de lineas-.
    offset_skill_md = len(text.splitlines()) - len(body.splitlines())
    # Se excluye por el nombre REAL del fichero descubierto, no por el
    # literal "SKILL.md": discover_skills acepta cualquier capitalizacion
    # (`names = {f.lower(): f ...}`), asi que un `skills/x/skill.md` no casaba
    # con el literal y acababa auditandose dos veces -una vez el cuerpo ya
    # adaptado y otra el fichero crudo de disco-. La senal del fichero crudo
    # senalaba ademas un problema que la adaptacion ya habia corregido.
    del_arbol, ilegibles_al_leer = detectar_en_arbol(
        src_dir, excluir={skill_md.name})
    senales = detectar(body, "SKILL.md", offset=offset_skill_md) + del_arbol
    res.senales = senales
    for s in senales:
        res.findings.append(Finding(s.severidad_base, s.id,
                                    t("portabilidad.senal",
                                      explicacion=t("senal." + s.id),
                                      ubicacion=s.ubicacion, muestra=s.muestra)))

    tools_used = sorted({tool for tool in CLAUDE_TOOL_NAMES
                        if re.search(rf"\b{tool}\b", body)})
    if tools_used:
        res.findings.append(Finding("media", "herramientas-claude",
            t("portabilidad.herramientas-claude", herramientas=", ".join(tools_used))))

    # Tamaño del cuerpo
    est_tokens = len(body) // CHARS_PER_TOKEN
    if est_tokens > SOFT_BODY_TOKENS:
        res.findings.append(Finding("baja", "cuerpo-largo",
            t("portabilidad.cuerpo-largo", tokens=est_tokens, limite=SOFT_BODY_TOKENS)))

    # ---- Escritura ----
    dest = out_dir / name
    if dest.exists():
        shutil.rmtree(dest)
    # Igual que arriba: por el nombre real, no por el literal. write_skill_md
    # escribe siempre el nombre canonico en mayusculas, asi que copiar ademas
    # el original metia en el paquete una segunda copia SIN adaptar. En un
    # sistema de ficheros sensible a mayusculas -Linux- el artefacto salia
    # con `SKILL.md` y `skill.md` a la vez (comprobado sobre un volumen APFS
    # sensible a mayusculas); en macOS los dos nombres colapsaban en uno y el
    # paquete se quedaba sin ningun `SKILL.md`.
    enlaces, ilegibles_al_copiar = copiar_skill(
        src_dir, dest, ignorar=set(IGNORED_DIRS) | {skill_md.name})
    for s in enlaces:
        res.findings.append(Finding("alta", "enlace-simbolico",
            t("portabilidad.enlace-simbolico", ubicacion=s.ubicacion, destino=s.muestra)))

    # Un fichero que no se pudo abrir no es un fichero limpio: nadie ha
    # mirado lo que contiene y, al no poder copiarlo, tampoco esta en el
    # artefacto. Callarlo dejaria el informe afirmando por omision que se
    # reviso un arbol que no se reviso entero -el mismo silencio que el
    # Bloque B viene a corregir en el motor de seguridad-.
    #
    # Las dos fases que leen el arbol (la deteccion de senales y la copia)
    # pueden tropezar con el mismo fichero, asi que se deduplica por ruta: a
    # quien lea el informe le importa que fichero se quedo fuera, no en cual
    # de las dos pasadas fallo la lectura.
    ilegibles = {}
    for ruta_ileg, motivo in list(ilegibles_al_leer) + list(ilegibles_al_copiar):
        ilegibles.setdefault(str(ruta_ileg).replace(os.sep, "/"), motivo)
    for ruta_ileg, motivo in sorted(ilegibles.items()):
        res.findings.append(Finding("media", "fichero-ilegible",
            t("portabilidad.fichero-ilegible", ruta=ruta_ileg, motivo=motivo)))

    for p in sorted(dest.rglob("*")):
        if p.is_file():
            res.extra_files.append(str(p.relative_to(dest)))
    if any(f.startswith("scripts/") for f in res.extra_files):
        res.findings.append(Finding("media", "scripts",
            t("portabilidad.scripts")))

    res.body = body
    res.fm_extra = {k: fm[k] for k in PORTABLE_KEYS
                    if k not in ("name", "description")
                    and isinstance(fm.get(k), str) and fm.get(k)}

    # Lo que no es del estándar pero vale la pena conservar baja a `metadata`,
    # fusionado con el `metadata` de origen si lo hubiera. Sin esto, `version`
    # salía al nivel superior y el destino rechazaba la skill entera.
    meta = {}
    if isinstance(fm.get("metadata"), dict):
        meta.update({str(k): str(v) for k, v in fm["metadata"].items()})
    bajadas = []
    for k in KEYS_A_METADATA:
        v = fm.get(k)
        if isinstance(v, str) and v:
            meta.setdefault(k, v)
            bajadas.append(k)
        elif isinstance(v, list) and v:
            meta.setdefault(k, list(v))
            bajadas.append(k)
    if meta:
        res.fm_meta = meta
    if bajadas:
        res.adaptations.append(
            t("adaptacion.claves-a-metadata", claves=", ".join(bajadas)))
    # La carpeta en disco es la variante de Mistral; el zip se reescribe al empaquetar.
    write_skill_md(res, dest, res.desc_folder)
    return res


def write_skill_md(res: SkillResult, dest: Path, description: str) -> None:
    """Escribe el SKILL.md con la descripción que corresponda al destino."""
    fm_out = {"name": res.name, "description": description}
    fm_out.update(res.fm_extra)
    lines = ["---"] + [f"{k}: {yaml_escape(v)}" for k, v in fm_out.items()]
    # `metadata` es un mapa, no un escalar: va como bloque anidado. Un valor
    # que sea lista (p. ej. `depends`) se anida a su vez como lista YAML: no
    # se aplana a texto porque `parse_simple_yaml` sabe leer justo esa forma.
    if res.fm_meta:
        lines.append("metadata:")
        for k, v in res.fm_meta.items():
            if isinstance(v, list):
                lines.append(f"  {k}:")
                lines += [f"    - {yaml_escape(item)}" for item in v]
            else:
                lines.append(f"  {k}: {yaml_escape(v)}")
    lines.append("---")
    (dest / "SKILL.md").write_text(
        "\n".join(lines) + "\n" + res.body.rstrip() + render_notes(res), encoding="utf-8")


def render_notes(res: SkillResult) -> str:
    """Aviso incrustado en el SKILL.md. Sólo se emite si hay algo que decir."""
    blocking = [f for f in res.findings if f.severity == "alta"]
    degraded = [f for f in res.findings if f.severity == "media"]
    if not (res.adaptations or blocking or degraded):
        return "\n"

    out = ["\n\n---\n", "## Notas de portabilidad (añadidas automáticamente)\n",
           "Esta skill se exportó desde un plugin de Claude al estándar abierto Agent Skills.\n"]
    if res.adaptations:
        out.append("**Cambios aplicados al exportar:**\n")
        out += [f"- {a}" for a in res.adaptations]
        out.append("")
    if blocking:
        out.append("**Probablemente no funcione en este entorno:**\n")
        out += [f"- {f.message}" for f in blocking]
        out.append("")
    if degraded:
        out.append("**Funcionará, pero con limitaciones:**\n")
        out += [f"- {f.message}" for f in degraded]
        out.append("")
    if blocking or degraded:
        out.append("Si una instrucción de esta skill depende de una herramienta que no tienes "
                   "disponible, dilo explícitamente y propón una alternativa. No simules el "
                   "resultado ni lo inventes.\n")
    return "\n".join(out) + "\n"


def a_skill_portatil(res: SkillResult) -> SkillPortatil:
    """Convierte el SkillResult del conversor en el modelo intermedio.

    Puente temporal: SkillResult existe desde antes del modelo y sigue siendo
    lo que manejan audit_and_adapt y el empaquetado.
    """
    skill = SkillPortatil(
        nombre=res.name, nombre_original=res.orig_name, carpeta=str(res.src_dir),
        descripcion=res.description, descripcion_bytes=nbytes(res.description),
        tiene_activacion=tiene_activacion(res.description),
        cuerpo_tokens=len(res.body) // CHARS_PER_TOKEN,
        ficheros=list(res.extra_files),
        tiene_scripts=any(f.startswith("scripts/") for f in res.extra_files),
        senales=list(res.senales), adaptaciones=list(res.adaptations))
    skill.capacidades = capacidades_de(skill.senales, skill.tiene_scripts)
    return skill


def auditar_seguridad(raiz, dirs_skill) -> VeredictoSeguridad:
    """Audita el paquete entero: patrones, estructura y veredicto."""
    ficheros = recorrer(raiz, dirs_skill)
    hallazgos = seg_patrones.analizar(ficheros, seg_patrones.cargar_reglas())
    hallazgos += seg_estructural.analizar(raiz, ficheros)
    # `opaco` se deriva de los HALLAZGOS, no del recorrido. Si se activara
    # con cualquier fichero binario, un repositorio impecable con un logo
    # citado en el README saldria `no_evaluable` con la lista de hallazgos
    # vacia: un veredicto sin nada que lo justifique, que es justo lo que
    # prohibe el criterio de aceptacion 9. Un binario que nadie documenta SI
    # produce hallazgo, y por ahi entra en la cuenta.
    #
    # SEC-ILEGIBLE-001 es la tercera fuente y la mas literal de las tres: un
    # fichero que no se ha podido abrir es contenido del que no se sabe
    # nada. Faltaba, y su ausencia era parte de por que `no_evaluable` no
    # llegaba a significar lo que promete su nombre.
    opaco = any(h.id in ("SEC-ARCHIVO-ANIDADO-001", "SEC-BINARIO-NO-DOCUMENTADO-001",
                         "SEC-ILEGIBLE-001")
                for h in hallazgos)
    return seg_riesgo.evaluar(hallazgos, opaco)


def bloqueo_para(carpeta_skill: str, veredicto):
    """El bloqueo de una skill, si lo hay.

    Las tres condiciones son necesarias. La de confianza tanto como las
    otras: un patron de confianza baja puede estar ahi por una razon
    legitima —una skill que DOCUMENTA un ataque es el caso obvio— y negarse
    a escribir por una sospecha debil convierte el gate en un obstaculo que
    la gente aprende a saltarse sin leer.
    """
    carpeta = str(carpeta_skill).replace(os.sep, "/").strip("/")
    # `Path(src_dir).relative_to(root)` devuelve "." cuando el origen ES el
    # directorio de la skill (un repositorio de una sola skill con el
    # SKILL.md en la raiz, que discover_skills si descubre). El prefijo
    # vacio hace que toda ruta pertenezca a esa skill, que es lo correcto.
    prefijo = "" if carpeta in ("", ".") else carpeta + "/"
    for h in veredicto.hallazgos:
        if h.ambito != "exportado":
            continue
        if h.severidad not in ("alta", "critica"):
            continue
        if h.confianza not in ("alta", "media"):
            continue
        fichero, _, linea = h.ubicacion.rpartition(":")
        if not fichero.startswith(prefijo):
            continue
        return Bloqueo(regla_id=h.id, severidad=h.severidad,
                       fichero=fichero, linea=int(linea))
    return None


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

# Limites defensivos sobre lo que se acepta analizar. No se descomprime nada
# ni se ejecuta nada, pero un repositorio absurdo puede agotar el disco.
MAX_BYTES_REPO = 200 * 1024 * 1024
MAX_FICHEROS_REPO = 20000
TIMEOUT_CLON = 300


def comprobar_tamano(raiz: Path) -> None:
    """Aborta si el arbol excede los limites. No sigue enlaces."""
    total, n = 0, 0
    for base, dirs, ficheros in os.walk(str(raiz)):
        dirs[:] = [d for d in dirs
                   if d != ".git" and not os.path.islink(os.path.join(base, d))]
        for nombre in ficheros:
            ruta = os.path.join(base, nombre)
            if os.path.islink(ruta):
                continue
            n += 1
            total += os.path.getsize(ruta)
            if n > MAX_FICHEROS_REPO:
                sys.exit(t("error.origen_demasiados_ficheros", limite=MAX_FICHEROS_REPO))
            if total > MAX_BYTES_REPO:
                sys.exit(t("error.origen_demasiado_grande",
                           limite=MAX_BYTES_REPO // (1024 * 1024)))


# Marca de propiedad del directorio de salida. `export` la escribe nada mas
# crear <out>, no al terminar: si una ejecucion se interrumpe a la mitad, el
# directorio sigue siendo reconocible como propio y la siguiente ejecucion
# puede limpiarlo sin exigir --force. Escribirla solo al final dejaria al
# usuario un destino a medio escribir que la herramienta ya no se atreve a
# tocar, es decir, un roto que ella misma ha causado.
NOMBRE_CENTINELA = ".cse-salida"

TEXTO_CENTINELA = (
    "Directorio de salida de claude-skills-exporter (convert.py export --out).\n"
    "Su contenido se borra y se regenera entero en cada exportación.\n"
    "Si borras este fichero, la herramienta dejará de reconocer el directorio\n"
    "como suyo y se negará a sobrescribirlo sin --force.\n"
)


def _cuelga_de(hijo: Path, padre: Path) -> bool:
    """True si `hijo` esta dentro de `padre`, o es el mismo `padre`.

    Path.is_relative_to no existe hasta Python 3.9 y aqui el minimo es 3.8.
    """
    try:
        hijo.relative_to(padre)
    except ValueError:
        return False
    return True


def es_salida_propia(out: Path) -> bool:
    """True si <out> puede vaciarse sin preguntar.

    Lo es si no existe, si esta vacio, o si lleva la marca que escribe esta
    herramienta. Un fichero suelto donde se esperaba un directorio no lo es.
    """
    if not out.exists():
        return True
    if not out.is_dir():
        return False
    if (out / NOMBRE_CENTINELA).exists():
        return True
    return not any(out.iterdir())


def comprobar_salida_segura(out: Path, src: str, forzar: bool) -> None:
    """Aborta antes de que `export` vacie un <out> que no ha escrito el.

    Se ejecuta ANTES del rmtree y ANTES de resolve_source: el fallo mas caro
    de esta herramienta consistia en borrar el destino y descubrir despues
    que el origen no servia para nada.
    """
    p_origen = Path(src).expanduser()
    # Un origen que no existe como ruta es una URL: se clonara en un temporal
    # y no hay ningun arbol del usuario con el que <out> pueda solaparse.
    origen = p_origen.resolve() if p_origen.exists() else None

    if origen is not None:
        # Estos dos casos no los salta ni --force. No son "borrar algo
        # valioso" sino "borrar la propia entrada": aunque dejaramos hacerlo,
        # el export destruiria el arbol que iba a leer y terminaria sin
        # encontrar ningun SKILL.md. Ofrecer --force ahi seria mentir.
        #
        # El caso simetrico -<out> DENTRO del origen- si esta permitido, y a
        # proposito: `export . --out ./salida` solo borra ./salida, el origen
        # sobrevive entero y el export funciona. Es ademas la forma del --out
        # por defecto y la que usan varias pruebas. La version peligrosa de
        # esa misma forma (`--out ./scripts`, sobre un directorio del propio
        # repositorio) ya la para la comprobacion de propiedad de abajo, que
        # no mira donde esta <out> sino si lo escribimos nosotros.
        if out == origen:
            sys.exit(
                t("error.out_es_origen", ruta=out))
        if _cuelga_de(origen, out):
            sys.exit(
                t("error.origen_dentro_de_out", origen=origen, ruta=out))

    if not forzar and not es_salida_propia(out):
        motivo = t("error.out_no_vacio" if out.is_dir() else "error.out_no_directorio")
        sys.exit(
            t("error.out_no_propio", ruta=out, motivo=motivo, marca=NOMBRE_CENTINELA))


def resolve_source(src: str, workdir: Path) -> Path:
    p = Path(src).expanduser()
    if p.exists():
        comprobar_tamano(p.resolve())
        return p.resolve()
    if not re.match(r"^(https?://|git@)", src):
        sys.exit(t("error.origen_invalido", origen=src))
    target = workdir / "repo"
    print(t("consola.clonando", origen=src))
    entorno = dict(os.environ)
    # Sin esto, un repositorio privado deja el proceso colgado esperando
    # credenciales que nadie va a teclear.
    entorno["GIT_TERMINAL_PROMPT"] = "0"
    try:
        r = subprocess.run(
            ["git", "clone", "--depth", "1", "--no-recurse-submodules", src, str(target)],
            capture_output=True, text=True, env=entorno, timeout=TIMEOUT_CLON)
    except subprocess.TimeoutExpired:
        sys.exit(t("error.clon_timeout", segundos=TIMEOUT_CLON))
    if r.returncode != 0:
        sys.exit(t("error.clon_fallo", salida=r.stderr.strip()))
    comprobar_tamano(target)
    return target


SUBCOMANDOS = ("inspect", "audit", "export")


def normalizar_argv(argv: list) -> list:
    """Antepone `export` cuando el primer argumento es un origen suelto.

    `convert.py <repo>` funcionaba antes de que existieran los subcomandos, y
    lo usan el «Paso 0» del SKILL.md, el comando /exportar-skills y el
    workflow de CI. Romperlo llegaría a todo el que tenga el plugin
    instalado en el mismo push, porque el marketplace está en autosync.
    """
    if not argv or argv[0] in SUBCOMANDOS or argv[0].startswith("-"):
        return list(argv)
    return ["export"] + list(argv)


def construir_parser():
    ap = argparse.ArgumentParser(
        prog="convert.py",
        description="Audita y exporta skills de un plugin de Claude al estándar "
                    "abierto Agent Skills.")
    subs = ap.add_subparsers(dest="comando", required=True)

    def comun(p):
        p.add_argument("source", help="URL del repositorio o ruta local")
        p.add_argument("--fail-on", dest="fail_on", default="ninguno",
                       choices=["ninguno", "degradado", "no_compatible"],
                       help="devolver código 2 si algún estado alcanza este umbral")
        p.add_argument("--lang", dest="lang", default=None, metavar="CODIGO",
                       help="idioma de los informes y mensajes: es (por defecto), en, fr, "
                            "o auto para usar el del sistema. También se lee de la "
                            "variable CSE_LANG")
        return p

    ins = comun(subs.add_parser(
        "inspect", help="qué contiene y qué exige la skill, sin elegir destino"))
    ins.add_argument("--keep-description-order", action="store_true",
                     help="no reordenar la descripción")

    aud = comun(subs.add_parser(
        "audit", help="matriz de compatibilidad; no escribe paquetes"))
    aud.add_argument("--target", nargs="*", default=None,
                     help="destinos a auditar (por defecto, todos)")
    aud.add_argument("--keep-description-order", action="store_true",
                     help="no reordenar la descripción")

    exp = comun(subs.add_parser("export", help="auditar y empaquetar"))
    exp.add_argument("--target", nargs="*", default=None,
                     help="restringe qué artefactos se producen; la auditoría "
                          "sigue cubriendo todos los destinos")
    exp.add_argument("--out", default="./dist-agentskills",
                     help="directorio de salida; SE BORRA ENTERO antes de escribir")
    exp.add_argument("--force", action="store_true",
                     help="vaciar el directorio de salida aunque no lo haya escrito "
                          "esta herramienta (pierdes lo que hubiera dentro)")
    exp.add_argument("--only", nargs="*", default=None,
                     help="exportar sólo estas skills; vale tanto el nombre de la "
                          "carpeta como el 'name' del frontmatter, que es el que "
                          "llevan el informe y los artefactos")
    exp.add_argument("--zip-only", action="store_true",
                     help="dejar sólo los .zip (pierdes la variante de carpeta)")
    exp.add_argument("--keep-description-order", action="store_true",
                     help="no reordenar la descripción")
    # Sólo en `export`: es la única rama que escribe artefactos y, por tanto,
    # la única que puede bloquear. `audit` no tiene nada que anular.
    exp.add_argument("--anular-revision-seguridad", dest="anular_seguridad",
                     action="store_true",
                     help="exportar aunque haya hallazgos de seguridad que bloqueen; "
                          "queda constancia escrita en el informe")
    return ap


def codigo_por_umbral(evaluaciones, umbral: str) -> int:
    if umbral == "ninguno":
        return 0
    limite = Estado.ORDEN.index(
        Estado.DEGRADADO if umbral == "degradado" else Estado.NO_COMPATIBLE)
    for por_destino in evaluaciones.values():
        for evs in por_destino.values():
            for ev in evs:
                if Estado.ORDEN.index(ev.estado) >= limite:
                    return 2
    return 0


def imprimir_inspect(skill) -> None:
    """Vuelca el modelo intermedio: lo que la skill es y exige, sin destino."""
    print("\n## {}".format(skill.nombre))
    if skill.nombre != skill.nombre_original:
        print(t("consola.inspect.nombre_original", nombre=skill.nombre_original))
    print(t("consola.inspect.descripcion", bytes=skill.descripcion_bytes,
            aviso="" if skill.tiene_activacion else t("consola.inspect.sin_activacion")))
    print(t("consola.inspect.cuerpo", tokens=skill.cuerpo_tokens))
    print(t("consola.inspect.ficheros", n=len(skill.ficheros),
            extra=t("consola.inspect.incluye_scripts") if skill.tiene_scripts else ""))

    if skill.capacidades:
        print(t("consola.inspect.capacidades"))
        for c in skill.capacidades:
            print("     · {:<24} {}".format(c.nombre, c.nivel))
    else:
        print(t("consola.inspect.capacidades_ninguna"))

    if skill.senales:
        print(t("consola.inspect.senales"))
        for s in skill.senales:
            print("     · {:<20} {}  {}".format(s.id, s.ubicacion, s.muestra))
    else:
        print(t("consola.inspect.senales_ninguna"))

    ambiguo = [c.nombre for c in skill.capacidades if c.nivel == "requerida"]
    if ambiguo and not skill.tiene_activacion:
        print(t("consola.inspect.ambiguo"))


def obtener_fecha_hoy() -> datetime.date:
    """La fecha de 'hoy' para toda la evaluación de compatibilidad.

    `CSE_FECHA` (ISO AAAA-MM-DD) la fija: la usan los golden files y las
    pruebas de reproducibilidad, que necesitan una fecha estable para no
    depender del día en que se ejecute la suite -de lo contrario, en cuanto
    la fecha real supere un `revisar_tras` de un perfil, los veredictos
    cambian de `compatible` a `no_verificable` y el CI se pone en rojo sin
    que nadie haya tocado una línea de código-. Sin la variable, se usa la
    fecha real del sistema.
    """
    bruta = os.environ.get("CSE_FECHA")
    if not bruta:
        return datetime.date.today()
    try:
        return datetime.date.fromisoformat(bruta)
    except ValueError:
        sys.exit(
            t("error.fecha_invalida", valor=bruta))


# El unico modo que no necesita ningun artefacto propio: el destino se
# instala apuntando a la URL del repositorio.
MODOS_SIN_ARTEFACTO = {"url_repositorio"}


def perfiles_por_artefacto(perfiles, elegidos):
    """Que destinos se sirven de cada uno de los dos artefactos.

    Devuelve `(ids_del_zip, ids_de_la_carpeta)`, ya restringidos a los
    destinos elegidos. `carpeta` es cualquier modo que produzca un
    directorio en disco, sea cual sea su nombre: `carpeta` en Mistral,
    `directorio_local` en Claude Code, y el que venga despues.
    """
    ids = sorted(elegidos) if elegidos else sorted(perfiles)
    del_zip = [i for i in ids if "zip" in perfiles[i].modos()]
    de_carpeta = [i for i in ids
                  if set(perfiles[i].modos()) - {"zip"} - MODOS_SIN_ARTEFACTO]
    return del_zip, de_carpeta


def presupuesto_de(perfiles, ids) -> int:
    """El presupuesto mas restrictivo de esos destinos.

    Un artefacto es uno solo y tiene que valer para todos los destinos que lo
    usen, asi que manda el mas estrecho. Sin ninguno, el tope del estandar.
    """
    return min([perfiles[i].presupuesto() for i in ids],
               default=MAX_DESCRIPTION_CHARS)


def ejecutar(args, perfiles, elegidos, hoy) -> int:
    # Los presupuestos salen de los modos que REALMENTE declaran los perfiles
    # elegidos, no de las dos constantes "carpeta" y "zip". Con esas dos, un
    # modo nuevo caia en el cajon de `carpeta` sin decirlo: `--target
    # claude-code` -que instala en modo `directorio_local`, con un tope
    # propio de 1024 B- recibia el presupuesto de Mistral, 490, y se le
    # rotulaba «Mistral» en los mensajes finales. Era el punto donde el
    # codigo contradecia su propio comentario, que promete que todo se deriva
    # de los perfiles.
    ids_zip, ids_carpeta = perfiles_por_artefacto(perfiles, elegidos)
    presupuesto_carpeta = presupuesto_de(perfiles, ids_carpeta)
    presupuesto_zip = presupuesto_de(perfiles, ids_zip)

    out = None
    if args.comando == "export":
        out = Path(args.out).expanduser().resolve()
        # Lo primero de todo, antes del rmtree y antes de resolve_source.
        comprobar_salida_segura(out, args.source, getattr(args, "force", False))
        if out.is_dir():
            shutil.rmtree(out)
        elif out.exists():
            # Solo se llega aqui con --force: sin el, un fichero donde se
            # esperaba un directorio ya habria abortado la comprobacion.
            out.unlink()
        # Las carpetas de skill cuelgan directamente de <out>, al lado de su
        # zip: mismos ficheros, distinta descripción.
        out.mkdir(parents=True)
        (out / NOMBRE_CENTINELA).write_text(TEXTO_CENTINELA, encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp:
        root = resolve_source(args.source, Path(tmp))

        skill_files = discover_skills(root)
        if not skill_files:
            sys.exit(t("error.sin_skills"))

        print(t("consola.skills_encontradas", n=len(skill_files)))

        # Va aquí, antes del bucle de audit_and_adapt. Desde que los
        # artefactos se preparan en un temporal y no en `out`, el recorrido
        # ya no podría verlos aunque se calculara después; se mantiene el
        # orden porque sigue siendo el correcto -auditar el origen tal como
        # está, no como queda después de trabajar sobre él-, pero ha dejado
        # de ser una condición de la que dependa el veredicto.
        veredicto_seguridad = auditar_seguridad(
            root, [str(sf.parent.relative_to(root)) for sf in skill_files])

        # Los TRES subcomandos preparan sus artefactos en un temporal que
        # desaparece con este bloque. `export` no es una excepción: publica a
        # `out` despues, y solo lo que el gate haya aprobado.
        #
        # Antes `export` usaba `out` directamente como directorio de trabajo,
        # asi que audit_and_adapt escribia la skill entera en el destino
        # final antes de que el gate opinara. El gate no podia entonces
        # limitarse a no escribir: tenia que BORRAR lo ya escrito, y entre
        # una cosa y otra existia una ventana en la que el artefacto
        # peligroso estaba en el directorio que el usuario mira -y que puede
        # estar sincronizado con un servicio en la nube, o vigilado por otro
        # proceso-.
        work_dir = Path(tmp) / "_trabajo"
        work_dir.mkdir(parents=True, exist_ok=True)

        solo = getattr(args, "only", None)
        # --only acepta los DOS identificadores que tiene una skill, porque
        # los dos son visibles y ninguno es mas legitimo que el otro: quien
        # mira el disco ve la carpeta, y quien lee el informe o los
        # artefactos ve el nombre del frontmatter. Antes filtraba solo por la
        # carpeta, mientras que artefactos, evaluaciones y bloqueos se
        # indexaban por el del frontmatter, asi que `--only <nombre-que-el-
        # usuario-acaba-de-leer>` podia no encontrar nada.
        pedidas = {sanitize_name(x) for x in (solo or ())}
        seleccionadas = [
            sf for sf in skill_files
            if not solo or pedidas & {sanitize_name(sf.parent.name),
                                      nombre_publicado(sf)}]
        if not seleccionadas:
            sys.exit(
                t("error.only_sin_coincidencia", disponibles=", ".join(sorted({
                    "{} ({})".format(nombre_publicado(sf), sf.parent.name)
                    for sf in skill_files}))))

        # Antes del primer audit_and_adapt, que ya escribe en work_dir. La
        # comprobacion mira solo las skills SELECCIONADAS: si --only deja
        # fuera a una de las dos que colisionan, no hay colision que resolver.
        #
        # `inspect` se libra a proposito: no indexa nada por nombre -imprime
        # cada skill por separado y vuelve antes de construir `evaluaciones`-,
        # asi que no puede atribuir mal ningun veredicto. Y es justo el
        # comando al que uno acude para diagnosticar este problema: abortarlo
        # dejaria al usuario sin la herramienta que se lo enseña.
        if args.comando != "inspect":
            comprobar_nombres_unicos(seleccionadas, root)

        results = []
        for sf in seleccionadas:
            r = audit_and_adapt(sf, work_dir, presupuesto_carpeta, presupuesto_zip,
                                reorder=not args.keep_description_order)
            results.append(r)
            print(t("consola.skill_riesgo", nombre="{:<40}".format(r.name),
                    riesgo=r.worst))

        if args.comando == "inspect":
            for r in results:
                imprimir_inspect(a_skill_portatil(r))
            return 0

        # `hoy` ya llegó validado desde main(): CSE_FECHA se comprueba antes
        # de tocar disco, no aquí en medio del procesamiento.

        # `audit` respeta --target: es él quien decide qué destinos evaluar.
        # `export` NO: su --target sólo restringe qué artefactos se
        # escriben, la auditoría sigue cubriendo los cinco destinos.
        perfiles_informe = perfiles
        if args.comando == "audit" and elegidos:
            perfiles_informe = {pid: perfiles[pid] for pid in elegidos}

        evaluaciones = {}
        for r in results:
            skill = a_skill_portatil(r)
            evaluaciones[r.name] = {
                pid: evaluar(skill, perfil, hoy) for pid, perfil in perfiles_informe.items()
            }

        if args.comando == "audit":
            print()
            print(informe_markdown(results, evaluaciones, args.source,
                                   perfiles_informe, veredicto_seguridad))
            # `audit` no escribe nada, así que nunca devuelve 3 -no hay
            # artefacto que bloquear-. Pero sí refleja el nivel de riesgo: el
            # código 2 es lo que hace utilizable `audit` en un pre-commit o
            # en un pipeline ajeno. Es el camino que la documentación
            # recomienda antes de exportar, y un paquete crítico saliendo con
            # código 0 no serviría para lo que se recomienda.
            return codigo_por_umbral(evaluaciones, args.fail_on) or (
                0 if veredicto_seguridad.nivel == Nivel.BAJO else 2)

        # -------- export --------
        # Qué artefactos hacen falta: los mismos destinos de los que ya
        # salieron los presupuestos, arriba. Se derivan una sola vez para que
        # el presupuesto con el que se recorta una descripción y el rótulo
        # con el que se anuncia no puedan discrepar nunca.
        quiere_zip = bool(ids_zip)
        quiere_carpeta = bool(ids_carpeta)

        # El gate va aquí, DENTRO de `export`: `audit` no escribe nada, así
        # que no hay nada que bloquear, y sus evaluaciones deben conservar
        # bloqueo_seguridad=None — si no, la nota «Artefactos no escritos por
        # seguridad» del informe aparecería en una ejecución que ni siquiera
        # intentó escribirlos.
        bloqueos = {}
        for r in results:
            carpeta = str(Path(r.src_dir).relative_to(root)).replace(os.sep, "/")
            bloqueos[r.name] = bloqueo_para(carpeta, veredicto_seguridad)
        for nombre, por_destino in evaluaciones.items():
            for evs in por_destino.values():
                for ev in evs:
                    ev.bloqueo_seguridad = bloqueos.get(nombre)

        anulado = getattr(args, "anular_seguridad", False)
        bloqueadas = {n for n, b in bloqueos.items() if b is not None}

        # Un zip por skill, con la carpeta de la skill en la raíz del zip:
        # es la única estructura que Perplexity acepta.
        for r in results:
            # Ahora el `continue` basta: no hay nada escrito en `out` que
            # deshacer. Lo que el gate rechaza sencillamente no se publica, y
            # se queda en el temporal hasta que este bloque lo borre. Aquí
            # había un rmtree y un unlink que existían solo para limpiar lo
            # que audit_and_adapt ya había escrito en el destino final.
            if r.name in bloqueadas and not anulado:
                b = bloqueos[r.name]
                print(t("consola.bloqueado", skill=r.name, regla=b.regla_id,
                        fichero=b.fichero, linea=b.linea), file=sys.stderr)
                continue

            # Publicar: del temporal al destino final. `move` renombra cuando
            # los dos estan en el mismo sistema de ficheros y copia cuando no,
            # asi que no se paga una segunda copia del arbol sin necesidad.
            shutil.move(str(work_dir / r.name), str(out / r.name))

            if quiere_zip:
                write_skill_md(r, out / r.name, r.desc_zip)      # dentro del zip: Perplexity
                zip_dir(out / r.name, out / f"{r.name}.zip", arc_prefix=r.name)
                for pid, perfil in perfiles.items():
                    if "zip" not in perfil.modos():
                        continue
                    for aviso in comprobar_limites(out / "{}.zip".format(r.name), perfil):
                        r.findings.append(Finding("alta", "limite-de-paquete", aviso))
            if quiere_carpeta:
                write_skill_md(r, out / r.name, r.desc_folder)   # en disco: Mistral
            elif (out / r.name).exists():
                shutil.rmtree(out / r.name)

        if args.zip_only:
            for r in results:
                if (out / r.name).exists():
                    shutil.rmtree(out / r.name)

        (out / "INFORME-PORTABILIDAD.md").write_text(
            informe_markdown(results, evaluaciones, args.source, perfiles,
                             veredicto_seguridad, anulado=anulado),
            encoding="utf-8")
        (out / "resumen.json").write_text(
            json.dumps(resumen_json(results, evaluaciones, args.source,
                                    veredicto_seguridad),
                       ensure_ascii=False, indent=2),
            encoding="utf-8")

    # Los rótulos salen de los perfiles que de verdad usan cada artefacto, no
    # de dos nombres escritos a mano. Antes decian siempre «Perplexity» y
    # «Mistral», asi que un `--target claude-code` anunciaba un artefacto de
    # Mistral que Mistral no iba a recibir.
    etiquetas = lambda ids: ", ".join(perfiles[i].label for i in ids)   # noqa: E731
    print(t("consola.ok_salida", ruta=out))
    if quiere_zip:
        print(t("consola.ok.zip", destinos=etiquetas(ids_zip)))
        print(t("consola.ok.zip_detalle", n=len(results), presupuesto=presupuesto_zip))
    if quiere_carpeta:
        if args.zip_only:
            print(t("consola.ok.carpeta_borrada", presupuesto=presupuesto_carpeta,
                    destinos=etiquetas(ids_carpeta)))
        else:
            print(t("consola.ok.carpeta", destinos=etiquetas(ids_carpeta)))
            print(t("consola.ok.carpeta_detalle", presupuesto=presupuesto_carpeta))
    print(t("consola.ok.informe", archivo="INFORME-PORTABILIDAD.md"))
    riesgo = [r.name for r in results if r.worst == "alta"]
    if riesgo:
        print(t("consola.aviso_riesgo_alto", skills=", ".join(riesgo)))

    if bloqueadas and not anulado:
        return 3
    if anulado:
        # La anulacion es una decision consciente que YA queda escrita en el
        # informe. Devolver ademas !=0 despues de habersela pedido al usuario
        # solo ensena a ignorar el codigo de salida. Ademas es lo que permite
        # que tests/generar_golden.py, test_seg_golden.py,
        # .github/validar_reglas.py y el CI ejecuten la herramienta sobre
        # material deliberadamente sucio sin envolver cada llamada.
        return codigo_por_umbral(evaluaciones, args.fail_on)
    return codigo_por_umbral(evaluaciones, args.fail_on) or (
        0 if veredicto_seguridad.nivel == Nivel.BAJO else 2)


def main(argv=None) -> int:
    args = construir_parser().parse_args(normalizar_argv(
        sys.argv[1:] if argv is None else argv))

    # El idioma se fija antes que cualquier otra cosa: todo mensaje posterior,
    # incluidos los de error, ya sale en el idioma pedido. El error de idioma
    # desconocido es la excepcion: se da en espanol fijo, porque no hay
    # ningun idioma al que traducirlo.
    try:
        i18n.fijar_idioma(i18n.idioma_pedido(args.lang))
    except i18n.IdiomaDesconocido as e:
        print("[error] idioma desconocido: {}. Disponibles: {}".format(
            e.codigo, ", ".join("{} — {}".format(c, n)
                                for c, n in sorted(e.disponibles.items()))),
            file=sys.stderr)
        return 1

    # Se valida cuanto antes, antes de tocar disco: un CSE_FECHA invalido
    # debe abortar limpio, sin dejar un directorio de salida a medias.
    hoy = obtener_fecha_hoy()

    try:
        perfiles = cargar_perfiles()
    except PerfilInvalido as e:
        print(t("error.perfil_invalido", detalle=e), file=sys.stderr)
        return 1

    elegidos = getattr(args, "target", None)
    if elegidos:
        desconocidos = [d for d in elegidos if d not in perfiles]
        if desconocidos:
            print(t("error.destino_desconocido", desconocidos=", ".join(desconocidos),
                    disponibles=", ".join(sorted(perfiles))), file=sys.stderr)
            return 1

    if args.comando == "export" and getattr(args, "zip_only", False):
        # --zip-only borra la carpeta al final asumiendo que el zip la
        # sustituye. Si ninguno de los destinos elegidos instala en modo
        # 'zip' -mistral-vibe-work sólo admite 'carpeta'-, esa asuncion es
        # falsa: no se genera ningun zip y la carpeta se borra igual, y el
        # export termina sin dejar ningun artefacto de skill, solo el informe.
        modos = set()
        for pid in (elegidos if elegidos else perfiles):
            modos.update(perfiles[pid].modos())
        if "zip" not in modos:
            objetivo = ", ".join(sorted(elegidos)) if elegidos else "los destinos elegidos"
            print(
                t("error.zip_only_sin_zip", objetivo=objetivo),
                file=sys.stderr)
            return 1

    return ejecutar(args, perfiles, elegidos, hoy)


if __name__ == "__main__":
    sys.exit(main())
