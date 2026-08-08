import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.informes import informe_markdown, resumen_json  # noqa: E402
from exporter.modelo import Estado, Evaluacion  # noqa: E402
from exporter.perfiles import cargar_perfiles  # noqa: E402


class Resultado:
    """Doble minimo de SkillResult, lo justo para el informe."""

    def __init__(self, name):
        self.name = name
        self.description = "Cárgala cuando el usuario lo pida."
        self.src_dir = "skills/" + name
        self.findings = []
        self.adaptations = []
        self.extra_files = []


def evs(destino, estado, motivos=()):
    return [Evaluacion(destino=destino, modo_instalacion="zip", estado=estado,
                       motivos=list(motivos))]


class InformeMarkdown(unittest.TestCase):

    def setUp(self):
        self.perfiles = cargar_perfiles()
        self.res = [Resultado("email-triage")]
        self.evaluaciones = {
            "email-triage": {
                "mistral-vibe-work": evs("mistral-vibe-work", Estado.NO_COMPATIBLE,
                                         ["scripts.ejecutar: requerida y el destino la declara «no»."]),
                "perplexity-computer": evs("perplexity-computer", Estado.COMPATIBLE),
            }
        }

    def test_lleva_la_matriz_con_una_columna_por_destino(self):
        md = informe_markdown(self.res, self.evaluaciones, "./x", self.perfiles)
        self.assertIn("## Matriz de compatibilidad", md)
        self.assertIn("Mistral Vibe Work", md)
        self.assertIn("Perplexity Computer", md)

    def test_la_advertencia_de_probar_en_destino_es_obligatoria(self):
        md = informe_markdown(self.res, self.evaluaciones, "./x", self.perfiles)
        self.assertIn("Ningún veredicto sustituye a probar la skill en el destino.", md)

    def test_ningun_estado_aparece_sin_motivo(self):
        md = informe_markdown(self.res, self.evaluaciones, "./x", self.perfiles)
        self.assertIn("scripts.ejecutar", md)


class ResumenJson(unittest.TestCase):

    def setUp(self):
        self.res = [Resultado("email-triage")]
        self.evaluaciones = {
            "email-triage": {
                "claude-code": evs("claude-code", Estado.COMPATIBLE),
            }
        }

    def test_estructura_minima(self):
        d = resumen_json(self.res, self.evaluaciones, "./x")
        self.assertEqual(d["report_version"], "2.0")
        self.assertEqual(d["origen"], "./x")
        skill = d["skills"][0]
        self.assertEqual(skill["name"], "email-triage")
        self.assertEqual(skill["compatibilidad"]["claude-code"][0]["estado"], "compatible")

    def test_el_bloqueo_de_seguridad_va_reservado_a_null(self):
        d = resumen_json(self.res, self.evaluaciones, "./x")
        self.assertIsNone(d["skills"][0]["compatibilidad"]["claude-code"][0]["bloqueo_seguridad"])

    def test_es_serializable_y_estable(self):
        import json
        a = json.dumps(resumen_json(self.res, self.evaluaciones, "./x"), sort_keys=True)
        b = json.dumps(resumen_json(self.res, self.evaluaciones, "./x"), sort_keys=True)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
