import json
import tempfile
import unittest
from pathlib import Path

from ayuda import importar_exporter

importar_exporter()
from exporter import i18n  # noqa: E402


class Catalogo(unittest.TestCase):
    """Cada prueba usa un directorio de catalogos propio y restaura el real."""

    def setUp(self):
        self._dir = i18n.DIRECTORIO
        self._activo = i18n.idioma_activo()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        i18n.DIRECTORIO = self._dir
        i18n._cache.clear()
        i18n.fijar_idioma(self._activo)

    def usar(self, **catalogos):
        for codigo, claves in catalogos.items():
            datos = {"_meta": {"idioma": codigo, "nombre": codigo.upper()}}
            datos.update(claves)
            (self.tmp / (codigo + ".json")).write_text(
                json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        i18n.DIRECTORIO = self.tmp
        i18n._cache.clear()


class T(Catalogo):

    def test_formatea_con_campos_con_nombre(self):
        self.usar(es={"a": "Hay {n} cosas en {donde}."})
        self.assertEqual(i18n.t("a", n=3, donde="casa"), "Hay 3 cosas en casa.")

    def test_las_llaves_dobles_son_llaves_literales(self):
        self.usar(es={"a": "Ruta ${{CLAUDE_PLUGIN_ROOT}}/x"})
        self.assertEqual(i18n.t("a"), "Ruta ${CLAUDE_PLUGIN_ROOT}/x")

    def test_un_dato_con_llaves_no_se_reinterpreta(self):
        # Review Focus 2: solo se formatea la plantilla, nunca el dato.
        self.usar(es={"a": "Visto: {muestra}"})
        self.assertEqual(i18n.t("a", muestra="${VAR} {x}"), "Visto: ${VAR} {x}")

    def test_usa_el_idioma_activo(self):
        self.usar(es={"a": "hola"}, en={"a": "hello"})
        i18n.fijar_idioma("en")
        self.assertEqual(i18n.t("a"), "hello")

    def test_si_falta_en_el_idioma_activo_cae_a_es(self):
        self.usar(es={"a": "hola", "b": "adios"}, en={"a": "hello"})
        i18n.fijar_idioma("en")
        self.assertEqual(i18n.t("b"), "adios")

    def test_si_falta_tambien_en_es_es_un_error_de_programacion(self):
        self.usar(es={"a": "hola"})
        with self.assertRaises(KeyError):
            i18n.t("no-existe")


class TOpcional(Catalogo):

    def test_devuelve_la_sobrescritura_si_existe(self):
        self.usar(es={}, en={"regla.X.titulo": "Title"})
        i18n.fijar_idioma("en")
        self.assertEqual(i18n.t_opcional("regla.X.titulo", "Titulo"), "Title")

    def test_devuelve_el_defecto_si_no_existe(self):
        self.usar(es={}, en={})
        i18n.fijar_idioma("en")
        self.assertEqual(i18n.t_opcional("regla.X.titulo", "Titulo"), "Titulo")

    def test_en_espanol_siempre_devuelve_el_defecto(self):
        self.usar(es={})
        self.assertEqual(i18n.t_opcional("regla.X.titulo", "Titulo"), "Titulo")

    def test_no_formatea_el_defecto(self):
        self.usar(es={})
        self.assertEqual(i18n.t_opcional("k", "usa {llaves}"), "usa {llaves}")


class Seleccion(Catalogo):

    def test_normaliza_formas_de_locale(self):
        # Review Focus 4
        for pedido, esperado in [("EN", "en"), ("en-US", "en"),
                                 ("fr_FR.UTF-8", "fr"), (" Fr ", "fr"),
                                 ("en_US@euro", "en")]:
            self.assertEqual(i18n.normalizar_codigo(pedido), esperado)

    def test_idioma_desconocido_lleva_la_lista(self):
        self.usar(es={}, en={})
        with self.assertRaises(i18n.IdiomaDesconocido) as ctx:
            i18n.fijar_idioma("xx")
        self.assertEqual(ctx.exception.codigo, "xx")
        self.assertEqual(sorted(ctx.exception.disponibles), ["en", "es"])

    def test_codigo_vacio_es_desconocido(self):
        self.usar(es={})
        with self.assertRaises(i18n.IdiomaDesconocido):
            i18n.fijar_idioma("")

    def test_un_idioma_nuevo_se_descubre_sin_tocar_codigo(self):
        self.usar(es={}, de={})
        self.assertIn("de", i18n.idiomas_disponibles())
        self.assertEqual(i18n.fijar_idioma("de"), "de")

    def test_ignora_ficheros_sin_meta(self):
        self.usar(es={})
        (self.tmp / "roto.json").write_text("[]", encoding="utf-8")
        self.assertNotIn("roto", i18n.idiomas_disponibles())


class CatalogoReal(unittest.TestCase):

    def test_es_json_existe_y_es_el_idioma_base(self):
        self.assertEqual(i18n.idiomas_disponibles()["es"], "Español")


if __name__ == "__main__":
    unittest.main()
