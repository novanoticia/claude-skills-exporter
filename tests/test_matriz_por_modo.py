"""La matriz separa los modos de instalacion de un destino cuando difieren.

ChatGPT se instala de dos formas: subiendo el zip (probado a mano el
2026-11-17) o por la URL del repositorio (sin probar). La casilla mostraba el
peor de los dos, asi que ChatGPT salia "no verificable" aunque el zip que
produce el conversor estuviera comprobado.

Ahora, si los modos de un destino dan estados distintos, la casilla los
muestra todos, cada uno con su estado. Si coinciden, o el destino tiene un
solo modo, la casilla no cambia. resumen.json ya los separaba.
"""

import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter import i18n  # noqa: E402
from exporter.informes import informe_markdown  # noqa: E402
from exporter.modelo import Bloqueo, Estado, Evaluacion  # noqa: E402
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


def fila(md: str, skill: str) -> str:
    return next(l for l in md.splitlines() if l.startswith("| `{}` |".format(skill)))


def chatgpt(zip_estado, url_estado, bloqueo=None):
    return [Evaluacion("chatgpt", "url_repositorio", url_estado,
                       bloqueo_seguridad=bloqueo),
            Evaluacion("chatgpt", "zip", zip_estado, bloqueo_seguridad=bloqueo)]


class CasillaPorModo(unittest.TestCase):

    def setUp(self):
        self.perfiles = cargar_perfiles()
        self.res = [Resultado("minima")]
        self.addCleanup(i18n.fijar_idioma, i18n.idioma_activo())
        i18n.fijar_idioma("es")

    def informe(self, evals_chatgpt, **kw):
        ev = {"minima": {
            "chatgpt": evals_chatgpt,
            "claude-ai": [Evaluacion("claude-ai", "zip", Estado.COMPATIBLE)],
        }}
        return fila(informe_markdown(self.res, ev, "./x", self.perfiles, **kw), "minima")

    def test_modos_distintos_se_ven_por_separado(self):
        f = self.informe(chatgpt(Estado.COMPATIBLE, Estado.NO_VERIFICABLE))
        self.assertIn("🟢 zip: compatible · 🔵 URL del repo: no verificable", f)

    def test_el_zip_va_primero(self):
        f = self.informe(chatgpt(Estado.DEGRADADO, Estado.COMPATIBLE))
        self.assertLess(f.index("zip:"), f.index("URL del repo:"))

    def test_modos_iguales_dan_una_sola_casilla(self):
        f = self.informe(chatgpt(Estado.COMPATIBLE, Estado.COMPATIBLE))
        self.assertNotIn("zip:", f)
        self.assertIn("🟢 compatible", f)

    def test_un_destino_de_un_solo_modo_no_cambia(self):
        f = self.informe(chatgpt(Estado.COMPATIBLE, Estado.NO_VERIFICABLE))
        celdas = [c.strip() for c in f.strip("|").split("|")]
        self.assertIn("🟢 compatible", celdas)

    def test_el_bloqueo_sigue_ocupando_la_casilla(self):
        f = self.informe(chatgpt(Estado.COMPATIBLE, Estado.NO_VERIFICABLE,
                                 bloqueo=Bloqueo("X-1", "alta", "SKILL.md", 1)))
        self.assertNotIn("zip:", f)
        self.assertIn("🚫", f)

    def test_las_etiquetas_se_traducen(self):
        i18n.fijar_idioma("en")
        f = self.informe(chatgpt(Estado.COMPATIBLE, Estado.NO_VERIFICABLE))
        self.assertIn("zip: compatible · 🔵 repo URL:", f)


if __name__ == "__main__":
    unittest.main()
