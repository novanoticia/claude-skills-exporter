"""Limites del estandar Agent Skills sobre el frontmatter exportado.

Tres defectos reproducidos sobre el formato que comparten todos los destinos:

  - `name`: el recorte a 64 caracteres se hacia DESPUES de sanear, asi que
    63 letras seguidas de `-b` salian terminadas en guion. El estandar
    prohibe que el nombre empiece o acabe en guion.
  - `depends`: salia como lista YAML anidada dentro de `metadata`, y el
    estandar define `metadata` como un mapa de cadenas. Ahora va como texto
    JSON (`["a", "b"]`), que cualquier lector puede volver a convertir en
    lista sin ambiguedad.
  - `compatibility`: el estandar la limita a 500 caracteres. No se recorta
    (cortar una lista de requisitos la falsea), pero se avisa.

Como en test_frontmatter_tipos, PyYAML solo se usa como lector
independiente cuando esta instalado.
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

from exporter.frontmatter import split_frontmatter  # noqa: E402

try:
    import yaml
except ImportError:      # el CI no lo instala; el runtime no lo necesita
    yaml = None

CONVERT = RAIZ_SCRIPTS / "convert.py"
sys.path.insert(0, str(RAIZ_SCRIPTS))
import convert  # noqa: E402

DESCRIPCION = "description: Cárgala cuando el usuario lo pida.\n"


def correr(skills: dict, prueba, *args):
    """Monta un repo con {carpeta: SKILL.md} y exporta. Devuelve (proceso, out)."""
    tmp = Path(tempfile.mkdtemp())
    prueba.addCleanup(shutil.rmtree, str(tmp), True)
    for carpeta, texto in skills.items():
        d = tmp / "repo" / "skills" / carpeta
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(texto, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(CONVERT), "export", str(tmp / "repo"),
         "--out", str(tmp / "out")] + list(args),
        capture_output=True, text=True, cwd=str(RAIZ),
        env=dict(os.environ, CSE_FECHA="2026-09-01"))
    return r, tmp / "out"


def exportar(texto: str, prueba) -> Path:
    r, out = correr({"caso": texto}, prueba)
    prueba.assertEqual(r.returncode, 0, r.stdout + r.stderr)
    return out


def frontmatter_de(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8").split("---")[1]


def hallazgos(out: Path) -> list:
    d = json.loads((out / "resumen.json").read_text(encoding="utf-8"))
    return d["skills"][0]["hallazgos"]


class NombreRecortado(unittest.TestCase):

    LARGO = "a" * 63 + "-b"

    def test_el_corte_no_deja_un_guion_al_final(self):
        n = convert.sanitize_name(self.LARGO)
        self.assertEqual(n, "a" * 63)
        self.assertFalse(n.endswith("-"))

    def test_nunca_supera_64_ni_acaba_en_guion(self):
        for raw in ("a" * 64 + "-b", "x-" * 40, "Á" + "b" * 70, "-" * 3 + "c" * 70):
            n = convert.sanitize_name(raw)
            self.assertLessEqual(len(n), 64, raw)
            self.assertFalse(n.startswith("-") or n.endswith("-"), raw)

    def test_un_nombre_que_ya_cabe_no_cambia(self):
        self.assertEqual(convert.sanitize_name("a" * 64), "a" * 64)
        self.assertEqual(convert.sanitize_name("mi-skill"), "mi-skill")

    def test_la_carpeta_exportada_lleva_el_nombre_saneado(self):
        out = exportar("---\nname: " + self.LARGO + "\n" + DESCRIPCION
                       + "---\n# X\n\nHaz algo.\n", self)
        self.assertTrue((out / ("a" * 63) / "SKILL.md").is_file())
        self.assertTrue((out / ("a" * 63 + ".zip")).is_file())
        self.assertFalse((out / ("a" * 63 + "-")).exists())

    def test_la_unicidad_usa_la_misma_normalizacion(self):
        # Tras el corte, los dos nombres publican lo mismo: debe abortar.
        r, out = correr({
            "uno": "---\nname: " + self.LARGO + "\n" + DESCRIPCION + "---\n# X\n",
            "dos": "---\nname: " + "a" * 63 + "\n" + DESCRIPCION + "---\n# X\n",
        }, self)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("a" * 63, r.stdout + r.stderr)
        self.assertFalse((out / ("a" * 63 + ".zip")).exists())


class DependsComoTextoJSON(unittest.TestCase):

    def test_la_lista_sale_como_cadena_json_bajo_metadata(self):
        out = exportar("---\nname: deps\n" + DESCRIPCION
                       + "depends:\n  - una\n  - otra\n---\n# X\n\nHaz algo.\n", self)
        fm = frontmatter_de(out / "deps" / "SKILL.md")
        self.assertIn("  depends: '[\"una\", \"otra\"]'\n", fm)
        self.assertNotIn("    - ", fm)
        leido, _, _ = split_frontmatter((out / "deps" / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual(json.loads(leido["metadata"]["depends"]), ["una", "otra"])
        if yaml is not None:
            meta = yaml.safe_load(fm)["metadata"]
            self.assertTrue(all(isinstance(v, str) for v in meta.values()), meta)
            self.assertEqual(json.loads(meta["depends"]), ["una", "otra"])

    def test_los_acentos_no_se_escapan_en_el_json(self):
        out = exportar("---\nname: deps\n" + DESCRIPCION
                       + "depends:\n  - cálculo\n---\n# X\n\nHaz algo.\n", self)
        fm = frontmatter_de(out / "deps" / "SKILL.md")
        self.assertIn("  depends: '[\"cálculo\"]'\n", fm)

    def test_no_pisa_un_depends_previo_en_metadata(self):
        out = exportar("---\nname: deps\n" + DESCRIPCION
                       + "metadata:\n  depends: propia\n  autor: Ana\n"
                       + "depends:\n  - una\n---\n# X\n\nHaz algo.\n", self)
        fm = frontmatter_de(out / "deps" / "SKILL.md")
        self.assertIn("  depends: propia\n", fm)
        self.assertIn("  autor: Ana\n", fm)
        self.assertNotIn("una", fm)

    def test_reexportar_no_cambia_el_frontmatter(self):
        primera = exportar("---\nname: deps\n" + DESCRIPCION
                           + "depends:\n  - una\n---\n# X\n\nHaz algo.\n", self)
        texto = (primera / "deps" / "SKILL.md").read_text(encoding="utf-8")
        segunda = exportar(texto, self)
        self.assertEqual(frontmatter_de(primera / "deps" / "SKILL.md"),
                         frontmatter_de(segunda / "deps" / "SKILL.md"))


class CompatibilityLarga(unittest.TestCase):

    def exportar_con(self, valor):
        return exportar("---\nname: compat\n" + DESCRIPCION
                        + "compatibility: " + valor + "\n---\n# X\n\nHaz algo.\n", self)

    def codigos(self, out):
        return [h["codigo"] for h in hallazgos(out)]

    def test_500_caracteres_no_avisa(self):
        out = self.exportar_con("r" * 500)
        self.assertNotIn("compatibility-larga", self.codigos(out))

    def test_501_caracteres_avisa_y_no_recorta(self):
        out = self.exportar_con("r" * 501)
        self.assertIn("compatibility-larga", self.codigos(out))
        fm, _, _ = split_frontmatter((out / "compat" / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual(fm["compatibility"], "r" * 501)

    def test_se_cuentan_caracteres_no_bytes(self):
        # 500 letras acentuadas son 1000 bytes UTF-8 pero 500 caracteres.
        out = self.exportar_con("é" * 500)
        self.assertNotIn("compatibility-larga", self.codigos(out))

    def test_el_aviso_cita_la_longitud(self):
        out = self.exportar_con("r" * 501)
        h = next(h for h in hallazgos(out) if h["codigo"] == "compatibility-larga")
        self.assertIn("501", h["mensaje"])


class PrometidasEnLaRevision(unittest.TestCase):
    """Dos casos que la revision automatica del PR 17 pidio cubrir."""

    def test_version_sin_comillas_en_el_origen_sale_como_cadena(self):
        out = exportar("---\nname: ver\n" + DESCRIPCION
                       + "version: 4.1\n---\n# X\n\nHaz algo.\n", self)
        fm = frontmatter_de(out / "ver" / "SKILL.md")
        self.assertIn('  version: "4.1"\n', fm)
        if yaml is not None:
            self.assertEqual(yaml.safe_load(fm)["metadata"]["version"], "4.1")


if __name__ == "__main__":
    unittest.main()
