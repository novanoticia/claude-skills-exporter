#!/usr/bin/env python3
"""
Valida la estructura del plugin antes de publicarlo.

Comprueba lo que rompe la carga del plugin en silencio:
  · JSON de los manifiestos mal formado
  · nombres que no cuadran entre manifiesto, marketplace y carpetas
  · SKILL.md sin frontmatter, sin name o sin description
  · nombre de skill que no coincide con su carpeta
  · comandos sin description
  · convert.py con error de sintaxis

Uso:  python3 .github/validate_plugin.py [raíz-del-repo]
Sale con código 1 si hay algún error. Los avisos no hacen fallar el CI.
"""

from __future__ import annotations

import json
import py_compile
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def load_json(path: Path):
    if not path.exists():
        err(f"{path.relative_to(ROOT)}: no existe")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        err(f"{path.relative_to(ROOT)}: JSON inválido — línea {e.lineno}, columna {e.colno}: {e.msg}")
        return None


def frontmatter(path: Path) -> dict | None:
    """Extrae las claves de nivel superior del frontmatter YAML."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() in ("---", "...")), None)
    if end is None:
        return None
    data, key = {}, None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_\-.]+)\s*:\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            key = m.group(1)
            v = m.group(2).strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            data[key] = v
        elif key and line.startswith((" ", "\t")):
            data[key] = (str(data.get(key, "")) + " " + line.strip()).strip()
    return data


NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# ---------------------------------------------------------------- manifiestos
plugin = load_json(ROOT / ".claude-plugin" / "plugin.json")
market = load_json(ROOT / ".claude-plugin" / "marketplace.json")

plugin_name = None
if plugin is not None:
    plugin_name = plugin.get("name")
    if not plugin_name:
        err("plugin.json: falta el campo obligatorio 'name'")
    elif not NAME_RE.match(plugin_name):
        err(f"plugin.json: 'name' debe ser kebab-case en minúsculas, no '{plugin_name}'")
    if not plugin.get("description"):
        warn("plugin.json: sin 'description'; se verá vacío en el selector de plugins")
    if "version" in plugin:
        warn(f"plugin.json: 'version' fijada en {plugin['version']!r}. "
             "Recuerda subirla en cada publicación o los usuarios no recibirán cambios")

if market is not None:
    if not market.get("name"):
        err("marketplace.json: falta 'name'")
    if not isinstance(market.get("owner"), dict) or not market["owner"].get("name"):
        err("marketplace.json: falta 'owner.name'")
    entries = market.get("plugins")
    if not isinstance(entries, list) or not entries:
        err("marketplace.json: 'plugins' debe ser una lista con al menos una entrada")
    else:
        for e in entries:
            if not e.get("name"):
                err("marketplace.json: una entrada de 'plugins' no tiene 'name'")
                continue
            if not e.get("source"):
                err(f"marketplace.json: la entrada '{e['name']}' no tiene 'source'")
            src = str(e.get("source", ""))
            if src.startswith("./") and src != "./":
                d = (ROOT / src).resolve()
                if not d.is_dir():
                    err(f"marketplace.json: 'source' apunta a {src}, que no existe")
        names = [e.get("name") for e in entries if e.get("name")]
        if plugin_name and plugin_name not in names:
            err(f"El nombre del plugin ('{plugin_name}') no aparece en marketplace.json {names}")

# --------------------------------------------------------------------- skills
skill_files = sorted((ROOT / "skills").rglob("SKILL.md")) if (ROOT / "skills").is_dir() else []
root_skill = ROOT / "SKILL.md"
if root_skill.exists():
    skill_files.append(root_skill)

if not skill_files:
    warn("No se encontró ningún SKILL.md. ¿Es esto realmente un plugin de skills?")

for sf in skill_files:
    rel = sf.relative_to(ROOT)
    fm = frontmatter(sf)
    if fm is None:
        err(f"{rel}: sin bloque frontmatter YAML (--- al principio y al final)")
        continue
    name, desc = fm.get("name"), fm.get("description")
    if not name:
        err(f"{rel}: el frontmatter no tiene 'name'")
    else:
        if not NAME_RE.match(name):
            err(f"{rel}: 'name' debe ser kebab-case en minúsculas, no '{name}'")
        if sf.parent != ROOT and sf.parent.name != name:
            err(f"{rel}: 'name' es '{name}' pero la carpeta se llama '{sf.parent.name}'; deben coincidir")
    if not desc:
        err(f"{rel}: el frontmatter no tiene 'description'. Sin ella la skill no se activa nunca")
    elif len(desc) > 1024:
        err(f"{rel}: 'description' tiene {len(desc)} caracteres; el límite es 1024")
    elif len(desc) > 500:
        warn(f"{rel}: 'description' de {len(desc)} caracteres. Se paga en cada sesión; conviene acortarla")

# ------------------------------------------------------------------- comandos
for cmd in sorted((ROOT / "commands").glob("*.md")) if (ROOT / "commands").is_dir() else []:
    fm = frontmatter(cmd)
    if fm is None or not fm.get("description"):
        warn(f"{cmd.relative_to(ROOT)}: sin 'description' en el frontmatter; "
             "se verá sin texto en el listado de comandos")

# --------------------------------------------------------------- scripts .py
for py in sorted(ROOT.rglob("*.py")):
    if any(part in {".git", "__pycache__", ".github"} for part in py.parts):
        continue
    try:
        py_compile.compile(str(py), doraise=True, cfile="/tmp/_chk.pyc")
    except py_compile.PyCompileError as e:
        err(f"{py.relative_to(ROOT)}: error de sintaxis — {e.msg.strip().splitlines()[-1]}")

# ------------------------------------------------- prueba de humo del conversor
# Compilar sólo detecta errores de sintaxis. Un NameError por una constante que se
# renombró pasa el py_compile y revienta en ejecución, así que hay que ejecutarlo
# de verdad — sobre este mismo repositorio, que es una entrada real y sin red.
CONV = ROOT / "skills" / "plugin-to-agentskills" / "scripts" / "convert.py"
if CONV.exists():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "salida"
        # --anular-revision-seguridad es deliberado: este repositorio contiene a
        # proposito su propio banco de pruebas malicioso (tests/fixtures/) y la
        # documentacion de los patrones (docs/). Esta es la prueba de humo del
        # conversor, no la del gate: el gate se prueba en tests/test_seg_gate.py.
        # --only es obligatorio desde que existe la guarda de nombres unicos:
        # tests/fixtures/ contiene ocho skills que publican todas `name:
        # fechas`, asi que exportar el repositorio entero aborta -y hace bien,
        # porque de esas ocho solo saldria un artefacto-. Aqui interesa la
        # skill que se publica de verdad, no el banco de pruebas.
        proc = subprocess.run([sys.executable, str(CONV), str(ROOT), "--out", str(out),
                               "--only", "plugin-to-agentskills",
                               "--anular-revision-seguridad"],
                              capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            cola = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
            err("convert.py falla al ejecutarse sobre este repositorio: " + " | ".join(cola))
        else:
            zips = list(out.glob("*.zip"))
            if not zips:
                err("convert.py terminó sin generar ningún .zip")
            if not (out / "INFORME-PORTABILIDAD.md").exists():
                err("convert.py terminó sin generar INFORME-PORTABILIDAD.md")
            # Los presupuestos por destino son la razón de que Perplexity acepte el zip.
            for z in zips:
                carpeta = out / z.stem / "SKILL.md"
                if not carpeta.exists():
                    err(f"falta la carpeta para Mistral de '{z.stem}'")
                    continue
                for etiqueta, texto, tope in (
                    ("carpeta", carpeta.read_text(encoding="utf-8"), 490),
                    ("zip", zipfile.ZipFile(z).read(f"{z.stem}/SKILL.md").decode(), 850),
                ):
                    m = re.search(r"^description:\s*(.*)$", texto, re.M)
                    if not m:
                        err(f"{z.stem} ({etiqueta}): SKILL.md sin 'description'")
                        continue
                    v = m.group(1).strip()
                    if v.startswith('"'):
                        v = v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
                    n = len(v.encode("utf-8"))
                    if n > tope:
                        err(f"{z.stem} ({etiqueta}): description de {n} bytes, tope {tope}")

# --------------------------------------------------------------------- salida
for w in warnings:
    print(f"::warning::{w}")
for e in errors:
    print(f"::error::{e}")

print()
print(f"{len(skill_files)} skill(s) revisadas · {len(errors)} error(es) · {len(warnings)} aviso(s)")
if errors:
    print("\nFALLO: corrige los errores antes de publicar — el plugin no cargaría.")
    sys.exit(1)
print("OK: la estructura del plugin es válida.")
