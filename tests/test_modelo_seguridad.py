import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.modelo import (  # noqa: E402
    AMBITOS,
    Bloqueo,
    Hallazgo,
    Nivel,
    VeredictoSeguridad,
)


def hallazgo(**kw):
    base = dict(id="SEC-X-001", familia="permisos_y_acciones", dimension="tecnico",
                severidad="alta", confianza="alta", ambito="paquete",
                ubicacion="scripts/setup.sh:2", muestra="curl … | sh",
                titulo="Titulo", mitigacion="Mitigacion")
    base.update(kw)
    return Hallazgo(**base)


class PrecedenciaDeNiveles(unittest.TestCase):

    def test_el_peor_gana(self):
        self.assertEqual(Nivel.peor([Nivel.BAJO, Nivel.ALTO, Nivel.MODERADO]), Nivel.ALTO)

    def test_critico_gana_a_todo(self):
        self.assertEqual(Nivel.peor([Nivel.ALTO, Nivel.CRITICO]), Nivel.CRITICO)

    def test_sin_niveles_es_bajo(self):
        self.assertEqual(Nivel.peor([]), Nivel.BAJO)

    def test_no_evaluable_no_esta_en_la_escala(self):
        # No es "peor que moderado": es "no puedo saberlo". riesgo.py lo aplica
        # aparte, y por eso no participa en la comparacion ordinal.
        self.assertNotIn(Nivel.NO_EVALUABLE, Nivel.ORDEN)


class Estructuras(unittest.TestCase):

    def test_el_hallazgo_es_comparable_por_valor(self):
        self.assertEqual(hallazgo(), hallazgo())

    def test_el_hallazgo_es_hashable(self):
        self.assertEqual(len({hallazgo(), hallazgo()}), 1)

    def test_el_bloqueo_lleva_donde_mirar(self):
        b = Bloqueo(regla_id="SEC-X-001", severidad="alta",
                    fichero="skills/x/scripts/run.sh", linea=3)
        self.assertEqual(b.linea, 3)
        self.assertEqual(b.fichero, "skills/x/scripts/run.sh")

    def test_los_ambitos_son_dos(self):
        self.assertEqual(AMBITOS, {"exportado", "paquete"})

    def test_el_veredicto_arranca_vacio_y_coherente(self):
        v = VeredictoSeguridad(nivel=Nivel.BAJO, recomendacion="instalacion_razonable",
                               dimensiones={}, escalada_por_combinacion=False,
                               hallazgos=[], hay_contenido_opaco=False)
        self.assertEqual(v.nivel, "bajo")
        self.assertEqual(v.hallazgos, [])


if __name__ == "__main__":
    unittest.main()
