"""Vocabularios cerrados y estructuras del modelo intermedio.

El modelo intermedio describe lo que una skill ES y EXIGE, sin referencia a
ningun destino. Cruzarlo con un perfil es cosa de compatibilidad.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class Estado:
    """Estados de compatibilidad, de mejor a peor."""

    COMPATIBLE = "compatible"
    COMPATIBLE_CON_ADAPTACION = "compatible_con_adaptacion"
    DEGRADADO = "degradado"
    NO_VERIFICABLE = "no_verificable"
    NO_COMPATIBLE = "no_compatible"

    # Precedencia: el peor gana. Un unico impedimento real pesa mas que
    # cualquier cantidad de cosas que si funcionan.
    ORDEN = [COMPATIBLE, COMPATIBLE_CON_ADAPTACION, DEGRADADO,
             NO_VERIFICABLE, NO_COMPATIBLE]

    @classmethod
    def peor(cls, estados) -> str:
        peor = cls.COMPATIBLE
        for e in estados:
            if cls.ORDEN.index(e) > cls.ORDEN.index(peor):
                peor = e
        return peor


# Niveles con que un perfil declara una capacidad.
NIVELES_CAPACIDAD = {"si", "si_con_confirmacion", "parcial", "no", "desconocido"}

# Niveles de confianza de la evidencia.
CONFIANZAS = {"oficial", "oficial-incompleto", "observado", "comunidad", "no-verificado"}

SEVERIDADES = {"alta", "media", "baja"}


@dataclass(frozen=True)
class Senal:
    """Un patron detectado en el cuerpo de la skill, con donde se vio."""

    id: str
    ubicacion: str      # "references/guia.md:42"
    muestra: str
    severidad_base: str  # solo la usa `inspect`, que corre sin destino


@dataclass(frozen=True)
class Capacidad:
    nombre: str
    nivel: str          # "requerida" | "opcional"


@dataclass
class SkillPortatil:
    """Lo que una skill es y exige, con independencia del destino."""

    nombre: str
    nombre_original: str
    carpeta: str
    descripcion: str
    descripcion_bytes: int = 0
    tiene_activacion: bool = False
    cuerpo_tokens: int = 0
    claves_retiradas: list = field(default_factory=list)
    claves_a_metadata: list = field(default_factory=list)
    ficheros: list = field(default_factory=list)
    tiene_scripts: bool = False
    senales: list = field(default_factory=list)
    capacidades: list = field(default_factory=list)
    adaptaciones: list = field(default_factory=list)


@dataclass
class Evaluacion:
    """Resultado de cruzar una SkillPortatil con un perfil de destino."""

    destino: str
    modo_instalacion: str
    estado: str
    motivos: list = field(default_factory=list)
    peligros: list = field(default_factory=list)
    bloqueo_seguridad: object = None   # reservado: siempre None en esta rebanada


# De senal detectada a capacidad exigida. Las senales que no aparecen aqui no
# exigen nada: o se adaptan solas (plugin-root se reescribe) o son cosmeticas.
CAPACIDAD_POR_SENAL = {
    "mcp-tool":           [("mcp.cliente", "requerida")],
    "applescript":        [("applescript", "requerida"), ("shell.ejecutar", "requerida")],
    "subagent":           [("subagentes", "requerida")],
    "hooks":              [("hooks", "requerida")],
    "home-tilde":         [("home.resolver", "requerida")],
    "estado-persistente": [("filesystem.escribir", "requerida")],
    "skill-tool":         [("skills.anidadas", "requerida")],
    "slash-plugin":       [("comandos.namespace", "opcional")],
}


def capacidades_de(senales, tiene_scripts: bool) -> list:
    """Deriva las capacidades que la skill exige, sin repetir ninguna."""
    vistas, salida = set(), []

    def anadir(nombre: str, nivel: str) -> None:
        if nombre in vistas:
            return
        vistas.add(nombre)
        salida.append(Capacidad(nombre, nivel))

    if tiene_scripts:
        anadir("scripts.ejecutar", "requerida")
    for s in senales:
        for nombre, nivel in CAPACIDAD_POR_SENAL.get(s.id, []):
            anadir(nombre, nivel)
    return salida
