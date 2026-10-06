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

CONVERT = RAIZ_SCRIPTS / "convert.py"
FIXTURES = RAIZ / "tests" / "fixtures"
GOLDEN = RAIZ / "tests" / "golden-i18n"
IDIOMAS = ("en", "fr")
# Dos fixtures de seguridad y dos de portabilidad (uno con senales y motivos,
# otro con adaptaciones y hallazgos de descripcion): los golden de es ya
# cubren todos; aqui se comprueba que el idioma no altera nada mas que el texto.
CASOS = ["repo-descarga-remota", "repo-escalada",
         "skill-con-mcp", "skill-description-larga"]
FECHA = "2026-08-08"

CAMPOS_DE_TEXTO = {"titulo", "mitigacion", "mensaje", "motivos", "adaptaciones"}


def exportar(fixture, idioma, destino):
    return subprocess.run(
        [sys.executable, str(CONVERT), "export", str(FIXTURES / fixture),
         "--out", str(destino), "--anular-revision-seguridad", "--lang", idioma],
        capture_output=True, text=True, cwd=str(RAIZ),
        env=dict(os.environ, CSE_FECHA=FECHA))


def resumen(fixture, idioma):
    tmp = tempfile.mkdtemp()
    try:
        r = exportar(fixture, idioma, Path(tmp))
        assert r.returncode == 0, r.stderr
        datos = json.loads((Path(tmp) / "resumen.json").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmp)
    datos["origen"] = "<origen>"
    return datos


def sin_texto(nodo):
    """Quita los campos de texto libre; deja claves y vocabularios cerrados."""
    if isinstance(nodo, dict):
        return {k: sin_texto(v) for k, v in nodo.items() if k not in CAMPOS_DE_TEXTO}
    if isinstance(nodo, list):
        return [sin_texto(x) for x in nodo]
    return nodo


class Golden(unittest.TestCase):

    def test_cada_idioma_produce_su_resumen_esperado(self):
        for idioma in IDIOMAS:
            for caso in CASOS:
                with self.subTest(idioma=idioma, caso=caso):
                    esperado = json.loads(
                        (GOLDEN / idioma / (caso + ".json")).read_text(encoding="utf-8"))
                    self.assertEqual(resumen(caso, idioma), esperado,
                                     "Si es deseado: python3 tests/generar_golden.py")


class ResumenEstable(unittest.TestCase):
    """Review Focus 5: resumen.json solo cambia de idioma en sus textos."""

    def test_misma_forma_y_mismos_vocabularios_en_todos_los_idiomas(self):
        for caso in CASOS:
            base = sin_texto(resumen(caso, "es"))
            for idioma in IDIOMAS:
                with self.subTest(idioma=idioma, caso=caso):
                    self.assertEqual(sin_texto(resumen(caso, idioma)), base)


class Redaccion(unittest.TestCase):
    """Restriccion 7: nunca «este repositorio es malicioso», en ningun idioma."""

    PROHIBIDAS = {
        "es": r"(?:este|el) repositorio es malicios",
        "en": r"(?:this|the) (?:repository|repo) is malicious",
        "fr": r"(?:ce|le) d[ée]p[ôo]t est malveillant",
    }

    def test_ninguna_plantilla_lo_afirma(self):
        for codigo, patron in self.PROHIBIDAS.items():
            ruta = RAIZ_SCRIPTS / "exporter" / "i18n" / (codigo + ".json")
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            for clave, texto in datos.items():
                if clave == "_meta":
                    continue
                with self.subTest(idioma=codigo, clave=clave):
                    self.assertIsNone(re.search(patron, texto, re.I), texto)


if __name__ == "__main__":
    unittest.main()
