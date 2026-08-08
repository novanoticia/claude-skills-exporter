"""Patrones que delatan dependencias del entorno de Claude.

La deteccion es por expresion regular y puede dar falsos positivos: por eso
cada senal lleva su ubicacion exacta y una muestra del texto, para que quien
lea el informe pueda ir a mirarlo.

La severidad NO vive aqui. Vive en el perfil del destino, porque depende de
el: `applescript` es media en Perplexity Computer, que lo ejecuta con un
corte a los ~90 s, y alta en Mistral Vibe Work, que no lo ejecuta y deja la
skill inerte. La severidad de este modulo es solo la reserva que usa
`inspect`, que corre sin destino elegido.
"""

from __future__ import annotations

import os
import re

from exporter.modelo import Senal

# Ficheros de texto en los que tiene sentido buscar.
EXTENSIONES_TEXTO = {".md", ".txt", ".py", ".sh", ".yaml", ".yml", ".json", ".toml"}

CLAUDE_TOOL_NAMES = [
    "TodoWrite", "AskUserQuestion", "NotebookEdit", "SlashCommand",
    "ExitPlanMode", "WebFetch", "TaskCreate", "TaskUpdate", "ToolSearch",
]

# (id, regex, severidad_base)
PATRONES = [
    ("plugin-root", re.compile(r"\$\{?CLAUDE_PLUGIN_ROOT\}?"), "alta"),
    ("mcp-tool", re.compile(r"\bmcp__[a-zA-Z0-9_\-]+"), "alta"),
    ("skill-tool", re.compile(r"\bSkill\s*\(\s*[\"'`]|\bSkill tool\b|\bherramienta Skill\b"), "alta"),
    ("subagent", re.compile(r"\bTask tool\b|\bsubagent_type\b|\bAgent tool\b|\bsubagente\b", re.I), "alta"),
    ("slash-plugin", re.compile(
        r"(?:^|[\s(`])/[a-z][a-z0-9]{2,}(?:-[a-z0-9]+)*:[a-z][a-z0-9]{2,}(?:-[a-z0-9]+)*\b"), "media"),
    ("hooks", re.compile(r"\bhooks?\.json\b|\bPreToolUse\b|\bPostToolUse\b"), "media"),
    ("applescript", re.compile(r"\bosascript\b|\btell\s+application\b", re.I), "media"),
    ("lote-destructivo", re.compile(
        r"\b(?:move|delete|borra|elimina|mueve|archiva)\b[^.\n]{0,60}\b(?:whose|todos|all|"
        r"cada|every|lote|batch|masiv)", re.I), "alta"),
    ("home-tilde", re.compile(r"(?<![\w/])(?:~/|\$HOME/)[\w.\-]"), "media"),
    ("estado-persistente", re.compile(r">>\s*[\"']?[~$./][^\s\"'|;)]*"), "media"),
    ("claude-md", re.compile(r"\bCLAUDE\.md\b"), "baja"),
    ("claude-brand", re.compile(r"\bClaude Code\b|\bCowork\b"), "baja"),
]

# Explicacion generica, valida sin destino. La especifica de cada plataforma
# la aporta el perfil en `peligros[].detalle`.
EXPLICACIONES = {
    "plugin-root": "Ruta ${CLAUDE_PLUGIN_ROOT}: solo existe dentro de un plugin de Claude Code.",
    "mcp-tool": "Invoca herramientas MCP por nombre; esos servidores no estaran conectados.",
    "skill-tool": "Invoca otras skills mediante la herramienta Skill de Claude.",
    "subagent": "Delega en subagentes via la herramienta Task, que no existe fuera de Claude Code.",
    "slash-plugin": "Referencia a comandos con namespace de plugin (/plugin:comando).",
    "hooks": "Depende de hooks del plugin, que no se exportan.",
    "applescript": "Usa AppleScript para llegar a aplicaciones del Mac.",
    "lote-destructivo": "Modifica o mueve elementos en bloque a partir de un filtro.",
    "home-tilde": "Lee o escribe en rutas con ~ o $HOME.",
    "estado-persistente": "Acumula estado con anexado (>>).",
    "claude-md": "Referencia a CLAUDE.md, convencion especifica de Claude Code.",
    "claude-brand": "Menciona el producto Claude por su nombre; conviene neutralizarlo.",
}


def detectar(texto: str, ruta: str) -> list:
    """Devuelve una Senal por cada par (patron, linea) que coincida.

    Una linea con dos llamadas MCP produce UNA senal, no dos: lo que importa
    para el informe es donde mirar, y la linea ya lo dice.
    """
    salida = []
    for numero, linea in enumerate(texto.splitlines(), start=1):
        for pid, rx, severidad in PATRONES:
            m = rx.search(linea)
            if m:
                salida.append(Senal(pid, "{}:{}".format(ruta, numero),
                                    m.group(0).strip()[:80], severidad))
    return salida


def detectar_en_arbol(raiz, excluir=frozenset()) -> list:
    """Recorre los ficheros de texto de una skill y acumula sus senales.

    `excluir` es un conjunto de nombres de fichero (basename, no ruta) que se
    saltan. Lo usa quien ya audito ese fichero por otra via -por ejemplo el
    cuerpo YA ADAPTADO del SKILL.md- y no quiere leerlo dos veces desde disco.
    """
    salida = []
    for base, _dirs, ficheros in os.walk(str(raiz)):
        for nombre in sorted(ficheros):
            if nombre in excluir:
                continue
            ruta = os.path.join(base, nombre)
            if os.path.splitext(nombre)[1].lower() not in EXTENSIONES_TEXTO:
                continue
            if os.path.islink(ruta):
                continue
            with open(ruta, encoding="utf-8", errors="replace") as fh:
                texto = fh.read()
            relativa = os.path.relpath(ruta, str(raiz))
            salida.extend(detectar(texto, relativa))
    return salida
