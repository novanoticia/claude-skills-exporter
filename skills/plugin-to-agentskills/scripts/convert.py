#!/usr/bin/env python3
"""
convert.py — Extrae las skills de un repositorio con un plugin de Claude y las
empaqueta en formato Agent Skills portable (Perplexity Computer / Mistral Vibe).

Sólo biblioteca estándar. Python 3.8+.

Uso:
    python3 convert.py <repo-url-o-ruta> [--out DIR] [--per-skill] [--only NOMBRE ...]

Salidas en <out>/:
    <nombre>-agentskills.zip   zip único con todas las skills (raíz = una carpeta por skill)
    skills/                    las mismas skills sin comprimir
    zips/                      un zip por skill (sólo con --per-skill)
    mistral/                   ficheros listos para pegar en el formulario de Mistral
    INFORME-PORTABILIDAD.md    qué se adaptó y qué se romperá fuera de Claude
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

# --------------------------------------------------------------------------
# Límites y constantes del estándar Agent Skills
# --------------------------------------------------------------------------

MAX_DESCRIPTION_CHARS = 1024      # límite duro habitual del campo description
SOFT_DESCRIPTION_CHARS = 350      # ~100 tokens: presupuesto del índice de Perplexity
SOFT_BODY_TOKENS = 5000           # cuerpo recomendado del SKILL.md
CHARS_PER_TOKEN = 4               # estimación grosera

# Claves de frontmatter que NO son del estándar abierto y se retiran al exportar.
CLAUDE_ONLY_KEYS = {
    "allowed-tools", "allowed_tools", "disable-model-invocation",
    "model", "argument-hint", "user-invocable", "context",
}

# Claves que se conservan tal cual.
PORTABLE_KEYS = ["name", "description", "license", "version", "depends", "metadata"]

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
    ("claude-md", re.compile(r"\bCLAUDE\.md\b"), "baja",
     "Referencia a CLAUDE.md, convención específica de Claude Code."),
    ("claude-brand", re.compile(r"\bClaude Code\b|\bCowork\b"), "baja",
     "Menciona el producto Claude por su nombre; conviene neutralizarlo."),
]


# --------------------------------------------------------------------------
# Frontmatter (parser mínimo, sin PyYAML)
# --------------------------------------------------------------------------

def split_frontmatter(text: str):
    """Devuelve (dict_frontmatter, texto_frontmatter_bruto, cuerpo)."""
    if not text.startswith("---"):
        return {}, "", text
    lines = text.splitlines(keepends=True)
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return {}, "", text
    raw = "".join(lines[1:end])
    body = "".join(lines[end + 1:])
    return parse_simple_yaml(raw), raw, body


def parse_simple_yaml(raw: str) -> dict:
    """Parser de nivel superior: clave: valor, escalares en bloque (| >) y listas."""
    data, key, buf, mode, indent = {}, None, [], None, 0

    def flush():
        nonlocal key, buf, mode
        if key is None:
            return
        if mode == "block":
            data[key] = "\n".join(buf).strip()
        elif mode == "list":
            data[key] = [x for x in buf if x]
        key, buf, mode = None, [], None

    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            if mode == "block":
                buf.append("")
            continue
        stripped = line.strip()
        cur_indent = len(line) - len(line.lstrip())

        if mode in ("block", "list") and cur_indent > indent:
            if mode == "list" and stripped.startswith("- "):
                buf.append(unquote(stripped[2:].strip()))
            elif mode == "block":
                buf.append(stripped)
            continue
        if mode == "list" and stripped.startswith("- ") and cur_indent >= indent:
            buf.append(unquote(stripped[2:].strip()))
            continue
        flush()

        m = re.match(r"^([A-Za-z0-9_\-.]+)\s*:\s*(.*)$", stripped)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        indent = cur_indent
        if v in ("|", "|-", ">", ">-", "|+", ">+"):
            key, mode, buf = k, "block", []
        elif v == "":
            key, mode, buf = k, "list", []
        else:
            data[k] = unquote(v)
    flush()
    return data


def unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def yaml_escape(v: str) -> str:
    """Serializa un escalar en una sola línea de forma segura."""
    v = " ".join(str(v).split())
    if re.search(r'[:#\[\]{}&*!|>%@`"\']', v) or v == "":
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return v


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

def audit_and_adapt(skill_md: Path, out_dir: Path) -> SkillResult:
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

    # Longitud de la descripción
    if len(res.description) > MAX_DESCRIPTION_CHARS:
        res.description = res.description[:MAX_DESCRIPTION_CHARS - 3].rstrip() + "..."
        res.findings.append(Finding("media", "description-larga",
            f"La descripción superaba {MAX_DESCRIPTION_CHARS} caracteres y se ha truncado. "
            "Reescríbela a mano: debe decir CUÁNDO cargar la skill, no qué hace."))
    elif len(res.description) > SOFT_DESCRIPTION_CHARS:
        res.findings.append(Finding("baja", "description-densa",
            f"Descripción de {len(res.description)} caracteres. Perplexity paga este coste "
            f"en cada sesión; por debajo de ~{SOFT_DESCRIPTION_CHARS} funciona mejor."))

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
            "Mistral Vibe Work no garantiza ejecución equivalente. Verifica dependencias."))

    fm_out = {"name": name, "description": res.description}
    for k in PORTABLE_KEYS:
        if k in ("name", "description"):
            continue
        if k in fm and isinstance(fm[k], str) and fm[k]:
            fm_out[k] = fm[k]

    lines = ["---"]
    for k, v in fm_out.items():
        lines.append(f"{k}: {yaml_escape(v)}")
    lines.append("---")
    header = "\n".join(lines) + "\n"

    notes = render_notes(res)
    (dest / "SKILL.md").write_text(header + body.rstrip() + notes, encoding="utf-8")
    return res


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


def fence_for(text: str) -> str:
    """Valla de código más larga que cualquier secuencia de backticks del contenido."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def write_mistral(res: SkillResult, skills_dir: Path, mistral_dir: Path) -> None:
    mistral_dir.mkdir(parents=True, exist_ok=True)
    md = (skills_dir / res.name / "SKILL.md").read_text(encoding="utf-8")
    _fm, _raw, body = split_frontmatter(md)
    body = body.strip()
    title = res.name.replace("-", " ").capitalize()
    attach = [f for f in res.extra_files]
    f_body = fence_for(body)
    f_desc = fence_for(res.description)
    lines = [
        "# Para pegar en Mistral · Vibe Work → Context → Skills → New Skill",
        "",
        "## Campo «Title»", "```", title, "```", "",
        "## Campo «Description»  (es el que decide cuándo se activa)", f_desc,
        res.description, f_desc, "",
        "## Campo «SKILL.md»", f_body + "markdown", body, f_body, "",
    ]
    if attach:
        lines += ["## Ficheros a adjuntar junto a la skill", ""]
        lines += [f"- `{f}`" for f in attach]
        lines += ["", "Están en la carpeta `skills/" + res.name + "/` de esta misma salida.", ""]
    (mistral_dir / f"{res.name}.md").write_text("\n".join(lines), encoding="utf-8")


