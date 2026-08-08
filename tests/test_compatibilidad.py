import datetime
import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.compatibilidad import evaluar  # noqa: E402
from exporter.modelo import Estado, Senal, SkillPortatil, capacidades_de  # noqa: E402
from exporter.perfiles import cargar_perfiles  # noqa: E402

HOY = datetime.date(2026, 8, 8)


def skill(senales=(), tiene_scripts=False, adaptaciones=()):
    s = SkillPortatil(nombre="x", nombre_original="x", carpeta="x",
                      descripcion="Cárgala cuando el usuario lo pida.",
                      tiene_activacion=True, tiene_scripts=tiene_scripts,
                      senales=list(senales), adaptaciones=list(adaptaciones))
    s.capacidades = capacidades_de(s.senales, s.tiene_scripts)
    return s


class MotorDeEstados(unittest.TestCase):

    def setUp(self):
        self.perfiles = cargar_perfiles()

    def test_skill_limpia_es_compatible_en_todas_partes(self):
        for perfil in self.perfiles.values():
            evs = evaluar(skill(), perfil, HOY)
            self.assertEqual(evs[0].estado, Estado.COMPATIBLE, perfil.id)

    def test_capacidad_requerida_ausente_es_no_compatible(self):
        # Mistral no tiene Python: una skill cuya logica vive en scripts/ queda inerte.
        evs = evaluar(skill(tiene_scripts=True), self.perfiles["mistral-vibe-work"], HOY)
        self.assertEqual(evs[0].estado, Estado.NO_COMPATIBLE)
        self.assertTrue(any("scripts.ejecutar" in m for m in evs[0].motivos))

    def test_la_misma_skill_es_compatible_donde_si_hay_python(self):
        evs = evaluar(skill(tiene_scripts=True), self.perfiles["perplexity-computer"], HOY)
        self.assertEqual(evs[0].estado, Estado.COMPATIBLE)

    def test_capacidad_desconocida_es_no_verificable(self):
        evs = evaluar(skill(tiene_scripts=True), self.perfiles["chatgpt"], HOY)
        self.assertEqual(evs[0].estado, Estado.NO_VERIFICABLE)

    def test_si_con_confirmacion_cuenta_como_disponible(self):
        senales = [Senal("applescript", "SKILL.md:9", "osascript", "media")]
        evs = evaluar(skill(senales), self.perfiles["claude-code"], HOY)
        self.assertEqual(evs[0].estado, Estado.COMPATIBLE)

    def test_capacidad_opcional_ausente_es_degradado(self):
        senales = [Senal("slash-plugin", "SKILL.md:4", "/mi-plugin:cmd", "media")]
        evs = evaluar(skill(senales), self.perfiles["mistral-vibe-work"], HOY)
        self.assertEqual(evs[0].estado, Estado.DEGRADADO)

    def test_las_adaptaciones_dan_compatible_con_adaptacion(self):
        evs = evaluar(skill(adaptaciones=["Descripción recortada."]),
                      self.perfiles["mistral-vibe-work"], HOY)
        self.assertEqual(evs[0].estado, Estado.COMPATIBLE_CON_ADAPTACION)


