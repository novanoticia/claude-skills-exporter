"""Informe legible y resumen en JSON.

El informe se abre con la matriz porque es la respuesta que el usuario viene
a buscar: no «cuanto riesgo tiene esta skill», sino «donde puedo subirla».
"""

from __future__ import annotations

from exporter.i18n import t
from exporter.modelo import Estado, Nivel

ICONO_SEG = {
    Nivel.BAJO: "🟢",
    Nivel.MODERADO: "🟡",
    Nivel.ALTO: "🟠",
    Nivel.CRITICO: "🔴",
    Nivel.NO_EVALUABLE: "🔵",
}

ICONO_SEVERIDAD = {"critica": "🔴", "alta": "🟠", "media": "🟡", "baja": "🔵"}


def etiqueta_dimension(d: str) -> str:
    return t("dimension." + d)


def etiqueta_nivel(nivel: str) -> str:
    return t("nivel." + nivel)


ICONO = {
    Estado.COMPATIBLE: "🟢",
    Estado.COMPATIBLE_CON_ADAPTACION: "🟡",
    Estado.DEGRADADO: "🟠",
    Estado.NO_VERIFICABLE: "🔵",
    Estado.NO_COMPATIBLE: "🔴",
}


def etiqueta_estado(estado: str) -> str:
    return t("estado." + estado)


def seccion_seguridad(veredicto) -> str:
    """La cabecera del informe: que puede hacer este paquete si lo instalas.

    Va arriba porque es la pregunta que nadie viene a hacer. Quien ejecuta un
    exportador quiere saber a donde puede subir sus skills, no si el
    repositorio le va a robar las claves — y por eso no se le puede pedir que
    la pida.
    """
    L = [t("informe.seguridad.titulo"), "",
         # Sin icono interpuesto: el spec §8 fija `**Nivel de riesgo:** alto`
         # y la prueba busca esa subcadena literal. Los iconos viven en la
         # tabla de dimensiones y en la lista de hallazgos, donde sirven para
         # barrer con la vista; aqui solo estorbarian al grep.
         t("informe.seguridad.nivel", nivel=etiqueta_nivel(veredicto.nivel)),
         "",
         t("informe.seguridad.recomendacion",
           texto=t("recomendacion." + veredicto.recomendacion)),
         ""]

    if veredicto.escalada_por_combinacion:
        dims = sorted({h.dimension for h in veredicto.hallazgos
                       if h.severidad == "alta" and h.confianza == "alta"})
        L += [t("informe.seguridad.escalada",
                dims=", ".join(etiqueta_dimension(d).lower() for d in dims)),
              ""]

    L += [t("informe.seguridad.tabla.cabecera"), "|---|---|"]
    for d in ("tecnico", "cadena_de_suministro", "comportamiento"):
        nivel = veredicto.dimensiones.get(d, Nivel.BAJO)
        L.append("| {} | {} {} |".format(
            etiqueta_dimension(d), ICONO_SEG[nivel], etiqueta_nivel(nivel)))
    L.append("")

    if veredicto.hay_contenido_opaco:
        L += [t("informe.seguridad.opaco"), ""]

    if not veredicto.hallazgos:
        L += [t("informe.seguridad.sin_hallazgos"), ""]
        return "\n".join(L)

    L += [t("informe.seguridad.hallazgos"), ""]
    for i, h in enumerate(veredicto.hallazgos, start=1):
        L += [t("informe.seguridad.hallazgo.linea1",
                i=i, icono=ICONO_SEVERIDAD[h.severidad], id=h.id,
                ubicacion=h.ubicacion, ambito=t("ambito." + h.ambito)),
              "   {}".format(h.titulo),
              t("informe.seguridad.hallazgo.mitigacion", texto=h.mitigacion),
              t("informe.seguridad.hallazgo.confianza",
                texto=t("confianza." + h.confianza)),
              ""]

    if any(h.familia == "conducta_de_prompt" for h in veredicto.hallazgos):
        L += [t("informe.seguridad.nota_prompt"), ""]

    return "\n".join(L)


