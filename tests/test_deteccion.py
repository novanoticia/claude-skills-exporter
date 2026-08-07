import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.deteccion import detectar  # noqa: E402


class Deteccion(unittest.TestCase):

    def test_registra_el_numero_de_linea(self):
        texto = "Primera linea\nSegunda linea\nUsa mcp__gmail__buscar aqui\n"
        senales = detectar(texto, "SKILL.md")
        self.assertEqual(len(senales), 1)
        self.assertEqual(senales[0].id, "mcp-tool")
        self.assertEqual(senales[0].ubicacion, "SKILL.md:3")

    def test_incluye_la_muestra_del_texto_encontrado(self):
        senales = detectar("Llama a mcp__gmail__buscar\n", "SKILL.md")
        self.assertIn("mcp__gmail__buscar", senales[0].muestra)

    def test_una_senal_por_id_y_linea_no_una_por_coincidencia(self):
        texto = "mcp__a__b y mcp__c__d en la misma linea\n"
        senales = detectar(texto, "SKILL.md")
        self.assertEqual(len(senales), 1)

    def test_varias_lineas_dan_varias_senales(self):
        texto = "mcp__a__b\nrelleno\nmcp__c__d\n"
        senales = detectar(texto, "SKILL.md")
        self.assertEqual([s.ubicacion for s in senales], ["SKILL.md:1", "SKILL.md:3"])

    def test_texto_limpio_no_produce_senales(self):
        self.assertEqual(detectar("Un procedimiento normal y corriente.\n", "SKILL.md"), [])

    def test_detecta_el_home_con_tilde(self):
        senales = detectar("Escribe en ~/.mi-skill/estado.jsonl\n", "SKILL.md")
        self.assertEqual([s.id for s in senales], ["home-tilde"])


if __name__ == "__main__":
    unittest.main()
