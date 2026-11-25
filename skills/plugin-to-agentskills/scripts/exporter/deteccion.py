"""Patrones que delatan dependencias del entorno de Claude.

La deteccion es por expresion regular y puede dar falsos positivos: por eso
cada senal lleva su ubicacion exacta y una muestra del texto, para que quien
lea el informe pueda ir a mirarlo.

La severidad NO vive aqui. Vive en el perfil del destino, porque depende de
el: `applescript` es alta en Perplexity Computer, que si lo ejecuta pero
corta la llamada a los ~90 s (peligro `perplexity-corte-90s`), y en Mistral
Vibe Work ni siquiera llega a disparar un peligro: la capacidad se declara
`no` y el destino sale no compatible por el canal de capacidades. La
severidad de este modulo es solo la reserva que usa `inspect`, que corre sin
destino elegido.
"""

from __future__ import annotations

import os
import re

from exporter.modelo import Senal

# Ficheros de texto en los que tiene sentido buscar.
EXTENSIONES_TEXTO = {".md", ".txt", ".py", ".sh", ".yaml", ".yml", ".json", ".toml"}

# Directorios que ningun artefacto exportado incluye jamas. Es el mismo
# conjunto que usa discover_skills() para no anidar skills y copiar_skill()
# para no copiarlos: detectar_en_arbol() lo pruna por la misma razon, para no
# avisar de senales dentro de ficheros -por ejemplo un README de
# node_modules/- que nunca llegan a ningun paquete.
IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


# Nombres de ficheros de credenciales y sufijos reservados para plantillas.
NOMBRES_SECRETO = {".env", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
                   "credentials.json", ".npmrc", ".pypirc"}
SUFIJOS_SECRETO = (".pem", ".p12", ".pfx", ".keystore")
ENV_PLANTILLA = {"example", "sample", "template", "dist", "defaults", "tpl"}

CLAVE_PRIVADA = re.compile(r"-----" r"BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")
ASIGNACION_SECRETA = re.compile(
    r"\b(?:[a-z0-9_.-]{0,64}(?:api[_-]?key|access[_-]?token|auth[_-]?token|"
    r"client[_-]?secret|private[_-]?key|secret[_-]?key|password)|token|secret)"
    r"""["']?[ \t]*[:=][ \t]*(?P<comilla>["']?)(?P<valor>[a-z0-9_+/=.:!@%-]{12,})"""
    r"""(?P=comilla)(?=[ \t]*(?:$|[\r\n#,;}\]]))""",
    re.I)
MARCADOR_SECRETO = re.compile(
    r"^(?:example|sample|dummy|placeholder|changeme|change[_-]?me|replace|your[_-]|[x*]+$)",
    re.I)


def nombre_de_credencial(nombre: str) -> bool:
    nombre = nombre.casefold()
    return (nombre in NOMBRES_SECRETO or nombre.endswith(SUFIJOS_SECRETO)
            or (nombre.startswith(".env.") and nombre.rsplit(".", 1)[-1] not in ENV_PLANTILLA))


def contiene_secreto(datos: bytes, nombre: str) -> bool:
    """Reconoce formatos de credencial sin devolver el valor detectado."""
    encoding = "utf-16" if datos.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8"
    texto = datos.decode(encoding, errors="replace")
    if CLAVE_PRIVADA.search(texto):
        return True
    # Una asignacion en Python puede apuntar a una variable o un atributo.
    # En configuraciones de texto el valor literal puede ir sin comillas.
    es_python = nombre.casefold().endswith(".py")
    return any((not es_python or m.group("comilla"))
               and not MARCADOR_SECRETO.match(m.group("valor"))
               for m in ASIGNACION_SECRETA.finditer(texto))


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

# Las explicaciones genericas de cada senal viven en el catalogo de idioma
# (exporter/i18n/*.json, claves `senal.<id>`). La especifica de cada plataforma
# la aporta el perfil en `peligros[].detalle`.


def detectar(texto: str, ruta: str, offset: int = 0) -> list:
    """Devuelve una Senal por cada par (patron, linea) que coincida.

    Una linea con dos llamadas MCP produce UNA senal, no dos: lo que importa
    para el informe es donde mirar, y la linea ya lo dice.

    `offset` desplaza la numeracion: quien llama con un fragmento de texto
    que empieza mas abajo en el fichero real -el cuerpo de un SKILL.md tras
    separar el frontmatter, por ejemplo- pasa aqui cuantas lineas se quedaron
    fuera del fragmento, para que la ubicacion reportada sea la linea real
    del fichero y no la linea dentro del fragmento.
    """
    salida = []
    for numero, linea in enumerate(texto.splitlines(), start=1 + offset):
        for pid, rx, severidad in PATRONES:
            m = rx.search(linea)
            if m:
                salida.append(Senal(pid, "{}:{}".format(ruta, numero),
                                    m.group(0).strip()[:80], severidad))
    return salida


def detectar_en_arbol(raiz, excluir=frozenset()) -> tuple:
    """Recorre los ficheros de texto de una skill y acumula sus senales.

    Devuelve `(senales, ilegibles)`. `ilegibles` es la lista de
    `(ruta_relativa, motivo)` de los ficheros que no se pudieron abrir.

    Un fichero sin permiso de lectura NO es un fichero limpio. Antes, el
    OSError sin capturar tumbaba el export entero con un traceback; pero
    tragarselo en silencio habria sido igual de malo por el otro lado,
    porque un informe sin hallazgos se lee como "aqui no hay nada" cuando en
    realidad significa "esto no lo he mirado". Por eso se devuelven aparte
    de las senales: no son un patron encontrado en la skill sino una
    limitacion de la propia auditoria, y quien llama decide como contarlo.
    `copiar_skill` tropieza despues con los mismos ficheros -tampoco puede
    leerlos para copiarlos-, asi que convert.py junta las dos listas.

    `excluir` es un conjunto de nombres de fichero que se saltan SOLO en la
    raiz del arbol. Lo usa quien ya audito ese fichero por otra via -por
    ejemplo el cuerpo YA ADAPTADO del SKILL.md- y no quiere leerlo dos veces
    desde disco. Antes se aplicaba a cualquier profundidad, y un SKILL.md
    anidado en una subcarpeta se quedaba sin auditar sin que nadie lo dijera.

    Los directorios de `IGNORED_DIRS` se podan de la busqueda: son los mismos
    que discover_skills() y copiar_skill() ya excluyen en el resto del
    pipeline, y sin esto una senal dentro de node_modules/ acababa marcando
    como no_compatible un fichero que el paquete exportado nunca incluye.
    """
    salida = []
    ilegibles = []
    for base, dirs, ficheros in os.walk(str(raiz)):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        en_la_raiz = base == str(raiz)   # os.walk devuelve la raiz tal cual
        for nombre in sorted(ficheros):
            if (en_la_raiz and nombre in excluir) or nombre_de_credencial(nombre):
                continue
            ruta = os.path.join(base, nombre)
            if os.path.splitext(nombre)[1].lower() not in EXTENSIONES_TEXTO:
                continue
            if os.path.islink(ruta):
                continue
            relativa = os.path.relpath(ruta, str(raiz))
            try:
                with open(ruta, "rb") as fh:
                    datos = fh.read()
            except OSError as e:
                ilegibles.append((relativa, e.strerror or str(e)))
                continue
            if not contiene_secreto(datos, nombre):
                salida.extend(detectar(datos.decode("utf-8", errors="replace"), relativa))
    return salida, ilegibles
