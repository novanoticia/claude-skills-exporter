"""El directorio de --out se borra entero: antes de hacerlo hay que estar
seguro de que lo escribio esta herramienta.

Antes de estas pruebas, `export --out .` desde dentro de un repositorio
borraba el arbol de trabajo entero y moria despues con FileNotFoundError,
porque el rmtree ocurria antes de validar nada.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ayuda import RAIZ, RAIZ_SCRIPTS

CONVERT = RAIZ_SCRIPTS / "convert.py"

SKILL = ("---\nname: fechas\n"
         "description: Cárgala cuando el usuario pida convertir una fecha.\n"
         "---\n# Fechas\nPaso 1.\n")


class Base(unittest.TestCase):

    def montar(self):
        """Un origen valido y un destino que aun no existe, hermanos."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(tmp), True)
        origen = tmp / "repo"
        (origen / "skills" / "fechas").mkdir(parents=True)
        (origen / "skills" / "fechas" / "SKILL.md").write_text(SKILL, encoding="utf-8")
        return tmp, origen, tmp / "salida"

    def exportar(self, origen, salida, *args, cwd=None):
        return subprocess.run(
            [sys.executable, str(CONVERT), "export", str(origen),
             "--out", str(salida)] + list(args),
            capture_output=True, text=True, cwd=str(cwd or RAIZ),
            env=dict(os.environ, CSE_FECHA="2026-08-08"))


class DestinoAjeno(Base):
    """Un directorio con cosas dentro que esta herramienta no ha escrito."""

    def poblar(self, salida):
        salida.mkdir(parents=True)
        (salida / "TESIS.md").write_text("mi tesis\n", encoding="utf-8")
        (salida / "fotos").mkdir()
        (salida / "fotos" / "boda.jpg").write_text("x", encoding="utf-8")

    def test_no_lo_borra_y_aborta(self):
        _, origen, salida = self.montar()
        self.poblar(salida)
        r = self.exportar(origen, salida)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--force", r.stderr + r.stdout)
        # Lo que importa: sigue todo ahi.
        self.assertTrue((salida / "TESIS.md").exists())
        self.assertTrue((salida / "fotos" / "boda.jpg").exists())

    def test_con_force_lo_borra_y_exporta(self):
        _, origen, salida = self.montar()
        self.poblar(salida)
        r = self.exportar(origen, salida, "--force")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((salida / "TESIS.md").exists())
        self.assertTrue((salida / "fechas.zip").exists())


class DestinoPropio(Base):

    def test_el_centinela_se_escribe_en_un_export_correcto(self):
        _, origen, salida = self.montar()
        r = self.exportar(origen, salida)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((salida / ".cse-salida").exists())

    def test_un_destino_ya_marcado_se_reescribe_sin_preguntar(self):
        _, origen, salida = self.montar()
        self.assertEqual(self.exportar(origen, salida).returncode, 0)
        (salida / "sobra.txt").write_text("de la vez anterior\n", encoding="utf-8")
        r = self.exportar(origen, salida)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((salida / "sobra.txt").exists())
        self.assertTrue((salida / "fechas.zip").exists())

    def test_un_destino_vacio_o_inexistente_funciona_como_siempre(self):
        _, origen, salida = self.montar()
        self.assertEqual(self.exportar(origen, salida).returncode, 0)

        _, origen2, salida2 = self.montar()
        salida2.mkdir(parents=True)
        self.assertEqual(self.exportar(origen2, salida2).returncode, 0)


class SolapamientoConElOrigen(Base):
    """--out no puede comerse el arbol del que va a leer."""

    def test_out_punto_desde_dentro_del_origen_aborta(self):
        _, origen, _ = self.montar()
        (origen / "TESIS.md").write_text("mi tesis\n", encoding="utf-8")
        antes = sorted(p.name for p in origen.rglob("*"))

        r = self.exportar(".", ".", cwd=origen)

        self.assertNotEqual(r.returncode, 0)
        self.assertIn("origen", r.stderr + r.stdout)
        self.assertEqual(sorted(p.name for p in origen.rglob("*")), antes)

    def test_out_que_contiene_al_origen_aborta(self):
        tmp, origen, _ = self.montar()
        r = self.exportar(origen, tmp)
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue((origen / "skills" / "fechas" / "SKILL.md").exists())

    def test_out_dentro_del_origen_esta_permitido(self):
        """`export . --out ./salida` solo borra ./salida: el origen sobrevive.

        Es la forma del --out por defecto y la que usa test_seg_integracion.
        """
        _, origen, _ = self.montar()
        dentro = origen / "salida"
        r = self.exportar(origen, dentro)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((dentro / "fechas.zip").exists())
        self.assertTrue((origen / "skills" / "fechas" / "SKILL.md").exists())

    def test_pero_no_sobre_un_directorio_del_propio_repositorio(self):
        """La version peligrosa de la misma forma la para la propiedad."""
        _, origen, _ = self.montar()
        r = self.exportar(origen, origen / "skills")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--force", r.stderr + r.stdout)
        self.assertTrue((origen / "skills" / "fechas" / "SKILL.md").exists())


class ElOrigenSigueIntacto(Base):
    """La reproduccion del informe de auditoria, como prueba."""

    def test_export_out_punto_no_destruye_el_arbol_de_trabajo(self):
        _, origen, _ = self.montar()
        (origen / "TESIS.md").write_text("mi tesis\n", encoding="utf-8")
        (origen / "fotos").mkdir()
        (origen / "fotos" / "boda.jpg").write_text("x", encoding="utf-8")
        antes = len([p for p in origen.rglob("*") if p.is_file()])

        self.exportar(".", ".", cwd=origen)

        despues = len([p for p in origen.rglob("*") if p.is_file()])
        self.assertEqual((antes, despues), (3, 3))


if __name__ == "__main__":
    unittest.main()
