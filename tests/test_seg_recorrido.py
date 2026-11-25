import io
import tempfile
import unittest
from pathlib import Path

from ayuda import importar_exporter

importar_exporter()

from exporter.deteccion import BLOQUE_CREDENCIAL, flujo_contiene_secreto
from exporter.seguridad.recorrido import es_binario, recorrer  # noqa: E402


def construir(tmp, ficheros):
    """Crea un arbol a partir de {ruta_relativa: contenido}."""
    raiz = Path(tmp)
    for rel, contenido in ficheros.items():
        p = raiz / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contenido, bytes):
            p.write_bytes(contenido)
        else:
            p.write_text(contenido, encoding="utf-8")
    return raiz


class CredencialesEnBloques(unittest.TestCase):

    def test_no_necesita_una_lectura_completa_y_reconoce_un_valor_dividido(self):
        class LecturaAcotada(io.BytesIO):
            def read(self, size=-1):
                if not 0 <= size <= BLOQUE_CREDENCIAL:
                    raise AssertionError("lectura sin limite")
                return super().read(size)

        valor = b"\nclient_secret= CSE_test_Q38PT2_literal\n"
        for pos in (BLOQUE_CREDENCIAL - 2, BLOQUE_CREDENCIAL - 4096, 2 * BLOQUE_CREDENCIAL + 5):
            with self.subTest(pos=pos):
                datos = b"\x00" * pos + valor + b"\x00" * BLOQUE_CREDENCIAL
                self.assertTrue(flujo_contiene_secreto(LecturaAcotada(datos), "datos.bin"))

    def test_una_lectura_dividida_tambien_detecta_utf16(self):
        valor = "\nclient_secret: CSE_test_Q38PT2_literal\n"
        datos = (" " * (BLOQUE_CREDENCIAL // 2 - 6) + valor).encode("utf-16")
        self.assertTrue(flujo_contiene_secreto(io.BytesIO(datos), "datos.txt"))


class Ambito(unittest.TestCase):
    """La distincion que sostiene todo el diseno."""

    ARBOL = {
        "scripts/setup.sh": "#!/bin/sh\necho fuera\n",
        "package.json": "{}\n",
        "skills/x/SKILL.md": "---\nname: x\n---\n# x\n",
        "skills/x/scripts/run.sh": "#!/bin/sh\necho dentro\n",
        "skills/x/references/guia.md": "texto\n",
    }

    def ambitos(self, raiz):
        return {f.ruta: f.ambito for f in recorrer(raiz, ["skills/x"])}

    def test_lo_de_la_raiz_es_ambito_paquete(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.ambitos(construir(tmp, self.ARBOL))
            self.assertEqual(a["scripts/setup.sh"], "paquete")
            self.assertEqual(a["package.json"], "paquete")

    def test_lo_de_dentro_de_la_skill_es_ambito_exportado(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self.ambitos(construir(tmp, self.ARBOL))
            self.assertEqual(a["skills/x/scripts/run.sh"], "exportado")
            self.assertEqual(a["skills/x/references/guia.md"], "exportado")

    def test_el_skill_md_es_exportado_porque_su_cuerpo_viaja(self):
        # Al empaquetar se le reescribe el frontmatter, pero el cuerpo viaja
        # intacto — y es justo donde vive una inyeccion de prompt.
        with tempfile.TemporaryDirectory() as tmp:
            a = self.ambitos(construir(tmp, self.ARBOL))
            self.assertEqual(a["skills/x/SKILL.md"], "exportado")

    def test_el_mismo_nombre_de_fichero_da_ambitos_distintos(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = construir(tmp, {
                "scripts/run.sh": "#!/bin/sh\n",
                "skills/x/SKILL.md": "---\nname: x\n---\n",
                "skills/x/scripts/run.sh": "#!/bin/sh\n",
            })
            a = {f.ruta: f.ambito for f in recorrer(raiz, ["skills/x"])}
            self.assertEqual(a["scripts/run.sh"], "paquete")
            self.assertEqual(a["skills/x/scripts/run.sh"], "exportado")

    def test_lo_podado_al_empaquetar_no_es_exportado(self):
        # copiar_skill nunca copia estos directorios, asi que un hallazgo ahi
        # no puede bloquear la escritura de un artefacto que no lo contiene.
        with tempfile.TemporaryDirectory() as tmp:
            raiz = construir(tmp, {
                "skills/x/SKILL.md": "---\nname: x\n---\n",
                "skills/x/node_modules/p/index.js": "x\n",
                "skills/x/dist/bundle.js": "x\n",
                "skills/x/scripts/run.sh": "#!/bin/sh\n",
            })
            a = {f.ruta: f.ambito for f in recorrer(raiz, ["skills/x"])}
            self.assertEqual(a["skills/x/node_modules/p/index.js"], "paquete")
            self.assertEqual(a["skills/x/dist/bundle.js"], "paquete")
            self.assertEqual(a["skills/x/scripts/run.sh"], "exportado")

    def test_una_skill_en_la_raiz_del_origen_es_toda_exportado(self):
        # `relative_to` devuelve "." cuando el origen ES el directorio de la
        # skill (un repositorio de una sola skill con el SKILL.md en la
        # raiz). Sin esta rama todo el arbol saldria `paquete` y el gate se
        # desactivaria en silencio.
        with tempfile.TemporaryDirectory() as tmp:
            raiz = construir(tmp, {"SKILL.md": "---\nname: sola\n---\n",
                                   "scripts/run.sh": "#!/bin/sh\n"})
            a = {f.ruta: f.ambito for f in recorrer(raiz, ["."])}
            self.assertEqual(a["SKILL.md"], "exportado")
            self.assertEqual(a["scripts/run.sh"], "exportado")


class QueSeRecorre(unittest.TestCase):

    def test_no_desciende_a_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = construir(tmp, {".git/config": "x\n", "a.md": "y\n"})
            self.assertEqual([f.ruta for f in recorrer(raiz, [])], ["a.md"])

    def test_no_desciende_a_pycache(self):
        # Lo genera el propio interprete al importar exporter, antes de que
        # empiece el recorrido. Sin esta exclusion la herramienta se delata
        # a si misma con nueve SEC-BINARIO-NO-DOCUMENTADO-001 en cada
        # ejecucion (comprobado en un checkout limpio).
        with tempfile.TemporaryDirectory() as tmp:
            raiz = construir(tmp, {"__pycache__/x.pyc": b"\x00\x01", "a.md": "y\n"})
            self.assertEqual([f.ruta for f in recorrer(raiz, [])], ["a.md"])

    def test_si_desciende_a_node_modules(self):
        # Es justo donde vive el riesgo de cadena de suministro. Si el arbol
        # es demasiado grande, comprobar_tamano aborta antes de llegar aqui.
        with tempfile.TemporaryDirectory() as tmp:
            raiz = construir(tmp, {"node_modules/p/index.js": "x\n"})
            self.assertIn("node_modules/p/index.js", [f.ruta for f in recorrer(raiz, [])])

    def test_omite_enlaces_simbolicos(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = construir(tmp, {"real.md": "x\n"})
            (raiz / "enlace.md").symlink_to(raiz / "real.md")
            self.assertEqual([f.ruta for f in recorrer(raiz, [])], ["real.md"])

    def test_las_rutas_usan_separadores_posix(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = construir(tmp, {"a/b/c.md": "x\n"})
            self.assertEqual([f.ruta for f in recorrer(raiz, [])], ["a/b/c.md"])

    def test_el_orden_es_estable(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = construir(tmp, {"z.md": "1\n", "a.md": "2\n", "m/n.md": "3\n"})
            uno = [f.ruta for f in recorrer(raiz, [])]
            dos = [f.ruta for f in recorrer(raiz, [])]
            self.assertEqual(uno, dos)
            self.assertEqual(uno, sorted(uno))


class Binarios(unittest.TestCase):

    def test_un_byte_nulo_lo_hace_binario(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = construir(tmp, {"b.bin": b"\x7fELF\x00\x00algo"})
            self.assertTrue(es_binario(raiz / "b.bin"))

    def test_el_texto_con_acentos_no_es_binario(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = construir(tmp, {"t.md": "cárgala cuando… ñ\n"})
            self.assertFalse(es_binario(raiz / "t.md"))

    def test_el_recorrido_marca_el_binario(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = construir(tmp, {"b.bin": b"\x00\x01", "t.md": "hola\n"})
            marcas = {f.ruta: f.binario for f in recorrer(raiz, [])}
            self.assertTrue(marcas["b.bin"])
            self.assertFalse(marcas["t.md"])


if __name__ == "__main__":
    unittest.main()
