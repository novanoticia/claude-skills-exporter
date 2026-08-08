#!/usr/bin/env python3
"""Regenera los golden files de tests/golden/.

Ejecutar SOLO cuando un cambio de comportamiento sea deseado, y revisar el
diff antes de commitear: ese diff es la unica senal de que un cambio en un
perfil de destino ha alterado informes anteriores.

    python3 tests/generar_golden.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ayuda import RAIZ, RAIZ_SCRIPTS  # noqa: E402
from test_golden import CON_SKILLS, FIXTURES, GOLDEN, normalizar  # noqa: E402


def main() -> int:
    GOLDEN.mkdir(exist_ok=True)
    for fixture in CON_SKILLS:
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [sys.executable, str(RAIZ_SCRIPTS / "convert.py"), "export",
                 str(FIXTURES / fixture), "--out", tmp],
                capture_output=True, text=True, cwd=str(RAIZ))
            if r.returncode != 0:
                print("[error] {}: {}".format(fixture, r.stderr), file=sys.stderr)
                return 1
            datos = normalizar(json.loads(
                (Path(tmp) / "resumen.json").read_text(encoding="utf-8")))
        (GOLDEN / (fixture + ".json")).write_text(
            json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print("regenerado", fixture)
    return 0


if __name__ == "__main__":
    sys.exit(main())
