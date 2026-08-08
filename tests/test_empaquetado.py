import tempfile
import unittest
import zipfile
from pathlib import Path

from ayuda import importar_exporter

importar_exporter()

from exporter.empaquetado import comprobar_limites, copiar_skill, zip_dir  # noqa: E402
from exporter.perfiles import cargar_perfiles  # noqa: E402


class CopiaSinSeguirEnlaces(unittest.TestCase):

    def test_no_copia_el_contenido_de_un_enlace(self):
        # copytree con symlinks=False copia el CONTENIDO de lo apuntado. Un
        # enlace a ~/.ssh/id_rsa acabaria dentro del zip que se sube a
        # ChatGPT o a Perplexity.
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            secreto = raiz / "secreto.txt"
            secreto.write_text("CLAVE-PRIVADA-QUE-NO-DEBE-VIAJAR", encoding="utf-8")

            origen = raiz / "skill"
            origen.mkdir()
            (origen / "nota.md").write_text("contenido normal", encoding="utf-8")
            (origen / "trampa.txt").symlink_to(secreto)

            destino = raiz / "salida"
            senales = copiar_skill(origen, destino, ignorar=set())

            self.assertFalse((destino / "trampa.txt").exists())
            self.assertTrue((destino / "nota.md").exists())
            copiado = "".join(p.read_text(encoding="utf-8")
                              for p in destino.rglob("*") if p.is_file())
            self.assertNotIn("CLAVE-PRIVADA-QUE-NO-DEBE-VIAJAR", copiado)

            self.assertEqual(len(senales), 1)
            self.assertEqual(senales[0].id, "enlace-simbolico")
            self.assertEqual(senales[0].severidad_base, "alta")
            self.assertIn("trampa.txt", senales[0].ubicacion)

    def test_una_skill_sin_enlaces_no_produce_senales(self):
        with tempfile.TemporaryDirectory() as tmp:
            origen = Path(tmp) / "skill"
            (origen / "references").mkdir(parents=True)
            (origen / "references" / "guia.md").write_text("hola", encoding="utf-8")
            senales = copiar_skill(origen, Path(tmp) / "salida", ignorar=set())
            self.assertEqual(senales, [])
            self.assertTrue((Path(tmp) / "salida" / "references" / "guia.md").exists())

    def test_respeta_los_nombres_ignorados(self):
        with tempfile.TemporaryDirectory() as tmp:
            origen = Path(tmp) / "skill"
            (origen / "__pycache__").mkdir(parents=True)
            (origen / "__pycache__" / "x.pyc").write_bytes(b"\x00")
            (origen / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
            copiar_skill(origen, Path(tmp) / "salida", ignorar={"__pycache__", "SKILL.md"})
            self.assertFalse((Path(tmp) / "salida" / "__pycache__").exists())
            self.assertFalse((Path(tmp) / "salida" / "SKILL.md").exists())

    def test_conserva_el_permiso_de_ejecucion(self):
        # read_bytes/write_bytes no arrastran el modo del fichero, a
        # diferencia de shutil.copy2. Un scripts/*.sh sin +x llega inerte a
        # Perplexity Computer, que SI ejecuta scripts/.
        with tempfile.TemporaryDirectory() as tmp:
            origen = Path(tmp) / "skill"
            (origen / "scripts").mkdir(parents=True)
            script = origen / "scripts" / "run.sh"
            script.write_text("#!/bin/sh\necho hola\n", encoding="utf-8")
            script.chmod(0o755)

            destino_raiz = Path(tmp) / "salida"
            copiar_skill(origen, destino_raiz, ignorar=set())

            copia = destino_raiz / "scripts" / "run.sh"
            self.assertTrue(copia.exists())
            self.assertEqual(copia.stat().st_mode & 0o777, 0o755)


class LimitesDePaquete(unittest.TestCase):

    def test_chatgpt_rechaza_demasiados_ficheros(self):
        perfil = cargar_perfiles()["chatgpt"]
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "grande.zip"
            with zipfile.ZipFile(z, "w") as zf:
                for i in range(501):
                    zf.writestr("f{}.txt".format(i), "x")
            avisos = comprobar_limites(z, perfil)
            self.assertTrue(any("ficheros" in a for a in avisos))

    def test_un_paquete_normal_no_produce_avisos(self):
        perfil = cargar_perfiles()["chatgpt"]
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "normal.zip"
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("SKILL.md", "---\nname: x\n---\n")
            self.assertEqual(comprobar_limites(z, perfil), [])

    def test_un_perfil_sin_limites_declarados_no_comprueba_nada(self):
        perfil = cargar_perfiles()["mistral-vibe-work"]
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "x.zip"
            with zipfile.ZipFile(z, "w") as zf:
                for i in range(600):
                    zf.writestr("f{}.txt".format(i), "x")
            self.assertEqual(comprobar_limites(z, perfil), [])


class Empaquetado(unittest.TestCase):

    def test_el_zip_lleva_la_carpeta_de_la_skill_en_la_raiz(self):
        with tempfile.TemporaryDirectory() as tmp:
            origen = Path(tmp) / "mi-skill"
            origen.mkdir()
            (origen / "SKILL.md").write_text("---\nname: mi-skill\n---\n", encoding="utf-8")
            z = Path(tmp) / "mi-skill.zip"
            zip_dir(origen, z, arc_prefix="mi-skill")
            with zipfile.ZipFile(z) as zf:
                self.assertEqual(zf.namelist(), ["mi-skill/SKILL.md"])


if __name__ == "__main__":
    unittest.main()
