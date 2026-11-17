"""El frontmatter exportado no lleva barras invertidas de escape.

Defecto observado en ChatGPT web el 2026-11-17: la skill `minima` se subio
bien, pero su descripcion aparecia con barras literales
(`diga \\"pasame esta fecha a ISO\\"`) y el contador del editor sumaba esos
cuatro caracteres. El conversor escribia la descripcion entre comillas
dobles con las comillas interiores escapadas. Es YAML valido -la app de
Codex lo leia bien-, pero el lector de ChatGPT web no decodifica los
escapes.

Dos cambios lo evitan:

  - Solo se entrecomilla cuando YAML lo exige. Una comilla, un corchete o
    una arroba en mitad del texto son legales en un escalar plano; lo que
    obliga a entrecomillar es un indicador al PRINCIPIO, `: ` o ` #` dentro,
    un `:` final o un escalar que YAML leeria como otro tipo.
  - Si hay que entrecomillar y el valor lleva `"` o `\\`, se usan comillas
    simples, que no tienen escapes con barra: la comilla simple se dobla.

Como en test_frontmatter_tipos, PyYAML solo se usa como lector
independiente cuando esta instalado.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ayuda import RAIZ, RAIZ_SCRIPTS, importar_exporter

importar_exporter()

from exporter.frontmatter import parse_simple_yaml, split_frontmatter, yaml_escape  # noqa: E402

try:
    import yaml
except ImportError:      # el CI no lo instala; el runtime no lo necesita
    yaml = None

CONVERT = RAIZ_SCRIPTS / "convert.py"

DESCRIPCION_MINIMA = ('Cárgala cuando el usuario pida convertir una fecha entre '
                      'formatos, diga "pásame esta fecha a ISO" o "qué día de la '
                      'semana fue". Convierte fechas entre representaciones habituales.')

# Llevan un caracter especial en mitad del texto: van sin comillas.
LLANO_CON_INDICADOR_DENTRO = [
    DESCRIPCION_MINIMA, 'dice "hola"', "l'eau", "v1.2 [beta]", "a, b", "x & y",
    "100%", "correo@ejemplo.invalid", "C#", "C:\\tmp", "https://ejemplo.invalid/a",
    "a{b}c", "uno | dos", "mayor > menor", "a*b", "¡hola!",
]

# YAML exige comillas: indicador al principio, `: ` o ` #` dentro, `:` final.
EXIGEN_COMILLAS = [
    '"Hola" dice', "'hola' dice", "[beta] v1", "{a}", "&ancla", "*alias", "!tag",
    "| bloque", "> plegado", "%dir", "@usuario", "`codigo`", ", coma", "#titulo",
    "con: dos puntos", "texto #comentario", "termina:", 'clave: "valor"',
    "ruta: C:\\tmp", "a: l'eau \"x\"",
]


class SinBarras(unittest.TestCase):

    def test_la_descripcion_de_minima_sale_tal_cual(self):
        self.assertEqual(yaml_escape(DESCRIPCION_MINIMA), DESCRIPCION_MINIMA)

    def test_un_indicador_en_mitad_del_texto_no_obliga_a_entrecomillar(self):
        for v in LLANO_CON_INDICADOR_DENTRO:
            self.assertEqual(yaml_escape(v), v, v)

    def test_lo_que_exige_comillas_las_lleva(self):
        for v in EXIGEN_COMILLAS:
            salida = yaml_escape(v)
            self.assertIn(salida[0], "\"'", v)
            self.assertEqual(salida[0], salida[-1], v)

    def test_nunca_hay_una_barra_que_no_estuviera_en_el_valor(self):
        for v in LLANO_CON_INDICADOR_DENTRO + EXIGEN_COMILLAS:
            self.assertEqual(yaml_escape(v).count("\\"), v.count("\\"), v)

    def test_con_comillas_dobles_o_barra_se_usan_comillas_simples(self):
        self.assertEqual(yaml_escape('"Hola" dice'), "'\"Hola\" dice'")
        self.assertEqual(yaml_escape("ruta: C:\\tmp"), "'ruta: C:\\tmp'")
        self.assertEqual(yaml_escape("a: l'eau \"x\""), "'a: l''eau \"x\"'")

    def test_sin_comillas_dobles_ni_barra_se_siguen_usando_dobles(self):
        self.assertEqual(yaml_escape("con: dos puntos"), '"con: dos puntos"')
        self.assertEqual(yaml_escape("4.1"), '"4.1"')
        self.assertEqual(yaml_escape("'hola' dice"), "\"'hola' dice\"")

    def test_el_parser_propio_lee_el_mismo_valor(self):
        for v in LLANO_CON_INDICADOR_DENTRO + EXIGEN_COMILLAS:
            leido = parse_simple_yaml("k: {}\n".format(yaml_escape(v)))["k"]
            self.assertEqual(leido, v, v)

    @unittest.skipIf(yaml is None, "PyYAML no esta instalado")
    def test_un_lector_yaml_independiente_lee_el_mismo_valor(self):
        for v in LLANO_CON_INDICADOR_DENTRO + EXIGEN_COMILLAS:
            leido = yaml.safe_load("k: {}\n".format(yaml_escape(v)))["k"]
            self.assertEqual(leido, v, v)


class PorElCLI(unittest.TestCase):

    def test_el_skill_md_de_minima_no_lleva_barras(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(tmp), True)
        origen = RAIZ / "tests" / "fixtures" / "skill-minima"
        r = subprocess.run(
            [sys.executable, str(CONVERT), "export", str(origen), "--out", str(tmp / "out")],
            capture_output=True, text=True, cwd=str(RAIZ),
            env=dict(os.environ, CSE_FECHA="2026-09-01"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        texto = (tmp / "out" / "minima" / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = texto.split("---")[1]
        self.assertNotIn("\\", frontmatter)
        self.assertIn("\ndescription: " + DESCRIPCION_MINIMA + "\n", frontmatter)
        fm, _, _ = split_frontmatter(texto)
        self.assertEqual(fm["description"], DESCRIPCION_MINIMA)


if __name__ == "__main__":
    unittest.main()
