import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ayuda import RAIZ

_spec = importlib.util.spec_from_file_location(
    "validar_idiomas", RAIZ / ".github" / "validar_idiomas.py")
validar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validar)

I18N = Path("skills/plugin-to-agentskills/scripts/exporter/i18n")
TARGETS = Path("skills/plugin-to-agentskills/scripts/exporter/targets")
REGLAS = Path("skills/plugin-to-agentskills/scripts/exporter/seguridad/reglas.json")


def copia():
    """Copia minima del repositorio con solo lo que mira el validador."""
    tmp = Path(tempfile.mkdtemp())
    for rel in (I18N, TARGETS, REGLAS):
        origen, destino = RAIZ / rel, tmp / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        if origen.is_dir():
            shutil.copytree(origen, destino)
        else:
            shutil.copy(origen, destino)
    return tmp


def leer(ruta):
    return json.loads(ruta.read_text(encoding="utf-8"))


def escribir(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def claves_extra(raiz):
    """Las claves regla.* y peligro.* que todo catalogo no-es debe llevar."""
    claves = []
    for r in leer(raiz / REGLAS)["reglas"]:
        claves += ["regla.{}.{}".format(r["id"], c)
                   for c in ("titulo", "detalle", "mitigacion")]
    for p in sorted((raiz / TARGETS).glob("*.json")):
        if p.name.startswith("_"):
            continue
        for peligro in leer(p).get("peligros", []):
            claves += ["peligro.{}.{}".format(peligro["id"], c)
                       for c in ("titulo", "detalle", "mitigacion")]
    return claves


class Validador(unittest.TestCase):

    def setUp(self):
        self.tmp = copia()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.dir = self.tmp / I18N
        # Catalogo sintetico valido: lo mismo que es.json mas las claves de
        # reglas y peligros. Cada prueba lo estropea de una manera.
        datos = leer(self.dir / "es.json")
        datos["_meta"] = {"idioma": "zz", "nombre": "Zzz"}
        for k in claves_extra(self.tmp):
            datos[k] = "texto"
        self.zz = self.dir / "zz.json"
        escribir(self.zz, datos)

    def errores(self):
        return validar.comprobar(self.tmp)

    def estropear(self, fn):
        datos = leer(self.zz)
        fn(datos)
        escribir(self.zz, datos)

    def test_el_repositorio_actual_es_valido(self):
        self.assertEqual(validar.comprobar(RAIZ), [])

    def test_el_catalogo_sintetico_es_valido(self):
        self.assertEqual(self.errores(), [])

    def test_clave_de_menos(self):
        self.estropear(lambda d: d.pop("informe.titulo"))
        self.assertTrue(any("falta la clave informe.titulo" in e for e in self.errores()),
                        self.errores())

    def test_clave_de_mas(self):
        self.estropear(lambda d: d.update({"informe.no_existe": "x"}))
        self.assertTrue(any("sobra la clave informe.no_existe" in e
                            for e in self.errores()), self.errores())

    def test_marcador_distinto(self):
        self.estropear(lambda d: d.update(
            {"informe.origen": d["informe.origen"].replace("{origen}", "{origin}")}))
        self.assertTrue(any("marcadores" in e and "informe.origen" in e
                            for e in self.errores()), self.errores())

    def test_plantilla_vacia(self):
        self.estropear(lambda d: d.update({"informe.titulo": "  "}))
        self.assertTrue(any("vacía" in e for e in self.errores()), self.errores())

    def test_plantilla_con_llave_suelta(self):
        self.estropear(lambda d: d.update({"informe.titulo": "abierta {"}))
        self.assertTrue(any("no es una plantilla válida" in e for e in self.errores()),
                        self.errores())

    def test_meta_no_coincide_con_el_fichero(self):
        self.estropear(lambda d: d.update({"_meta": {"idioma": "qq", "nombre": "Z"}}))
        self.assertTrue(any("_meta" in e for e in self.errores()), self.errores())

    def test_regla_inexistente(self):
        self.estropear(lambda d: d.update({"regla.SEC-NO-EXISTE-001.titulo": "x"}))
        self.assertTrue(any("SEC-NO-EXISTE-001" in e for e in self.errores()),
                        self.errores())

    def test_regla_sin_traducir(self):
        self.estropear(lambda d: d.pop(next(k for k in d if k.startswith("regla."))))
        self.assertTrue(any("falta la clave regla." in e for e in self.errores()),
                        self.errores())

    def test_peligro_sin_traducir(self):
        self.estropear(lambda d: d.pop(next(k for k in d if k.startswith("peligro."))))
        self.assertTrue(any("falta la clave peligro." in e for e in self.errores()),
                        self.errores())

    def test_marcador_posicional_en_otro_idioma(self):
        # `{}` sin nombre pasa la comparacion de conjuntos (se descarta) y
        # revienta en ejecucion con IndexError: str.format(**datos).
        self.estropear(lambda d: d.update(
            {"consola.skills_encontradas": d["consola.skills_encontradas"] + " {}"}))
        self.assertTrue(any("consola.skills_encontradas" in e and "marcador" in e
                            for e in self.errores()), self.errores())

    def test_marcador_numerico_en_otro_idioma(self):
        self.estropear(lambda d: d.update({"informe.origen": "- **Source:** `{0}`"}))
        self.assertTrue(any("informe.origen" in e and "marcador" in e
                            for e in self.errores()), self.errores())

    def test_marcador_posicional_en_es(self):
        es = leer(self.dir / "es.json")
        es["informe.origen"] = "- **Origen:** `{}`"
        escribir(self.dir / "es.json", es)
        self.assertTrue(any(e.startswith("es.json") and "marcador" in e
                            for e in self.errores()), self.errores())

    def test_marcador_con_atributo(self):
        self.estropear(lambda d: d.update({"informe.origen": "- **Source:** `{origen.real}`"}))
        self.assertTrue(any("informe.origen" in e and "marcador" in e
                            for e in self.errores()), self.errores())

    def test_es_no_lleva_claves_de_regla(self):
        es = leer(self.dir / "es.json")
        es["regla.SEC-EXEC-REMOTO-001.titulo"] = "x"
        escribir(self.dir / "es.json", es)
        self.assertTrue(any(e.startswith("es.json") and "regla." in e
                            for e in self.errores()), self.errores())

    def test_falta_es(self):
        (self.dir / "es.json").unlink()
        self.assertTrue(any("falta es.json" in e for e in self.errores()),
                        self.errores())


if __name__ == "__main__":
    unittest.main()
