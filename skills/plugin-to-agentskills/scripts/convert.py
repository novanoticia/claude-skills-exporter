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
from exporter.deteccion import CLAUDE_TOOL_NAMES, EXPLICACIONES, detectar, detectar_en_arbol
from exporter.empaquetado import comprobar_limites, copiar_skill, zip_dir
from exporter.frontmatter import split_frontmatter, yaml_escape
from exporter.informes import informe_markdown, resumen_json
from exporter.modelo import Estado, SkillPortatil, capacidades_de
from exporter.perfiles import PerfilInvalido, cargar_perfiles, presupuesto_por_modo

# --------------------------------------------------------------------------
# Límites y constantes del estándar Agent Skills
# --------------------------------------------------------------------------

# Tope del estándar Agent Skills, en CARACTERES. Es también el que aplican
# ChatGPT (Skills), claude.ai y la Skills API, y lo aplican como error duro.
MAX_DESCRIPTION_CHARS = 1024

# Los presupuestos POR DESTINO (en BYTES UTF-8, no en caracteres: en español un
# acento ocupa dos y una raya tres, así que contar letras engaña por un 2-3%) ya
# no son constantes de este fichero: se derivan de los perfiles de exporter/targets/
# con presupuesto_por_modo(), el más restrictivo de los destinos que aceptan ese
# modo de instalación. Añadir un destino es escribir un JSON, no tocar esta lista.
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

IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


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
            "SKILL.md no tiene bloque frontmatter YAML. Se generará uno mínimo; "
            "revisa el nombre y la descripción a mano."))
    if not res.description:
        res.findings.append(Finding("alta", "sin-description",
            "Falta 'description'. Es el campo que decide cuándo se activa la skill: "
            "sin él, Perplexity y Mistral casi nunca la cargarán."))
        res.description = f"Skill importada de {src_dir.name}. PENDIENTE: escribir descripción de activación."
    if name != orig_name:
        res.adaptations.append(f"Nombre normalizado: '{orig_name}' → '{name}'.")
    if sanitize_name(src_dir.name) != name:
        res.findings.append(Finding("media", "nombre-vs-carpeta",
            f"El nombre del frontmatter ('{name}') no coincidía con la carpeta "
            f"('{src_dir.name}'). Se exporta la carpeta con el nombre del frontmatter."))

    # Orden de la descripción: primero CUÁNDO cargarla, después qué hace.
    # Va ANTES del recorte a propósito: si hay que cortar, se pierde lo prescindible.
    if reorder:
        reordered, moved = reorder_description(res.description)
        if moved:
            res.description = reordered
            res.adaptations.append(
                "Descripción reordenada: las frases que dicen CUÁNDO cargar la skill se han "
                "puesto delante de las que describen qué hace. Es lo único que el destino lee "
                "para decidir si la activa, y ahora es lo primero que sobrevive a un recorte.")
    if not tiene_activacion(res.description):
        res.findings.append(Finding("alta", "description-sin-activacion",
            "La descripción no dice en ningún momento CUÁNDO cargar la skill: no hay ni un "
            "'Cárgala cuando…', ni un 'cuando el usuario…', ni ejemplos de frases reales. "
            "Describe el contenido, no el disparador. El destino casi nunca la activará. "
            "Esto no se puede arreglar automáticamente sin inventar: reescríbela empezando "
            "por los disparadores."))

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
            f"Descripción ajustada a cada destino: {origen_bytes} bytes de origen → "
            f"{nbytes(res.desc_zip)} B en el `.zip` (Perplexity, tope {presupuesto_zip}) y "
            f"{nbytes(res.desc_folder)} B en la carpeta (Mistral, tope {presupuesto_carpeta}). "
            "Se podan primero los ejemplos entrecomillados y después las frases que sólo "
            "cuentan qué hace la skill; el criterio de activación se conserva.")
    if origen_bytes > presupuesto_zip:
        res.findings.append(Finding("media", "description-larga",
            f"La descripción de origen medía {origen_bytes} bytes UTF-8 y no cabe entera en "
            "ningún destino. El recorte automático mantiene frases completas, pero no puede "
            "reescribir: revisa el resultado y, si ha perdido matiz, redáctala a mano en un "
            "solo párrafo que diga primero cuándo activarse y luego para qué sirve."))
    elif origen_bytes > presupuesto_carpeta:
        res.findings.append(Finding("baja", "description-densa",
            f"Descripción de {origen_bytes} bytes: cabe en el zip de Perplexity pero no en la "
            f"carpeta de Mistral ({presupuesto_carpeta} B), donde va recortada. El índice del "
            "destino paga este coste en cada sesión, así que cuanto más breve, mejor."))

    # Claves no portables
    dropped = [k for k in fm if k in CLAUDE_ONLY_KEYS]
    if dropped:
        res.adaptations.append("Claves de frontmatter retiradas (no existen fuera de Claude): "
                               + ", ".join(sorted(dropped)) + ".")

    # Adaptación de rutas ANTES de auditar, para no avisar de lo que ya se arregló.
    new_body = re.sub(r"\$\{?CLAUDE_PLUGIN_ROOT\}?/skills/[a-zA-Z0-9_\-]+/", "", body)
    new_body = re.sub(r"\$\{?CLAUDE_PLUGIN_ROOT\}?/", "", new_body)
    if new_body != body:
        res.adaptations.append("Rutas ${CLAUDE_PLUGIN_ROOT}/... convertidas en rutas relativas a la skill.")
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
    senales = detectar(body, "SKILL.md") + detectar_en_arbol(src_dir, excluir={"SKILL.md"})
    res.senales = senales
    for s in senales:
        res.findings.append(Finding(s.severidad_base, s.id,
                                    "{} Visto en {}: {}".format(
                                        EXPLICACIONES[s.id], s.ubicacion, s.muestra)))

    tools_used = sorted({t for t in CLAUDE_TOOL_NAMES if re.search(rf"\b{t}\b", body)})
    if tools_used:
        res.findings.append(Finding("media", "herramientas-claude",
            "Nombra herramientas propias de Claude: " + ", ".join(tools_used) +
            ". Fuera de Claude no existen con ese nombre."))

    # Tamaño del cuerpo
    est_tokens = len(body) // CHARS_PER_TOKEN
    if est_tokens > SOFT_BODY_TOKENS:
        res.findings.append(Finding("baja", "cuerpo-largo",
            f"Cuerpo de ~{est_tokens} tokens (recomendado <{SOFT_BODY_TOKENS}). "
            "Mueve el material condicional a references/ para que se cargue sólo cuando haga falta."))

    # ---- Escritura ----
    dest = out_dir / name
    if dest.exists():
        shutil.rmtree(dest)
    enlaces = copiar_skill(src_dir, dest, ignorar=set(IGNORED_DIRS) | {"SKILL.md"})
    for s in enlaces:
        res.findings.append(Finding("alta", "enlace-simbolico",
            "Se omitió un enlace simbólico al empaquetar: {} ({}). Copiar su "
            "contenido habría metido en el paquete un fichero de fuera de la "
            "skill.".format(s.ubicacion, s.muestra)))

    for p in sorted(dest.rglob("*")):
        if p.is_file():
            res.extra_files.append(str(p.relative_to(dest)))
    if any(f.startswith("scripts/") for f in res.extra_files):
        res.findings.append(Finding("media", "scripts",
            "Incluye scripts/. Perplexity Computer puede ejecutarlos en su sandbox; "
            "Mistral Vibe Work los guarda pero NO tiene Python (comprobado), así que allí "
            "no se ejecutan. Si la lógica vive en el script, el SKILL.md debe traer un "
            "procedimiento manual equivalente al que caer."))

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
    if meta:
        res.fm_meta = meta
    if bajadas:
        res.adaptations.append(
            "Claves movidas a `metadata` (el frontmatter del estándar es un "
            "conjunto cerrado y al nivel superior el destino las rechaza): "
            + ", ".join(bajadas) + ".")
    # La carpeta en disco es la variante de Mistral; el zip se reescribe al empaquetar.
    write_skill_md(res, dest, res.desc_folder)
    return res


