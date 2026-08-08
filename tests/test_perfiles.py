import datetime
import json
import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.modelo import CONFIANZAS, NIVELES_CAPACIDAD, SEVERIDADES  # noqa: E402
from exporter.perfiles import PerfilInvalido, cargar_perfiles  # noqa: E402

ESPERADOS = {"chatgpt", "claude-ai", "claude-code",
             "mistral-vibe-work", "perplexity-computer"}


class CargaDePerfiles(unittest.TestCase):

    def setUp(self):
        self.perfiles = cargar_perfiles()

    def test_estan_los_cinco_destinos(self):
        self.assertEqual(set(self.perfiles), ESPERADOS)

    def test_el_id_coincide_con_el_nombre_del_fichero(self):
        for pid, perfil in self.perfiles.items():
            self.assertEqual(pid, perfil.id)

    def test_los_niveles_de_capacidad_son_del_vocabulario(self):
        for perfil in self.perfiles.values():
            for nombre, nivel in perfil.datos["capacidades"].items():
                self.assertIn(nivel, NIVELES_CAPACIDAD,
                              "{}: capacidad {}".format(perfil.id, nombre))

    def test_la_confianza_es_del_vocabulario(self):
        for perfil in self.perfiles.values():
            self.assertIn(perfil.datos["evidencia"]["confianza"], CONFIANZAS)

    def test_las_severidades_de_peligro_son_del_vocabulario(self):
        for perfil in self.perfiles.values():
            for p in perfil.datos["peligros"]:
                self.assertIn(p["severidad"], SEVERIDADES)

    def test_toda_evidencia_lleva_fecha_iso(self):
        for perfil in self.perfiles.values():
            datetime.date.fromisoformat(perfil.datos["evidencia"]["verificado_el"])
            datetime.date.fromisoformat(perfil.datos["evidencia"]["revisar_tras"])


class ConsultasDelPerfil(unittest.TestCase):

    def setUp(self):
        self.perfiles = cargar_perfiles()

    def test_mistral_no_ejecuta_scripts(self):
        self.assertEqual(self.perfiles["mistral-vibe-work"].capacidad("scripts.ejecutar"), "no")

    def test_perplexity_si_ejecuta_scripts(self):
        self.assertEqual(self.perfiles["perplexity-computer"].capacidad("scripts.ejecutar"), "si")

    def test_una_capacidad_no_declarada_es_desconocida(self):
        self.assertEqual(self.perfiles["chatgpt"].capacidad("capacidad.inventada"), "desconocido")

    def test_los_presupuestos_son_los_comprobados(self):
        self.assertEqual(self.perfiles["mistral-vibe-work"].presupuesto(), 490)
        self.assertEqual(self.perfiles["perplexity-computer"].presupuesto(), 850)

    def test_mistral_declara_el_peligro_del_estado(self):
        peligros = self.perfiles["mistral-vibe-work"].peligros_para("estado-persistente")
        self.assertEqual(len(peligros), 1)
        self.assertEqual(peligros[0]["severidad"], "alta")

    def test_caducidad_por_fecha(self):
        perfil = self.perfiles["mistral-vibe-work"]
        self.assertFalse(perfil.caducado(datetime.date(2026, 8, 1)))
        self.assertTrue(perfil.caducado(datetime.date(2030, 1, 1)))


class PerfilesInvalidos(unittest.TestCase):

    def test_un_json_roto_aborta_indicando_el_fichero(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            malo = Path(tmp) / "roto.json"
            malo.write_text("{ esto no es json", encoding="utf-8")
            with self.assertRaises(PerfilInvalido) as ctx:
                cargar_perfiles(Path(tmp))
            self.assertIn("roto.json", str(ctx.exception))

    def test_falta_una_clave_obligatoria(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            malo = Path(tmp) / "incompleto.json"
            malo.write_text(json.dumps({"id": "incompleto"}), encoding="utf-8")
            with self.assertRaises(PerfilInvalido):
                cargar_perfiles(Path(tmp))


if __name__ == "__main__":
    unittest.main()
