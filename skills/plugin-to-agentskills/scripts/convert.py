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
    python3 convert.py <repo-url-o-ruta> [--out DIR] [--only NOMBRE ...]

Salidas en <out>/:
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
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from exporter.descripcion import (
    ACTIVATION_RX,
    clamp_description,
    compact_description,
    nbytes,
    reorder_description,
    tiene_activacion,
)
from exporter.frontmatter import split_frontmatter, yaml_escape

# --------------------------------------------------------------------------
# Límites y constantes del estándar Agent Skills
# --------------------------------------------------------------------------

# Tope del estándar Agent Skills, en CARACTERES. Es también el que aplican
# ChatGPT (Skills), claude.ai y la Skills API, y lo aplican como error duro.
MAX_DESCRIPTION_CHARS = 1024

# Presupuestos POR DESTINO, en BYTES UTF-8 (no en caracteres: en español un acento
# ocupa dos y una raya tres, así que contar letras engaña por un 2-3%).
BUDGET_MISTRAL = 490              # carpeta descomprimida
BUDGET_PERPLEXITY = 850           # dentro del .zip
BUDGET_DEFAULT = BUDGET_PERPLEXITY
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

# Herramientas propias del entorno Claude que, si la skill las invoca por nombre,
# probablemente no existan en Perplexity/Mistral con la misma semántica.
CLAUDE_TOOL_NAMES = [
    "TodoWrite", "AskUserQuestion", "NotebookEdit", "SlashCommand",
    "ExitPlanMode", "WebFetch", "TaskCreate", "TaskUpdate", "ToolSearch",
]

PATTERNS = [
    # (id, regex, severidad, explicación)
    ("plugin-root", re.compile(r"\$\{?CLAUDE_PLUGIN_ROOT\}?"), "alta",
     "Ruta ${CLAUDE_PLUGIN_ROOT}: sólo existe dentro de un plugin de Claude Code."),
    ("mcp-tool", re.compile(r"\bmcp__[a-zA-Z0-9_\-]+"), "alta",
     "Invoca herramientas MCP por nombre; esos servidores no estarán conectados."),
    ("skill-tool", re.compile(r"\bSkill\s*\(\s*[\"'`]|\bSkill tool\b|\bherramienta Skill\b"), "alta",
     "Invoca otras skills mediante la herramienta Skill de Claude."),
    ("subagent", re.compile(r"\bTask tool\b|\bsubagent_type\b|\bAgent tool\b|\bsubagente\b", re.I), "alta",
     "Delega en subagentes vía la herramienta Task, que no existe fuera de Claude Code."),
    # Comando con namespace de plugin: /plugin:comando. Excluye namespaces XML tipo /w:p.
    ("slash-plugin", re.compile(
        r"(?:^|[\s(`])/[a-z][a-z0-9]{2,}(?:-[a-z0-9]+)*:[a-z][a-z0-9]{2,}(?:-[a-z0-9]+)*\b", re.M), "media",
     "Referencia a comandos con namespace de plugin (/plugin:comando)."),
    ("hooks", re.compile(r"\bhooks?\.json\b|\bPreToolUse\b|\bPostToolUse\b"), "media",
     "Depende de hooks del plugin, que no se exportan."),
    ("applescript", re.compile(r"\bosascript\b|\btell\s+application\b", re.I), "media",
     "Usa AppleScript para llegar a aplicaciones del Mac. Perplexity Computer sí lo "
     "ejecuta (comprobado), pero corta cada llamada en torno a 90 segundos: un lote largo "
     "se queda a medias y deja el trabajo inconsistente. Trocea los lotes y verifica el "
     "resultado después de cada trozo. Mistral no lo ejecuta en absoluto."),
    ("lote-destructivo", re.compile(
        r"\b(?:move|delete|borra|elimina|mueve|archiva)\b[^.\n]{0,60}\b(?:whose|todos|all|"
        r"cada|every|lote|batch|masiv)", re.I), "alta",
     "Modifica o mueve elementos en bloque a partir de un filtro. Si el entorno de destino "
     "corta la llamada a mitad —Perplexity Computer lo hace— el lote queda parcialmente "
     "aplicado y sin registro fiable de qué se tocó. Antes de exportar: procesa en trozos "
     "pequeños, verifica releyendo el estado después de cada uno, y no confíes en que el "
     "filtro se haya aplicado como esperabas: compruébalo sobre los elementos afectados."),
    ("home-tilde", re.compile(r"(?<![\w/])(?:~/|\$HOME/)[\w.\-]"), "media",
     "Lee o escribe en rutas con ~ o $HOME. Comprobado en Mistral Vibe Work: $HOME vale "
     "'/', así que '~/.mi-skill/' termina creando '//.mi-skill/'. Usa rutas relativas a "
     "la carpeta de la skill, o pide al usuario una ruta absoluta explícita."),
    ("estado-persistente", re.compile(r">>\s*[\"']?[~$./][^\s\"'|;)]*"), "media",
     "Acumula estado con anexado (>>). Comprobado en Mistral Vibe Work: la escritura "
     "puede reportar éxito y el fichero no existir después. Reléelo para confirmarlo, o "
     "reescribe el fichero entero de una vez en lugar de ir anexando."),
    ("claude-md", re.compile(r"\bCLAUDE\.md\b"), "baja",
     "Referencia a CLAUDE.md, convención específica de Claude Code."),
    ("claude-brand", re.compile(r"\bClaude Code\b|\bCowork\b"), "baja",
     "Menciona el producto Claude por su nombre; conviene neutralizarlo."),
]


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