def write_skill_md(res: SkillResult, dest: Path, description: str) -> None:
    """Escribe el SKILL.md con la descripción que corresponda al destino."""
    fm_out = {"name": res.name, "description": description}
    fm_out.update(res.fm_extra)
    lines = ["---"] + [f"{k}: {yaml_escape(v)}" for k, v in fm_out.items()]
    # `metadata` es un mapa, no un escalar: va como bloque anidado.
    if res.fm_meta:
        lines.append("metadata:")
        lines += [f"  {k}: {yaml_escape(v)}" for k, v in res.fm_meta.items()]
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
                sys.exit("[error] El origen supera los {} ficheros. Se aborta el "
                         "análisis.".format(MAX_FICHEROS_REPO))
            if total > MAX_BYTES_REPO:
                sys.exit("[error] El origen supera los {} MB. Se aborta el "
                         "análisis.".format(MAX_BYTES_REPO // (1024 * 1024)))


def resolve_source(src: str, workdir: Path) -> Path:
    p = Path(src).expanduser()
    if p.exists():
        comprobar_tamano(p.resolve())
        return p.resolve()
    if not re.match(r"^(https?://|git@)", src):
        sys.exit("[error] '{}' no existe como ruta ni parece una URL de "
                 "repositorio.".format(src))
    target = workdir / "repo"
    print("[info] clonando {} ...".format(src))
    entorno = dict(os.environ)
    # Sin esto, un repositorio privado deja el proceso colgado esperando
    # credenciales que nadie va a teclear.
    entorno["GIT_TERMINAL_PROMPT"] = "0"
    try:
        r = subprocess.run(
            ["git", "clone", "--depth", "1", "--no-recurse-submodules", src, str(target)],
            capture_output=True, text=True, env=entorno, timeout=TIMEOUT_CLON)
    except subprocess.TimeoutExpired:
        sys.exit("[error] el clon superó los {} s y se ha cancelado.".format(TIMEOUT_CLON))
    if r.returncode != 0:
        sys.exit("[error] git clone falló:\n{}\n\nSi el repositorio es privado, "
                 "necesitas git ya autenticado, o descárgalo a mano y pasa la "
                 "ruta local.".format(r.stderr.strip()))
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
    exp.add_argument("--out", default="./dist-agentskills", help="directorio de salida")
    exp.add_argument("--only", nargs="*", default=None,
                     help="exportar sólo estas skills")
    exp.add_argument("--zip-only", action="store_true",
                     help="dejar sólo los .zip (pierdes la variante de carpeta)")
    exp.add_argument("--keep-description-order", action="store_true",
                     help="no reordenar la descripción")
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
        print("   nombre original: {}".format(skill.nombre_original))
    print("   descripción: {} bytes{}".format(
        skill.descripcion_bytes,
        "" if skill.tiene_activacion else "  ⚠ SIN criterio de activación"))
    print("   cuerpo: ~{} tokens".format(skill.cuerpo_tokens))
    print("   ficheros: {}{}".format(
        len(skill.ficheros), " (incluye scripts/)" if skill.tiene_scripts else ""))

    if skill.capacidades:
        print("   capacidades exigidas:")
        for c in skill.capacidades:
            print("     · {:<24} {}".format(c.nombre, c.nivel))
    else:
        print("   capacidades exigidas: ninguna")

    if skill.senales:
        print("   señales:")
        for s in skill.senales:
            print("     · {:<20} {}  {}".format(s.id, s.ubicacion, s.muestra))
    else:
        print("   señales: ninguna")

    ambiguo = [c.nombre for c in skill.capacidades if c.nivel == "requerida"]
    if ambiguo and not skill.tiene_activacion:
        print("   ⚠ Exige capacidades y no dice cuándo cargarse: revisa la "
              "descripción antes de auditar contra ningún destino.")


def ejecutar(args, perfiles, elegidos) -> int:
    # Los perfiles ya están cargados: de ellos salen los presupuestos de
    # descripción (el más restrictivo por modo de instalación), con
    # independencia del subcomando y de qué destinos se hayan elegido.
    presupuesto_carpeta = presupuesto_por_modo(perfiles, "carpeta")   # Mistral: 490
    presupuesto_zip = presupuesto_por_modo(perfiles, "zip")           # el resto: 850

    out = None
    if args.comando == "export":
        out = Path(args.out).expanduser().resolve()
        if out.exists():
            shutil.rmtree(out)
        # Las carpetas de skill cuelgan directamente de <out>, al lado de su
        # zip: mismos ficheros, distinta descripción.
        out.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as tmp:
        root = resolve_source(args.source, Path(tmp))

        skill_files = discover_skills(root)
        if not skill_files:
            sys.exit("[error] No se encontró ningún SKILL.md. ¿Seguro que el repo contiene "
                     "skills? Un plugin sin carpeta skills/ no tiene nada portable.")

        print(f"[info] {len(skill_files)} skill(s) encontradas.")

        # `inspect` y `audit` no escriben ningún fichero de salida: trabajan
        # sobre una copia efímera que desaparece con este bloque. `export`
        # usa `out`, que sí sobrevive fuera de él.
        work_dir = out if out is not None else Path(tmp) / "_trabajo"
        work_dir.mkdir(parents=True, exist_ok=True)

        solo = getattr(args, "only", None)
        results = []
        for sf in skill_files:
            nm = sanitize_name(sf.parent.name)
            if solo and nm not in {sanitize_name(x) for x in solo}:
                continue
            r = audit_and_adapt(sf, work_dir, presupuesto_carpeta, presupuesto_zip,
                                reorder=not args.keep_description_order)
            results.append(r)
            print(f"  · {r.name:<40} riesgo={r.worst}")

        if not results:
            sys.exit("[error] --only no coincidió con ninguna skill.")

        if args.comando == "inspect":
            for r in results:
                imprimir_inspect(a_skill_portatil(r))
            return 0

        hoy = datetime.date.today()

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
            print(informe_markdown(results, evaluaciones, args.source, perfiles_informe))
            return codigo_por_umbral(evaluaciones, args.fail_on)

        # -------- export --------
        # Qué artefactos hacen falta: la unión de los modos de instalación
        # de los destinos elegidos (todos, si no se restringió con
        # --target). `carpeta` es el único modo no-zip que este conversor
        # sabe producir, así que cualquier modo que no sea `zip` ni
        # `url_repositorio` (que no necesita ningún artefacto propio)
        # implica querer la carpeta.
        modos_deseados = set()
        for pid in (elegidos if elegidos else perfiles):
            modos_deseados.update(perfiles[pid].modos())
        quiere_zip = "zip" in modos_deseados
        quiere_carpeta = bool(modos_deseados - {"zip", "url_repositorio"})

        # Un zip por skill, con la carpeta de la skill en la raíz del zip:
        # es la única estructura que Perplexity acepta.
        for r in results:
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
            informe_markdown(results, evaluaciones, args.source, perfiles),
            encoding="utf-8")
        (out / "resumen.json").write_text(
            json.dumps(resumen_json(results, evaluaciones, args.source),
                       ensure_ascii=False, indent=2),
            encoding="utf-8")

    print(f"\n[ok] Salida en: {out}")
    if quiere_zip:
        print(f"     Perplexity → <skill>.zip   ({len(results)} zip(s), uno por skill; "
              f"descripción ≤{presupuesto_zip} B)")
    if quiere_carpeta:
        if args.zip_only:
            print(f"     Mistral    → no disponible: --zip-only ha borrado la variante de "
                  f"{presupuesto_carpeta} B")
        else:
            print(f"     Mistral    → <skill>/      (descripción ≤{presupuesto_carpeta} B — NO es el "
                  f"zip descomprimido)")
    print(f"     Informe    → INFORME-PORTABILIDAD.md")
    riesgo = [r.name for r in results if r.worst == "alta"]
    if riesgo:
        print(f"\n[aviso] Riesgo alto en: {', '.join(riesgo)}. Lee el informe antes de subirlas.")

    return codigo_por_umbral(evaluaciones, args.fail_on)


def main(argv=None) -> int:
    args = construir_parser().parse_args(normalizar_argv(
        sys.argv[1:] if argv is None else argv))

    try:
        perfiles = cargar_perfiles()
    except PerfilInvalido as e:
        print("[error] perfil de destino inválido: {}".format(e), file=sys.stderr)
        return 1

    elegidos = getattr(args, "target", None)
    if elegidos:
        desconocidos = [t for t in elegidos if t not in perfiles]
        if desconocidos:
            print("[error] destino desconocido: {}. Disponibles: {}".format(
                ", ".join(desconocidos), ", ".join(sorted(perfiles))), file=sys.stderr)
            return 1

    return ejecutar(args, perfiles, elegidos)


if __name__ == "__main__":
    sys.exit(main())
