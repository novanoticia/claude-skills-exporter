import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ayuda import RAIZ, RAIZ_SCRIPTS

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = Path(__file__).resolve().parent / "golden-seguridad"
CONVERT = RAIZ_SCRIPTS / "convert.py"

FIXTURES_SEG = ["repo-descarga-remota", "repo-postinstall", "repo-secreto",
                "repo-ofuscado", "repo-inyeccion-prompt", "repo-binario",
                "repo-red-legitima", "repo-skill-maliciosa", "repo-escalada"]


def auditar(fixture, destino):
    return subprocess.run(
        [sys.executable, str(CONVERT), "export", str(FIXTURES / fixture),
         "--out", str(destino), "--anular-revision-seguridad"],
        capture_output=True, text=True, cwd=str(RAIZ),
        env=dict(os.environ, CSE_FECHA="2026-08-08"))


def seguridad_de(caso, destino):
    auditar(caso, destino)
    return json.loads((destino / "resumen.json").read_text(encoding="utf-8"))["seguridad"]


class Golden(unittest.TestCase):

    def test_cada_fixture_produce_su_veredicto_esperado(self):
        for f in FIXTURES_SEG:
            with self.subTest(fixture=f):
                tmp = tempfile.mkdtemp()
                self.addCleanup(shutil.rmtree, tmp)
                r = auditar(f, Path(tmp))
                resumen = Path(tmp) / "resumen.json"
                # Ejecucion y comprobacion separadas: `auditar` devuelve un
                # CompletedProcess, que es truthy siempre —incluso si el
                # conversor ha reventado—, asi que meterlo en la condicion
                # escondia el stderr y dejaba un assertIsNotNone sin
                # diagnostico.
                self.assertTrue(resumen.exists(), r.stderr)
                obtenido = json.loads(resumen.read_text(encoding="utf-8"))
                esperado = json.loads((GOLDEN / (f + ".json")).read_text(encoding="utf-8"))
                self.assertEqual(obtenido["seguridad"], esperado["seguridad"],
                                 "El veredicto de {} ha cambiado. Si es deseado: "
                                 "python3 tests/generar_golden.py".format(f))


class CasosConcretos(unittest.TestCase):

    def seg(self, caso):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        return seguridad_de(caso, Path(tmp))

    def test_descarga_remota_es_alto_y_no_bloquea(self):
        s = self.seg("repo-descarga-remota")
        self.assertEqual(s["nivel_riesgo"], "alto")
        self.assertEqual([h["ambito"] for h in s["hallazgos"]
                          if h["id"] == "SEC-EXEC-REMOTO-001"], ["paquete"])

    def test_la_red_documentada_no_escala(self):
        # La guarda contra el exceso de celo: un plugin no es inseguro por
        # usar la red.
        self.assertIn(self.seg("repo-red-legitima")["nivel_riesgo"], ("bajo", "moderado"))

    def test_la_escalada_por_combinacion_dispara(self):
        s = self.seg("repo-escalada")
        self.assertEqual(s["nivel_riesgo"], "critico")
        self.assertTrue(s["escalada_por_combinacion"])

    def test_la_inyeccion_esta_en_ambito_exportado(self):
        s = self.seg("repo-inyeccion-prompt")
        prompt = [h for h in s["hallazgos"] if h["familia"] == "conducta_de_prompt"]
        self.assertTrue(prompt)
        self.assertEqual({h["ambito"] for h in prompt}, {"exportado"})


class FixturesInertes(unittest.TestCase):
    """GitHub pasa un escaner de secretos sobre los repositorios publicos."""

    DOMINIO = re.compile(r"https?://([^/\s\"']+)")
    CLAVE_REAL = re.compile(
        r"(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{32,}|"
        r"-----BEGIN (RSA |OPENSSH )?PRIVATE KEY-----)")

    def test_todos_los_dominios_son_invalid(self):
        for f in FIXTURES_SEG:
            for p in (FIXTURES / f).rglob("*"):
                if not p.is_file() or p.suffix in (".bin",):
                    continue
                texto = p.read_text(encoding="utf-8", errors="replace")
                for dominio in self.DOMINIO.findall(texto):
                    self.assertTrue(dominio.endswith(".invalid"),
                                    "{}: dominio resoluble {}".format(p, dominio))

    def test_ninguna_clave_parece_real(self):
        for f in FIXTURES_SEG:
            for p in (FIXTURES / f).rglob("*"):
                if p.is_file():
                    texto = p.read_text(encoding="utf-8", errors="replace")
                    self.assertIsNone(self.CLAVE_REAL.search(texto), str(p))


class EsteRepositorio(unittest.TestCase):
    """No puede delatar la skill que publica; sí su propio banco de pruebas."""

    # Excepciones documentadas, una a una. Todo lo que no este aqui y proceda
    # de skills/plugin-to-agentskills/ es un falso positivo.
    EXCEPCIONES = (
        # El catalogo de patrones. patrones.analizar ya lo salta (tarea 3),
        # asi que esta entrada es cinturon y tirantes.
        "/seguridad/reglas.json",
        # SEC-EXEC-DINAMICO-001 casa con `subprocess.run(` en convert.py,
        # que es el `git clone` de resolve_source: el UNICO proceso externo
        # del programa, expresamente permitido por el paso de CI "El analisis
        # sigue siendo estatico" (PERMITIDO = {("subprocess", "run")}) y
        # auditado alli por AST, que es una comprobacion mas fuerte que esta
        # regex. Bajarla de confianza o afinar el patron perderia deteccion
        # real en paquetes ajenos a cambio de nada.
        "scripts/convert.py",
    )

    def test_ningun_hallazgo_procede_de_la_skill_publicada(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        subprocess.run(
            [sys.executable, str(CONVERT), "export", str(RAIZ), "--out", tmp,
             "--anular-revision-seguridad"],
            capture_output=True, text=True, cwd=str(RAIZ),
            env=dict(os.environ, CSE_FECHA="2026-08-08"))
        s = json.loads((Path(tmp) / "resumen.json").read_text(encoding="utf-8"))["seguridad"]
        intrusos = ["{} :: {}".format(h["id"], h["ubicacion"]) for h in s["hallazgos"]
                    if h["ubicacion"].startswith("skills/plugin-to-agentskills/")
                    and not any(e in h["ubicacion"] for e in self.EXCEPCIONES)]
        self.assertEqual(intrusos, [],
                         "El motor delata la skill que se publica:\n  "
                         + "\n  ".join(intrusos))


if __name__ == "__main__":
    unittest.main()
