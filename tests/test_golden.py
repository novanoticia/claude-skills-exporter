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

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = Path(__file__).resolve().parent / "golden"
CONVERT = RAIZ_SCRIPTS / "convert.py"

CON_SKILLS = ["skill-minima", "skill-con-scripts", "skill-con-mcp",
              "skill-sin-activacion", "skill-description-larga",
              "skill-frontmatter-exotico"]

# Fecha fija para todo el modulo, via CSE_FECHA: los perfiles llevan
# `revisar_tras` y, sin fijarla, el veredicto de un golden file cambia de
# `compatible` a `no_verificable` el dia que la fecha real del sistema
# supere esa fecha, con CI en rojo y cero cambios de codigo de por medio.
FECHA_FIJA = "2026-08-08"


def _entorno_con_fecha_fija() -> dict:
    entorno = dict(os.environ)
    entorno["CSE_FECHA"] = FECHA_FIJA
    return entorno


def exportar(fixture: str, destino: Path):
    return subprocess.run(
        [sys.executable, str(CONVERT), "export", str(FIXTURES / fixture),
         "--out", str(destino)],
        capture_output=True, text=True, cwd=str(RAIZ), env=_entorno_con_fecha_fija())


def exportar_ruta(origen: Path, destino: Path):
    """Como `exportar`, pero para un origen que no vive bajo fixtures/.

    Lo usa `SkillConEnlace`: un enlace simbolico no se puede fijar como
    contenido de fixture -apunta fuera de la carpeta de la skill, y ese
    destino no sobrevive a un `git clone` en otra maquina-, asi que ese caso
    se construye en un directorio temporal en cada ejecucion.
    """
    return subprocess.run(
        [sys.executable, str(CONVERT), "export", str(origen),
         "--out", str(destino)],
        capture_output=True, text=True, cwd=str(RAIZ), env=_entorno_con_fecha_fija())


def normalizar(resumen: dict) -> dict:
    """Quita lo que depende de la ruta temporal, no del contenido."""
    resumen["origen"] = "<origen>"
    return resumen


class GoldenFiles(unittest.TestCase):

    def test_cada_fixture_produce_su_resumen_esperado(self):
        for fixture in CON_SKILLS:
            with self.subTest(fixture=fixture):
                with tempfile.TemporaryDirectory() as tmp:
                    r = exportar(fixture, Path(tmp))
                    self.assertEqual(r.returncode, 0, r.stderr)
                    obtenido = normalizar(json.loads(
                        (Path(tmp) / "resumen.json").read_text(encoding="utf-8")))
                    esperado = json.loads(
                        (GOLDEN / (fixture + ".json")).read_text(encoding="utf-8"))
                    self.assertEqual(
                        obtenido, esperado,
                        "El resumen de {} ha cambiado. Si el cambio es deseado, "
                        "regenera con: python3 tests/generar_golden.py".format(fixture))


