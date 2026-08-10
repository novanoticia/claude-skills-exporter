"""El guardian que promete que el conversor no ejecuta nada.

Estas pruebas existen porque el guardian vivia incrustado en el YAML del
workflow. Nadie podia ejecutarlo sin extraerlo a mano, y asi paso mucho
tiempo comprobando bastante menos de lo que su nombre prometia: solo miraba
las llamadas por atributo, de modo que un `from os import system` seguido de
`system(...)` lo atravesaba y el paso salia en verde.

Un guardian sin pruebas es exactamente el defecto que vigila: algo que
afirma una garantia que no esta dando.
"""

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

from ayuda import RAIZ

SUBARBOL = "skills/plugin-to-agentskills/scripts"


def _cargar():
    """`.github` no es un paquete importable: se carga por ruta."""
    ruta = RAIZ / ".github" / "validar_estatico.py"
    spec = importlib.util.spec_from_file_location("validar_estatico", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


estatico = _cargar()


class Base(unittest.TestCase):

    def arbol(self, codigo, nombre="modulo.py"):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(tmp), True)
        d = tmp / SUBARBOL
        d.mkdir(parents=True)
        (d / nombre).write_text(codigo, encoding="utf-8")
        return tmp

    def ids(self, codigo):
        return estatico.infracciones(self.arbol(codigo))


class LasTresFormasDeLlegarAEjecutar(Base):

    def test_por_atributo(self):
        """La unica que se comprobaba antes."""
        self.assertEqual(len(self.ids("import os\nos.system('x')\n")), 1)

    def test_por_nombre_simple(self):
        """`from os import system; system(...)`: atravesaba el guardian."""
        self.assertTrue(self.ids("from os import system\nsystem('x')\n"))

    def test_un_builtin_sin_modulo_delante(self):
        """`exec(...)` no tiene modulo, asi que no era un ast.Attribute."""
        self.assertTrue(self.ids("exec('codigo')\n"))
        self.assertTrue(self.ids("eval('1+1')\n"))

    def test_el_import_con_alias(self):
        """La llamada ya no se llama como ningun nombre de la lista.

        Es el caso que solo caza mirando el import, y la razon de que
        comprobar los imports no sea redundante con lo demas.
        """
        codigo = "from os import system as arrancar\narrancar('x')\n"
        malos = self.ids(codigo)
        self.assertTrue(malos)
        self.assertIn("from os import system", malos[0])

    def test_a_granel(self):
        self.assertTrue(self.ids("from subprocess import *\n"))
        self.assertTrue(self.ids("from os import *\n"))


class LoQueDebeSeguirPasando(Base):

    def test_subprocess_run_es_el_git_clone_y_esta_permitido(self):
        self.assertEqual(
            self.ids("import subprocess\nsubprocess.run(['git', 'clone'])\n"), [])

    def test_re_compile_no_es_un_proceso(self):
        """El falso positivo evidente al ampliar la lista de nombres."""
        self.assertEqual(self.ids("import re\nre.compile('x')\n"), [])

    def test_subprocess_popen_sigue_prohibido(self):
        self.assertTrue(self.ids("import subprocess\nsubprocess.Popen(['x'])\n"))

    def test_from_pathlib_import_path_es_inofensivo(self):
        self.assertEqual(self.ids("from pathlib import Path\nPath('.')\n"), [])


class ElRepositorioDeVerdad(unittest.TestCase):

    def test_no_tiene_ninguna_infraccion(self):
        """Si esto falla, alguien ha metido un proceso externo nuevo."""
        self.assertEqual(estatico.infracciones(RAIZ), [])

    def test_y_el_validador_sale_con_cero(self):
        self.assertEqual(estatico.main(RAIZ), 0)


class ElWorkflowLoInvoca(unittest.TestCase):
    """Que el fichero exista no sirve de nada si el CI no lo llama."""

    def test_el_paso_de_ci_ejecuta_este_validador(self):
        yml = (RAIZ / ".github" / "workflows" / "validar.yml").read_text(
            encoding="utf-8")
        self.assertIn("validar_estatico.py", yml)


if __name__ == "__main__":
    unittest.main()
