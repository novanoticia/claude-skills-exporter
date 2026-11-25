"""Mas de un SKILL.md: en el mismo directorio se aborta; anidado, se avisa.

Antes, los dos casos se resolvian en silencio:

  - Dos ficheros de skill en el MISMO directorio (`SKILL.md` y `skill.md`,
    posible en un sistema de ficheros sensible a mayusculas): discover_skills
    se quedaba con uno de los dos segun el orden en que el sistema listara
    el directorio, y el otro viajaba al paquete sin adaptar. No hay forma de
    saber cual es el bueno, asi que se aborta.
  - Un SKILL.md dentro de la carpeta de otra skill: discover_skills no
    desciende (la subcarpeta pertenece a la skill de arriba), y la copia y
    la deteccion excluian el nombre `SKILL.md` a CUALQUIER profundidad. El
    anidado ni se exportaba como skill ni viajaba dentro del paquete, y su
    contenido no se auditaba. En cambio un `skill.md` anidado, en
    minusculas, si se copiaba. Ahora la exclusion es solo la del SKILL.md
    de la raiz: el anidado se copia y se audita como cualquier otro fichero,
    y el informe avisa de que no se exporta como skill propia.
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
from unittest.mock import patch

from ayuda import RAIZ, RAIZ_SCRIPTS, importar_exporter

importar_exporter()
import convert

CONVERT = RAIZ_SCRIPTS / "convert.py"


def skill_md(nombre, cuerpo="Paso 1."):
    return ("---\nname: {}\n"
            "description: Cárgala cuando el usuario pida convertir una fecha.\n"
            "---\n# Fechas\n{}\n".format(nombre, cuerpo))


class Base(unittest.TestCase):

    def montar(self, ficheros):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(tmp), True)
        raiz = tmp / "repo"
        for rel, c in ficheros.items():
            p = raiz / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(c, encoding="utf-8")
        return raiz, tmp / "out"

    def correr(self, comando, raiz, salida, *args):
        return subprocess.run(
            [sys.executable, str(CONVERT), comando, str(raiz)]
            + (["--out", str(salida)] if comando == "export" else [])
            + list(args),
            capture_output=True, text=True, cwd=str(RAIZ),
            env=dict(os.environ, CSE_FECHA="2026-09-01"))

    def hallazgos(self, salida, skill=0):
        d = json.loads((salida / "resumen.json").read_text(encoding="utf-8"))
        return d["skills"][skill]["hallazgos"]


class CapturaPortable(Base):

    def test_exporta_un_archivo_regular(self):
        raiz, salida = self.montar({"skills/x/SKILL.md": skill_md("fechas")})
        r = self.correr("export", raiz, salida)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((salida / "fechas.zip").is_file())

    def test_sin_dir_fd_puede_copiar_un_archivo_regular(self):
        rel = Path("skills/x/SKILL.md")
        raiz, salida = self.montar({rel: skill_md("fechas")})
        with patch.object(convert.os, "supports_dir_fd", set()):
            convert.copiar_skill_md(raiz, rel, salida)
        self.assertEqual(salida.read_bytes(), (raiz / rel).read_bytes())

    def test_sin_dir_fd_rechaza_un_componente_enlazado(self):
        raiz, salida = self.montar({"skills/x/SKILL.md": skill_md("fechas")})
        enlace = raiz / "enlace"
        try:
            enlace.symlink_to(raiz / "skills/x", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("el sistema no permite crear enlaces")
        with patch.object(convert.os, "supports_dir_fd", set()):
            with self.assertRaises(SystemExit):
                convert.copiar_skill_md(raiz, Path("enlace/SKILL.md"), salida)
        self.assertFalse(salida.exists())


class ArchivoPrincipalSeguro(Base):

    @unittest.skipUnless(hasattr(os, "symlink"), "el sistema no admite enlaces")
    def test_rechaza_enlace_en_los_tres_comandos(self):
        raiz, salida = self.montar({"skills/x/README.md": "Skill de prueba.\n"})
        destino = raiz.parent / "destino.md"
        destino.write_text(skill_md("fechas"), encoding="utf-8")
        (raiz / "skills/x/Skill.md").symlink_to(destino)
        for comando in ("inspect", "audit", "export"):
            with self.subTest(comando=comando):
                filtro = ("--only", "fechas") if comando == "export" else ()
                r = self.correr(comando, raiz, salida, *filtro)
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertIn("skills/x/Skill.md", r.stderr)
                self.assertIn("enlaces simbólicos", r.stderr)
                self.assertFalse((salida / "fechas.zip").exists())
                self.assertFalse((salida / "fechas" / "SKILL.md").exists())


class EnElMismoDirectorioAborta(Base):

    def montar_duplicado(self):
        raiz, salida = self.montar({
            "skills/x/SKILL.md": skill_md("fechas"),
            "skills/x/skill.md": skill_md("otra"),
            "skills/y/SKILL.md": skill_md("horas"),
        })
        if len([p for p in (raiz / "skills" / "x").iterdir()]) != 2:
            self.skipTest("sistema de ficheros insensible a mayusculas")
        return raiz, salida

    def test_export_aborta_citando_la_carpeta_y_los_ficheros(self):
        raiz, salida = self.montar_duplicado()
        r = self.correr("export", raiz, salida)
        texto = r.stdout + r.stderr
        self.assertEqual(r.returncode, 1, texto)
        self.assertIn("skills/x", texto)
        self.assertIn("SKILL.md", texto)
        self.assertIn("skill.md", texto)

    def test_no_escribe_nada_en_el_destino(self):
        raiz, salida = self.montar_duplicado()
        self.correr("export", raiz, salida)
        self.assertEqual(
            sorted(p.name for p in salida.iterdir() if p.name != ".cse-salida"), [])

    def test_audit_e_inspect_tambien_abortan(self):
        # inspect tambien: no hay forma de saber cual de los dos describir.
        raiz, salida = self.montar_duplicado()
        for comando in ("audit", "inspect"):
            r = self.correr(comando, raiz, salida)
            self.assertEqual(r.returncode, 1, comando + r.stdout + r.stderr)

    def test_only_que_deja_fuera_esa_carpeta_no_aborta(self):
        raiz, salida = self.montar_duplicado()
        r = self.correr("export", raiz, salida, "--only", "horas")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((salida / "horas.zip").is_file())


class AnidadoAvisa(Base):

    def test_avisa_y_sigue_exportando_solo_la_de_arriba(self):
        raiz, salida = self.montar({
            "skills/x/SKILL.md": skill_md("fechas"),
            "skills/x/sub/SKILL.md": skill_md("interna"),
        })
        r = self.correr("export", raiz, salida)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((salida / "fechas.zip").is_file())
        self.assertFalse((salida / "interna.zip").exists())
        h = [h for h in self.hallazgos(salida) if h["codigo"] == "skill-anidada"]
        self.assertEqual(len(h), 1)
        self.assertIn("sub/SKILL.md", h[0]["mensaje"])

    def test_el_anidado_viaja_en_el_paquete(self):
        raiz, salida = self.montar({
            "skills/x/SKILL.md": skill_md("fechas"),
            "skills/x/sub/SKILL.md": skill_md("interna"),
        })
        self.correr("export", raiz, salida)
        nombres = zipfile.ZipFile(str(salida / "fechas.zip")).namelist()
        self.assertIn("fechas/SKILL.md", nombres)
        self.assertIn("fechas/sub/SKILL.md", nombres)
        self.assertTrue((salida / "fechas" / "sub" / "SKILL.md").is_file())

    def test_el_anidado_se_audita(self):
        # Antes se saltaba por nombre y su contenido no producia senales.
        raiz, salida = self.montar({
            "skills/x/SKILL.md": skill_md("fechas"),
            "skills/x/sub/SKILL.md": skill_md("interna", "Llama a mcp__srv__accion."),
        })
        self.correr("export", raiz, salida)
        mensajes = [h["mensaje"] for h in self.hallazgos(salida)
                    if h["codigo"] == "mcp-tool"]
        self.assertTrue(any("sub/SKILL.md" in m for m in mensajes), mensajes)

    def test_mayusculas_y_minusculas_se_tratan_igual(self):
        raiz, salida = self.montar({
            "skills/x/SKILL.md": skill_md("fechas"),
            "skills/x/a/SKILL.md": skill_md("a"),
            "skills/x/b/skill.md": skill_md("b"),
        })
        self.correr("export", raiz, salida)
        nombres = zipfile.ZipFile(str(salida / "fechas.zip")).namelist()
        self.assertIn("fechas/a/SKILL.md", nombres)
        self.assertIn("fechas/b/skill.md", nombres)
        h = next(h for h in self.hallazgos(salida) if h["codigo"] == "skill-anidada")
        self.assertIn("a/SKILL.md", h["mensaje"])
        self.assertIn("b/skill.md", h["mensaje"])

    def test_un_skill_md_en_la_raiz_del_repo_tambien_cuenta(self):
        # Caso realista: el repo entero es una skill y dentro hay otras.
        raiz, salida = self.montar({
            "SKILL.md": skill_md("todo"),
            "skills/y/SKILL.md": skill_md("horas"),
        })
        r = self.correr("export", raiz, salida)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        h = [h for h in self.hallazgos(salida) if h["codigo"] == "skill-anidada"]
        self.assertEqual(len(h), 1)
        self.assertIn("skills/y/SKILL.md", h[0]["mensaje"])

    def test_sin_anidados_no_hay_aviso(self):
        raiz, salida = self.montar({
            "skills/x/SKILL.md": skill_md("fechas"),
            "skills/x/references/guia.md": "# Guía\n",
        })
        self.correr("export", raiz, salida)
        self.assertNotIn("skill-anidada",
                         [h["codigo"] for h in self.hallazgos(salida)])


if __name__ == "__main__":
    unittest.main()
