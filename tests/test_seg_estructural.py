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


class ArchivosYSecretos(Base):

    def test_un_zip_se_senala_y_no_se_abre(self):
        self.assertIn("SEC-ARCHIVO-ANIDADO-001", self.ids({"paquete.zip": b"PK\x03\x04\x00"}))

    def test_env_y_claves_privadas(self):
        self.assertIn("SEC-SECRETO-EN-REPO-001", self.ids({".env": "A=1\n"}))
        self.assertIn("SEC-SECRETO-EN-REPO-001", self.ids({"claves/id_rsa": "falso\n"}))
        self.assertIn("SEC-SECRETO-EN-REPO-001", self.ids({"cert.pem": "falso\n"}))

    def test_un_env_de_ejemplo_no_dispara(self):
        self.assertNotIn("SEC-SECRETO-EN-REPO-001", self.ids({".env.example": "A=\n"}))


class Ambito(Base):

    def test_el_hallazgo_hereda_el_ambito_del_fichero(self):
        hs = self.hallazgos({"skills/x/SKILL.md": "---\nname: x\n---\n",
                             "skills/x/.env": "A=1\n"},
                            dirs_skill=["skills/x"])
        secretos = [h for h in hs if h.id == "SEC-SECRETO-EN-REPO-001"]
        self.assertEqual([h.ambito for h in secretos], ["exportado"])


if __name__ == "__main__":
    unittest.main()
