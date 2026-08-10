"""El presupuesto y el rotulo salen de los modos reales de cada perfil.

Solo se calculaban dos presupuestos, uno para el modo `carpeta` y otro para
`zip`, asi que cualquier modo nuevo caia en el cajon de `carpeta` sin
decirlo. `--target claude-code` -que instala en modo `directorio_local`, con
un tope propio de 1024 B- recibia el presupuesto de Mistral, 490, y se
anunciaba como «Mistral» en los mensajes finales.

Era el punto donde el codigo contradecia su propio comentario, que promete
que todo se deriva de los perfiles de exporter/targets/.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ayuda import RAIZ, RAIZ_SCRIPTS, importar_exporter

importar_exporter()

import convert  # noqa: E402
from exporter.perfiles import cargar_perfiles  # noqa: E402

CONVERT = RAIZ_SCRIPTS / "convert.py"

# 612 bytes: cabe de sobra en el tope de Claude Code (1024) y no en el de
# Mistral (490). Es lo que hace visible el presupuesto equivocado.
DESCRIPCION = (
    "Cárgala cuando el usuario pida convertir una fecha entre formatos, diga "
    "«pásame esta fecha a ISO», «qué día de la semana fue», o necesite calcular "
    "diferencias entre fechas, sumar días hábiles, interpretar sellos de tiempo "
    "Unix, o normalizar fechas escritas en lenguaje natural en español o inglés "
    "dentro de documentos, hojas de cálculo y registros de sistemas heredados, "
    "incluyendo formatos regionales ambiguos como los de día y mes intercambiados, "
    "husos horarios con y sin desplazamiento explícito, y años de dos cifras que "
    "hay que resolver contra un siglo de referencia acordado con el usuario.")


class ElRepartoPorArtefacto(unittest.TestCase):
    """La pieza que decide, comprobada sin pasar por el CLI."""

    def setUp(self):
        self.perfiles = cargar_perfiles()

    def test_claude_code_no_es_un_destino_de_zip(self):
        ids_zip, ids_carpeta = convert.perfiles_por_artefacto(
            self.perfiles, ["claude-code"])
        self.assertEqual(ids_zip, [])
        self.assertEqual(ids_carpeta, ["claude-code"])

    def test_directorio_local_trae_su_propio_presupuesto(self):
        _zip, carpeta = convert.perfiles_por_artefacto(self.perfiles, ["claude-code"])
        self.assertEqual(convert.presupuesto_de(self.perfiles, carpeta), 1024)

    def test_y_mistral_el_suyo(self):
        _zip, carpeta = convert.perfiles_por_artefacto(
            self.perfiles, ["mistral-vibe-work"])
        self.assertEqual(convert.presupuesto_de(self.perfiles, carpeta), 490)

    def test_con_los_dos_manda_el_mas_estrecho(self):
        """Una sola carpeta tiene que valer para los dos destinos."""
        _zip, carpeta = convert.perfiles_por_artefacto(
            self.perfiles, ["claude-code", "mistral-vibe-work"])
        self.assertEqual(sorted(carpeta), ["claude-code", "mistral-vibe-work"])
        self.assertEqual(convert.presupuesto_de(self.perfiles, carpeta), 490)

    def test_sin_target_se_reparten_los_cinco(self):
        ids_zip, ids_carpeta = convert.perfiles_por_artefacto(self.perfiles, None)
        self.assertEqual(ids_zip, ["chatgpt", "claude-ai", "perplexity-computer"])
        self.assertEqual(ids_carpeta, ["claude-code", "mistral-vibe-work"])

    def test_url_repositorio_no_pide_ningun_artefacto_propio(self):
        """chatgpt declara url_repositorio Y zip: entra por el zip, no por la
        carpeta."""
        _zip, carpeta = convert.perfiles_por_artefacto(self.perfiles, ["chatgpt"])
        self.assertEqual(carpeta, [])


class ElArtefactoQueSeEscribe(unittest.TestCase):

    def exportar(self, *args):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(tmp), True)
        (tmp / "repo" / "skills" / "larga").mkdir(parents=True)
        (tmp / "repo" / "skills" / "larga" / "SKILL.md").write_text(
            "---\nname: larga\ndescription: %s\n---\n# F\nPaso 1.\n" % DESCRIPCION,
            encoding="utf-8")
        salida = tmp / "out"
        r = subprocess.run(
            [sys.executable, str(CONVERT), "export", str(tmp / "repo"),
             "--out", str(salida)] + list(args),
            capture_output=True, text=True, cwd=str(RAIZ),
            env=dict(os.environ, CSE_FECHA="2026-08-08"))
        return r, salida

    def bytes_de_la_carpeta(self, salida):
        texto = (salida / "larga" / "SKILL.md").read_text(encoding="utf-8")
        d = re.search(r"^description: (.*)$", texto, re.M).group(1)
        return len(d.encode("utf-8"))

    def test_claude_code_recibe_su_descripcion_entera(self):
        """612 bytes caben en 1024. Antes se recortaban a 486."""
        r, salida = self.exportar("--target", "claude-code")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.bytes_de_la_carpeta(salida), len(DESCRIPCION.encode()))

    def test_mistral_sigue_recibiendo_la_suya_recortada(self):
        _r, salida = self.exportar("--target", "mistral-vibe-work")
        self.assertLessEqual(self.bytes_de_la_carpeta(salida), 490)

    def test_con_los_dos_se_escribe_la_que_vale_para_ambos(self):
        _r, salida = self.exportar("--target", "claude-code", "mistral-vibe-work")
        self.assertLessEqual(self.bytes_de_la_carpeta(salida), 490)


class ElRotuloFinal(ElArtefactoQueSeEscribe):

    def test_claude_code_ya_no_se_anuncia_como_mistral(self):
        r, _salida = self.exportar("--target", "claude-code")
        self.assertIn("Claude Code", r.stdout)
        self.assertNotIn("Mistral", r.stdout)

    def test_cada_artefacto_nombra_a_quien_lo_usa(self):
        r, _salida = self.exportar()
        self.assertIn("Claude Code, Mistral Vibe Work", r.stdout)
        self.assertIn("ChatGPT, claude.ai, Perplexity Computer", r.stdout)

    def test_un_destino_solo_de_zip_no_anuncia_carpeta(self):
        r, _salida = self.exportar("--target", "perplexity-computer")
        self.assertIn("<skill>.zip", r.stdout)
        self.assertNotIn("<skill>/", r.stdout)


if __name__ == "__main__":
    unittest.main()