def _celda(evaluaciones, anulado: bool = False) -> str:
    if not evaluaciones:
        return "—"
    estado = Estado.peor([e.estado for e in evaluaciones])
    if any(e.bloqueo_seguridad is not None for e in evaluaciones):
        # El bloqueo se decide por skill (tarea 8, `bloqueo_para`): todas las
        # evaluaciones de una misma skill lo comparten. Sin esta guarda el
        # icono normal de compatibilidad mentiria sobre un artefacto que no
        # se ha escrito.
        #
        # Con anulacion el artefacto SI esta escrito, asi que "bloqueado"
        # seria igual de falso por el otro lado. Se dice lo que ha pasado:
        # el estado real que le corresponde, marcado con el aviso de que
        # arrastra un bloqueo que alguien decidio saltarse.
        if not anulado:
            return t("informe.matriz.bloqueado")
        return t("informe.matriz.con_bloqueo", estado=etiqueta_estado(estado))
    return "{} {}".format(ICONO[estado], etiqueta_estado(estado))


# De peor a mejor. `Finding.severity` usa el vocabulario de portabilidad,
# que no tiene `critica`: esa solo existe en el de seguridad.
ORDEN_SEVERIDAD = ("alta", "media", "baja")


def _hallazgos_de_portabilidad(r) -> list:
    """Los Finding de una skill, que hasta ahora solo veia resumen.json.

    El informe renderizaba origen, descripcion, adaptaciones y evaluaciones
    por destino, pero nunca recorria `r.findings`. El CLI remite al informe,
    asi que quien lo leia no llegaba a ver ni la descripcion sin criterio de
    activacion, ni el enlace simbolico omitido, ni el fichero que no se pudo
    leer: existian solo en el JSON.

    Se dicen "de portabilidad" a proposito. El informe ya trae una lista de
    hallazgos mas arriba, la de seguridad, con otro vocabulario -ids SEC-,
    ambito, confianza-, y llamar igual a las dos cosas en el mismo documento
    invitaria a confundirlas.

    Se ordenan de peor a mejor, de forma estable: quien abre el informe por
    una skill con veinte hallazgos necesita los graves arriba, y dentro de
    cada severidad el orden en que el pipeline los encontro sigue siendo
    informativo (primero el frontmatter, luego las senales, luego el
    empaquetado).
    """
    if not r.findings:
        return []
    orden = {s: i for i, s in enumerate(ORDEN_SEVERIDAD)}
    ordenados = sorted(r.findings,
                       key=lambda f: orden.get(f.severity, len(ORDEN_SEVERIDAD)))
    L = [t("informe.portabilidad.titulo", n=len(ordenados)), ""]
    for f in ordenados:
        L.append(t("informe.portabilidad.linea",
                   icono=ICONO_SEVERIDAD.get(f.severity, "•"), codigo=f.code,
                   severidad=t("severidad." + f.severity), mensaje=f.message))
    L.append("")
    return L


