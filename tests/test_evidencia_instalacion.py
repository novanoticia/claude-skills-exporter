"""La instalacion sin probar se dice, modo por modo.

`evaluar` devolvia el mismo estado y los mismos motivos para todos los modos
de un destino. Una skill de texto salia `compatible` en ChatGPT dos veces:
por zip, que nadie ha subido nunca, y por URL de repositorio, que este
conversor ni siquiera valida —exporta skills sueltas, no plugins—.

El perfil puede declarar ahora, por modo, que la instalacion no esta probada.
Es opcional: un perfil que no lo declara se evalua como siempre.
"""

import copy
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ayuda import RAIZ, RAIZ_SCRIPTS, importar_exporter

importar_exporter()

from exporter.compatibilidad import anotar_limites, evaluar  # noqa: E402
from exporter.modelo import Estado, SkillPortatil  # noqa: E402
from exporter.perfiles import Perfil, cargar_perfiles  # noqa: E402

CONVERT = RAIZ_SCRIPTS / "convert.py"
HOY = datetime.date(2026, 9, 1)
OTROS = ("claude-ai", "claude-code", "mistral-vibe-work", "perplexity-computer")


def skill(tiene_scripts=False):
    from exporter.modelo import capacidades_de
    s = SkillPortatil(nombre="x", nombre_original="x", carpeta="x",
                      descripcion="Cárgala cuando el usuario lo pida.",
                      tiene_activacion=True, tiene_scripts=tiene_scripts)
    s.capacidades = capacidades_de(s.senales, s.tiene_scripts)
    return s


def por_modo(evs) -> dict:
    return {e.modo_instalacion: e for e in evs}


class ChatGPTDeclaraQueNoEstaProbado(unittest.TestCase):

    def setUp(self):
        self.perfiles = cargar_perfiles()
        self.evs = por_modo(evaluar(skill(), self.perfiles["chatgpt"], HOY))

    def test_una_skill_limpia_ya_no_sale_compatible(self):
        self.assertEqual(self.evs["zip"].estado, Estado.NO_VERIFICABLE)
        self.assertEqual(self.evs["url_repositorio"].estado, Estado.NO_VERIFICABLE)

    def test_cada_modo_lleva_su_propio_motivo(self):
        zip_, url = self.evs["zip"].motivos, self.evs["url_repositorio"].motivos
        self.assertEqual(len(zip_), 1)
        self.assertEqual(len(url), 1)
        self.assertNotEqual(zip_, url)

    def test_el_motivo_del_zip_cita_la_fuente_documental(self):
        self.assertIn("help.openai.com", self.evs["zip"].motivos[0])

    def test_el_motivo_de_la_url_dice_que_no_se_valida_un_plugin(self):
        motivo = self.evs["url_repositorio"].motivos[0]
        self.assertIn("plugin", motivo)
        self.assertIn("agent-plugins.org", motivo)

    def test_los_otros_cuatro_perfiles_no_cambian(self):
        for pid in OTROS:
            for ev in evaluar(skill(), self.perfiles[pid], HOY):
                self.assertEqual(ev.estado, Estado.COMPATIBLE, pid)
                self.assertEqual(ev.motivos, [], pid)

    def test_y_ninguno_de_ellos_declara_el_campo(self):
        for pid in OTROS:
            self.assertNotIn("evidencia_por_modo",
                             self.perfiles[pid].datos["instalacion"], pid)


class LaIncertidumbreNoTapaLoConocido(unittest.TestCase):

    def test_un_limite_incumplido_sigue_siendo_no_compatible(self):
        evs = evaluar(skill(), cargar_perfiles()["chatgpt"], HOY)
        anotar_limites(evs, ["El zip lleva 501 ficheros y ChatGPT admite 500."])
        m = por_modo(evs)
        self.assertEqual(m["zip"].estado, Estado.NO_COMPATIBLE)
        self.assertEqual(m["url_repositorio"].estado, Estado.NO_VERIFICABLE)
        # Y el motivo de la instalacion sin probar no desaparece.
        self.assertEqual(len(m["zip"].motivos), 2)

    def test_una_capacidad_que_falta_sigue_siendo_no_compatible(self):
        datos = copy.deepcopy(cargar_perfiles()["chatgpt"].datos)
        datos["capacidades"]["scripts.ejecutar"] = "no"
        for ev in evaluar(skill(tiene_scripts=True), Perfil(datos), HOY):
            self.assertEqual(ev.estado, Estado.NO_COMPATIBLE)


