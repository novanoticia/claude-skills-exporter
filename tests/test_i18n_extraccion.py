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


if __name__ == "__main__":
    unittest.main()
