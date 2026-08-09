import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.modelo import Hallazgo, Nivel  # noqa: E402
from exporter.seguridad.riesgo import RECOMENDACION, evaluar  # noqa: E402


def h(severidad="alta", dimension="tecnico", confianza="alta", hid="SEC-X-001"):
    return Hallazgo(id=hid, familia="permisos_y_acciones", dimension=dimension,
                    severidad=severidad, confianza=confianza, ambito="paquete",
                    ubicacion="a.sh:1", muestra="…", titulo="T", mitigacion="M")


class NivelBase(unittest.TestCase):

    def test_sin_hallazgos_es_bajo(self):
        self.assertEqual(evaluar([], False).nivel, Nivel.BAJO)

    def test_solo_bajas_es_bajo(self):
        self.assertEqual(evaluar([h(severidad="baja")], False).nivel, Nivel.BAJO)

    def test_una_media_es_moderado(self):
        self.assertEqual(evaluar([h(severidad="media")], False).nivel, Nivel.MODERADO)

    def test_una_alta_es_alto(self):
        self.assertEqual(evaluar([h(severidad="alta")], False).nivel, Nivel.ALTO)

    def test_una_critica_es_critico(self):
        self.assertEqual(evaluar([h(severidad="critica")], False).nivel, Nivel.CRITICO)


class EscaladaPorCombinacion(unittest.TestCase):

    def test_dos_altas_en_dimensiones_distintas_escalan(self):
        v = evaluar([h(dimension="tecnico", hid="SEC-A-001"),
                     h(dimension="cadena_de_suministro", hid="SEC-B-001")], False)
        self.assertEqual(v.nivel, Nivel.CRITICO)
        self.assertTrue(v.escalada_por_combinacion)

    def test_dos_altas_en_la_misma_dimension_no_escalan(self):
        v = evaluar([h(dimension="tecnico", hid="SEC-A-001"),
                     h(dimension="tecnico", hid="SEC-B-001")], False)
        self.assertEqual(v.nivel, Nivel.ALTO)
        self.assertFalse(v.escalada_por_combinacion)

    def test_una_confianza_menor_que_alta_no_escala(self):
        # Una heuristica no puede disparar sola el peor veredicto.
        v = evaluar([h(dimension="tecnico", confianza="alta", hid="SEC-A-001"),
                     h(dimension="comportamiento", confianza="media", hid="SEC-B-001")], False)
        self.assertEqual(v.nivel, Nivel.ALTO)
        self.assertFalse(v.escalada_por_combinacion)

    def test_la_confianza_baja_tampoco_escala(self):
        v = evaluar([h(dimension="tecnico", confianza="alta", hid="SEC-A-001"),
                     h(dimension="comportamiento", confianza="baja", hid="SEC-B-001")], False)
        self.assertEqual(v.nivel, Nivel.ALTO)
        self.assertFalse(v.escalada_por_combinacion)


class ContenidoOpaco(unittest.TestCase):

    def test_sustituye_a_bajo(self):
        self.assertEqual(evaluar([], True).nivel, Nivel.NO_EVALUABLE)

    def test_no_sustituye_a_moderado(self):
        self.assertEqual(evaluar([h(severidad="media")], True).nivel, Nivel.MODERADO)

    def test_no_sustituye_a_alto(self):
        self.assertEqual(evaluar([h(severidad="alta")], True).nivel, Nivel.ALTO)

    def test_el_veredicto_recuerda_que_habia_opacidad(self):
        self.assertTrue(evaluar([h(severidad="alta")], True).hay_contenido_opaco)


class Dimensiones(unittest.TestCase):

    def test_cada_dimension_lleva_su_propio_nivel(self):
        v = evaluar([h(dimension="tecnico", severidad="alta"),
                     h(dimension="cadena_de_suministro", severidad="media", hid="SEC-B-001")],
                    False)
        self.assertEqual(v.dimensiones["tecnico"], Nivel.ALTO)
        self.assertEqual(v.dimensiones["cadena_de_suministro"], Nivel.MODERADO)
        self.assertEqual(v.dimensiones["comportamiento"], Nivel.BAJO)

    def test_estan_siempre_las_tres(self):
        self.assertEqual(set(evaluar([], False).dimensiones),
                         {"tecnico", "cadena_de_suministro", "comportamiento"})


class Recomendacion(unittest.TestCase):

    def test_hay_una_por_nivel(self):
        for nivel in (Nivel.BAJO, Nivel.MODERADO, Nivel.ALTO,
                      Nivel.CRITICO, Nivel.NO_EVALUABLE):
            self.assertIn(nivel, RECOMENDACION)

    def test_alto_exige_revision_humana(self):
        self.assertEqual(evaluar([h(severidad="alta")], False).recomendacion,
                         "revision_humana_obligatoria")

    def test_bajo_es_razonable(self):
        self.assertEqual(evaluar([], False).recomendacion, "instalacion_razonable")


class Reproducibilidad(unittest.TestCase):

    def test_el_orden_de_los_hallazgos_no_cambia_el_veredicto(self):
        a = [h(dimension="tecnico", hid="SEC-A-001"),
             h(dimension="cadena_de_suministro", hid="SEC-B-001")]
        self.assertEqual(evaluar(a, False).nivel, evaluar(list(reversed(a)), False).nivel)


if __name__ == "__main__":
    unittest.main()
