"""El frontmatter exportado conserva el tipo y el valor de cada escalar.

Dos defectos reproducidos sobre el formato compartido por todos los destinos:

  - `name: "123"` se exportaba como `name: 123`. Un lector YAML obtiene un
    entero, y el estandar pide cadenas. Lo mismo con `true`, `null` o una
    fecha: `yaml_escape` no protegia los escalares de tipado implicito.
  - Una descripcion entrecomillada con comillas escapadas acumulaba barras
    invertidas: `unquote` quitaba los delimitadores sin decodificar los
    escapes, y el serializador los volvia a escapar.

El conversor no usa PyYAML ni debe. Aqui se usa solo como lector
INDEPENDIENTE cuando esta instalado: comprobar la salida con el mismo parser
limitado que la genera no demostraria nada. Las comprobaciones sobre el texto
literal corren siempre, tambien en el CI, que no lo instala.
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

from exporter.frontmatter import (  # noqa: E402
    parse_simple_yaml, split_frontmatter, unquote, yaml_escape)

try:
    import yaml
except ImportError:      # el CI no lo instala; el runtime no lo necesita
    yaml = None

CONVERT = RAIZ_SCRIPTS / "convert.py"

# Escalares que YAML convertiria en otra cosa si van sin comillas.
TIPADO_IMPLICITO = [
    "123", "-7", "+7", "1_000", "0x1F", "0o17", "017",
    "4.1", "-0.5", ".5", "1e3", "6.02E23", ".inf", "-.INF", ".nan",
    "true", "True", "FALSE", "yes", "No", "on", "OFF", "y", "N",
    "null", "Null", "NULL", "~",
    "2026-10-07", "2026-10-07T10:00:00Z", "2026-10-07 10:00:00",
]

# Texto corriente: no debe ganar comillas que antes no llevaba.
TEXTO_LLANO = [
    "mi-skill", "fechas", "Carga un fichero", "v1.2.3", "1.2.3", "abc123",
    "123abc", "2026-10", "nulo", "yesterday", "online", "truth", "MIT",
    "Apache-2.0", "áéíóú ñ", "-con-guion-inicial",
]


class EscalaresDeTipadoImplicito(unittest.TestCase):

    def test_van_entre_comillas(self):
        for v in TIPADO_IMPLICITO:
            self.assertEqual(yaml_escape(v), '"{}"'.format(v), v)

    def test_el_texto_llano_sigue_sin_comillas(self):
        for v in TEXTO_LLANO:
            self.assertEqual(yaml_escape(v), v, v)

    def test_lo_que_ya_se_entrecomillaba_sigue_igual(self):
        self.assertEqual(yaml_escape("con: dos puntos"), '"con: dos puntos"')
        self.assertEqual(yaml_escape(""), '""')
        self.assertEqual(yaml_escape('dice "hola"'), '"dice \\"hola\\""')

    def test_un_indicador_de_lista_o_clave_al_principio_se_protege(self):
        for v in ("- uno", "? dos", "-", "?"):
            self.assertEqual(yaml_escape(v), '"{}"'.format(v), v)

    @unittest.skipIf(yaml is None, "PyYAML no esta instalado")
    def test_un_lector_yaml_independiente_lee_siempre_una_cadena(self):
        for v in TIPADO_IMPLICITO + TEXTO_LLANO + ["- uno", "? dos", "a: b", "#x"]:
            leido = yaml.safe_load("k: {}\n".format(yaml_escape(v)))["k"]
            self.assertIsInstance(leido, str, v)
            self.assertEqual(leido, v)


class EscapesReversibles(unittest.TestCase):

    def test_comillas_dobles_decodifican_sus_escapes(self):
        self.assertEqual(unquote(r'"dice \"hola\""'), 'dice "hola"')
        self.assertEqual(unquote(r'"C:\\ruta"'), "C:\\ruta")
        self.assertEqual(unquote(r'"a\tb"'), "a\tb")

    def test_comillas_simples_solo_doblan_la_comilla(self):
        self.assertEqual(unquote("'l''eau'"), "l'eau")
        # En comillas simples la barra invertida es literal.
        self.assertEqual(unquote(r"'C:\ruta'"), "C:\\ruta")
        self.assertEqual(unquote("'dice \"hola\"'"), 'dice "hola"')

    def test_un_escape_que_no_se_soporta_se_deja_como_esta(self):
        # No se reinterpreta lo que el subconjunto no cubre.
        self.assertEqual(unquote(r'"\d+ digitos"'), "\\d+ digitos")

    def test_sin_comillas_no_se_toca(self):
        self.assertEqual(unquote(r"C:\ruta \"x\""), 'C:\\ruta \\"x\\"')
        self.assertEqual(unquote("  llano  "), "llano")

    def test_ida_y_vuelta_no_cambia_el_valor(self):
        valores = ['dice "hola"', "l'eau", "C:\\ruta\\x", 'a\\"b', "áé — ñ: x",
                   "123", "true", "- uno", 'mezcla "a" y \'b\' y \\ fin']
        for v in valores:
            self.assertEqual(unquote(yaml_escape(v)), v, v)

    def test_reexportar_no_acumula_escapes(self):
        v = 'Cárgala cuando pidan "resumir" un texto'
        una = yaml_escape(v)
        dos = yaml_escape(unquote(una))
        tres = yaml_escape(unquote(dos))
        self.assertEqual(una, dos)
        self.assertEqual(dos, tres)

    def test_el_parser_aplica_lo_mismo_dentro_de_metadata(self):
        fm = parse_simple_yaml(
            'metadata:\n  autor: "Ana \\"la\\" Ruiz"\n  version: "4.1"\n')
        self.assertEqual(fm["metadata"], {"autor": 'Ana "la" Ruiz', "version": "4.1"})


def exportar(skill_md: str, prueba) -> Path:
    tmp = Path(tempfile.mkdtemp())
    prueba.addCleanup(shutil.rmtree, str(tmp), True)
    carpeta = tmp / "repo" / "skills" / "caso"
    carpeta.mkdir(parents=True)
    (carpeta / "SKILL.md").write_text(skill_md, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(CONVERT), "export", str(tmp / "repo"),
         "--out", str(tmp / "out")],
        capture_output=True, text=True, cwd=str(RAIZ),
        env=dict(os.environ, CSE_FECHA="2026-09-01"))
    prueba.assertEqual(r.returncode, 0, r.stdout + r.stderr)
    return tmp / "out"


def frontmatter_de(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8").split("---")[1]


class PorElCLI(unittest.TestCase):

    def test_un_nombre_numerico_sale_como_cadena(self):
        out = exportar('---\nname: "123"\ndescription: Cárgala cuando el '
                       'usuario lo pida.\n---\n# X\n\nHaz algo.\n', self)
        fm = frontmatter_de(out / "123" / "SKILL.md")
        self.assertIn('\nname: "123"\n', fm)
        if yaml is not None:
            self.assertEqual(yaml.safe_load(fm)["name"], "123")

    def test_los_metadatos_siguen_siendo_cadenas(self):
        out = exportar(
            "---\nname: tipos\ndescription: Cárgala cuando el usuario lo pida.\n"
            "version: '4.1'\nmetadata:\n  activo: 'true'\n  fecha: '2026-10-07'\n"
            "  autor: Ana\n---\n# X\n\nHaz algo.\n", self)
        fm = frontmatter_de(out / "tipos" / "SKILL.md")
        self.assertIn('  activo: "true"\n', fm)
        self.assertIn('  fecha: "2026-10-07"\n', fm)
        self.assertIn('  version: "4.1"\n', fm)
        self.assertIn("  autor: Ana\n", fm)
        if yaml is not None:
            meta = yaml.safe_load(fm)["metadata"]
            self.assertEqual(meta, {"activo": "true", "fecha": "2026-10-07",
                                    "version": "4.1", "autor": "Ana"})

    def test_las_comillas_de_la_descripcion_no_ganan_barras(self):
        descripcion = 'Cárgala cuando el usuario pida "resumir" un texto en C:\\tmp.'
        origen = ('---\nname: comillas\ndescription: "Cárgala cuando el usuario '
                  'pida \\"resumir\\" un texto en C:\\\\tmp."\n---\n# X\n\nHaz algo.\n')
        out = exportar(origen, self)
        for ruta in (out / "comillas" / "SKILL.md",):
            fm, _, _ = split_frontmatter(ruta.read_text(encoding="utf-8"))
            self.assertEqual(fm["description"], descripcion)
            if yaml is not None:
                leido = yaml.safe_load(frontmatter_de(ruta))["description"]
                self.assertEqual(leido, descripcion)

    def test_reexportar_la_salida_da_el_mismo_frontmatter(self):
        origen = ('---\nname: vuelta\ndescription: "Cárgala cuando pidan '
                  '\\"resumir\\" o l\'eau."\nversion: \'4.1\'\n---\n# X\n\nHaz algo.\n')
        primera = exportar(origen, self)
        texto = (primera / "vuelta" / "SKILL.md").read_text(encoding="utf-8")
        segunda = exportar(texto, self)
        self.assertEqual(frontmatter_de(primera / "vuelta" / "SKILL.md"),
                         frontmatter_de(segunda / "vuelta" / "SKILL.md"))


if __name__ == "__main__":
    unittest.main()
