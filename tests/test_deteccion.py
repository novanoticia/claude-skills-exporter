import os
import tempfile
import unittest
from pathlib import Path

from ayuda import importar_exporter

importar_exporter()

from exporter.deteccion import detectar, detectar_en_arbol  # noqa: E402


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

    def test_el_offset_desplaza_el_numero_de_linea_reportado(self):
        # El cuerpo de un SKILL.md ya no empieza en la linea 1 del fichero
        # real una vez que se le ha quitado el frontmatter: quien llama debe
        # poder decir cuantas lineas se quedaron fuera para que la ubicacion
        # que se reporta sea la del fichero, no la del fragmento.
        texto = "Relleno\nUsa mcp__gmail__buscar aqui\n"
        senales = detectar(texto, "SKILL.md", offset=9)
        self.assertEqual(senales[0].ubicacion, "SKILL.md:11")

    def test_offset_por_defecto_es_cero(self):
        senales = detectar("Usa mcp__gmail__buscar\n", "SKILL.md")
        self.assertEqual(senales[0].ubicacion, "SKILL.md:1")


class DeteccionEnArbol(unittest.TestCase):
    """Cubre la mitad del modulo que toca disco: os.walk, symlinks, filtro
    por extension y el nuevo parametro `excluir`. Ficheros reales, sin mocks.
    """

    def test_encuentra_senales_en_fichero_anidado_con_ruta_relativa_a_la_raiz(self):
        with tempfile.TemporaryDirectory() as raiz:
            carpeta = Path(raiz) / "references"
            carpeta.mkdir()
            fichero = carpeta / "guia.md"
            fichero.write_text("Primera linea\nUsa mcp__gmail__buscar aqui\n", encoding="utf-8")

            senales, _ = detectar_en_arbol(raiz)

            self.assertEqual(len(senales), 1)
            self.assertEqual(senales[0].id, "mcp-tool")
            self.assertEqual(senales[0].ubicacion, "references/guia.md:2")

    def test_ignora_ficheros_con_extension_fuera_de_extensiones_texto(self):
        with tempfile.TemporaryDirectory() as raiz:
            fichero = Path(raiz) / "logo.png"
            fichero.write_bytes(b"mcp__gmail__buscar\n")

            senales, _ = detectar_en_arbol(raiz)

            self.assertEqual(senales, [])

    def test_ignora_symlinks_en_lugar_de_seguirlos(self):
        with tempfile.TemporaryDirectory() as raiz:
            objetivo = Path(raiz) / "real.md"
            objetivo.write_text("Usa mcp__gmail__buscar aqui\n", encoding="utf-8")
            enlace = Path(raiz) / "enlace.md"
            os.symlink(objetivo, enlace)

            senales, _ = detectar_en_arbol(raiz)

            # El fichero real SI produce senal; el symlink que apunta a el, no
            # se sigue, asi que solo se ve una vez (por real.md).
            self.assertEqual(len(senales), 1)
            self.assertEqual(senales[0].ubicacion, "real.md:1")

    def test_excluir_se_salta_el_fichero_nombrado(self):
        with tempfile.TemporaryDirectory() as raiz:
            (Path(raiz) / "SKILL.md").write_text(
                "Usa mcp__gmail__buscar aqui\n", encoding="utf-8")
            (Path(raiz) / "otro.md").write_text(
                "Tambien mcp__gmail__buscar\n", encoding="utf-8")

            senales, _ = detectar_en_arbol(raiz, excluir={"SKILL.md"})

            self.assertEqual(len(senales), 1)
            self.assertEqual(senales[0].ubicacion, "otro.md:1")

    def test_arbol_sin_nada_sospechoso_da_lista_vacia(self):
        with tempfile.TemporaryDirectory() as raiz:
            (Path(raiz) / "SKILL.md").write_text(
                "Un procedimiento normal y corriente.\n", encoding="utf-8")

            self.assertEqual(detectar_en_arbol(raiz), ([], []))

    def test_no_desciende_en_directorios_ignorados(self):
        # Sin podar node_modules/, una senal ahi dentro marcaba como
        # no_compatible un fichero que copiar_skill() jamas incluye en el
        # paquete exportado: el veredicto hablaba de algo que no viaja.
        with tempfile.TemporaryDirectory() as raiz:
            paquete = Path(raiz) / "node_modules" / "algun-paquete"
            paquete.mkdir(parents=True)
            (paquete / "README.md").write_text(
                "Usa mcp__gmail__buscar aqui\n", encoding="utf-8")
            (Path(raiz) / "SKILL.md").write_text(
                "Un procedimiento normal y corriente.\n", encoding="utf-8")

            self.assertEqual(detectar_en_arbol(raiz), ([], []))


if __name__ == "__main__":
    unittest.main()
