#!/usr/bin/env python3
"""Valida reglas.json y exige que cada regla tenga un fixture que la dispare.

Lo segundo importa mas que lo primero. En un motor que crece por acumulacion
de patrones, una regla que nadie sabe demostrar es una regla que nadie ha
probado: no se sabe si dispara, ni si dispara de mas. Esta comprobacion
obliga a que anadir una regla venga acompanado de la prueba de que sirve.

Requiere `jsonschema`, que solo se instala en CI: el conversor sigue siendo
solo-stdlib.
"""

import json
import subprocess
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("[error] falta jsonschema. En CI: pip install jsonschema", file=sys.stderr)
    sys.exit(1)

SEG = Path("skills/plugin-to-agentskills/scripts/exporter/seguridad")
FIXTURES = Path("tests/fixtures")
CONVERT = Path("skills/plugin-to-agentskills/scripts/convert.py")


def main(raiz: Path) -> int:
    reglas = json.loads((raiz / SEG / "reglas.json").read_text(encoding="utf-8"))
    esquema = json.loads((raiz / SEG / "_schema.json").read_text(encoding="utf-8"))
    try:
        jsonschema.validate(reglas, esquema)
    except jsonschema.ValidationError as e:
        print("[error] reglas.json: {}".format(e.message), file=sys.stderr)
        return 1

    # El spec §10 pide TRES comprobaciones y el schema solo cubre que el
    # patron sea una cadena de tres caracteres o mas. Un patron que no
    # compile se manifestaria, sin esto, como "once reglas huerfanas": un
    # mensaje que apunta al sitio equivocado y cuesta media hora entender.
    sys.path.insert(0, str(raiz / "skills/plugin-to-agentskills/scripts"))
    from exporter.seguridad.patrones import ReglaInvalida, cargar_reglas  # noqa: E402
    try:
        cargar_reglas(raiz / SEG / "reglas.json")
    except ReglaInvalida as e:
        print("[error] {}".format(e), file=sys.stderr)
        return 1

    sys.path.insert(0, str(raiz / "tests"))
    from test_seg_golden import FIXTURES_SEG  # noqa: E402

    disparadas = set()
    import os
    import tempfile
    for f in FIXTURES_SEG:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                [sys.executable, str(raiz / CONVERT), "export",
                 str(raiz / FIXTURES / f), "--out", tmp,
                 "--anular-revision-seguridad"],
                capture_output=True, text=True, cwd=str(raiz),
                env=dict(os.environ, CSE_FECHA="2026-08-08"))
            resumen = Path(tmp) / "resumen.json"
            if resumen.exists():
                datos = json.loads(resumen.read_text(encoding="utf-8"))
                disparadas |= {h["id"] for h in datos["seguridad"]["hallazgos"]}

    declaradas = {r["id"] for r in reglas["reglas"]}
    huerfanas = sorted(declaradas - disparadas)
    if huerfanas:
        print("[error] reglas sin ningun fixture que las dispare:", file=sys.stderr)
        for h in huerfanas:
            print("  " + h, file=sys.stderr)
        print("Anade un fixture en tests/fixtures/ que la active, o retira la regla.",
              file=sys.stderr)
        return 1

    print("{} reglas validas, todas cubiertas por al menos un fixture.".format(
        len(declaradas)))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
