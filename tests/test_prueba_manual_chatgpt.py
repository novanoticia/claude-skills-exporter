"""La prueba manual de ChatGPT web queda registrada en el perfil.

El 2026-11-17 se subio a ChatGPT web (cuenta Plus) el zip que genera el
conversor, por Habilidades -> Anadir -> Subir desde tu ordenador. Se acepto,
se invoco y respondio. Esta prueba fija tres consecuencias en el perfil:

  - el modo zip pasa a `probada: true`, con la fuente en un registro
    versionado (docs/pruebas-manuales.md), y deja de salir no_verificable;
  - la URL de repositorio sigue sin probar: es otro contrato;
  - el tope de zip pasa de los 50 MiB de la API a los 780 MiB que anuncia la
    interfaz. Los otros dos limites siguen siendo los de la API.

El esquema admite ahora `probada: true` sin `motivo`: los dos motivos del
vocabulario dicen "sin probar", y obligar a poner uno contradecia el dato.
"""

import datetime
import json
import unittest
from pathlib import Path

from ayuda import RAIZ, importar_exporter

importar_exporter()

from exporter.compatibilidad import evaluar  # noqa: E402
from exporter.modelo import Estado, SkillPortatil, capacidades_de  # noqa: E402
from exporter.perfiles import cargar_perfiles  # noqa: E402

try:
    import jsonschema
except ImportError:      # el CI de pruebas no lo instala; validar_perfiles si
    jsonschema = None

TARGETS = RAIZ / "skills" / "plugin-to-agentskills" / "scripts" / "exporter" / "targets"
REGISTRO = RAIZ / "docs" / "pruebas-manuales.md"
HOY = datetime.date(2026, 9, 1)
MIB = 1024 * 1024


def skill():
    s = SkillPortatil(nombre="x", nombre_original="x", carpeta="x",
                      descripcion="Cárgala cuando el usuario lo pida.",
                      tiene_activacion=True)
    s.capacidades = capacidades_de(s.senales, s.tiene_scripts)
    return s


class ElPerfilRegistraLaPrueba(unittest.TestCase):

    def setUp(self):
        self.perfil = cargar_perfiles()["chatgpt"]
        self.por_modo = self.perfil.datos["instalacion"]["evidencia_por_modo"]

    def test_el_zip_esta_probado_y_sin_motivo(self):
        self.assertIs(self.por_modo["zip"]["probada"], True)
        self.assertNotIn("motivo", self.por_modo["zip"])
        self.assertIsNone(self.perfil.instalacion_sin_probar("zip"))

    def test_la_url_de_repositorio_sigue_sin_probar(self):
        self.assertIs(self.por_modo["url_repositorio"]["probada"], False)
        self.assertIsNotNone(self.perfil.instalacion_sin_probar("url_repositorio"))

    def test_la_fuente_es_el_registro_versionado(self):
        self.assertTrue(self.por_modo["zip"]["fuente"].endswith("/docs/pruebas-manuales.md"))
        self.assertTrue(REGISTRO.is_file())

    def test_el_registro_cuenta_que_se_probo_y_que_no(self):
        texto = REGISTRO.read_text(encoding="utf-8")
        for dato in ("2026-11-17", "Subir desde tu ordenador", "179 / 500",
                     "780 MiB", "activación automática"):
            self.assertIn(dato, texto, dato)

    def test_el_registro_figura_entre_las_fuentes(self):
        urls = [f["url"] for f in self.perfil.datos["evidencia"]["fuentes"]]
        self.assertIn(self.por_modo["zip"]["fuente"], urls)

    def test_el_tope_del_zip_es_el_de_la_interfaz(self):
        self.assertEqual(self.perfil.limite("zip_max_bytes"), 780 * MIB)

    def test_los_otros_limites_siguen_siendo_los_de_la_api(self):
        self.assertEqual(self.perfil.limite("ficheros_max"), 500)
        self.assertEqual(self.perfil.limite("fichero_max_bytes"), 25 * MIB)


class LaEvaluacionCambiaSoloEnElZip(unittest.TestCase):

    def test_el_zip_sale_compatible_y_la_url_no_verificable(self):
        evs = {e.modo_instalacion: e
               for e in evaluar(skill(), cargar_perfiles()["chatgpt"], HOY)}
        self.assertEqual(evs["zip"].estado, Estado.COMPATIBLE)
        self.assertEqual(evs["zip"].motivos, [])
        self.assertEqual(evs["url_repositorio"].estado, Estado.NO_VERIFICABLE)


@unittest.skipIf(jsonschema is None, "jsonschema no esta instalado")
class ElEsquemaExigeMotivoSoloSinProbar(unittest.TestCase):

    def setUp(self):
        self.esquema = json.loads((TARGETS / "_schema.json").read_text(encoding="utf-8"))
        self.datos = json.loads((TARGETS / "chatgpt.json").read_text(encoding="utf-8"))

    def valida(self, entrada):
        self.datos["instalacion"]["evidencia_por_modo"]["zip"] = entrada
        try:
            jsonschema.validate(self.datos, self.esquema)
            return True
        except jsonschema.ValidationError:
            return False

    def test_probada_sin_motivo_es_valida(self):
        self.assertTrue(self.valida({"probada": True, "fuente": "https://a.invalid/x"}))

    def test_sin_probar_exige_motivo(self):
        self.assertFalse(self.valida({"probada": False, "fuente": "https://a.invalid/x"}))

    def test_probada_con_motivo_se_rechaza_por_contradictoria(self):
        self.assertFalse(self.valida({"probada": True, "motivo": "paquete-sin-probar",
                                      "fuente": "https://a.invalid/x"}))


if __name__ == "__main__":
    unittest.main()
