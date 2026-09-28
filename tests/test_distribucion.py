"""La distribucion del plugin lleva solo lo instalable y nada binario."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / ".github" / "construir_distribucion.py"

_spec = importlib.util.spec_from_file_location("construir_distribucion", str(SCRIPT))
distribucion = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(distribucion)


class Distribucion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.destino = distribucion.construir(RAIZ, Path(cls._tmp.name) / "dist")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_es_limpia(self):
        self.assertEqual(distribucion.verificar(self.destino), [])

    def test_lleva_lo_instalable(self):
        for rel in (".claude-plugin/plugin.json", ".claude-plugin/icon.svg",
                    "commands/exportar-skills.md",
                    "skills/plugin-to-agentskills/SKILL.md",
                    "skills/plugin-to-agentskills/scripts/convert.py",
                    "skills/plugin-to-agentskills/scripts/exporter/seguridad/reglas.json",
                    "README.md", "LICENSE"):
            self.assertTrue((self.destino / rel).is_file(), rel)

    def test_no_lleva_el_banco_de_pruebas(self):
        for rel in ("tests", "docs", ".github", "AGENTS.md"):
            self.assertFalse((self.destino / rel).exists(), rel)
        self.assertEqual(list(self.destino.rglob("__pycache__")), [])

    def test_detecta_un_binario(self):
        (self.destino / "skills" / "intruso.bin").write_bytes(b"\x7fELF\x00\x01")
        try:
            problemas = distribucion.verificar(self.destino)
        finally:
            (self.destino / "skills" / "intruso.bin").unlink()
        self.assertEqual(len(problemas), 1)
        self.assertIn("binario", problemas[0])

    def test_la_distribucion_es_un_plugin_valido(self):
        # El validador ejecuta convert.py dentro de la distribucion; sin esto
        # dejaria __pycache__ y test_no_lleva_el_banco_de_pruebas dependeria
        # del orden de ejecucion.
        entorno = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run(
            [sys.executable, str(RAIZ / ".github" / "validate_plugin.py"), str(self.destino)],
            capture_output=True, text=True, env=entorno)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_rechaza_un_destino_dentro_del_repositorio(self):
        with self.assertRaises(SystemExit):
            distribucion.construir(RAIZ, RAIZ / "dist-prueba")
        self.assertFalse((RAIZ / "dist-prueba").exists())


if __name__ == "__main__":
    unittest.main()