def write_report(results: list, out: Path, source: str, single_zip: Path) -> None:
    sev_icon = {"alta": "🔴", "media": "🟡", "baja": "🔵", "ninguna": "🟢"}
    L = [
        "# Informe de portabilidad",
        "",
        f"- **Origen:** `{source}`",
        f"- **Skills exportadas:** {len(results)}",
        f"- **Zip único:** `{single_zip.name}`",
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
    ap = argparse.ArgumentParser(description="Plugin de Claude → Agent Skills portable")
    ap.add_argument("source", help="URL del repositorio o ruta local")
    ap.add_argument("--out", default="./dist-agentskills", help="directorio de salida")
    ap.add_argument("--per-skill", action="store_true",
                    help="además, un .zip por skill (lo que Perplexity espera realmente)")
    ap.add_argument("--only", nargs="*", default=None, help="exportar sólo estas skills")
    args = ap.parse_args()

    out = Path(args.out).expanduser().resolve()
    if out.exists():
        shutil.rmtree(out)
    skills_dir = out / "skills"
    skills_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as tmp:
        root = resolve_source(args.source, Path(tmp))
        label = re.sub(r"\.git$", "", args.source.rstrip("/").split("/")[-1])
        if sanitize_name(label) in ("", "skill", "."):
            label = root.resolve().name          # p. ej. cuando el origen es "." o "./"
        label = sanitize_name(label) or "skills"

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
            r = audit_and_adapt(sf, skills_dir)
            results.append(r)
            print(f"  · {r.name:<40} riesgo={r.worst}")

        if not results:
            sys.exit("[error] --only no coincidió con ninguna skill.")

        single = out / f"{sanitize_name(label)}-agentskills.zip"
        zip_dir(skills_dir, single)

        mistral_dir = out / "mistral"
        for r in results:
            write_mistral(r, skills_dir, mistral_dir)

        if args.per_skill:
            for r in results:
                zip_dir(skills_dir / r.name, out / "zips" / f"{r.name}.zip", arc_prefix=r.name)

        write_report(results, out, args.source, single)
        (out / "resumen.json").write_text(json.dumps(
            [{"name": r.name, "risk": r.worst, "findings": [f.__dict__ for f in r.findings],
              "adaptations": r.adaptations} for r in results], ensure_ascii=False, indent=2),
            encoding="utf-8")

    print(f"\n[ok] Salida en: {out}")
    print(f"     zip único → {single.name}")
    if args.per_skill:
        print(f"     zips individuales → zips/")
    print(f"     Mistral → mistral/   ·   Informe → INFORME-PORTABILIDAD.md")
    riesgo = [r.name for r in results if r.worst == "alta"]
    if riesgo:
        print(f"\n[aviso] Riesgo alto en: {', '.join(riesgo)}. Lee el informe antes de subirlas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
