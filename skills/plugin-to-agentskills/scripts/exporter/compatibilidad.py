"""Cruza lo que una skill exige con lo que un destino ofrece.

Dos canales, porque hay dos clases de hecho:

  - Capacidades: lo que el destino puede hacer. Presencia o ausencia.
  - Peligros de conducta: lo que el destino hace MAL teniendo la capacidad.

El segundo canal existe porque el primero no basta. Mistral Vibe Work
declara filesystem.escribir = «si» y es verdad: escribe. Lo que falla es que
la escritura no sobrevive y el agente reconstruye de memoria el registro
perdido. Por el canal de capacidades eso pasa la revision; solo el canal de
peligros lo detiene.
"""

from __future__ import annotations

import datetime

from exporter.modelo import Estado, Evaluacion

# Niveles con los que damos la capacidad por disponible. `parcial` no basta
# para una capacidad requerida: si solo funciona a medias, el resultado de la
# skill tambien.
CAPACIDAD_SUFICIENTE = {"si", "si_con_confirmacion"}

# Un peligro disparado contribuye este estado. Un peligro `alta` lleva a
# no_compatible aunque no falte ninguna capacidad: la skill se instala y se
# ejecuta, pero su consecuencia la hace inadecuada para ese destino.
#
# `baja` mapea a COMPATIBLE a proposito, y no significa "se ignora":
# Estado.peor() nunca elige COMPATIBLE por encima de nada, asi que el estado no
# cambia, pero el peligro y su motivo SI quedan registrados para que salgan en
# el informe. Es lo que pide el diseno: «baja → nota informativa».
ESTADO_POR_SEVERIDAD = {
    "alta": Estado.NO_COMPATIBLE,
    "media": Estado.DEGRADADO,
    "baja": Estado.COMPATIBLE,
}


def evaluar(skill, perfil, hoy: datetime.date) -> list:
    """Devuelve una Evaluacion por cada modo de instalacion del perfil."""
    motivos, peligros, estados = [], [], []

    # --- Canal 1: capacidades ---
    for cap in skill.capacidades:
        nivel = perfil.capacidad(cap.nombre)
        if nivel in CAPACIDAD_SUFICIENTE:
            continue
        if nivel == "desconocido":
            estados.append(Estado.NO_VERIFICABLE)
            motivos.append(
                "{}: el perfil no declara esta capacidad, asi que no se puede "
                "afirmar nada.".format(cap.nombre))
        elif cap.nivel == "requerida":
            estados.append(Estado.NO_COMPATIBLE)
            motivos.append(
                "{}: requerida por la skill y el destino la declara «{}».".format(
                    cap.nombre, nivel))
        else:
            estados.append(Estado.DEGRADADO)
            motivos.append(
                "{}: opcional, y el destino la declara «{}».".format(cap.nombre, nivel))

    # --- Canal 2: peligros de conducta ---
    vistos = set()
    for senal in skill.senales:
        for peligro in perfil.peligros_para(senal.id):
            if peligro["id"] in vistos:
                continue
            vistos.add(peligro["id"])
            peligros.append(peligro)
            estados.append(ESTADO_POR_SEVERIDAD[peligro["severidad"]])
            motivos.append("{} (visto en {}).".format(peligro["titulo"], senal.ubicacion))

    # --- Caducidad de la evidencia ---
    if perfil.caducado(hoy):
        estados.append(Estado.NO_VERIFICABLE)
        motivos.append(
            "La evidencia de este perfil venció el {} (revisar_tras) y no se ha "
            "vuelto a comprobar.".format(perfil.datos["evidencia"]["revisar_tras"]))

    # --- Adaptaciones aplicadas ---
    if skill.adaptaciones:
        estados.append(Estado.COMPATIBLE_CON_ADAPTACION)
        motivos.extend("Adaptación aplicada: {}".format(a) for a in skill.adaptaciones)

    estado = Estado.peor(estados)
    return [Evaluacion(destino=perfil.id, modo_instalacion=modo, estado=estado,
                       motivos=list(motivos), peligros=list(peligros),
                       bloqueo_seguridad=None)
            for modo in perfil.modos()]
