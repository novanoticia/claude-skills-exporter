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

from exporter.i18n import t, t_opcional
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


def texto_de_peligro(peligro, campo: str) -> str:
    """`titulo`, `detalle` o `mitigacion` de un peligro, en el idioma activo.

    El espanol vive en el perfil de destino; los catalogos de otros idiomas
    lo sobrescriben con la clave `peligro.<id>.<campo>`.
    """
    return t_opcional("peligro.{}.{}".format(peligro["id"], campo), peligro[campo])


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
            motivos.append(t("compat.capacidad.desconocida", nombre=cap.nombre))
        elif cap.nivel == "requerida":
            estados.append(Estado.NO_COMPATIBLE)
            motivos.append(
                t("compat.capacidad.requerida", nombre=cap.nombre, nivel=nivel))
        else:
            estados.append(Estado.DEGRADADO)
            motivos.append(
                t("compat.capacidad.opcional", nombre=cap.nombre, nivel=nivel))

    # --- Canal 2: peligros de conducta ---
    vistos = set()
    for senal in skill.senales:
        for peligro in perfil.peligros_para(senal.id):
            if peligro["id"] in vistos:
                continue
            vistos.add(peligro["id"])
            peligros.append(peligro)
            estados.append(ESTADO_POR_SEVERIDAD[peligro["severidad"]])
            motivos.append(t("compat.peligro.visto", titulo=texto_de_peligro(peligro, "titulo"),
                             ubicacion=senal.ubicacion))

    # --- Caducidad de la evidencia ---
    if perfil.caducado(hoy):
        estados.append(Estado.NO_VERIFICABLE)
        motivos.append(
            t("compat.evidencia.vencida", fecha=perfil.datos["evidencia"]["revisar_tras"]))

    # --- Adaptaciones aplicadas ---
    if skill.adaptaciones:
        estados.append(Estado.COMPATIBLE_CON_ADAPTACION)
        motivos.extend(t("compat.adaptacion", texto=a) for a in skill.adaptaciones)

    # --- Instalacion sin probar, modo por modo ---
    #
    # Todo lo anterior vale igual para cualquier modo del destino. Esto no:
    # que un zip tenga el formato correcto no dice nada de instalar por URL,
    # y ninguna de las dos cosas esta probada solo porque la otra lo este.
    # Se suma a lo ya visto, no lo sustituye: Estado.peor deja ganar a un
    # impedimento conocido sobre esta incertidumbre.
    evaluaciones = []
    for modo in perfil.modos():
        estados_modo, motivos_modo = list(estados), list(motivos)
        sin_probar = perfil.instalacion_sin_probar(modo)
        if sin_probar is not None:
            estados_modo.append(Estado.NO_VERIFICABLE)
            motivos_modo.append(t("compat.instalacion." + sin_probar["motivo"],
                                  destino=perfil.label, fuente=sin_probar["fuente"]))
        evaluaciones.append(Evaluacion(
            destino=perfil.id, modo_instalacion=modo,
            estado=Estado.peor(estados_modo), motivos=motivos_modo,
            peligros=list(peligros), bloqueo_seguridad=None))
    return evaluaciones


def anotar_limites(evaluaciones, avisos, modo: str = "zip") -> None:
    """Lleva a la Evaluacion del modo `zip` los limites de paquete incumplidos.

    Los limites se miden sobre el paquete ya hecho, y eso ocurre despues de
    `evaluar`. Sin este paso el hallazgo existia pero la matriz y `--fail-on`
    no se enteraban: el informe decia a la vez que el zip incumplia el perfil
    y que el destino era compatible.

    Solo toca el modo que usa el paquete. Un destino que tambien se instala
    por URL de repositorio no sube ese zip, y su celda no cambia.

    Un limite incumplido es un impedimento conocido, asi que gana a
    `no_verificable`: una evidencia caducada no puede taparlo. Lo que se
    afirma es que incumple EL PERFIL, no que la plataforma lo rechace.
    """
    if not avisos:
        return
    for ev in evaluaciones:
        if ev.modo_instalacion != modo:
            continue
        ev.motivos.extend(t("compat.limite_paquete", aviso=a) for a in avisos)
        ev.estado = Estado.peor([ev.estado, Estado.NO_COMPATIBLE])
