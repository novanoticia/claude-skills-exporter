import json
import re
import string
import unittest
from pathlib import Path

from ayuda import RAIZ_SCRIPTS, importar_exporter

importar_exporter()

CATALOGOS = RAIZ_SCRIPTS / "exporter" / "i18n"


def claves(codigo):
    datos = json.loads((CATALOGOS / (codigo + ".json")).read_text(encoding="utf-8"))
    datos.pop("_meta")
    return datos


class EsJson(unittest.TestCase):

    def test_ninguna_plantilla_de_es_esta_vacia(self):
        for k, v in claves("es").items():
            with self.subTest(clave=k):
                self.assertTrue(v.strip())

    def test_las_plantillas_son_validas_para_str_format(self):
        # Una `{` suelta se descubriria en ejecucion, solo en el camino que
        # la usa. Parsear la plantilla las encuentra todas aqui.
        for k, v in claves("es").items():
            with self.subTest(clave=k):
                list(string.Formatter().parse(v))

    def test_los_vocabularios_cerrados_tienen_todas_sus_claves(self):
        from exporter.modelo import Estado
        esperadas = set()
        esperadas |= {"dimension." + d for d in
                      ("tecnico", "cadena_de_suministro", "comportamiento")}
        esperadas |= {"nivel." + n for n in
                      ("bajo", "moderado", "alto", "critico", "no_evaluable")}
        esperadas |= {"severidad." + s for s in ("critica", "alta", "media", "baja")}
        esperadas |= {"confianza." + c for c in ("alta", "media", "baja")}
        esperadas |= {"ambito." + a for a in ("exportado", "paquete")}
        esperadas |= {"recomendacion." + r for r in (
            "instalacion_razonable", "revisar_permisos",
            "revision_humana_obligatoria", "bloqueada", "revision_incompleta")}
        esperadas |= {"estado." + e for e in Estado.ORDEN}
        self.assertEqual(esperadas - set(claves("es")), set())


class Marcadores(unittest.TestCase):

    def test_la_adaptacion_de_plugin_root_conserva_sus_llaves(self):
        # Review Focus 1: `${CLAUDE_PLUGIN_ROOT}` es texto literal, no un campo.
        from exporter import i18n
        i18n.fijar_idioma("es")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", i18n.t("adaptacion.rutas-plugin-root"))
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", i18n.t("senal.plugin-root"))

    def test_cada_senal_detectable_tiene_explicacion(self):
        from exporter.deteccion import PATRONES
        faltan = {"senal." + pid for pid, _, _ in PATRONES} - set(claves("es"))
        self.assertEqual(faltan, set())

    def test_cada_codigo_de_portabilidad_tiene_texto(self):
        codigos = ["sin-frontmatter", "sin-description", "nombre-vs-carpeta",
                   "description-sin-activacion", "description-larga",
                   "description-densa", "senal", "herramientas-claude",
                   "cuerpo-largo", "enlace-simbolico", "fichero-ilegible", "scripts"]
        faltan = {"portabilidad." + c for c in codigos} - set(claves("es"))
        self.assertEqual(faltan, set())

    def test_los_limites_de_paquete_tienen_texto(self):
        faltan = {"empaquetado.limite_zip_bytes", "empaquetado.limite_zip_ficheros",
                  "empaquetado.limite_fichero"} - set(claves("es"))
        self.assertEqual(faltan, set())


if __name__ == "__main__":
    unittest.main()
