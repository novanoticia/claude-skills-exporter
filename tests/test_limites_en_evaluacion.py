"""Un limite de paquete incumplido tiene que verse en la matriz y en --fail-on.

`comprobar_limites` anadia el hallazgo `limite-de-paquete` DESPUES de calcular
las evaluaciones, y solo en `export`. El resultado era contradictorio: el
informe avisaba de que el zip incumplia el perfil de ChatGPT, la matriz decia
que ChatGPT era compatible, y `--fail-on no_compatible` devolvia 0. `audit`,
que no empaqueta, ni siquiera llegaba a emitir el hallazgo.

Lo que se comprueba es el perfil configurado, no la plataforma: nadie ha
observado que ChatGPT rechace un zip por esto.
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
import zipfile
from pathlib import Path

from ayuda import RAIZ, RAIZ_SCRIPTS, importar_exporter

importar_exporter()

from exporter.compatibilidad import anotar_limites, evaluar  # noqa: E402
from exporter.empaquetado import comprobar_limites  # noqa: E402
from exporter.modelo import Estado, SkillPortatil  # noqa: E402
from exporter.perfiles import Perfil, cargar_perfiles  # noqa: E402

CONVERT = RAIZ_SCRIPTS / "convert.py"

# Anterior al `revisar_tras` de los cinco perfiles: asi el estado de partida
# es `compatible` y lo unico que puede cambiarlo es el limite.
FECHA = "2026-09-01"
HOY = datetime.date(2026, 9, 1)

# La descripcion empieza por la frase de activacion para que el conversor no
# tenga nada que adaptar: el estado de partida es `compatible` a secas.
SKILL_MD = ("---\nname: mini\ndescription: Cárgala cuando el usuario pida un "
            "resumen breve de un texto.\n---\n# Mini\n\nResume el texto.\n")


def montar_repo(tmp: Path, auxiliares: int) -> Path:
    """Una skill de texto con `auxiliares` ficheros ademas del SKILL.md."""
    carpeta = tmp / "repo" / "skills" / "mini"
    (carpeta / "notas").mkdir(parents=True)
    (carpeta / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    for i in range(auxiliares):
        (carpeta / "notas" / "n{}.txt".format(i)).write_text("nota\n", encoding="utf-8")
    return tmp / "repo"


def lanzar(*args):
    return subprocess.run(
        [sys.executable, str(CONVERT)] + [str(a) for a in args],
        capture_output=True, text=True, cwd=str(RAIZ),
        env=dict(os.environ, CSE_FECHA=FECHA))


def estados(resumen: dict, destino: str) -> dict:
    """{modo: estado} de un destino para la unica skill del resumen."""
    return {ev["modo_instalacion"]: ev["estado"]
            for ev in resumen["skills"][0]["compatibilidad"][destino]}


class ExportConUnZipQueIncumpleElPerfil(unittest.TestCase):

    def exportar(self, auxiliares, *args):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(tmp), True)
        repo = montar_repo(tmp, auxiliares)
        salida = tmp / "out"
        r = lanzar("export", repo, "--out", salida, *args)
        resumen = json.loads((salida / "resumen.json").read_text(encoding="utf-8"))
        return r, salida, resumen

    def test_501_entradas_devuelven_2_con_umbral_estricto(self):
        r, salida, resumen = self.exportar(
            500, "--target", "chatgpt", "--fail-on", "no_compatible")
        with zipfile.ZipFile(salida / "mini.zip") as z:
            self.assertEqual(len(z.namelist()), 501)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_solo_cambia_la_celda_del_zip_de_chatgpt(self):
        _, _, resumen = self.exportar(500, "--target", "chatgpt")
        chatgpt = estados(resumen, "chatgpt")
        self.assertEqual(chatgpt["zip"], Estado.NO_COMPATIBLE)
        # Instalar por URL no usa el zip: su limite no le afecta.
        self.assertEqual(chatgpt["url_repositorio"], Estado.COMPATIBLE)
        # Y un limite que solo declara ChatGPT no degrada a nadie mas.
        for destino in ("perplexity-computer", "claude-ai", "mistral-vibe-work",
                        "claude-code"):
            for estado in estados(resumen, destino).values():
                self.assertEqual(estado, Estado.COMPATIBLE, destino)

    def test_el_motivo_dice_perfil_y_no_rechazo_de_la_plataforma(self):
        _, salida, resumen = self.exportar(500, "--target", "chatgpt")
        del_zip = [ev for ev in resumen["skills"][0]["compatibilidad"]["chatgpt"]
                   if ev["modo_instalacion"] == "zip"][0]
        motivo = " ".join(del_zip["motivos"])
        self.assertIn("501", motivo)
        self.assertIn("500", motivo)
        self.assertIn("perfil", motivo)
        informe = (salida / "INFORME-PORTABILIDAD.md").read_text(encoding="utf-8")
        self.assertIn("501", informe)

    def test_el_paquete_se_sigue_escribiendo(self):
        # Portabilidad no es el gate: incumplir el perfil avisa y cambia el
        # estado, pero no veta la publicacion. El codigo 3 sigue reservado a
        # seguridad.
        r, salida, _ = self.exportar(500, "--target", "chatgpt")
        self.assertTrue((salida / "mini.zip").is_file())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_500_entradas_cumplen(self):
        r, salida, resumen = self.exportar(
            499, "--target", "chatgpt", "--fail-on", "no_compatible")
        with zipfile.ZipFile(salida / "mini.zip") as z:
            self.assertEqual(len(z.namelist()), 500)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(estados(resumen, "chatgpt")["zip"], Estado.COMPATIBLE)
        self.assertNotIn("limite-de-paquete", json.dumps(resumen))

    def test_el_limite_se_evalua_aunque_el_zip_no_se_publique(self):
        # `export --target` solo restringe artefactos: la auditoria cubre los
        # cinco destinos, y la celda del zip de ChatGPT habla de ese zip se
        # escriba o no.
        _, salida, resumen = self.exportar(500, "--target", "mistral-vibe-work")
        self.assertFalse((salida / "mini.zip").exists())
        self.assertEqual(estados(resumen, "chatgpt")["zip"], Estado.NO_COMPATIBLE)


class AuditVeLoMismoQueExport(unittest.TestCase):

    def auditar(self, auxiliares, *args):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(tmp), True)
        return lanzar("audit", montar_repo(tmp, auxiliares), *args)

    def test_501_entradas_devuelven_2_con_umbral_estricto(self):
        r = self.auditar(500, "--target", "chatgpt", "--fail-on", "no_compatible")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("501", r.stdout)

    def test_500_entradas_devuelven_0(self):
        r = self.auditar(499, "--target", "chatgpt", "--fail-on", "no_compatible")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_audit_sigue_sin_escribir_nada(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(tmp), True)
        repo = montar_repo(tmp, 500)
        antes = sorted(p.relative_to(tmp).as_posix() for p in tmp.rglob("*"))
        lanzar("audit", repo, "--target", "chatgpt")
        despues = sorted(p.relative_to(tmp).as_posix() for p in tmp.rglob("*"))
        self.assertEqual(antes, despues)


def perfil_con_limites(**limites) -> Perfil:
    """ChatGPT con umbrales pequenos, para no fabricar ficheros de megas."""
    datos = copy.deepcopy(cargar_perfiles()["chatgpt"].datos)
    datos["limites_paquete"] = {"zip_max_bytes": None, "ficheros_max": None,
                                "fichero_max_bytes": None}
    datos["limites_paquete"].update(limites)
    return Perfil(datos)


def zip_con(tmp: Path, ficheros: dict) -> Path:
    z = Path(tmp) / "p.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:
        for nombre, datos in ficheros.items():
            zf.writestr(nombre, datos)
    return z


class LosTresLimitesEnSuFrontera(unittest.TestCase):
    """Justo por debajo, igual y por encima: el limite es inclusivo."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_tamano_por_fichero(self):
        perfil = perfil_con_limites(fichero_max_bytes=100)
        for tam, esperado in ((99, 0), (100, 0), (101, 1)):
            z = zip_con(self.tmp, {"a.txt": b"x" * tam})
            self.assertEqual(len(comprobar_limites(z, perfil)), esperado, tam)

    def test_tamano_del_zip(self):
        z = zip_con(self.tmp, {"a.txt": b"x" * 1000})
        tam = z.stat().st_size
        for limite, esperado in ((tam + 1, 0), (tam, 0), (tam - 1, 1)):
            perfil = perfil_con_limites(zip_max_bytes=limite)
            self.assertEqual(len(comprobar_limites(z, perfil)), esperado, limite)

    def test_numero_de_ficheros(self):
        perfil = perfil_con_limites(ficheros_max=3)
        for n, esperado in ((2, 0), (3, 0), (4, 1)):
            z = zip_con(self.tmp, {"f{}.txt".format(i): b"x" for i in range(n)})
            self.assertEqual(len(comprobar_limites(z, perfil)), esperado, n)


