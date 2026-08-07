import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.frontmatter import (  # noqa: E402
    parse_simple_yaml,
    split_frontmatter,
    yaml_escape,
)


class ParseoDeFrontmatter(unittest.TestCase):

    def test_separa_frontmatter_y_cuerpo(self):
        fm, _, cuerpo = split_frontmatter(
            "---\nname: mi-skill\ndescription: Hola\n---\n# Titulo\n")
        self.assertEqual(fm["name"], "mi-skill")
        self.assertEqual(fm["description"], "Hola")
        self.assertEqual(cuerpo, "# Titulo\n")

    def test_sin_frontmatter_devuelve_texto_intacto(self):
        fm, _, cuerpo = split_frontmatter("# Solo cuerpo\n")
        self.assertEqual(fm, {})
        self.assertEqual(cuerpo, "# Solo cuerpo\n")

    def test_metadata_anidado_sobrevive_como_mapa(self):
        # Regresion del fallo corregido en e3307b3: un `metadata:` con claves
        # dentro se perdia entero porque se asumia que toda clave sin valor
        # abria una lista.
        fm = parse_simple_yaml("name: x\nmetadata:\n  version: '4.1'\n  autor: Pablo\n")
        self.assertEqual(fm["metadata"], {"version": "4.1", "autor": "Pablo"})

    def test_lista_sigue_siendo_lista(self):
        fm = parse_simple_yaml("depends:\n  - una\n  - otra\n")
        self.assertEqual(fm["depends"], ["una", "otra"])


class Serializacion(unittest.TestCase):

    def test_entrecomilla_lo_que_rompe_el_yaml(self):
        self.assertEqual(yaml_escape("con: dos puntos"), '"con: dos puntos"')

    def test_deja_en_crudo_lo_inocuo(self):
        self.assertEqual(yaml_escape("mi-skill"), "mi-skill")


if __name__ == "__main__":
    unittest.main()
