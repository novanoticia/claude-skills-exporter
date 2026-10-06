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


class Ingles(unittest.TestCase):

    def export(self, fixture, *extra):
        tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, tmp)
        r = correr("export", str(FIXTURES / fixture), "--out", tmp,
                   "--anular-revision-seguridad", "--lang", "en", *extra)
        informe = Path(tmp) / "INFORME-PORTABILIDAD.md"
        return r, (informe.read_text(encoding="utf-8") if informe.exists() else "")

    def test_el_informe_sale_en_ingles(self):
        r, informe = self.export("repo-descarga-remota")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("# Portability and security report", informe)
        self.assertIn("**Risk level:**", informe)
        self.assertNotIn("Nivel de riesgo", informe)
        self.assertNotIn("Seguridad del paquete", informe)

    def test_la_regla_sale_traducida(self):
        _, informe = self.export("repo-descarga-remota")
        self.assertIn("Downloads remote content and runs it", informe)
        self.assertNotIn("Descarga contenido remoto", informe)

    def test_la_consola_sale_en_ingles(self):
        r, _ = self.export("repo-descarga-remota")
        self.assertRegex(r.stdout, r"\[info\] \d+ skill\(s\) found")
        self.assertNotIn("encontradas", r.stdout)
        self.assertIn("[ok] Output in:", r.stdout)

    def test_los_errores_salen_en_ingles(self):
        r = correr("inspect", "/no/existe/seguro", "--lang", "en")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("does not exist as a path", r.stderr + r.stdout)
        self.assertNotIn("no existe como ruta", r.stderr + r.stdout)

    def test_el_peligro_de_un_perfil_sale_traducido(self):
        # mistral-home-es-raiz se dispara con `~/` en una skill.
        tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, tmp)
        raiz = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, raiz)
        skill = raiz / "skills" / "tilde"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: tilde\ndescription: Cargala cuando el usuario pida guardar notas.\n---\n"
            "Guarda en ~/notas/diario.md lo que el usuario diga.\n", encoding="utf-8")
        r = correr("export", str(raiz), "--out", tmp, "--anular-revision-seguridad",
                   "--lang", "en")
        informe = (Path(tmp) / "INFORME-PORTABILIDAD.md").read_text(encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("$HOME is “/”, so ~/ writes to the root", informe)


class Frances(unittest.TestCase):

    def test_el_informe_sale_en_frances(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = correr("export", str(FIXTURES / "repo-descarga-remota"), "--out", tmp,
                       "--anular-revision-seguridad", "--lang", "fr")
            informe = (Path(tmp) / "INFORME-PORTABILIDAD.md").read_text(encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("**Niveau de risque :**", informe)
        self.assertNotIn("Nivel de riesgo", informe)
        self.assertNotIn("Risk level", informe)
        self.assertIn("Télécharge du contenu distant et l'exécute", informe)


class Auto(unittest.TestCase):

    def test_toma_el_primer_locale_significativo(self):
        self.assertEqual(i18n.detectar_del_entorno({"LANG": "fr_FR.UTF-8"}), "fr")

    def test_lc_all_manda_sobre_lang(self):
        self.assertEqual(
            i18n.detectar_del_entorno({"LC_ALL": "en_GB.UTF-8", "LANG": "fr_FR.UTF-8"}), "en")

    def test_c_y_posix_se_saltan(self):
        self.assertEqual(
            i18n.detectar_del_entorno({"LC_ALL": "C", "LANG": "fr_FR.UTF-8"}), "fr")
        self.assertEqual(
            i18n.detectar_del_entorno({"LC_ALL": "C.UTF-8", "LANG": "fr_FR.UTF-8"}), "fr")
        self.assertEqual(i18n.detectar_del_entorno({"LANG": "POSIX"}), "es")

    def test_idioma_sin_catalogo_cae_a_espanol(self):
        self.assertEqual(i18n.detectar_del_entorno({"LANG": "de_DE.UTF-8"}), "es")

    def test_un_idioma_sin_catalogo_no_salta_a_la_variable_siguiente(self):
        # Mezclar el idioma de dos variables seria peor que caer al base.
        self.assertEqual(
            i18n.detectar_del_entorno({"LC_ALL": "de_DE.UTF-8", "LANG": "fr_FR.UTF-8"}), "es")

    def test_sin_variables_es_espanol(self):
        self.assertEqual(i18n.detectar_del_entorno({}), "es")

    def test_auto_se_resuelve_en_idioma_pedido(self):
        self.assertEqual(i18n.idioma_pedido("auto", {"LANG": "fr_FR.UTF-8"}), "fr")
        self.assertEqual(
            i18n.idioma_pedido(None, {"CSE_LANG": "auto", "LANG": "en_US.UTF-8"}), "en")
        self.assertEqual(i18n.idioma_pedido("AUTO", {"LANG": "fr_FR.UTF-8"}), "fr")

    def test_auto_en_el_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = correr("export", str(FIXTURES / "repo-descarga-remota"), "--out", tmp,
                       "--anular-revision-seguridad", "--lang", "auto",
                       entorno={"LANG": "fr_FR.UTF-8", "LC_ALL": "", "LC_MESSAGES": ""})
            informe = (Path(tmp) / "INFORME-PORTABILIDAD.md").read_text(encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Niveau de risque", informe)

    def test_sin_auto_la_variable_lang_no_cambia_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            correr("export", str(FIXTURES / "repo-descarga-remota"), "--out", tmp,
                   "--anular-revision-seguridad", entorno={"LANG": "fr_FR.UTF-8"})
            informe = (Path(tmp) / "INFORME-PORTABILIDAD.md").read_text(encoding="utf-8")
        self.assertIn("Nivel de riesgo", informe)


if __name__ == "__main__":
    unittest.main()
