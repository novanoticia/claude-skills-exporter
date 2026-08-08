import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.descripcion import (  # noqa: E402
    clamp_description,
    compact_description,
    nbytes,
    reorder_description,
    split_sentences,
    tiene_activacion,
)


class ConteoEnBytes(unittest.TestCase):

    def test_las_tildes_cuentan_doble(self):
        # El limite de 1024 se mide en bytes UTF-8, no en caracteres: es la
        # causa de que Perplexity rechazara un zip con 1063 caracteres.
        self.assertEqual(len("cárgala"), 7)
        self.assertEqual(nbytes("cárgala"), 8)


class TroceoEnFrases(unittest.TestCase):

    def test_no_rompe_dentro_de_comillas(self):
        frases = split_sentences('Cárgala cuando el usuario diga "¿es importante?". Hace cosas.')
        self.assertEqual(len(frases), 2)

    def test_no_rompe_en_abreviaturas(self):
        frases = split_sentences("Usa datos, p. ej. correos. Después informa.")
        self.assertEqual(len(frases), 2)


class Reordenado(unittest.TestCase):

    def test_adelanta_la_frase_de_activacion(self):
        texto, movido = reorder_description(
            "Analiza bandejas de correo. Actívalo cuando el usuario diga «filtra mi correo».")
        self.assertTrue(movido)
        self.assertTrue(texto.startswith("Actívalo cuando"))

    def test_no_inventa_activacion_si_no_la_hay(self):
        texto, movido = reorder_description("Esta skill genera informes. Y tablas.")
        self.assertFalse(movido)
        self.assertEqual(texto, "Esta skill genera informes. Y tablas.")


class Recorte(unittest.TestCase):

    def test_nunca_corta_a_mitad_de_palabra(self):
        largo = "Cárgala cuando el usuario lo pida. " + ("palabra " * 200)
        salida = clamp_description(largo, 490)
        self.assertLessEqual(nbytes(salida), 490)
        self.assertFalse(salida.endswith("palab"))

    def test_compactar_conserva_el_criterio_de_activacion(self):
        largo = ("Analiza bandejas con calibración estadística y modelos de prioridad. "
                 "Actívalo cuando el usuario diga «filtra mi correo», «revisa mi bandeja», "
                 "«qué correos importan» o «limpia el buzón». " + ("Relleno. " * 60))
        salida = compact_description(largo, 490)
        self.assertLessEqual(nbytes(salida), 490)
        self.assertIn("Actívalo cuando", salida)


class DeteccionDeActivacion(unittest.TestCase):

    def test_reconoce_disparadores_en_espanol_e_ingles(self):
        self.assertTrue(tiene_activacion("Cárgala cuando el usuario pida algo."))
        self.assertTrue(tiene_activacion("Use this skill when the user asks."))

    def test_una_descripcion_que_solo_describe_no_tiene_activacion(self):
        self.assertFalse(tiene_activacion("Esta skill genera informes financieros."))


if __name__ == "__main__":
    unittest.main()