def audit_and_adapt(skill_md: Path, out_dir: Path, reorder: bool = True) -> SkillResult:
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
            compact_description(res.description, BUDGET_MISTRAL), BUDGET_MISTRAL)
        res.desc_zip = clamp_description(
            compact_description(res.description, BUDGET_PERPLEXITY), BUDGET_PERPLEXITY)
    else:
        res.desc_folder = clamp_description(res.description, BUDGET_MISTRAL)
        res.desc_zip = clamp_description(res.description, BUDGET_PERPLEXITY)
    res.description = res.desc_zip   # la que se muestra en el informe

    if origen_bytes > BUDGET_MISTRAL:
        res.adaptations.append(
            f"Descripción ajustada a cada destino: {origen_bytes} bytes de origen → "
            f"{nbytes(res.desc_zip)} B en el `.zip` (Perplexity, tope {BUDGET_PERPLEXITY}) y "
            f"{nbytes(res.desc_folder)} B en la carpeta (Mistral, tope {BUDGET_MISTRAL}). "
            "Se podan primero los ejemplos entrecomillados y después las frases que sólo "
            "cuentan qué hace la skill; el criterio de activación se conserva.")
    if origen_bytes > BUDGET_PERPLEXITY:
        res.findings.append(Finding("media", "description-larga",
            f"La descripción de origen medía {origen_bytes} bytes UTF-8 y no cabe entera en "
            "ningún destino. El recorte automático mantiene frases completas, pero no puede "
            "reescribir: revisa el resultado y, si ha perdido matiz, redáctala a mano en un "
            "solo párrafo que diga primero cuándo activarse y luego para qué sirve."))
    elif origen_bytes > BUDGET_MISTRAL:
        res.findings.append(Finding("baja", "description-densa",
            f"Descripción de {origen_bytes} bytes: cabe en el zip de Perplexity pero no en la "
            f"carpeta de Mistral ({BUDGET_MISTRAL} B), donde va recortada. El índice del "
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

    # Patrones problemáticos en el cuerpo
    for code, rx, sev, expl in PATTERNS:
        hits = rx.findall(body)
        if hits:
            sample = sorted({h if isinstance(h, str) else h[0] for h in hits})[:4]
            res.findings.append(Finding(sev, code, f"{expl} Ejemplos: {', '.join(sample)}"))

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
    shutil.copytree(src_dir, dest, ignore=shutil.ignore_patterns(*IGNORED_DIRS, "SKILL.md"))

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


# --------------------------------------------------------------------------
# Empaquetado
# --------------------------------------------------------------------------

def zip_dir(src: Path, dest_zip: Path, arc_prefix: str = "") -> None:
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                arc = Path(arc_prefix) / p.relative_to(src) if arc_prefix else p.relative_to(src)
                z.write(p, arc.as_posix())


def write_report(results: list, out: Path, source: str) -> None:
    sev_icon = {"alta": "🔴", "media": "🟡", "baja": "🔵", "ninguna": "🟢"}
    L = [
        "# Informe de portabilidad",
        "",
        f"- **Origen:** `{source}`",
        f"- **Skills exportadas:** {len(results)}",
        "",
        "## Dónde sube cada cosa",
        "",
        "**El `.zip` y la carpeta no son intercambiables.** Llevan los mismos ficheros, pero",
        f"la descripción se ajusta al presupuesto de cada destino: {BUDGET_PERPLEXITY} bytes",
        f"en el zip y {BUDGET_MISTRAL} en la carpeta. Descomprimir el zip **no** produce la",
        "carpeta de Mistral: su descripción sería demasiado larga.",
        "",
        "| Destino | Qué subir | Dónde |",
        "|---|---|---|",
        "| Perplexity Computer | `<skill>.zip` — tal cual, sin tocar | "
        "perplexity.ai/computer/skills → Create skill → Upload a skill |",
        "| Mistral Vibe Work | `<skill>/` — la carpeta, no el zip | "
        "chat.mistral.ai/work → Context → Skills → New Skill |",
        "",
        "## Resumen",
        "",
        "| Skill | Riesgo | Avisos | Adaptaciones | Ficheros extra |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        L.append(f"| `{r.name}` | {sev_icon[r.worst]} {r.worst} | {len(r.findings)} | "
                 f"{len(r.adaptations)} | {len(r.extra_files)} |")
    L += ["", "**Riesgo alto** = la skill contiene instrucciones que casi seguro fallarán "
          "fuera de Claude. **Medio** = funcionará, pero degradada. **Bajo** = cosmético.", ""]

    for r in results:
        L += [f"## `{r.name}`", "",
              f"- Origen: `{r.src_dir}`",
              f"- Descripción ({len(r.description)} car.): {r.description[:300]}", ""]
        if r.adaptations:
            L += ["**Adaptado automáticamente:**", ""] + [f"- {a}" for a in r.adaptations] + [""]
        if r.findings:
            L += ["**Avisos:**", ""]
            for f in r.findings:
                L.append(f"- {sev_icon[f.severity]} *{f.code}* — {f.message}")
            L.append("")
        else:
            L += ["Sin avisos: esta skill es portable tal cual.", ""]
    (out / "INFORME-PORTABILIDAD.md").write_text("\n".join(L), encoding="utf-8")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def resolve_source(src: str, workdir: Path) -> Path:
    p = Path(src).expanduser()
    if p.exists():
        return p.resolve()
    if not re.match(r"^(https?://|git@)", src):
        sys.exit(f"[error] '{src}' no existe como ruta ni parece una URL de repositorio.")
    target = workdir / "repo"
    print(f"[info] clonando {src} ...")
    r = subprocess.run(["git", "clone", "--depth", "1", src, str(target)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"[error] git clone falló:\n{r.stderr.strip()}")
    return target


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Plugin de Claude → Agent Skills portable",
        epilog="Salida: <skill>.zip para Perplexity y <skill>/ para Mistral. Mismos "
               "ficheros, pero la descripción se ajusta al presupuesto de cada destino: "
               "descomprimir el zip NO produce la carpeta de Mistral.")
    ap.add_argument("source", help="URL del repositorio o ruta local")
    ap.add_argument("--out", default="./dist-agentskills", help="directorio de salida")
    ap.add_argument("--only", nargs="*", default=None, help="exportar sólo estas skills")
    ap.add_argument("--zip-only", action="store_true",
                    help="dejar sólo los .zip (pierdes la variante de Mistral)")
    ap.add_argument("--keep-description-order", action="store_true",
                    help="no reordenar la descripción (por defecto la activación va primero)")
    args = ap.parse_args()

    out = Path(args.out).expanduser().resolve()
    if out.exists():
        shutil.rmtree(out)
    # Las carpetas de skill cuelgan directamente de <out>, al lado de su zip: mismos
    # ficheros, distinta descripción.
    out.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as tmp:
        root = resolve_source(args.source, Path(tmp))

        skill_files = discover_skills(root)
        if not skill_files:
            sys.exit("[error] No se encontró ningún SKILL.md. ¿Seguro que el repo contiene "
                     "skills? Un plugin sin carpeta skills/ no tiene nada portable.")

        print(f"[info] {len(skill_files)} skill(s) encontradas.")
        results = []
        for sf in skill_files:
            nm = sanitize_name(sf.parent.name)
            if args.only and nm not in {sanitize_name(x) for x in args.only}:
                continue
            r = audit_and_adapt(sf, out, reorder=not args.keep_description_order)
            results.append(r)
            print(f"  · {r.name:<40} riesgo={r.worst}")

        if not results:
            sys.exit("[error] --only no coincidió con ninguna skill.")

        # Un zip por skill, con la carpeta de la skill en la raíz del zip:
        # es la única estructura que Perplexity acepta.
        for r in results:
            write_skill_md(r, out / r.name, r.desc_zip)      # dentro del zip: Perplexity
            zip_dir(out / r.name, out / f"{r.name}.zip", arc_prefix=r.name)
            write_skill_md(r, out / r.name, r.desc_folder)   # en disco: Mistral

        if args.zip_only:
            for r in results:
                shutil.rmtree(out / r.name)

        write_report(results, out, args.source)
        (out / "resumen.json").write_text(json.dumps(
            [{"name": r.name, "risk": r.worst, "findings": [f.__dict__ for f in r.findings],
              "adaptations": r.adaptations} for r in results], ensure_ascii=False, indent=2),
            encoding="utf-8")

    print(f"\n[ok] Salida en: {out}")
    print(f"     Perplexity → <skill>.zip   ({len(results)} zip(s), uno por skill; "
          f"descripción ≤{BUDGET_PERPLEXITY} B)")
    if not args.zip_only:
        print(f"     Mistral    → <skill>/      (descripción ≤{BUDGET_MISTRAL} B — NO es el "
              f"zip descomprimido)")
    else:
        print(f"     Mistral    → no disponible: --zip-only ha borrado la variante de {BUDGET_MISTRAL} B")
    print(f"     Informe    → INFORME-PORTABILIDAD.md")
    riesgo = [r.name for r in results if r.worst == "alta"]
    if riesgo:
        print(f"\n[aviso] Riesgo alto en: {', '.join(riesgo)}. Lee el informe antes de subirlas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
