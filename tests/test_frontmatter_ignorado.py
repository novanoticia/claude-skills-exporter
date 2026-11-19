"""Lo que el lector de frontmatter no sabe leer se avisa, no se pierde callado.

Tres formas se descartaban sin dejar rastro en el informe:

  - una `compatibility` en lista sin ningun elemento con texto;
  - un bloque que empieza como lista y sigue como mapa (`metadata:` /
    `- a` / `autor: Ana`): no es YAML valido y se leia como lista;
  - un mapa de mas de un nivel dentro de `metadata` (`a:` / `b: c`): el
    lector solo cubre uno, y `a` salia como cadena vacia.

No se intenta leerlas: el subconjunto de YAML es deliberadamente pequeno. Se
avisa con el hallazgo `frontmatter-ignorado`, que nombra lo que no viaja.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ayuda import RAIZ, RAIZ_SCRIPTS, importar_exporter

importar_exporter()

from exporter.frontmatter import parse_simple_yaml, split_frontmatter  # noqa: E402

CONVERT = RAIZ_SCRIPTS / "convert.py"
CABECERA = "---\nname: caso\ndescription: Cárgala cuando el usuario lo pida.\n"


def exportar(frontmatter: str, prueba) -> Path:
    tmp = Path(tempfile.mkdtemp())
    prueba.addCleanup(shutil.rmtree, str(tmp), True)
    d = tmp / "repo" / "skills" / "caso"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(CABECERA + frontmatter + "---\n# X\n\nHaz algo.\n",
                                encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(CONVERT), "export", str(tmp / "repo"),
         "--out", str(tmp / "out")],
        capture_output=True, text=True, cwd=str(RAIZ),
        env=dict(os.environ, CSE_FECHA="2026-09-01"))
    prueba.assertEqual(r.returncode, 0, r.stdout + r.stderr)
    return tmp / "out"


def ignorado(out: Path):
    d = json.loads((out / "resumen.json").read_text(encoding="utf-8"))
    return [h for h in d["skills"][0]["hallazgos"] if h["codigo"] == "frontmatter-ignorado"]


class ElLectorApuntaLoQueNoLee(unittest.TestCase):

    def test_mapa_de_dos_niveles(self):
        perdidas = []
        fm = parse_simple_yaml("metadata:\n  a:\n    b: c\n  autor: Ana\n", perdidas)
        self.assertEqual(fm["metadata"], {"autor": "Ana"})
        self.assertEqual(perdidas, ["metadata.a"])

    def test_lista_seguida_de_mapa(self):
        perdidas = []
        fm = parse_simple_yaml("metadata:\n  - a\n  autor: Ana\n", perdidas)
        self.assertEqual(perdidas, ["metadata"])

    def test_lo_que_si_lee_no_apunta_nada(self):
        perdidas = []
        parse_simple_yaml("metadata:\n  deps:\n    - a\n  autor: Ana\n"
                          "depends:\n  - x\n", perdidas)
        self.assertEqual(perdidas, [])

    def test_sin_lista_de_perdidas_sigue_funcionando(self):
        fm, _, _ = split_frontmatter("---\nmetadata:\n  a:\n    b: c\n---\n")
        self.assertEqual(fm["metadata"], {})


class ElInformeLoAvisa(unittest.TestCase):

    def test_compatibility_en_lista_vacia(self):
        h = ignorado(exportar("compatibility:\n  - ''\n", self))
        self.assertEqual(len(h), 1)
        self.assertIn("compatibility", h[0]["mensaje"])

    def test_metadata_de_dos_niveles(self):
        out = exportar("metadata:\n  a:\n    b: c\n  autor: Ana\n", self)
        h = ignorado(out)
        self.assertEqual(len(h), 1)
        self.assertIn("metadata.a", h[0]["mensaje"])
        texto = (out / "caso" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("  autor: Ana\n", texto)
        self.assertNotIn("  a: ", texto)

    def test_metadata_que_mezcla_lista_y_mapa(self):
        h = ignorado(exportar("metadata:\n  - a\n  autor: Ana\n", self))
        self.assertEqual(len(h), 1)
        self.assertIn("metadata", h[0]["mensaje"])

    def test_un_frontmatter_normal_no_avisa(self):
        out = exportar("metadata:\n  autor: Ana\ncompatibility: Python 3.8+\n", self)
        self.assertEqual(ignorado(out), [])


if __name__ == "__main__":
    unittest.main()