def informe_markdown(resultados, evaluaciones, origen, perfiles,
                     seguridad=None, anulado: bool = False) -> str:
    ids = sorted(perfiles)
    L = [t("informe.titulo"), ""]
    if seguridad is not None:
        L += [seccion_seguridad(seguridad), ""]
    if anulado:
        L += [t("informe.nota_anulacion"), ""]
    L += [
        t("informe.origen", origen=origen),
        t("informe.skills_analizadas", n=len(resultados)),
        "",
        t("informe.matriz.titulo"),
        "",
        "| " + t("informe.matriz.skill") + " | "
        + " | ".join(perfiles[i].label for i in ids) + " |",
        "|---" * (len(ids) + 1) + "|",
    ]
    for r in resultados:
        celdas = [_celda(evaluaciones.get(r.name, {}).get(i, []), anulado)
                  for i in ids]
        L.append("| `{}` | {} |".format(r.name, " | ".join(celdas)))
    L += [
        "",
        t("informe.matriz.aviso"),
        "",
        t("informe.detalle.titulo"),
        "",
    ]
    for r in resultados:
        L += ["### `{}`".format(r.name), ""]
        bloqueo = next((ev.bloqueo_seguridad
                        for i in ids
                        for ev in evaluaciones.get(r.name, {}).get(i, [])
                        if ev.bloqueo_seguridad is not None), None)
        if bloqueo is not None:
            # El §7 del diseno exige que la entrada de la skill se encabece
            # con el bloqueo y su motivo. Sin esto el "por que" solo vive en
            # stderr y en resumen.json, y el informe -que es lo que el
            # usuario lee- dice que hay un 🚫 sin decir de donde sale.
            #
            # Con anulacion los artefactos SI estan en disco, asi que la
            # formula de siempre afirmaba algo falso. El bloqueo sigue siendo
            # lo mas importante de esta entrada y no se pierde ni una linea
            # de el: lo que cambia es el verbo, de "no se escribieron" a "se
            # escribieron de todos modos, y fue una decision".
            if anulado:
                L += [t("informe.detalle.bloqueo_anulado",
                        regla=bloqueo.regla_id,
                        severidad=t("severidad." + bloqueo.severidad),
                        fichero=bloqueo.fichero, linea=bloqueo.linea), ""]
            else:
                L += [t("informe.detalle.bloqueo",
                        regla=bloqueo.regla_id,
                        severidad=t("severidad." + bloqueo.severidad),
                        fichero=bloqueo.fichero, linea=bloqueo.linea), ""]
        L += [t("informe.detalle.origen", origen=r.src_dir),
              t("informe.detalle.descripcion", texto=r.description[:300]), ""]
        if r.adaptations:
            L += [t("informe.detalle.adaptado"), ""]
            L += ["- {}".format(a) for a in r.adaptations]
            L.append("")
        L += _hallazgos_de_portabilidad(r)
        for i in ids:
            for ev in evaluaciones.get(r.name, {}).get(i, []):
                if ev.estado == Estado.COMPATIBLE:
                    continue
                L.append(t("informe.destino.cabecera",
                           icono=ICONO[ev.estado], destino=perfiles[i].label,
                           modo=ev.modo_instalacion,
                           estado=etiqueta_estado(ev.estado)))
                L.append("")
                L += ["- {}".format(m) for m in ev.motivos]
                for p in ev.peligros:
                    L.append(t("informe.destino.mitigacion", texto=p["mitigacion"]))
                    L.append(t("informe.destino.evidencia",
                               confianza=p["evidencia"]["confianza"],
                               fecha=p["evidencia"]["verificado_el"]))
                # Las capacidades no tienen evidencia propia -no son un
                # peligro observado, son una casilla que el perfil declara o
                # no-, así que la cita es la del perfil entero: es la fuente
                # real de "cuán fiable es lo que este destino declara saber
                # hacer". Sin esto, la mayoría de las celdas rojas (las que
                # vienen del canal de capacidades) no citaban evidencia
                # ninguna, incumpliendo el criterio de aceptación 4.
                ev_perfil = perfiles[i].datos["evidencia"]
                L.append(t("informe.destino.evidencia_perfil",
                           confianza=ev_perfil["confianza"],
                           fecha=ev_perfil["verificado_el"]))
                L.append("")
    return "\n".join(L) + "\n"


def resumen_json(resultados, evaluaciones, origen, seguridad=None) -> dict:
    # `seguridad` lleva valor por defecto None a proposito: tests/test_informes.py
    # llama a esta funcion con la aridad antigua, y su cometido es la matriz de
    # compatibilidad, no la seguridad.
    return {
        "report_version": "3.0",
        "origen": origen,
        "seguridad": None if seguridad is None else {
            "nivel_riesgo": seguridad.nivel,
            "recomendacion_instalacion": seguridad.recomendacion,
            "dimensiones": dict(seguridad.dimensiones),
            "escalada_por_combinacion": seguridad.escalada_por_combinacion,
            "hay_contenido_opaco": seguridad.hay_contenido_opaco,
            "hallazgos": [
                {
                    "id": h.id, "familia": h.familia, "dimension": h.dimension,
                    "severidad": h.severidad, "confianza": h.confianza,
                    "ambito": h.ambito, "ubicacion": h.ubicacion,
                    "muestra": h.muestra, "titulo": h.titulo,
                    "mitigacion": h.mitigacion,
                }
                for h in seguridad.hallazgos
            ],
        },
        "skills": [
            {
                "name": r.name,
                "adaptaciones": list(r.adaptations),
                "hallazgos": [
                    {"severidad": f.severity, "codigo": f.code, "mensaje": f.message}
                    for f in r.findings
                ],
                "compatibilidad": {
                    destino: [
                        {
                            "modo_instalacion": ev.modo_instalacion,
                            "estado": ev.estado,
                            "motivos": list(ev.motivos),
                            "peligros": [p["id"] for p in ev.peligros],
                            "bloqueo_seguridad": (
                                None if ev.bloqueo_seguridad is None else {
                                    "regla_id": ev.bloqueo_seguridad.regla_id,
                                    "severidad": ev.bloqueo_seguridad.severidad,
                                    "fichero": ev.bloqueo_seguridad.fichero,
                                    "linea": ev.bloqueo_seguridad.linea,
                                }),
                        }
                        for ev in evs
                    ]
                    for destino, evs in sorted(evaluaciones.get(r.name, {}).items())
                },
            }
            for r in resultados
        ],
    }
