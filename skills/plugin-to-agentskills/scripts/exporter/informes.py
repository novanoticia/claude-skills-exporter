"""Informe legible y resumen en JSON.

El informe se abre con la matriz porque es la respuesta que el usuario viene
a buscar: no «cuanto riesgo tiene esta skill», sino «donde puedo subirla».
"""

from __future__ import annotations

from exporter.modelo import Estado

ICONO = {
    Estado.COMPATIBLE: "🟢",
    Estado.COMPATIBLE_CON_ADAPTACION: "🟡",
    Estado.DEGRADADO: "🟠",
    Estado.NO_VERIFICABLE: "🔵",
    Estado.NO_COMPATIBLE: "🔴",
}

ETIQUETA = {
    Estado.COMPATIBLE: "compatible",
    Estado.COMPATIBLE_CON_ADAPTACION: "adaptación",
    Estado.DEGRADADO: "degradado",
    Estado.NO_VERIFICABLE: "no verificable",
    Estado.NO_COMPATIBLE: "no compatible",
}


def _celda(evaluaciones) -> str:
    if not evaluaciones:
        return "—"
    estado = Estado.peor([e.estado for e in evaluaciones])
    return "{} {}".format(ICONO[estado], ETIQUETA[estado])


def informe_markdown(resultados, evaluaciones, origen, perfiles) -> str:
    ids = sorted(perfiles)
    L = [
        "# Informe de portabilidad",
        "",
        "- **Origen:** `{}`".format(origen),
        "- **Skills analizadas:** {}".format(len(resultados)),
        "",
        "## Matriz de compatibilidad",
        "",
        "| Skill | " + " | ".join(perfiles[i].label for i in ids) + " |",
        "|---" * (len(ids) + 1) + "|",
    ]
    for r in resultados:
        celdas = [_celda(evaluaciones.get(r.name, {}).get(i, [])) for i in ids]
        L.append("| `{}` | {} |".format(r.name, " | ".join(celdas)))
    L += [
        "",
        "> Ningún veredicto sustituye a probar la skill en el destino.",
        "",
        "## Detalle por skill",
        "",
    ]
    for r in resultados:
        L += ["### `{}`".format(r.name), "",
              "- Origen: `{}`".format(r.src_dir),
              "- Descripción: {}".format(r.description[:300]), ""]
        if r.adaptations:
            L += ["**Adaptado automáticamente:**", ""]
            L += ["- {}".format(a) for a in r.adaptations]
            L.append("")
        for i in ids:
            for ev in evaluaciones.get(r.name, {}).get(i, []):
                if ev.estado == Estado.COMPATIBLE:
                    continue
                L.append("**{} · {} ({})** — {}".format(
                    ICONO[ev.estado], perfiles[i].label, ev.modo_instalacion,
                    ETIQUETA[ev.estado]))
                L.append("")
                L += ["- {}".format(m) for m in ev.motivos]
                for p in ev.peligros:
                    L.append("- *Mitigación:* {}".format(p["mitigacion"]))
                    L.append("  Evidencia: {} · verificado el {}.".format(
                        p["evidencia"]["confianza"], p["evidencia"]["verificado_el"]))
                # Las capacidades no tienen evidencia propia -no son un
                # peligro observado, son una casilla que el perfil declara o
                # no-, así que la cita es la del perfil entero: es la fuente
                # real de "cuán fiable es lo que este destino declara saber
                # hacer". Sin esto, la mayoría de las celdas rojas (las que
                # vienen del canal de capacidades) no citaban evidencia
                # ninguna, incumpliendo el criterio de aceptación 4.
                ev_perfil = perfiles[i].datos["evidencia"]
                L.append("  Evidencia del perfil: {} · verificado el {}.".format(
                    ev_perfil["confianza"], ev_perfil["verificado_el"]))
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