class PeligrosDeConducta(unittest.TestCase):

    def setUp(self):
        self.perfiles = cargar_perfiles()

    def test_peligro_alto_da_no_compatible_aunque_la_capacidad_exista(self):
        # El hibrido: Mistral SI escribe (filesystem.escribir = si), pero la
        # escritura no sobrevive. Capacidad presente, peligro alto.
        senales = [Senal("estado-persistente", "SKILL.md:40", ">> log.jsonl", "media")]
        perfil = self.perfiles["mistral-vibe-work"]
        self.assertEqual(perfil.capacidad("filesystem.escribir"), "si")
        evs = evaluar(skill(senales), perfil, HOY)
        self.assertEqual(evs[0].estado, Estado.NO_COMPATIBLE)
        self.assertEqual(evs[0].peligros[0]["id"], "mistral-estado-no-persiste")

    def test_el_mismo_patron_no_dispara_donde_el_perfil_no_lo_declara(self):
        senales = [Senal("estado-persistente", "SKILL.md:40", ">> log.jsonl", "media")]
        evs = evaluar(skill(senales), self.perfiles["claude-code"], HOY)
        self.assertEqual(evs[0].estado, Estado.COMPATIBLE)
        self.assertEqual(evs[0].peligros, [])

    def test_peligro_baja_registra_nota_pero_no_cambia_estado(self):
        # Un peligro con severidad 'baja' debe registrarse en peligros y motivos,
        # pero no debe degradar el estado porque COMPATIBLE es el mejor de todos.
        from exporter.perfiles import Perfil
        datos_perfil = {
            "id": "test-baja",
            "label": "Test Baja",
            "instalacion": {
                "modos": ["directorio"],
                "ruta_ui": "test",
                "una_skill_por_subida": False
            },
            "formato": {
                "acepta": ["agent-skills"],
                "frontmatter_cerrado": False,
                "presupuesto_description_bytes": 512,
                "tope_duro_description": {"valor": 1024, "unidad": "caracteres"},
                "conserva_arbol": True
            },
            "limites_paquete": {
                "zip_max_bytes": None,
                "ficheros_max": None,
                "fichero_max_bytes": None
            },
            "capacidades": {
                "mcp.cliente": "si"
            },
            "peligros": [
                {
                    "id": "peligro-bajo-test",
                    "dispara_con": ["mcp-tool"],
                    "severidad": "baja",
                    "titulo": "Peligro menor informativo",
                    "detalle": "Esto es solo una nota.",
                    "mitigacion": "Nada requerido.",
                    "evidencia": {"confianza": "observado", "verificado_el": "2026-08-01"}
                }
            ],
            "evidencia": {
                "verificado_el": "2026-08-01",
                "revisar_tras": "2099-12-31",
                "confianza": "observado",
                "fuentes": []
            }
        }
        perfil = Perfil(datos_perfil)
        senales = [Senal("mcp-tool", "SKILL.md:5", "client.beta.messages", "alta")]
        evs = evaluar(skill(senales), perfil, HOY)
        # El estado debe ser compatible porque baja no lo degrada
        self.assertEqual(evs[0].estado, Estado.COMPATIBLE)
        # Pero el peligro debe estar registrado
        self.assertEqual(len(evs[0].peligros), 1)
        self.assertEqual(evs[0].peligros[0]["id"], "peligro-bajo-test")
        # Y debe haber un motivo registrado
        self.assertTrue(len(evs[0].motivos) > 0)
        self.assertTrue(any("peligro-bajo-test" in m or "Peligro menor" in m for m in evs[0].motivos))

    def test_el_mismo_peligro_por_multiples_senales_se_registra_una_sola_vez(self):
        # Si dos senales del mismo id (o con distinto ubicacion pero mismo peligro)
        # disparan el mismo peligro, debe registrarse una sola vez gracias a 'vistos'.
        senales = [
            Senal("estado-persistente", "SKILL.md:40", ">> log.jsonl", "media"),
            Senal("estado-persistente", "SKILL.md:50", ">> registro.txt", "media")
        ]
        perfil = self.perfiles["mistral-vibe-work"]
        evs = evaluar(skill(senales), perfil, HOY)
        # Aunque hay dos senales con el mismo id, el peligro se registra una sola vez
        self.assertEqual(len(evs[0].peligros), 1)
        self.assertEqual(evs[0].peligros[0]["id"], "mistral-estado-no-persiste")


class Caducidad(unittest.TestCase):

    def setUp(self):
        self.perfiles = cargar_perfiles()

    def test_evidencia_vencida_degrada_a_no_verificable(self):
        evs = evaluar(skill(), self.perfiles["mistral-vibe-work"], datetime.date(2030, 1, 1))
        self.assertEqual(evs[0].estado, Estado.NO_VERIFICABLE)
        self.assertTrue(any("revisar_tras" in m for m in evs[0].motivos))

    def test_pero_no_rescata_un_no_compatible(self):
        evs = evaluar(skill(tiene_scripts=True), self.perfiles["mistral-vibe-work"],
                      datetime.date(2030, 1, 1))
        self.assertEqual(evs[0].estado, Estado.NO_COMPATIBLE)


class ModosDeInstalacion(unittest.TestCase):

    def test_una_evaluacion_por_modo_declarado(self):
        perfiles = cargar_perfiles()
        evs = evaluar(skill(), perfiles["chatgpt"], HOY)
        self.assertEqual([e.modo_instalacion for e in evs], ["url_repositorio", "zip"])

    def test_el_bloqueo_de_seguridad_esta_reservado_y_vacio(self):
        perfiles = cargar_perfiles()
        evs = evaluar(skill(), perfiles["claude-code"], HOY)
        self.assertIsNone(evs[0].bloqueo_seguridad)


if __name__ == "__main__":
    unittest.main()
