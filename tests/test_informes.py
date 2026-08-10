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

    def test_un_veredicto_causado_por_capacidad_tambien_cita_evidencia(self):
        # El veredicto de mistral-vibe-work en self.evaluaciones lo causa el
        # canal de capacidades (scripts.ejecutar) y no lleva ningun peligro:
        # es justo el caso que antes se quedaba sin evidencia ni fecha,
        # incumpliendo el criterio de aceptacion 4 («cada no_compatible o
        # degradado cita... su evidencia y su fecha de verificacion»).
        md = informe_markdown(self.res, self.evaluaciones, "./x", self.perfiles)
        ev_perfil = self.perfiles["mistral-vibe-work"].datos["evidencia"]
        self.assertIn(ev_perfil["confianza"], md)
        self.assertIn(ev_perfil["verificado_el"], md)


class Finding:
    """Doble minimo del Finding de convert.py, que no es importable aqui."""

    def __init__(self, severity, code, message):
        self.severity, self.code, self.message = severity, code, message


class HallazgosDePortabilidadEnElInforme(unittest.TestCase):
    """El informe no imprimia ni un solo Finding.

    Renderizaba origen, descripcion, adaptaciones y evaluaciones por destino,
    pero nunca recorria `r.findings`. Vivian solo en resumen.json, y el CLI
    remite al informe: quien lo leia no los veia nunca.
    """

    def setUp(self):
        self.perfiles = cargar_perfiles()
        self.res = [Resultado("email-triage")]
        self.evaluaciones = {"email-triage": {
            "perplexity-computer": evs("perplexity-computer", Estado.COMPATIBLE)}}

    def md(self):
        return informe_markdown(self.res, self.evaluaciones, "./x", self.perfiles)

    def test_el_markdown_los_contiene(self):
        self.res[0].findings = [
            Finding("alta", "description-sin-activacion",
                    "Falta el criterio de activación.")]
        md = self.md()
        self.assertIn("description-sin-activacion", md)
        self.assertIn("Falta el criterio de activación.", md)

    def test_lleva_severidad_codigo_y_mensaje(self):
        self.res[0].findings = [Finding("media", "scripts", "Incluye scripts/.")]
        md = self.md()
        self.assertIn("`scripts`", md)
        self.assertIn("severidad **media**", md)
        self.assertIn("Incluye scripts/.", md)

    def test_los_graves_van_primero(self):
        self.res[0].findings = [
            Finding("baja", "cuerpo-largo", "Cuerpo largo."),
            Finding("alta", "sin-frontmatter", "Sin frontmatter."),
            Finding("media", "scripts", "Incluye scripts/."),
        ]
        md = self.md()
        self.assertLess(md.index("sin-frontmatter"), md.index("scripts"))
        self.assertLess(md.index("scripts"), md.index("cuerpo-largo"))

    def test_se_distinguen_de_los_de_seguridad(self):
        """El informe lleva dos listas de hallazgos con vocabularios
        distintos; llamarlas igual invitaria a confundirlas."""
        self.res[0].findings = [Finding("alta", "sin-frontmatter", "Sin frontmatter.")]
        self.assertIn("**Hallazgos de portabilidad (1):**", self.md())

    def test_sin_hallazgos_no_aparece_la_seccion(self):
        self.assertNotIn("Hallazgos de portabilidad", self.md())

    def test_la_seccion_de_seguridad_no_se_toca(self):
        """La de arriba ya funcionaba: esto no debe alterarla."""
        self.res[0].findings = [Finding("alta", "sin-frontmatter", "Sin frontmatter.")]
        md = self.md()
        self.assertNotIn("## Seguridad del paquete", md)   # no se pasó veredicto


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
        self.assertEqual(d["report_version"], "3.0")
        self.assertEqual(d["origen"], "./x")
        skill = d["skills"][0]
        self.assertEqual(skill["name"], "email-triage")
        self.assertEqual(skill["compatibilidad"]["claude-code"][0]["estado"], "compatible")

    def test_el_bloqueo_de_seguridad_va_reservado_a_null(self):
        d = resumen_json(self.res, self.evaluaciones, "./x")
        self.assertIsNone(d["skills"][0]["compatibilidad"]["claude-code"][0]["bloqueo_seguridad"])

    def test_un_bloqueo_se_serializa_como_objeto(self):
        from exporter.modelo import Bloqueo
        self.evaluaciones["email-triage"]["claude-code"][0].bloqueo_seguridad = Bloqueo(
            regla_id="SEC-EXEC-REMOTO-001", severidad="alta",
            fichero="skills/x/scripts/run.sh", linea=3)
        d = resumen_json(self.res, self.evaluaciones, "./x")
        b = d["skills"][0]["compatibilidad"]["claude-code"][0]["bloqueo_seguridad"]
        self.assertEqual(b["regla_id"], "SEC-EXEC-REMOTO-001")
        self.assertEqual(b["linea"], 3)

    def test_es_serializable_y_estable(self):
        import json
        a = json.dumps(resumen_json(self.res, self.evaluaciones, "./x"), sort_keys=True)
        b = json.dumps(resumen_json(self.res, self.evaluaciones, "./x"), sort_keys=True)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
