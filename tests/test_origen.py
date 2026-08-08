import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
