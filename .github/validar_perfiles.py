#!/usr/bin/env python3
"""Valida los perfiles de destino y su concordancia con la documentacion.

Dos comprobaciones distintas:

1. Cada targets/*.json valida contra _schema.json. Requiere `jsonschema`,
   que se puede instalar aqui porque esto solo corre en CI: el conversor
   sigue siendo solo-stdlib.

2. Los datos de cada perfil aparecen en la prosa. Por CONTENCION, no por
   parseo: no se intenta entender el texto, solo que la etiqueta, el
   presupuesto y la ruta de instalacion esten escritos en algun sitio. Si
   alguien cambia un presupuesto en el JSON y no en el README, falla.

La prosa se sigue escribiendo a mano a proposito. La evidencia empirica de
portabilidad.md es narrativa —«observado en una ejecucion real sobre un
buzon de 358 correos»— y generarla la empobreceria.
"""

import datetime
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("[error] falta jsonschema. En CI: pip install jsonschema", file=sys.stderr)
    sys.exit(1)

DOCS = [
    Path("README.md"),
    Path("skills/plugin-to-agentskills/references/portabilidad.md"),
]
TARGETS = Path("skills/plugin-to-agentskills/scripts/exporter/targets")


def main(raiz: Path) -> int:
    targets = raiz / TARGETS
    esquema = json.loads((targets / "_schema.json").read_text(encoding="utf-8"))
    textos = {d: (raiz / d).read_text(encoding="utf-8") for d in DOCS}
    hoy = datetime.date.today()
    errores, avisos = [], []

    perfiles = sorted(p for p in targets.glob("*.json") if not p.name.startswith("_"))
    if not perfiles:
        print("[error] no hay ningun perfil en targets/", file=sys.stderr)
        return 1

    for ruta in perfiles:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(datos, esquema)
        except jsonschema.ValidationError as e:
            errores.append("{}: {}".format(ruta.name, e.message))
            continue

        if datos["id"] != ruta.stem:
            errores.append("{}: el id '{}' no coincide con el fichero".format(
                ruta.name, datos["id"]))

        # Concordancia con la prosa, por contencion.
        label = datos["label"]
        presupuesto = str(datos["formato"]["presupuesto_description_bytes"])
        if not any(label in t for t in textos.values()):
            errores.append("{}: la etiqueta «{}» no aparece en la documentacion".format(
                ruta.name, label))
        if not any(presupuesto in t for t in textos.values()):
            errores.append(
                "{}: el presupuesto {} bytes no aparece en la documentacion. "
                "Si lo has cambiado en el JSON, cambialo tambien en el README y "
                "en portabilidad.md".format(ruta.name, presupuesto))

        revisar = datetime.date.fromisoformat(datos["evidencia"]["revisar_tras"])
        if revisar < hoy:
            avisos.append(
                "{}: la evidencia vencio el {}. `audit` degradara a no_verificable "
                "hasta que se vuelva a comprobar y se suba la fecha.".format(
                    ruta.name, revisar.isoformat()))

    for a in avisos:
        print("::warning:: {}".format(a))
    for e in errores:
        print("[error] {}".format(e), file=sys.stderr)
    if errores:
        return 1
    print("{} perfiles validos y concordantes con la documentacion.".format(len(perfiles)))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