class AnotarLimites(unittest.TestCase):

    def evaluaciones(self, perfil, hoy=HOY):
        s = SkillPortatil(nombre="x", nombre_original="x", carpeta="x",
                          descripcion="Cárgala cuando el usuario lo pida.",
                          tiene_activacion=True)
        return evaluar(s, perfil, hoy)

    def test_sin_avisos_no_toca_nada(self):
        evs = self.evaluaciones(cargar_perfiles()["chatgpt"])
        anotar_limites(evs, [])
        self.assertEqual({e.estado for e in evs}, {Estado.COMPATIBLE})
        self.assertEqual([e.motivos for e in evs], [[], []])

    def test_un_aviso_marca_solo_el_modo_zip(self):
        evs = self.evaluaciones(cargar_perfiles()["chatgpt"])
        anotar_limites(evs, ["El zip lleva 501 ficheros y ChatGPT admite 500."])
        por_modo = {e.modo_instalacion: e for e in evs}
        self.assertEqual(por_modo["zip"].estado, Estado.NO_COMPATIBLE)
        self.assertEqual(len(por_modo["zip"].motivos), 1)
        self.assertEqual(por_modo["url_repositorio"].estado, Estado.COMPATIBLE)
        self.assertEqual(por_modo["url_repositorio"].motivos, [])

    def test_un_incumplimiento_conocido_gana_a_la_evidencia_caducada(self):
        # Con el perfil caducado todo sale `no_verificable`. Un limite
        # incumplido es un impedimento conocido: no puede quedar tapado por
        # la incertidumbre.
        evs = self.evaluaciones(cargar_perfiles()["chatgpt"],
                                hoy=datetime.date(2030, 1, 1))
        self.assertEqual({e.estado for e in evs}, {Estado.NO_VERIFICABLE})
        anotar_limites(evs, ["El zip lleva 501 ficheros y ChatGPT admite 500."])
        por_modo = {e.modo_instalacion: e for e in evs}
        self.assertEqual(por_modo["zip"].estado, Estado.NO_COMPATIBLE)
        self.assertEqual(por_modo["url_repositorio"].estado, Estado.NO_VERIFICABLE)
        # El motivo de la caducidad no se pierde.
        self.assertEqual(len(por_modo["zip"].motivos), 2)


if __name__ == "__main__":
    unittest.main()
