"""El artefacto sale siempre con exactamente un SKILL.md en mayusculas.

discover_skills acepta cualquier capitalizacion (`names = {f.lower(): f
...}`), pero la copia y la deteccion excluian el literal "SKILL.md". Una
skill en `skills/x/skill.md` no casaba con ese literal, asi que:

  - en un sistema de ficheros sensible a mayusculas el paquete salia con
    `SKILL.md` Y `skill.md`, y el segundo era el original SIN adaptar
    -comprobado sobre un volumen APFS sensible a mayusculas-;
  - en macOS los dos nombres colapsaban en uno y el paquete se quedaba sin
    ningun `SKILL.md`.

La asercion de aqui es exacta (`== ["minus/SKILL.md"]`) a proposito: es la
unica forma de que la prueba detecte los dos sintomas, porque cada uno solo
se manifiesta en un tipo de sistema de ficheros.
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

from ayuda import RAIZ, RAIZ_SCRIPTS

CONVERT = RAIZ_SCRIPTS / "convert.py"

# Un patron que la adaptacion REESCRIBE en el cuerpo. Sirve para distinguir
# el SKILL.md adaptado del original crudo: si el crudo se cuela en el
# paquete o en la auditoria, el patron reaparece.
CUERPO = "# Minus\nUsa ${CLAUDE_PLUGIN_ROOT}/bin para arrancar.\n"

SKILL = ("---\nname: minus\n"
         "description: Cárgala cuando el usuario pida convertir una fecha.\n"
         "---\n" + CUERPO)


class Base(unittest.TestCase):

    def exportar(self, nombre_fichero):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(tmp), True)
        skill = tmp / "repo" / "skills" / "x"
        skill.mkdir(parents=True)
        (skill / nombre_fichero).write_text(SKILL, encoding="utf-8")
        salida = tmp / "out"
        r = subprocess.run(
            [sys.executable, str(CONVERT), "export", str(tmp / "repo"),
             "--out", str(salida)],
            capture_output=True, text=True, cwd=str(RAIZ),
            env=dict(os.environ, CSE_FECHA="2026-08-08"))
        return r, salida


class ElZipLlevaUnUnicoSkillMd(Base):

    def test_minusculas(self):
        r, salida = self.exportar("skill.md")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            zipfile.ZipFile(str(salida / "minus.zip")).namelist(),
            ["minus/SKILL.md"])

    def test_capitalizacion_mixta(self):
        r, salida = self.exportar("Skill.md")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            zipfile.ZipFile(str(salida / "minus.zip")).namelist(),
            ["minus/SKILL.md"])

    def test_mayusculas_sigue_igual(self):
        """La forma canonica no puede haberse roto por el camino."""
        r, salida = self.exportar("SKILL.md")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            zipfile.ZipFile(str(salida / "minus.zip")).namelist(),
            ["minus/SKILL.md"])

    def test_la_carpeta_para_mistral_tambien(self):
        _r, salida = self.exportar("skill.md")
        self.assertEqual([p.name for p in (salida / "minus").iterdir()],
                         ["SKILL.md"])


class ElUnicoSkillMdEsElAdaptado(Base):
    """No basta con que haya uno: tiene que ser el bueno."""

    def test_el_cuerpo_del_zip_esta_adaptado(self):
        _r, salida = self.exportar("skill.md")
        texto = zipfile.ZipFile(
            str(salida / "minus.zip")).read("minus/SKILL.md").decode("utf-8")
        # Se compara la LINEA, no el literal suelto: las «Notas de
        # portabilidad» que el conversor añade al final mencionan
        # ${CLAUDE_PLUGIN_ROOT} a proposito, para explicar lo que reescribio.
        self.assertIn("Usa bin para arrancar.", texto)
        self.assertNotIn("Usa ${CLAUDE_PLUGIN_ROOT}/bin para arrancar.", texto)

    def test_no_queda_ningun_hallazgo_del_fichero_crudo(self):
        """El crudo se auditaba aparte y delataba lo que ya estaba corregido."""
        _r, salida = self.exportar("skill.md")
        datos = json.loads((salida / "resumen.json").read_text(encoding="utf-8"))
        mensajes = [h["mensaje"] for h in datos["skills"][0]["hallazgos"]]
        self.assertEqual([m for m in mensajes if "skill.md:" in m], [])


if __name__ == "__main__":
    unittest.main()