class ElCampoEsOpcionalYSeRespeta(unittest.TestCase):

    def con_evidencia(self, por_modo_):
        datos = copy.deepcopy(cargar_perfiles()["chatgpt"].datos)
        if por_modo_ is None:
            datos["instalacion"].pop("evidencia_por_modo", None)
        else:
            datos["instalacion"]["evidencia_por_modo"] = por_modo_
        return Perfil(datos)

    def test_sin_el_campo_se_evalua_como_antes(self):
        for ev in evaluar(skill(), self.con_evidencia(None), HOY):
            self.assertEqual(ev.estado, Estado.COMPATIBLE)
            self.assertEqual(ev.motivos, [])

    def test_un_modo_probado_no_anade_nada(self):
        perfil = self.con_evidencia({
            "zip": {"probada": True, "motivo": "paquete-sin-probar",
                    "fuente": "https://ejemplo.invalid/prueba"}})
        for ev in evaluar(skill(), perfil, HOY):
            self.assertEqual(ev.estado, Estado.COMPATIBLE)
            self.assertEqual(ev.motivos, [])

    def test_solo_se_marca_el_modo_declarado(self):
        perfil = self.con_evidencia({
            "zip": {"probada": False, "motivo": "paquete-sin-probar",
                    "fuente": "https://ejemplo.invalid/ayuda"}})
        m = por_modo(evaluar(skill(), perfil, HOY))
        self.assertEqual(m["zip"].estado, Estado.NO_VERIFICABLE)
        self.assertEqual(m["url_repositorio"].estado, Estado.COMPATIBLE)

    def test_las_listas_de_cada_modo_son_independientes(self):
        # Antes todos los modos compartian contenido; una lista compartida
        # haria que anotar un modo ensuciara el otro.
        m = por_modo(evaluar(skill(), cargar_perfiles()["chatgpt"], HOY))
        m["zip"].motivos.append("solo aqui")
        self.assertNotIn("solo aqui", m["url_repositorio"].motivos)


class PorElCLI(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        carpeta = self.tmp / "repo" / "skills" / "mini"
        carpeta.mkdir(parents=True)
        (carpeta / "SKILL.md").write_text(
            "---\nname: mini\ndescription: Cárgala cuando el usuario pida un "
            "resumen breve de un texto.\n---\n# Mini\n\nResume el texto.\n",
            encoding="utf-8")

    def lanzar(self, *args):
        return subprocess.run(
            [sys.executable, str(CONVERT)] + [str(a) for a in args],
            capture_output=True, text=True, cwd=str(RAIZ),
            env=dict(os.environ, CSE_FECHA="2026-09-01"))

    def test_el_informe_explica_los_dos_modos_de_chatgpt(self):
        salida = self.tmp / "out"
        r = self.lanzar("export", self.tmp / "repo", "--out", salida)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        informe = (salida / "INFORME-PORTABILIDAD.md").read_text(encoding="utf-8")
        self.assertIn("ChatGPT (zip)", informe)
        self.assertIn("ChatGPT (url_repositorio)", informe)
        resumen = json.loads((salida / "resumen.json").read_text(encoding="utf-8"))
        compat = resumen["skills"][0]["compatibilidad"]
        self.assertEqual({e["estado"] for e in compat["chatgpt"]},
                         {Estado.NO_VERIFICABLE})
        for pid in OTROS:
            self.assertEqual({e["estado"] for e in compat[pid]},
                             {Estado.COMPATIBLE}, pid)

    def test_el_zip_se_sigue_escribiendo(self):
        salida = self.tmp / "out"
        self.lanzar("export", self.tmp / "repo", "--out", salida,
                    "--target", "chatgpt")
        self.assertTrue((salida / "mini.zip").is_file())

    def test_no_verificable_no_dispara_el_umbral_no_compatible(self):
        r = self.lanzar("audit", self.tmp / "repo", "--target", "chatgpt",
                        "--fail-on", "no_compatible")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_pero_si_el_umbral_degradado(self):
        r = self.lanzar("audit", self.tmp / "repo", "--target", "chatgpt",
                        "--fail-on", "degradado")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_el_umbral_degradado_no_salta_por_los_demas_destinos(self):
        r = self.lanzar("audit", self.tmp / "repo", "--target", "perplexity-computer",
                        "claude-ai", "--fail-on", "degradado")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