class Reproducibilidad(unittest.TestCase):

    def test_dos_ejecuciones_dan_el_mismo_resumen(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            exportar("skill-con-mcp", a)
            exportar("skill-con-mcp", b)
            self.assertEqual(
                (a / "resumen.json").read_text(encoding="utf-8"),
                (b / "resumen.json").read_text(encoding="utf-8"))


class RepoSinSkills(unittest.TestCase):

    def test_aborta_sin_fabricar_un_zip_vacio(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "salida"
            r = exportar("repo-sin-skills", destino)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("SKILL.md", r.stderr + r.stdout)
            self.assertEqual(list(destino.glob("*.zip")) if destino.exists() else [], [])


class CasosConcretos(unittest.TestCase):

    def leer(self, fixture):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        exportar(fixture, Path(tmp))
        return json.loads((Path(tmp) / "resumen.json").read_text(encoding="utf-8"))

    def test_scripts_no_compatible_en_mistral_compatible_en_perplexity(self):
        d = self.leer("skill-con-scripts")
        compat = d["skills"][0]["compatibilidad"]
        self.assertEqual(compat["mistral-vibe-work"][0]["estado"], "no_compatible")
        self.assertEqual(compat["perplexity-computer"][0]["estado"], "compatible")

    def test_mcp_no_compatible_fuera_de_claude_code(self):
        d = self.leer("skill-con-mcp")
        compat = d["skills"][0]["compatibilidad"]
        self.assertEqual(compat["claude-code"][0]["estado"], "compatible")
        for destino in ("chatgpt", "claude-ai", "mistral-vibe-work", "perplexity-computer"):
            self.assertEqual(compat[destino][0]["estado"], "no_compatible", destino)

    def test_sin_activacion_produce_hallazgo_alto(self):
        d = self.leer("skill-sin-activacion")
        codigos = [h["codigo"] for h in d["skills"][0]["hallazgos"]]
        self.assertIn("description-sin-activacion", codigos)

    def test_el_frontmatter_exotico_conserva_version_bajo_metadata(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        exportar("skill-frontmatter-exotico", Path(tmp))
        texto = (Path(tmp) / "frontmatter-exotico" / "SKILL.md").read_text(encoding="utf-8")
        # El frontmatter real es solo lo que va entre el primer par de "---":
        # es lo unico que un parser YAML de destino lee. Las "Notas de
        # portabilidad" que van despues, en el cuerpo, SI pueden nombrar
        # "allowed-tools" o "model" en prosa -es lo que le explica al humano
        # que sube la skill que esas claves se retiraron y por que-, y eso no
        # es un fallo: ningun destino interpreta el cuerpo como YAML.
        frontmatter = texto.split("---")[1]
        self.assertIn("metadata:", texto)
        self.assertIn("version:", texto)
        self.assertNotIn("\nversion:", frontmatter)
        self.assertNotIn("allowed-tools", frontmatter)
        self.assertNotIn("model:", frontmatter)


class SkillConEnlace(unittest.TestCase):
    """El octavo caso, con enlace simbolico.

    No hay `tests/fixtures/skill-con-enlace/`: un enlace no se puede fijar
    como contenido de fixture porque tiene que apuntar a algo que exista, y
    apuntar dentro del propio repositorio no probaria nada (no hay fuga si
    el destino ya era publico). El enlace tiene que apuntar a un fichero
    "secreto" fuera de la skill, y eso solo tiene sentido construido en un
    directorio temporal en cada ejecucion -igual que ya hace
    test_empaquetado.py::CopiaSinSeguirEnlaces para el mismo motivo-, nunca
    committeado.
    """

    def construir(self, raiz: Path) -> Path:
        secreto = raiz / "secreto.txt"
        secreto.write_text("CLAVE-PRIVADA-QUE-NO-DEBE-VIAJAR", encoding="utf-8")

        repo = raiz / "repo"
        origen = repo / "skills" / "con-enlace"
        origen.mkdir(parents=True)
        (origen / "SKILL.md").write_text(
            "---\n"
            "name: con-enlace\n"
            "description: Cárgala cuando el usuario pida probar un enlace "
            'simbólico, diga "prueba el enlace" o "revisa el atajo". Skill de '
            "prueba para comprobar que un enlace simbólico no viaja al "
            "paquete.\n"
            "---\n\n"
            "# Prueba de enlace\n\n"
            "Nada que hacer: esta skill solo existe para tener un enlace "
            "simbólico dentro.\n",
            encoding="utf-8")
        (origen / "trampa.txt").symlink_to(secreto)
        return repo

    def test_el_enlace_se_omite_y_su_contenido_no_llega_a_ningun_artefacto(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            repo = self.construir(raiz)
            destino = raiz / "salida"

            r = exportar_ruta(repo, destino)
            self.assertEqual(r.returncode, 0, r.stderr)

            resumen = json.loads((destino / "resumen.json").read_text(encoding="utf-8"))
            skill = resumen["skills"][0]
            codigos = [h["codigo"] for h in skill["hallazgos"]]
            self.assertIn("enlace-simbolico", codigos)

            # La carpeta exportada (la variante de Mistral) no trae el enlace.
            self.assertFalse((destino / "con-enlace" / "trampa.txt").exists())

            secreto_txt = "CLAVE-PRIVADA-QUE-NO-DEBE-VIAJAR"

            # Ningun fichero de la carpeta exportada reproduce el contenido.
            for p in (destino / "con-enlace").rglob("*"):
                if p.is_file():
                    self.assertNotIn(secreto_txt.encode("utf-8"), p.read_bytes())

            # El .zip (la variante de Perplexity/ChatGPT/claude.ai) tampoco lo trae.
            with zipfile.ZipFile(destino / "con-enlace.zip") as z:
                self.assertNotIn("con-enlace/trampa.txt", z.namelist())
                for nombre in z.namelist():
                    self.assertNotIn(secreto_txt.encode("utf-8"), z.read(nombre))

            # Ni el informe humano ni el resumen maquina lo citan.
            informe = (destino / "INFORME-PORTABILIDAD.md").read_text(encoding="utf-8")
            self.assertNotIn(secreto_txt, informe)
            self.assertNotIn(
                secreto_txt,
                (destino / "resumen.json").read_text(encoding="utf-8"))


class FechaSimulada(unittest.TestCase):
    """CSE_FECHA es la mitigacion del criterio de aceptacion 7: convierte la
    bomba de tiempo (los perfiles caducan y el veredicto cambia solo, sin que
    nadie toque una linea de codigo) en un comportamiento cubierto por
    pruebas.
    """

    def _exportar_con_fecha(self, fecha: str, destino: Path):
        entorno = dict(os.environ)
        entorno["CSE_FECHA"] = fecha
        return subprocess.run(
            [sys.executable, str(CONVERT), "export", str(FIXTURES / "skill-minima"),
             "--out", str(destino)],
            capture_output=True, text=True, cwd=str(RAIZ), env=entorno)

    def test_una_fecha_posterior_a_revisar_tras_da_no_verificable(self):
        # mistral-vibe-work.json tiene revisar_tras: 2026-10-27. Con una
        # fecha simulada muy posterior, la evidencia de ese perfil ha
        # caducado y el veredicto debe reflejarlo, no seguir afirmando
        # "compatible" con datos vencidos.
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "salida"
            r = self._exportar_con_fecha("2030-01-01", destino)
            self.assertEqual(r.returncode, 0, r.stderr)
            resumen = json.loads((destino / "resumen.json").read_text(encoding="utf-8"))
            estado = resumen["skills"][0]["compatibilidad"]["mistral-vibe-work"][0]["estado"]
            self.assertEqual(estado, "no_verificable")

    def test_una_fecha_csefecha_invalida_aborta_con_mensaje_en_espanol(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "salida"
            r = self._exportar_con_fecha("no-es-una-fecha", destino)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("CSE_FECHA", r.stderr + r.stdout)
            self.assertFalse(destino.exists())


if __name__ == "__main__":
    unittest.main()
