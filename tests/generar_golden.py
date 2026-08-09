#!/usr/bin/env python3
"""Regenera los golden files de tests/golden/.

Ejecutar SOLO cuando un cambio de comportamiento sea deseado, y revisar el
diff antes de commitear: ese diff es la unica senal de que un cambio en un
perfil de destino ha alterado informes anteriores.

    python3 tests/generar_golden.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ayuda import RAIZ, RAIZ_SCRIPTS  # noqa: E402
from test_golden import CON_SKILLS, FECHA_FIJA, FIXTURES, GOLDEN, normalizar  # noqa: E402


def main() -> int:
    GOLDEN.mkdir(exist_ok=True)
    entorno = dict(os.environ)
    # Misma fecha fija que usan las pruebas: si aqui se usara la fecha real
    # del sistema, cada regeneracion produciria un golden distinto sin que
    # nadie hubiera cambiado nada, y el diff dejaria de ser una senal fiable.
    entorno["CSE_FECHA"] = FECHA_FIJA
    for fixture in CON_SKILLS:
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [sys.executable, str(RAIZ_SCRIPTS / "convert.py"), "export",
                 str(FIXTURES / fixture), "--out", tmp],
                capture_output=True, text=True, cwd=str(RAIZ), env=entorno)
            if r.returncode != 0:
                print("[error] {}: {}".format(fixture, r.stderr), file=sys.stderr)
                return 1
            datos = normalizar(json.loads(
                (Path(tmp) / "resumen.json").read_text(encoding="utf-8")))
        (GOLDEN / (fixture + ".json")).write_text(
            json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print("regenerado", fixture)

    from test_seg_golden import FIXTURES_SEG  # noqa: E402
    GOLDEN_SEG = Path(__file__).resolve().parent / "golden-seguridad"
    GOLDEN_SEG.mkdir(exist_ok=True)
    for fixture in FIXTURES_SEG:
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [sys.executable, str(RAIZ_SCRIPTS / "convert.py"), "export",
                 str(FIXTURES / fixture), "--out", tmp,
                 "--anular-revision-seguridad"],
                capture_output=True, text=True, cwd=str(RAIZ), env=entorno)
            resumen = Path(tmp) / "resumen.json"
            # Aqui NO se comprueba el codigo de salida: un fixture de
            # seguridad esta hecho para ensuciar el veredicto, y con la
            # anulacion devuelve 0 pero podria devolver 2 si alguien cambia
            # la tabla. Lo unico que importa es que haya producido salida.
            if not resumen.exists():
                print("[error] {}: sin resumen.json\n{}".format(fixture, r.stderr),
                      file=sys.stderr)
                return 1
            datos = normalizar(json.loads(resumen.read_text(encoding="utf-8")))
        (GOLDEN_SEG / (fixture + ".json")).write_text(
            json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print("regenerado (seguridad)", fixture)
    return 0


if __name__ == "__main__":
    sys.exit(main())
