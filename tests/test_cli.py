import tempfile
import unittest
from pathlib import Path

from ayuda import importar_exporter

importar_exporter()

import convert  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class CompatibilidadHaciaAtras(unittest.TestCase):

    def test_una_ruta_suelta_se_interpreta_como_export(self):
        # `convert.py <origen>` funcionaba antes de existir los subcomandos.
        # El «Paso 0» de la skill y el comando /exportar-skills lo usan asi.
        self.assertEqual(normalizar(["./mi-plugin"]), ["export", "./mi-plugin"])

    def test_una_url_suelta_tambien(self):
        self.assertEqual(normalizar(["https://github.com/u/r", "--out", "d"]),
                         ["export", "https://github.com/u/r", "--out", "d"])

    def test_un_subcomando_explicito_se_respeta(self):
        self.assertEqual(normalizar(["audit", "./x"]), ["audit", "./x"])

    def test_las_opciones_de_ayuda_no_se_tocan(self):
        self.assertEqual(normalizar(["--help"]), ["--help"])


def normalizar(argv):
    return convert.normalizar_argv(argv)


class Parser(unittest.TestCase):

    def test_inspect_no_admite_target(self):
        p = convert.construir_parser()
        with self.assertRaises(SystemExit):
            p.parse_args(["inspect", "./x", "--target", "chatgpt"])

    def test_audit_admite_varios_targets(self):
        args = convert.construir_parser().parse_args(
            ["audit", "./x", "--target", "chatgpt", "claude-code"])
        self.assertEqual(args.target, ["chatgpt", "claude-code"])

    def test_fail_on_por_defecto_es_ninguno(self):
        args = convert.construir_parser().parse_args(["audit", "./x"])
        self.assertEqual(args.fail_on, "ninguno")

    def test_export_conserva_las_opciones_heredadas(self):
        args = convert.construir_parser().parse_args(
            ["export", "./x", "--out", "d", "--only", "a", "b", "--zip-only",
             "--keep-description-order"])
        self.assertEqual(args.out, "d")
        self.assertEqual(args.only, ["a", "b"])
        self.assertTrue(args.zip_only)
        self.assertTrue(args.keep_description_order)


class DestinoDesconocido(unittest.TestCase):

    def test_lista_los_ids_disponibles(self):
        codigo = convert.main(["audit", ".", "--target", "no-existe"])
        self.assertEqual(codigo, 1)


class ZipOnlyConDestinoSinModoZip(unittest.TestCase):

    def test_zip_only_con_target_solo_carpeta_es_error(self):
        # mistral-vibe-work solo instala en modo 'carpeta'. Con --zip-only,
        # el codigo de export borraba esa carpeta al final asumiendo que
        # existia un zip que la sustituyera, y aqui no lo hay: el resultado
        # era un directorio de salida sin ningun artefacto de skill.
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "salida"
            codigo = convert.main([
                "export", str(FIXTURES / "skill-minima"),
                "--target", "mistral-vibe-work", "--zip-only",
                "--out", str(destino),
            ])
            self.assertEqual(codigo, 1)
            self.assertFalse(destino.exists())

    def test_zip_only_con_un_destino_que_si_admite_zip_no_es_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "salida"
            codigo = convert.main([
                "export", str(FIXTURES / "skill-minima"),
                "--target", "perplexity-computer", "--zip-only",
                "--out", str(destino),
            ])
            self.assertEqual(codigo, 0)
            self.assertTrue(list(destino.glob("*.zip")))


if __name__ == "__main__":
    unittest.main()
