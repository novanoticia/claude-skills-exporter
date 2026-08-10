"""De hallazgos a veredicto: dimensiones, nivel y recomendacion.

Todo lo de aqui es determinista y explicable. Ese es el reparto que sostiene
el proyecto: las reglas mecanicas viven en esta herramienta, y el juicio
sobre lo ambiguo corresponde a un auditor con criterio. Un nivel de riesgo
que no se pueda derivar paso a paso de los hallazgos no vale nada, porque
nadie puede discutirlo.
"""

from __future__ import annotations

from exporter.modelo import DIMENSIONES, Nivel, VeredictoSeguridad

NIVEL_POR_SEVERIDAD = {
    "critica": Nivel.CRITICO,
    "alta": Nivel.ALTO,
    "media": Nivel.MODERADO,
    "baja": Nivel.BAJO,
}

RECOMENDACION = {
    Nivel.BAJO: "instalacion_razonable",
    Nivel.MODERADO: "revisar_permisos",
    Nivel.ALTO: "revision_humana_obligatoria",
    Nivel.CRITICO: "bloqueada",
    Nivel.NO_EVALUABLE: "revision_incompleta",
}

TEXTO_RECOMENDACION = {
    "instalacion_razonable":
        "No se han detectado indicadores estáticos relevantes. Instalación "
        "razonable tras leer el informe.",
    "revisar_permisos":
        "Se han detectado operaciones de riesgo que requieren revisión. "
        "Instalación posible tras revisar los permisos que pide.",
    "revision_humana_obligatoria":
        "Se han detectado patrones incompatibles con el principio de mínimo "
        "privilegio. No se recomienda la instalación automática: exige revisión humana.",
    "bloqueada":
        "El contenido incluye patrones potencialmente maliciosos o altamente "
        "sospechosos. La instalación no puede recomendarse.",
    "revision_incompleta":
        "El paquete contiene material que no se ha podido analizar. La instalación "
        "no puede recomendarse hasta completar la revisión.",
}

# Para escalar por combinacion hace falta confianza ALTA: una heuristica no
# puede disparar sola el peor veredicto del sistema. El «al menos media» es
# del gate (tarea 8), que es otra decision y con otras consecuencias.
CONFIANZA_PARA_ESCALAR = {"alta"}


def _nivel_de(hallazgos) -> str:
    return Nivel.peor([NIVEL_POR_SEVERIDAD[h.severidad] for h in hallazgos])


def evaluar(hallazgos, hay_contenido_opaco: bool) -> VeredictoSeguridad:
    """Deriva el veredicto del paquete a partir de sus hallazgos."""
    nivel = _nivel_de(hallazgos)

    # Escalada por combinacion. Dos hallazgos altos en dimensiones distintas
    # son cualitativamente peores que dos en la misma: un paquete que descarga
    # y ejecuta codigo remoto Y ADEMAS no fija ninguna version esta haciendo
    # dos cosas malas que se refuerzan.
    altos = [h for h in hallazgos
             if h.severidad == "alta" and h.confianza in CONFIANZA_PARA_ESCALAR]
    escalada = len({h.dimension for h in altos}) >= 2
    if escalada:
        nivel = Nivel.CRITICO

    # `no_evaluable` no es un grado peor: es la ausencia de veredicto. Solo
    # manda cuando no hay ningun otro que dar, es decir cuando lo peor que se
    # ha encontrado es un aviso.
    #
    # Antes exigia nivel BAJO, y eso lo hacia inalcanzable por construccion:
    # toda fuente de opacidad produce un hallazgo -tiene que producirlo, o el
    # veredicto no se podria justificar- y esos hallazgos son de severidad
    # media, luego el nivel nunca era BAJO cuando habia opacidad. Un valor
    # del vocabulario publico que no podia darse jamas.
    #
    # MODERADO tambien cede, y ALTO y CRITICO no: si se ha encontrado algo
    # de verdad malo, ese veredicto informa mas que "no he podido mirarlo
    # todo". La opacidad domina cuando no hay nada peor que un aviso.
    if hay_contenido_opaco and nivel in (Nivel.BAJO, Nivel.MODERADO):
        nivel = Nivel.NO_EVALUABLE

    dimensiones = {d: _nivel_de([h for h in hallazgos if h.dimension == d])
                   for d in sorted(DIMENSIONES)}

    return VeredictoSeguridad(
        nivel=nivel,
        recomendacion=RECOMENDACION[nivel],
        dimensiones=dimensiones,
        escalada_por_combinacion=escalada,
        hallazgos=sorted(hallazgos, key=lambda h: (h.ubicacion, h.id)),
        hay_contenido_opaco=hay_contenido_opaco)
