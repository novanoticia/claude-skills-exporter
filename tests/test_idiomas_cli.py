import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ayuda import RAIZ, RAIZ_SCRIPTS, importar_exporter

importar_exporter()
from exporter import i18n  # noqa: E402

CONVERT = RAIZ_SCRIPTS / "convert.py"
FIXTURES = RAIZ / "tests" / "fixtures"


def correr(*args, entorno=None):
    env = dict(os.environ, CSE_FECHA="2026-08-08")
    env.pop("CSE_LANG", None)
    env.update(entorno or {})
    return subprocess.run([sys.executable, str(CONVERT)] + list(args),
                          capture_output=True, text=True, cwd=str(RAIZ), env=env)


class IdiomaPedido(unittest.TestCase):

    def test_el_flag_gana_a_la_variable(self):
        self.assertEqual(i18n.idioma_pedido("fr", {"CSE_LANG": "en"}), "fr")

    def test_sin_flag_se_lee_la_variable(self):
        self.assertEqual(i18n.idioma_pedido(None, {"CSE_LANG": "en"}), "en")

    def test_sin_nada_es_espanol(self):
        self.assertEqual(i18n.idioma_pedido(None, {}), "es")

    def test_variable_vacia_cuenta_como_ausente(self):
        self.assertEqual(i18n.idioma_pedido(None, {"CSE_LANG": ""}), "es")


class LangEnElCli(unittest.TestCase):

    def test_idioma_desconocido_da_error_en_espanol_con_la_lista(self):
        r = correr("inspect", str(FIXTURES / "repo-descarga-remota"), "--lang", "xx")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("[error] idioma desconocido: xx", r.stderr)
        self.assertIn("es — Español", r.stderr)

    def test_variable_invalida_sin_flag_tambien_es_error(self):
        r = correr("inspect", str(FIXTURES / "repo-descarga-remota"),
                   entorno={"CSE_LANG": "xx"})
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("idioma desconocido: xx", r.stderr)

    def test_el_flag_valido_gana_a_una_variable_invalida(self):
        r = correr("inspect", str(FIXTURES / "repo-descarga-remota"),
                   "--lang", "es", entorno={"CSE_LANG": "xx"})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_acepta_forma_de_locale(self):
        r = correr("inspect", str(FIXTURES / "repo-descarga-remota"), "--lang", "ES_es.UTF-8")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_la_forma_antigua_sin_subcomando_acepta_el_flag(self):
        # Review Focus 8: `convert.py <repo> --lang es` antepone `export`.
        with tempfile.TemporaryDirectory() as tmp:
            r = correr(str(FIXTURES / "repo-descarga-remota"), "--out", tmp,
                       "--anular-revision-seguridad", "--lang", "es")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_los_tres_subcomandos_aceptan_el_flag(self):
        for sub in ("inspect", "audit"):
            with self.subTest(sub=sub):
                # Fixture limpio: `audit` devuelve 2 si el riesgo no es bajo.
                r = correr(sub, str(FIXTURES / "skill-minima"), "--lang", "es")
                self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
