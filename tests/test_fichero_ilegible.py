"""Un fichero que no se puede leer no tumba el export: avisa y sigue.

Antes, un `chmod 000` dentro de una skill hacia subir un PermissionError sin
capturar hasta lo alto del programa. El export moria con un traceback -y,
hasta que existio la guarda de --out, lo hacia DESPUES de haber borrado el
directorio de salida-.

Lo contrario, tragarse el OSError en silencio, seria el mismo defecto que el
Bloque B corrige en el motor de seguridad: un informe sin hallazgos se lee
como "aqui no hay nada" cuando en realidad significa "esto no lo he mirado".
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from ayuda import RAIZ, RAIZ_SCRIPTS, importar_exporter

importar_exporter()

from exporter.deteccion import detectar_en_arbol   # noqa: E402
from exporter.empaquetado import copiar_skill      # noqa: E402

CONVERT = RAIZ_SCRIPTS / "convert.py"

SKILL = ("---\nname: x\n"
         "description: Cárgala cuando el usuario pida convertir una fecha.\n"
         "---\n# Fechas\nPaso 1.\n")


def sin_permisos(p: Path) -> None:
    p.chmod(0o000)


class Base(unittest.TestCase):

    def setUp(self):
        if os.geteuid() == 0:
            self.skipTest("root lee cualquier fichero: el caso no se puede montar")

    def montar(self):
        tmp = Path(tempfile.mkdtemp())
        # El chmod 000 impide borrar el arbol si no se restaura antes.
        self.addCleanup(self._limpiar, tmp)
        skill = tmp / "repo" / "skills" / "x"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(SKILL, encoding="utf-8")
        (skill / "notas.md").write_text("notas internas\n", encoding="utf-8")
        sin_permisos(skill / "notas.md")
        return tmp, tmp / "repo", tmp / "out"

    def _limpiar(self, tmp):
        for p in tmp.rglob("*"):
            try:
                p.chmod(0o700)
            except OSError:
                pass
        shutil.rmtree(str(tmp), ignore_errors=True)


class LasDosFasesQueLeen(Base):
    """Ni la deteccion ni la copia pueden dejar subir el OSError."""

    def test_la_deteccion_lo_reporta_en_vez_de_reventar(self):
        _, raiz, _ = self.montar()
        senales, ilegibles = detectar_en_arbol(raiz / "skills" / "x")
        self.assertEqual([r for r, _m in ilegibles], ["notas.md"])
        self.assertEqual(senales, [])

    def test_la_copia_lo_reporta_en_vez_de_reventar(self):
        tmp, raiz, _ = self.montar()
        destino = tmp / "copia"
        enlaces, ilegibles = copiar_skill(
            raiz / "skills" / "x", destino, ignorar=set())
        self.assertEqual(enlaces, [])
        self.assertEqual([r for r, _m in ilegibles], ["notas.md"])
        # Lo que si se podia leer esta copiado; lo otro, no.
        self.assertTrue((destino / "SKILL.md").exists())
        self.assertFalse((destino / "notas.md").exists())


class ElExportTermina(Base):

    def exportar(self):
        tmp, raiz, salida = self.montar()
        r = subprocess.run(
            [sys.executable, str(CONVERT), "export", str(raiz), "--out", str(salida)],
            capture_output=True, text=True, cwd=str(RAIZ),
            env=dict(os.environ, CSE_FECHA="2026-08-08"))
        return r, salida

    def test_no_muere_con_un_traceback(self):
        r, _ = self.exportar()
        self.assertNotIn("Traceback", r.stderr)
        # El codigo 1 es el del fallo duro; aqui se sale por la via normal.
        self.assertNotEqual(r.returncode, 1)

    def test_el_artefacto_se_escribe_igual(self):
        _, salida = self.exportar()
        self.assertTrue((salida / "x.zip").exists())
        self.assertTrue((salida / "INFORME-PORTABILIDAD.md").exists())

    def test_el_hallazgo_aparece_en_resumen_json(self):
        _, salida = self.exportar()
        datos = json.loads((salida / "resumen.json").read_text(encoding="utf-8"))
        ilegibles = [h for s in datos["skills"] for h in s["hallazgos"]
                     if h["codigo"] == "fichero-ilegible"]
        self.assertEqual(len(ilegibles), 1, "se esperaba uno y solo uno")
        self.assertEqual(ilegibles[0]["severidad"], "media")
        self.assertIn("notas.md", ilegibles[0]["mensaje"])

    def test_el_mensaje_no_miente_sobre_lo_que_viaja(self):
        """Si dice que no se copio, el zip no puede contenerlo."""
        _, salida = self.exportar()
        self.assertEqual(
            zipfile.ZipFile(str(salida / "x.zip")).namelist(), ["x/SKILL.md"])


if __name__ == "__main__":
    unittest.main()
