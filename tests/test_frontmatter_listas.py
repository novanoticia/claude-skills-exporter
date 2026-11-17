"""Listas donde el lector de frontmatter las perdia sin avisar.

Dos defectos reproducidos:

  - Una lista dentro de `metadata` (`metadata:` / `deps:` / `- a`) convertia
    `metadata` entero en una lista: las claves hermanas desaparecian y la
    skill exportada salia sin `metadata`.
  - Una `compatibility` escrita como lista YAML no se exportaba: el filtro de
    claves portables solo acepta cadenas, y no quedaba rastro en el informe.

El estandar define `metadata` como un mapa de cadenas y `compatibility` como
cadena. Una lista dentro de `metadata` se guarda como texto JSON, igual que
`depends`; una `compatibility` en lista se une con comas y se anota.
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

try:
    import yaml
except ImportError:      # el CI no lo instala; el runtime no lo necesita
    yaml = None

CONVERT = RAIZ_SCRIPTS / "convert.py"
CABECERA = "---\nname: caso\ndescription: Cárgala cuando el usuario lo pida.\n"


def exportar(frontmatter: str, prueba) -> Path:
    """Exporta una skill con ese frontmatter extra y devuelve su carpeta."""
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


def leer(out: Path):
    texto = (out / "caso" / "SKILL.md").read_text(encoding="utf-8")
    return split_frontmatter(texto)


class ElLectorConservaListasAnidadas(unittest.TestCase):

    def test_una_lista_dentro_de_metadata_no_lo_convierte_en_lista(self):
        fm = parse_simple_yaml("metadata:\n  deps:\n    - a\n    - b\n  autor: Ana\n")
        self.assertEqual(fm["metadata"], {"deps": ["a", "b"], "autor": "Ana"})

    def test_el_guion_puede_ir_a_la_altura_de_la_clave(self):
        fm = parse_simple_yaml("metadata:\n  deps:\n  - a\n  autor: Ana\n")
        self.assertEqual(fm["metadata"], {"deps": ["a"], "autor": "Ana"})

    def test_las_listas_y_mapas_simples_no_cambian(self):
        fm = parse_simple_yaml("depends:\n  - a\n  - b\nmetadata:\n  autor: Ana\n")
        self.assertEqual(fm["depends"], ["a", "b"])
        self.assertEqual(fm["metadata"], {"autor": "Ana"})


class MetadataConListaSeExporta(unittest.TestCase):

    def setUp(self):
        self.out = exportar("metadata:\n  deps:\n    - a\n    - b\n  autor: Ana\n", self)

    def test_la_lista_sale_como_texto_json_y_la_hermana_se_conserva(self):
        fm, raw, _ = leer(self.out)
        self.assertEqual(fm["metadata"]["autor"], "Ana")
        self.assertEqual(json.loads(fm["metadata"]["deps"]), ["a", "b"])
        self.assertIn("  deps: '[\"a\", \"b\"]'\n", raw)

    def test_un_lector_yaml_ve_un_mapa_de_cadenas(self):
        if yaml is None:
            self.skipTest("PyYAML no instalado")
        _, raw, _ = leer(self.out)
        meta = yaml.safe_load(raw)["metadata"]
        self.assertTrue(all(isinstance(v, str) for v in meta.values()), meta)


class CompatibilityEnLista(unittest.TestCase):

    def setUp(self):
        self.out = exportar("compatibility:\n  - Python 3.8+\n  - git\n", self)

    def test_se_exporta_unida_con_comas(self):
        fm, _, _ = leer(self.out)
        self.assertEqual(fm["compatibility"], "Python 3.8+, git")

    def test_el_cambio_queda_anotado(self):
        _, _, cuerpo = leer(self.out)
        self.assertIn("compatibility", cuerpo.split("# X", 1)[1])

    def test_reexportar_no_cambia_el_frontmatter(self):
        texto = (self.out / "caso" / "SKILL.md").read_text(encoding="utf-8")
        _, raw, _ = split_frontmatter(texto)
        segunda = exportar(raw.split("description:", 1)[1].split("\n", 1)[1], self)
        self.assertEqual(leer(self.out)[0]["compatibility"],
                         leer(segunda)[0]["compatibility"])


if __name__ == "__main__":
    unittest.main()
