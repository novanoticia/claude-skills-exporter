import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ayuda import importar_exporter

importar_exporter()

import convert  # noqa: E402


class LimitesDeEntrada(unittest.TestCase):

    def test_un_repo_normal_pasa(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.md").write_text("hola", encoding="utf-8")
            convert.comprobar_tamano(Path(tmp))   # no debe lanzar

    def test_demasiados_ficheros_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = convert.MAX_FICHEROS_REPO
            convert.MAX_FICHEROS_REPO = 3
            try:
                for i in range(5):
                    (Path(tmp) / "f{}.txt".format(i)).write_text("x", encoding="utf-8")
                with self.assertRaises(SystemExit):
                    convert.comprobar_tamano(Path(tmp))
            finally:
                convert.MAX_FICHEROS_REPO = original

    def test_demasiado_grande_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = convert.MAX_BYTES_REPO
            convert.MAX_BYTES_REPO = 10
            try:
                (Path(tmp) / "grande.bin").write_bytes(b"x" * 100)
                with self.assertRaises(SystemExit):
                    convert.comprobar_tamano(Path(tmp))
            finally:
                convert.MAX_BYTES_REPO = original

    def test_no_cuenta_los_enlaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "real.bin"
            destino.write_bytes(b"x" * 1000)
            (Path(tmp) / "enlace.bin").symlink_to(destino)
            original = convert.MAX_BYTES_REPO
            convert.MAX_BYTES_REPO = 1500
            try:
                convert.comprobar_tamano(Path(tmp))   # 1000, no 2000
            finally:
                convert.MAX_BYTES_REPO = original


class OrigenInvalido(unittest.TestCase):

    def test_ni_ruta_ni_url_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                convert.resolve_source("no-existe-ni-es-url", Path(tmp))


class CredencialesDelOrigen(unittest.TestCase):

    def test_rechaza_url_sensible_antes_del_clon_y_de_tocar_la_salida(self):
        urls = (
            "https://cuenta:valor-ficticio@example.invalid/repo",
            "https://valor-ficticio@example.invalid/repo",
            "https://cuenta:valor-ficticio@example.invalid:error/repo",
            "https://valor-ficticio%40example.invalid/repo",
            "https://example.invalid/repo?token=valor-ficticio",
            "https://example.invalid/repo#valor-ficticio",
            "ssh://cuenta:valor-ficticio@example.invalid/repo",
        )
        with tempfile.TemporaryDirectory() as tmp:
            salida = Path(tmp) / "salida"
            salida.mkdir()
            testigo = salida / "conservar.txt"
            testigo.touch()
            for url in urls:
                for comando in ("inspect", "audit", "export"):
                    with self.subTest(comando=comando):
                        args = [comando, url]
                        if comando == "export":
                            args += ["--out", str(salida), "--force"]
                        consola = io.StringIO()
                        with patch.object(convert.subprocess, "run") as git, redirect_stdout(consola):
                            with self.assertRaises(SystemExit) as error:
                                convert.main(args)
                        git.assert_not_called()
                        self.assertNotIn("valor-ficticio", consola.getvalue() + str(error.exception))
                        self.assertEqual(list(salida.iterdir()), [testigo])

    def test_error_de_git_excluye_el_diagnostico_original(self):
        url = "https://example.invalid/repo"
        git_error = subprocess.CompletedProcess([], 128, stderr="dato privado: valor-ficticio")
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as consola:
            with patch.object(convert.subprocess, "run", return_value=git_error):
                with self.assertRaises(SystemExit) as error:
                    convert.resolve_source(url, Path(tmp))
        self.assertIn("128", str(error.exception))
        self.assertNotIn("valor-ficticio", consola.getvalue() + str(error.exception))

    def test_las_urls_limpias_se_mantienen_en_el_clon_y_los_informes(self):
        urls = ("https://example.invalid/proyecto/repo", "git@example.invalid:proyecto/repo")

        def clonar(argumentos, **_):
            destino = Path(argumentos[-1])
            destino.mkdir()
            (destino / "SKILL.md").write_text(
                "---\nname: fechas\ndescription: Cárgala cuando el usuario pida convertir fechas.\n"
                "---\n# Fechas\nPaso 1.\n", encoding="utf-8")
            return subprocess.CompletedProcess(argumentos, 0)

        for url in urls:
            with self.subTest(url=url), tempfile.TemporaryDirectory() as tmp:
                salida = Path(tmp) / "salida"
                with patch.object(convert.subprocess, "run", side_effect=clonar) as git:
                    with redirect_stdout(io.StringIO()) as consola:
                        self.assertEqual(convert.main(["export", url, "--out", str(salida)]), 0)
                self.assertEqual(git.call_args.args[0][-2], url)
                self.assertIn(url, consola.getvalue())
                self.assertIn(url, (salida / "INFORME-PORTABILIDAD.md").read_text(encoding="utf-8"))
                resumen = json.loads((salida / "resumen.json").read_text(encoding="utf-8"))
                self.assertEqual(resumen["origen"], url)


if __name__ == "__main__":
    unittest.main()
