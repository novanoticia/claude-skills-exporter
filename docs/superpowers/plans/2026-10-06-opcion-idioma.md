# Opción de idioma (`--lang`) — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que `convert.py` produzca informes, consola, hallazgos y errores en español (por defecto), inglés o francés con `--lang`, y que Claude responda en ese idioma.

**Architecture:** Un paquete `exporter/i18n/` con un catálogo JSON por idioma y una función `t(clave, **datos)` que lee el idioma activo (estado de proceso, fijado una vez en `main()`). Los literales de los `.py` pasan a `es.json`. Los textos de `reglas.json` y de `targets/*.json` se quedan en español donde están; `en.json` y `fr.json` los sobrescriben con `regla.<ID>.*` y `peligro.<id>.*`. Un validador de CI exige que los catálogos tengan las mismas claves y los mismos marcadores.

**Tech Stack:** Python 3.8+ solo biblioteca estándar en ejecución (`json`, `pathlib`, `string`, `os`, `re`); `unittest`; `jsonschema` no se usa.

**Spec:** `docs/superpowers/specs/2026-10-06-opcion-idioma-diseno.md` (incluye §9 «Enmiendas», que **prevalece** sobre §2–§4 donde difieran).

## Global Constraints

Copiadas de `AGENTS.md` y del spec; cada tarea las hereda.

- Python 3.8+ y solo biblioteca estándar en `exporter/`. Nada de `jsonschema` fuera de `.github/`.
- El análisis es estático: `i18n` solo lee JSON del propio paquete. `.github/validar_estatico.py` debe seguir en verde.
- Identificadores en ASCII; comentarios y *docstrings* del código **sin acentos**. Los textos de los catálogos son datos visibles al usuario: llevan la acentuación correcta de **su** idioma.
- Nombres de artefactos invariables: `<skill>.zip`, `<skill>/`, `INFORME-PORTABILIDAD.md`, `resumen.json`.
- Vocabularios cerrados (familia, dimensión, severidad, confianza, ámbito, nivel): **no se inventan valores**. En `resumen.json` siguen en español; en la prosa del informe se muestran traducidos.
- La forma de `resumen.json` y su schema **no cambian**.
- `tests/__init__.py` no debe existir.
- Redacción del informe: nunca «este repositorio es malicioso», en ningún idioma.
- Fixtures inertes (`.invalid`, claves falsas).
- Con `--lang es` o sin flag, la salida debe quedar **byte a byte idéntica** a la de antes del cambio.
- Mensajes de commit en español, sujeto imperativo en tercera persona («Anade…»), cuerpo con el porqué, y terminan con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Ejecutar las pruebas **exactamente así** (nunca `| tail &&`):

```bash
python3 -m unittest discover -s tests -t tests > /tmp/suite.log 2>&1; echo "codigo=$?"
grep -E "^(OK|FAILED|Ran )" /tmp/suite.log
```

## Review Focus

Entradas que el spec insinúa y ninguna tarea cubriría sola; cada línea tiene su prueba en la tarea indicada.

1. **Llaves literales en una plantilla** (`${CLAUDE_PLUGIN_ROOT}` en una adaptación): en el catálogo van como `${{CLAUDE_PLUGIN_ROOT}}`; la salida debe mostrar `${CLAUDE_PLUGIN_ROOT}` (Tarea 3).
2. **Datos con llaves** (una `muestra` como `${VAR}` o `{x}`): solo se formatea la plantilla, nunca el dato; no debe lanzar `KeyError` ni sustituir nada (Tarea 1 y Tarea 5).
3. **`CSE_LANG` en el entorno del desarrollador** altera los golden en español: las pruebas lo eliminan al arrancar (Tarea 2).
4. **Código de idioma con forma de locale** (`EN`, `en-US`, `fr_FR.UTF-8`) se acepta; uno inexistente (`xx`, vacío) da error en español con la lista, y `--lang` gana a `CSE_LANG` (Tarea 2).
5. **`resumen.json` no cambia de forma entre idiomas**: mismas claves y mismos valores de vocabulario cerrado; solo difieren los campos de texto (Tarea 9).
6. **Un catálogo con una clave de más o de menos, o un marcador distinto**, rompe el CI en lugar de fallar en ejecución (Tarea 6).
7. **Una traducción que cite literalmente un patrón peligroso** (frase de inyección de prompt, descarga-y-ejecuta) bloquearía la autoexportación del plugin, porque `i18n/*.json` vive en `skills/` con ámbito `exportado` (Tarea 7 y Tarea 8).
8. **Forma antigua `convert.py <repo> --lang en`** (sin subcomando) debe seguir funcionando vía `normalizar_argv` (Tarea 2).

---

## Mapa de ficheros

| Fichero | Acción | Responsabilidad |
|---|---|---|
| `skills/plugin-to-agentskills/scripts/exporter/i18n/__init__.py` | crear | `t`, `t_opcional`, `fijar_idioma`, `idioma_activo`, `idiomas_disponibles`, `normalizar_codigo`, `idioma_pedido`, `detectar_del_entorno` |
| `.../exporter/i18n/es.json` | crear | todos los literales hoy incrustados en `.py`; fuente de verdad de las claves |
| `.../exporter/i18n/en.json`, `fr.json` | crear | traducciones + `regla.*` y `peligro.*` |
| `.../convert.py` | modificar | flag `--lang`, selección de idioma, literales → `t()` |
| `.../exporter/informes.py` | modificar | literales y diccionarios de etiquetas → `t()` |
| `.../exporter/compatibilidad.py` | modificar | motivos → `t()`; peligros → `t_opcional` |
| `.../exporter/deteccion.py` | modificar | `EXPLICACIONES` → claves `senal.<id>` |
| `.../exporter/seguridad/riesgo.py` | modificar | `TEXTO_RECOMENDACION` → claves `recomendacion.<valor>` |
| `.../exporter/seguridad/estructural.py` | modificar | textos de `_h(...)` → `t()` |
| `.../exporter/seguridad/patrones.py` | modificar | `titulo`/`mitigacion` pasan por `t_opcional` |
| `.github/validar_idiomas.py` | crear | validador de catálogos (solo stdlib) |
| `.github/workflows/validar.yml` | modificar | un paso nuevo |
| `tests/test_i18n.py`, `tests/test_idiomas_cli.py`, `tests/test_idiomas_golden.py` | crear | pruebas |
| `tests/golden-i18n/{en,fr}/` | crear | golden de los otros idiomas |
| `tests/generar_golden.py` | modificar | regenerar también `golden-i18n` |
| `tests/ayuda.py` | modificar | quita `CSE_LANG` del entorno |
| `skills/plugin-to-agentskills/SKILL.md`, `commands/exportar-skills.md` | modificar | indicar a Claude que responda en el idioma pedido |
| `README.md`, `AGENTS.md` | modificar | documentar el flag, el validador y el nuevo número de pruebas |

## Cómo comprobar que el español no se movió (se usa en las Tareas 3–5)

Es una refactorización: el criterio de «hecho» es que nada cambie. Se captura **antes de tocar nada** la salida completa del conversor sobre todos los fixtures y se compara tras cada tarea.

Script auxiliar, **fuera del repositorio** (no se comitea):

```bash
cat > /tmp/cse-i18n-snapshot.sh <<'EOF'
#!/bin/bash
# Uso: cse-i18n-snapshot.sh <directorio-destino> [flags extra del conversor]
DEST="$1"; shift
rm -rf "$DEST"; mkdir -p "$DEST"
cd "$(git rev-parse --show-toplevel)"
WORK=/tmp/cse-i18n-trabajo
for f in tests/fixtures/*/; do
  n=$(basename "$f")
  rm -rf "$WORK"
  CSE_FECHA=2026-08-08 python3 skills/plugin-to-agentskills/scripts/convert.py export "$f" \
    --out "$WORK" --anular-revision-seguridad "$@" \
    > "$DEST/$n.stdout" 2> "$DEST/$n.stderr"
  echo "$?" > "$DEST/$n.codigo"
  # Los zip llevan fechas de modificacion: se compara su contenido, no el binario.
  for z in "$WORK"/*.zip; do
    [ -e "$z" ] || continue
    python3 - "$z" >> "$DEST/$n.zips" <<'PY'
import hashlib, sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
print(sys.argv[1].split("/")[-1])
for i in sorted(z.namelist()):
    print(" ", i, hashlib.sha256(z.read(i)).hexdigest()[:16])
PY
    rm "$z"
  done
  [ -d "$WORK" ] && cp -R "$WORK" "$DEST/$n"
done
for n in inspect audit; do
  for f in tests/fixtures/*/; do
    b=$(basename "$f")
    CSE_FECHA=2026-08-08 python3 skills/plugin-to-agentskills/scripts/convert.py $n "$f" "$@" \
      > "$DEST/$b.$n.stdout" 2> "$DEST/$b.$n.stderr"
  done
done
EOF
chmod +x /tmp/cse-i18n-snapshot.sh
```

Para comparar: `/tmp/cse-i18n-snapshot.sh /tmp/cse-i18n-despues && diff -r /tmp/cse-i18n-antes /tmp/cse-i18n-despues && echo IGUAL`.

---

### Task 1: Núcleo `i18n` (`t`, selección de idioma, autodescubrimiento)

**Files:**
- Create: `skills/plugin-to-agentskills/scripts/exporter/i18n/__init__.py`
- Create: `skills/plugin-to-agentskills/scripts/exporter/i18n/es.json`
- Test: `tests/test_i18n.py`

**Interfaces:**
- Produces (usados por todas las tareas siguientes):
  - `t(clave: str, **datos) -> str` — texto del idioma activo; si falta cae a `es`; si falta también en `es` lanza `KeyError(clave)`. Siempre aplica `str.format(**datos)`.
  - `t_opcional(clave: str, defecto: str) -> str` — el texto del catálogo del idioma activo **sin** caer a `es`, o `defecto`. No formatea.
  - `fijar_idioma(codigo: str) -> str` — normaliza, valida y fija; devuelve el código normalizado; lanza `IdiomaDesconocido(codigo, disponibles)`.
  - `idioma_activo() -> str`.
  - `idiomas_disponibles() -> dict` — `{codigo: nombre}` de los ficheros `*.json` con `_meta.nombre`.
  - `normalizar_codigo(codigo: str) -> str` — `"FR_fr.UTF-8"` → `"fr"`.
  - `IDIOMA_BASE = "es"`; `DIRECTORIO: Path`; `_cache: dict`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `tests/test_i18n.py`:

```python
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
```

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: `python3 -m unittest discover -s tests -t tests -p "test_i18n.py" > /tmp/i18n.log 2>&1; echo "codigo=$?"; grep -E "^(OK|FAILED|Ran |ImportError|ModuleNotFound)" /tmp/i18n.log`
Expected: `codigo=1`, error de importación de `exporter.i18n`.

- [ ] **Step 3: Implementar**

Crear `skills/plugin-to-agentskills/scripts/exporter/i18n/es.json`:

```json
{
  "_meta": {"idioma": "es", "nombre": "Español"}
}
```

Crear `skills/plugin-to-agentskills/scripts/exporter/i18n/__init__.py`:

```python
"""Textos visibles en varios idiomas.

Un catalogo JSON por idioma en este mismo directorio: `clave -> plantilla`,
con campos `{nombre}` de `str.format`. El idioma activo es estado de modulo,
fijado una sola vez al arrancar `main()`: el programa es de un solo proceso
y de un solo hilo, y pasar el idioma como parametro tocaria decenas de
firmas por poco beneficio.

Anadir un idioma es soltar aqui un `xx.json` con su `_meta`; se descubre
solo, igual que los perfiles de `exporter/targets/`.

Solo biblioteca estandar y solo lectura de ficheros propios: este modulo no
ejecuta nada de lo que analiza.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

IDIOMA_BASE = "es"
DIRECTORIO = Path(__file__).resolve().parent

_activo = IDIOMA_BASE
_cache: dict = {}


class IdiomaDesconocido(Exception):
    def __init__(self, codigo: str, disponibles: dict):
        super().__init__(codigo)
        self.codigo = codigo
        self.disponibles = disponibles


def normalizar_codigo(codigo: str) -> str:
    """`FR_fr.UTF-8` -> `fr`; `en-US` -> `en`."""
    return re.split(r"[-_.@]", codigo.strip().lower())[0]


def _cargar(codigo: str) -> dict:
    if codigo not in _cache:
        ruta = DIRECTORIO / (codigo + ".json")
        _cache[codigo] = json.loads(ruta.read_text(encoding="utf-8"))
    return _cache[codigo]


def idiomas_disponibles() -> dict:
    """`{codigo: nombre en su propia lengua}` de los catalogos legibles."""
    salida = {}
    for ruta in sorted(DIRECTORIO.glob("*.json")):
        try:
            meta = json.loads(ruta.read_text(encoding="utf-8"))["_meta"]
            salida[ruta.stem] = meta["nombre"]
        except (OSError, ValueError, KeyError, TypeError):
            # Un catalogo roto no se ofrece. Quien lo rompa lo ve en CI:
            # validar_idiomas.py lo comprueba fichero a fichero.
            continue
    return salida


def fijar_idioma(codigo: str) -> str:
    global _activo
    normalizado = normalizar_codigo(codigo)
    disponibles = idiomas_disponibles()
    if normalizado not in disponibles:
        raise IdiomaDesconocido(codigo, disponibles)
    _activo = normalizado
    return normalizado


def idioma_activo() -> str:
    return _activo


def t(clave: str, **datos) -> str:
    """Texto de `clave` en el idioma activo.

    Si falta en ese idioma cae al espanol, para que un catalogo incompleto
    degrade en vez de romper; si falta tambien en espanol es un error de
    programacion y se lanza KeyError. Solo se formatea la PLANTILLA: los
    datos se insertan como valores y no se reinterpretan.
    """
    plantilla = _cargar(_activo).get(clave)
    if plantilla is None:
        plantilla = _cargar(IDIOMA_BASE)[clave]
    return plantilla.format(**datos)


def t_opcional(clave: str, defecto: str) -> str:
    """La sobrescritura de `clave` en el idioma activo, o `defecto`.

    Para los textos que viven en espanol en reglas.json y en los perfiles de
    destino: ahi `defecto` es el espanol de origen, y los catalogos de otros
    idiomas lo sobrescriben. No cae a `es` (su catalogo no los lleva) y no
    formatea, porque esos textos no son plantillas.
    """
    return _cargar(_activo).get(clave, defecto)
```

- [ ] **Step 4: Ejecutar y comprobar que pasan**

Run: el mismo comando del Step 2.
Expected: `codigo=0`, `OK`.

- [ ] **Step 5: Comprobar que el CI estático sigue en verde**

Run: `python3 .github/validar_estatico.py . ; echo "codigo=$?"`
Expected: `codigo=0`.

- [ ] **Step 6: Capturar la línea base del español**

Esta captura es la referencia de las Tareas 3–5 y se hace **ahora**, con el código aún sin tocar.

Run: `/tmp/cse-i18n-snapshot.sh /tmp/cse-i18n-antes; ls /tmp/cse-i18n-antes | head -5`
(si el script no existe aún, crearlo con el bloque de «Cómo comprobar que el español no se movió»).
Expected: se listan directorios y ficheros `.stdout`/`.codigo`.

- [ ] **Step 7: Commit**

```bash
git add skills/plugin-to-agentskills/scripts/exporter/i18n tests/test_i18n.py \
        docs/superpowers/specs/2026-10-06-opcion-idioma-diseno.md \
        docs/superpowers/plans/2026-10-06-opcion-idioma.md
git commit -m "Anade el nucleo de textos por idioma y el plan de la opcion --lang

El conversor escribe todo en espanol y no hay donde enganchar otros idiomas.
Se crea exporter/i18n con t(), t_opcional() y el autodescubrimiento de
catalogos, para que anadir un idioma sea soltar un fichero. Todavia nada lo
usa: el espanol de salida no cambia.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Flag `--lang`, `CSE_LANG` y selección de idioma en `main()`

**Files:**
- Modify: `skills/plugin-to-agentskills/scripts/convert.py` (`construir_parser` ~l.751–795, `main` ~l.1141)
- Modify: `skills/plugin-to-agentskills/scripts/exporter/i18n/__init__.py`
- Modify: `tests/ayuda.py`
- Test: `tests/test_idiomas_cli.py`

**Interfaces:**
- Consumes: `fijar_idioma`, `IdiomaDesconocido`, `idiomas_disponibles` (Tarea 1).
- Produces: `idioma_pedido(flag, entorno=None) -> str`; en `i18n`. Con `--lang auto`, delega en `detectar_del_entorno` (Tarea 10); hasta entonces `auto` no existe y se rechaza como desconocido.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `tests/test_idiomas_cli.py`:

```python
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ayuda import RAIZ, RAIZ_SCRIPTS, importar_exporter

importar_exporter()
from exporter import i18n  # noqa: E402

CONVERT = RAIZ_SCRIPTS / "convert.py"
FIXTURES = RAIZ / "tests" / "fixtures"


def correr(*args, entorno=None):
    env = dict(os.environ, CSE_FECHA="2026-08-08")
    env.pop("CSE_LANG", None)
    env.update(entorno or {})
    return subprocess.run([sys.executable, str(CONVERT)] + list(args),
                          capture_output=True, text=True, cwd=str(RAIZ), env=env)


class IdiomaPedido(unittest.TestCase):

    def test_el_flag_gana_a_la_variable(self):
        self.assertEqual(i18n.idioma_pedido("fr", {"CSE_LANG": "en"}), "fr")

    def test_sin_flag_se_lee_la_variable(self):
        self.assertEqual(i18n.idioma_pedido(None, {"CSE_LANG": "en"}), "en")

    def test_sin_nada_es_espanol(self):
        self.assertEqual(i18n.idioma_pedido(None, {}), "es")

    def test_variable_vacia_cuenta_como_ausente(self):
        self.assertEqual(i18n.idioma_pedido(None, {"CSE_LANG": ""}), "es")


class LangEnElCli(unittest.TestCase):

    def test_idioma_desconocido_da_error_en_espanol_con_la_lista(self):
        r = correr("inspect", str(FIXTURES / "repo-descarga-remota"), "--lang", "xx")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("[error] idioma desconocido: xx", r.stderr)
        self.assertIn("es — Español", r.stderr)

    def test_variable_invalida_sin_flag_tambien_es_error(self):
        r = correr("inspect", str(FIXTURES / "repo-descarga-remota"),
                   entorno={"CSE_LANG": "xx"})
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("idioma desconocido: xx", r.stderr)

    def test_el_flag_valido_gana_a_una_variable_invalida(self):
        r = correr("inspect", str(FIXTURES / "repo-descarga-remota"),
                   "--lang", "es", entorno={"CSE_LANG": "xx"})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_acepta_forma_de_locale(self):
        r = correr("inspect", str(FIXTURES / "repo-descarga-remota"), "--lang", "ES_es.UTF-8")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_la_forma_antigua_sin_subcomando_acepta_el_flag(self):
        # Review Focus 8: `convert.py <repo> --lang es` antepone `export`.
        with tempfile.TemporaryDirectory() as tmp:
            r = correr(str(FIXTURES / "repo-descarga-remota"), "--out", tmp,
                       "--anular-revision-seguridad", "--lang", "es")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_los_tres_subcomandos_aceptan_el_flag(self):
        for sub in ("inspect", "audit"):
            with self.subTest(sub=sub):
                r = correr(sub, str(FIXTURES / "repo-descarga-remota"), "--lang", "es")
                self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: `python3 -m unittest discover -s tests -t tests -p "test_idiomas_cli.py" > /tmp/cli.log 2>&1; echo "codigo=$?"; grep -E "^(OK|FAILED|Ran )" /tmp/cli.log`
Expected: `FAILED` (no existe `idioma_pedido` ni `--lang`).

- [ ] **Step 3: `idioma_pedido` en `i18n`**

Añadir al final de `exporter/i18n/__init__.py`:

```python
def idioma_pedido(flag, entorno=None) -> str:
    """Que idioma se pidio: el flag, si no CSE_LANG, si no el base.

    Una variable vacia cuenta como ausente. No valida: eso lo hace
    fijar_idioma, que es quien conoce los catalogos.
    """
    entorno = os.environ if entorno is None else entorno
    return flag or entorno.get("CSE_LANG") or IDIOMA_BASE
```

- [ ] **Step 4: Cablear el flag y `main()`**

En `convert.py`, importar arriba junto a los demás `from exporter...`:

```python
from exporter import i18n
```

En `construir_parser`, dentro de `comun(p)`, **después** del argumento `--fail-on`:

```python
        p.add_argument("--lang", dest="lang", default=None, metavar="CODIGO",
                       help="idioma de los informes y mensajes: es (por defecto), en, fr. "
                            "También se lee de la variable CSE_LANG")
```

En `main`, justo después de `args = construir_parser().parse_args(...)` y **antes** de `obtener_fecha_hoy()`:

```python
    # El idioma se fija antes que cualquier otra cosa: todo mensaje posterior,
    # incluidos los de error, ya sale en el idioma pedido. El error de idioma
    # desconocido es la excepcion: se da en espanol fijo, porque no hay
    # ningun idioma al que traducirlo.
    try:
        i18n.fijar_idioma(i18n.idioma_pedido(args.lang))
    except i18n.IdiomaDesconocido as e:
        print("[error] idioma desconocido: {}. Disponibles: {}".format(
            e.codigo, ", ".join("{} — {}".format(c, n)
                                for c, n in sorted(e.disponibles.items()))),
            file=sys.stderr)
        return 1
```

- [ ] **Step 5: Aislar las pruebas de `CSE_LANG`**

En `tests/ayuda.py`, tras los `import`, añadir (Review Focus 3):

```python
import os

# Una CSE_LANG puesta en el shell del desarrollador cambiaria el idioma de
# todos los conversores que lanzan las pruebas y rompería los golden.
os.environ.pop("CSE_LANG", None)
```

- [ ] **Step 6: Ejecutar las pruebas del flag y la suite completa**

Run: el comando del Step 2, y después la suite completa con la forma de `AGENTS.md`.
Expected: `OK` en las dos; la suite pasa de 355 a 355 + (las nuevas de `test_i18n` y `test_idiomas_cli`).

- [ ] **Step 7: Commit**

```bash
git add skills/plugin-to-agentskills/scripts/convert.py \
        skills/plugin-to-agentskills/scripts/exporter/i18n/__init__.py \
        tests/test_idiomas_cli.py tests/ayuda.py
git commit -m "Anade --lang y CSE_LANG a los tres subcomandos

El flag y la variable ya fijan el idioma, con error claro en espanol si no
existe. Las pruebas dejan de heredar CSE_LANG del shell para que un
desarrollador con la variable puesta no rompa los golden. Aun no hay
catalogos de otros idiomas, asi que lo unico elegible es es.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Informe y recomendaciones → `t()` (`informes.py`, `riesgo.py`)

**Files:**
- Modify: `skills/plugin-to-agentskills/scripts/exporter/informes.py`
- Modify: `skills/plugin-to-agentskills/scripts/exporter/seguridad/riesgo.py`
- Modify: `skills/plugin-to-agentskills/scripts/exporter/i18n/es.json`
- Test: `tests/test_i18n_extraccion.py` (nuevo; también lo usan las Tareas 4–6)

**Interfaces:**
- Consumes: `t` (Tarea 1).
- Produces: claves `informe.*`, `estado.<valor>`, `dimension.<valor>`, `nivel.<valor>`, `severidad.<valor>`, `confianza.<valor>`, `ambito.<valor>`, `recomendacion.<valor>`. Las Tareas 4–6 añaden más al mismo `es.json`.

**Regla de extracción** (vale para las Tareas 3–6): el valor en `es.json` es el literal **tal cual**, con cada campo de `.format()`/f-string renombrado a un nombre descriptivo (`{origen}`, `{n}`…), y con toda llave literal duplicada (`{{`/`}}`). Una cadena partida en varias líneas de código se une en un solo valor. Ninguna clave se reutiliza con textos distintos.

**Claves de esta tarea.** Origen en `informes.py` salvo que se indique:

| Clave | Literal de origen |
|---|---|
| `informe.titulo` | `# Informe de portabilidad y seguridad` |
| `informe.seguridad.titulo` | `## Seguridad del paquete` |
| `informe.seguridad.nivel` | `**Nivel de riesgo:** {nivel}` |
| `informe.seguridad.recomendacion` | `**Recomendación:** {texto}` |
| `informe.seguridad.escalada` | el bloque `> Escalado a crítico **por combinación**: …({dims}). Cada uno … refuerzan.` |
| `informe.seguridad.tabla.cabecera` | `\| Dimensión \| Nivel \|` |
| `informe.seguridad.opaco` | `> El paquete contiene material que **no se ha podido analizar** …` |
| `informe.seguridad.sin_hallazgos` | `No se han detectado indicadores estáticos relevantes.` |
| `informe.seguridad.hallazgos` | `### Hallazgos` |
| `informe.seguridad.hallazgo.linea1` | `{i}. {icono} \`{id}\` · \`{ubicacion}\` · ámbito: **{ambito}**` |
| `informe.seguridad.hallazgo.mitigacion` | `   *Mitigación:* {texto}` |
| `informe.seguridad.hallazgo.confianza` | `   *Confianza:* {texto}.` |
| `informe.seguridad.nota_prompt` | `> Los hallazgos de conducta de prompt cubren **formulaciones conocidas**. …` |
| `informe.nota_anulacion` | `NOTA_ANULACION` (las dos líneas, unidas con `\n`) |
| `informe.origen` | `- **Origen:** \`{origen}\`` |
| `informe.skills_analizadas` | `- **Skills analizadas:** {n}` |
| `informe.matriz.titulo` | `## Matriz de compatibilidad` |
| `informe.matriz.skill` | `Skill` (cabecera de la primera columna) |
| `informe.matriz.aviso` | `> Ningún veredicto sustituye a probar la skill en el destino.` |
| `informe.matriz.bloqueado` | `🚫 bloqueado` |
| `informe.matriz.con_bloqueo` | `⚠️ {estado} (con bloqueo)` |
| `informe.detalle.titulo` | `## Detalle por skill` |
| `informe.detalle.bloqueo_anulado` | `> ⚠️ **Exportada pese a un bloqueo …** \`{regla}\` (severidad {severidad}) en \`{fichero}:{linea}\`. …` |
| `informe.detalle.bloqueo` | `> 🚫 **Artefactos no escritos por seguridad:** \`{regla}\` (severidad {severidad}) en \`{fichero}:{linea}\`.` |
| `informe.detalle.origen` | `- Origen: \`{origen}\`` |
| `informe.detalle.descripcion` | `- Descripción: {texto}` |
| `informe.detalle.adaptado` | `**Adaptado automáticamente:**` |
| `informe.portabilidad.titulo` | `**Hallazgos de portabilidad ({n}):**` |
| `informe.portabilidad.linea` | `- {icono} \`{codigo}\` · severidad **{severidad}** — {mensaje}` |
| `informe.destino.cabecera` | `**{icono} · {destino} ({modo})** — {estado}` |
| `informe.destino.mitigacion` | `- *Mitigación:* {texto}` |
| `informe.destino.evidencia` | `  Evidencia: {confianza} · verificado el {fecha}.` |
| `informe.destino.evidencia_perfil` | `  Evidencia del perfil: {confianza} · verificado el {fecha}.` |
| `estado.<v>` | uno por valor de `Estado` (`ETIQUETA`): `compatible`, `adaptación`, `degradado`, `no verificable`, `no compatible` — la clave usa el **valor** de la constante en `modelo.py` |
| `dimension.tecnico`, `.cadena_de_suministro`, `.comportamiento` | `ETIQUETA_DIMENSION` |
| `nivel.bajo`, `.moderado`, `.alto`, `.critico`, `.no_evaluable` | el valor con `_` cambiado por espacio, como se muestra hoy |
| `severidad.critica`, `.alta`, `.media`, `.baja` | los mismos valores en español |
| `confianza.alta`, `.media`, `.baja` y `ambito.exportado`, `.paquete` | ídem |
| `recomendacion.<v>` | los cinco textos de `TEXTO_RECOMENDACION` en `riesgo.py`, con clave = la recomendación (`instalacion_razonable`, `revisar_permisos`, `revision_humana_obligatoria`, `bloqueada`, `revision_incompleta`) |

- [ ] **Step 1: Escribir la prueba de caracterización**

Crear `tests/test_i18n_extraccion.py`:

```python
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
```

- [ ] **Step 2: Ejecutar y comprobar que falla**

Run: `python3 -m unittest discover -s tests -t tests -p "test_i18n_extraccion.py" > /tmp/ext.log 2>&1; echo "codigo=$?"; grep -E "^(OK|FAILED|Ran )" /tmp/ext.log`
Expected: `FAILED` en `test_los_vocabularios_cerrados_tienen_todas_sus_claves` (es.json está vacío).

- [ ] **Step 3: Rellenar `es.json` y sustituir los literales**

Para cada fila de la tabla: añadir la clave a `es.json` con el literal **verbatim** de `informes.py`/`riesgo.py`, y sustituirlo en el código. Las constantes de módulo que guardan texto (`NOTA_ANULACION`, `ETIQUETA_DIMENSION`, `ETIQUETA`, `TEXTO_RECOMENDACION`) **se eliminan** y pasan a funciones, porque se evalúan al importar, antes de que `main()` fije el idioma.

En `informes.py`:

```python
from exporter.i18n import t


def etiqueta_dimension(d: str) -> str:
    return t("dimension." + d)


def etiqueta_estado(estado: str) -> str:
    return t("estado." + estado)


def etiqueta_nivel(nivel: str) -> str:
    return t("nivel." + nivel)
```

Ejemplos de la sustitución (el resto sigue el mismo patrón):

```python
# antes
L = ["## Seguridad del paquete", "",
     "**Nivel de riesgo:** " + veredicto.nivel.replace("_", " "),
     "",
     "**Recomendación:** " + TEXTO_RECOMENDACION[veredicto.recomendacion],
     ""]
# despues
L = [t("informe.seguridad.titulo"), "",
     t("informe.seguridad.nivel", nivel=etiqueta_nivel(veredicto.nivel)),
     "",
     t("informe.seguridad.recomendacion",
       texto=t("recomendacion." + veredicto.recomendacion)),
     ""]
```

```python
# antes
L.append("| {} | {} {} |".format(
    ETIQUETA_DIMENSION[d], ICONO_SEG[nivel], nivel.replace("_", " ")))
# despues
L.append("| {} | {} {} |".format(
    etiqueta_dimension(d), ICONO_SEG[nivel], etiqueta_nivel(nivel)))
```

```python
# antes
return "{} {}".format(ICONO[estado], ETIQUETA[estado])
# despues
return "{} {}".format(ICONO[estado], etiqueta_estado(estado))
```

Los `ICONO*` (emojis) **no** se traducen y se quedan como están. Las cabeceras de la tabla `\| Skill \| …` se construyen con `t("informe.matriz.skill")` en la primera celda y `perfiles[i].label` en las demás.

En `riesgo.py`: **eliminar** `TEXTO_RECOMENDACION`. Antes, `grep -rn "TEXTO_RECOMENDACION" skills tests` y, si alguna prueba lo importa, cambiar esa prueba a `from exporter.i18n import t` y `t("recomendacion." + valor)`.

`resumen_json` **no se toca**: `nivel_riesgo`, `recomendacion_instalacion` y demás siguen siendo el vocabulario en español.

- [ ] **Step 4: Ejecutar las pruebas nuevas y la suite**

Run: `Step 2` y después la suite completa.
Expected: ambas `OK`. Si `tests/golden/*` falla, **no regenerar**: es un literal mal copiado.

- [ ] **Step 5: Comprobar que el español no se movió**

Run: `/tmp/cse-i18n-snapshot.sh /tmp/cse-i18n-despues && diff -r /tmp/cse-i18n-antes /tmp/cse-i18n-despues && echo IGUAL`
Expected: `IGUAL`.

- [ ] **Step 6: Commit**

```bash
git add skills/plugin-to-agentskills/scripts tests/test_i18n_extraccion.py
git commit -m "Mueve el texto del informe y de las recomendaciones al catalogo es

El informe tenia sus cadenas incrustadas y tres diccionarios de etiquetas
evaluados al importar, antes de poder elegir idioma. Pasan a t() y a
funciones. El espanol sale byte a byte igual, comprobado contra una captura
previa del conversor sobre todos los fixtures.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Hallazgos de portabilidad, adaptaciones, señales y motivos → `t()`

**Files:**
- Modify: `skills/plugin-to-agentskills/scripts/convert.py` (`audit_and_adapt`, l.~255–460)
- Modify: `skills/plugin-to-agentskills/scripts/exporter/deteccion.py` (`EXPLICACIONES`)
- Modify: `skills/plugin-to-agentskills/scripts/exporter/compatibilidad.py`
- Modify: `skills/plugin-to-agentskills/scripts/exporter/i18n/es.json`
- Test: `tests/test_i18n_extraccion.py`

**Interfaces:**
- Consumes: `t`.
- Produces: claves `portabilidad.<codigo>`, `adaptacion.<id>`, `senal.<id>`, `compat.*`.

**Claves.** El `<codigo>` es el que ya lleva el `Finding` (`sin-frontmatter`, `sin-description`, `nombre-vs-carpeta`, `description-sin-activacion`, `description-larga`, `description-densa`, `herramientas-claude`, `cuerpo-largo`, `enlace-simbolico`, `fichero-ilegible`, `scripts`, `limite-de-paquete`). Los `Finding` de señales usan `portabilidad.senal`.

| Clave | Origen | Campos |
|---|---|---|
| `portabilidad.sin-frontmatter` | `convert.py` ~l.262 | — |
| `portabilidad.sin-description` | ~l.266 | — |
| `portabilidad.nombre-vs-carpeta` | ~l.273 | `{nombre}`, `{carpeta}` |
| `portabilidad.description-sin-activacion` | ~l.288 | — |
| `portabilidad.description-larga` | ~l.315 | `{bytes}` |
| `portabilidad.description-densa` | ~l.321 | `{bytes}`, `{presupuesto}` |
| `portabilidad.senal` | ~l.367 | `{explicacion}`, `{ubicacion}`, `{muestra}` |
| `portabilidad.herramientas-claude` | ~l.373 | `{herramientas}` |
| `portabilidad.cuerpo-largo` | ~l.380 | `{tokens}`, `{limite}` |
| `portabilidad.enlace-simbolico` | ~l.398 | `{ubicacion}`, `{destino}` |
| `portabilidad.fichero-ilegible` | ~l.417 | `{ruta}`, `{motivo}` |
| `portabilidad.scripts` | ~l.426 | — |
| `portabilidad.limite-de-paquete` | `limite-de-paquete` en `ejecutar` (~l.1084): el `aviso` lo construye `empaquetado.py`; ver Step 3 | — |
| `adaptacion.nombre` | ~l.271 | `{original}`, `{nuevo}` |
| `adaptacion.descripcion-reordenada` | ~l.283 | — |
| `adaptacion.descripcion-ajustada` | ~l.308 | `{origen_bytes}`, `{zip_bytes}`, `{tope_zip}`, `{carpeta_bytes}`, `{tope_carpeta}` |
| `adaptacion.claves-retiradas` | ~l.329 | `{claves}` |
| `adaptacion.rutas-plugin-root` | ~l.336 | — (**lleva `${{CLAUDE_PLUGIN_ROOT}}`**) |
| `adaptacion.claves-a-metadata` | ~l.455 | `{claves}` |
| `senal.<id>` | `EXPLICACIONES` en `deteccion.py`, una por cada una de las 12 | — (`senal.plugin-root` lleva `${{CLAUDE_PLUGIN_ROOT}}`) |
| `compat.capacidad.desconocida` | `compatibilidad.py` | `{nombre}` |
| `compat.capacidad.requerida` | idem | `{nombre}`, `{nivel}` |
| `compat.capacidad.opcional` | idem | `{nombre}`, `{nivel}` |
| `compat.peligro.visto` | idem | `{titulo}`, `{ubicacion}` |
| `compat.evidencia.vencida` | idem | `{fecha}` |
| `compat.adaptacion` | idem | `{texto}` |

- [ ] **Step 1: Escribir las pruebas que fallan**

Añadir a `tests/test_i18n_extraccion.py`:

```python
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
```

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: el comando de la Tarea 3 Step 2.
Expected: `FAILED` en las tres.

- [ ] **Step 3: Rellenar `es.json` y sustituir**

Regla de extracción de la Tarea 3. Patrón de cada `Finding` de `convert.py` (el `code` y la severidad **no cambian**):

```python
# antes
res.findings.append(Finding("media", "nombre-vs-carpeta",
    f"El nombre del frontmatter ('{name}') no coincidía con la carpeta "
    f"('{src_dir.name}'). Se exporta la carpeta con el nombre del frontmatter."))
# despues
res.findings.append(Finding("media", "nombre-vs-carpeta",
    t("portabilidad.nombre-vs-carpeta", nombre=name, carpeta=src_dir.name)))
```

```python
# antes
res.adaptations.append("Rutas ${CLAUDE_PLUGIN_ROOT}/... convertidas en rutas relativas a la skill.")
# despues
res.adaptations.append(t("adaptacion.rutas-plugin-root"))
```

`es.json` lleva: `"adaptacion.rutas-plugin-root": "Rutas ${{CLAUDE_PLUGIN_ROOT}}/... convertidas en rutas relativas a la skill."`.

En `deteccion.py`: **eliminar** el diccionario `EXPLICACIONES`; en `convert.py`, la línea de las señales pasa a:

```python
res.findings.append(Finding(s.severidad_base, s.id,
    t("portabilidad.senal", explicacion=t("senal." + s.id),
      ubicacion=s.ubicacion, muestra=s.muestra)))
```

Antes de borrar `EXPLICACIONES`: `grep -rn "EXPLICACIONES" skills tests`; actualizar cualquier referencia.

`portabilidad.limite-de-paquete`: leer en `empaquetado.py` y en `convert.py` ~l.1075–1085 de dónde sale el texto de `aviso`. Si lo construye `empaquetado.py` con literales, moverlos a `t("portabilidad.limite-de-paquete", ...)` con los campos que use; si no hay literal propio, no se añade clave y se anota en el commit.

En `compatibilidad.py` sustituir los seis literales por `t("compat....", ...)`. Importar con `from exporter.i18n import t`.

- [ ] **Step 4: Ejecutar pruebas, suite y comparación**

Run: Step 2 (debe dar `OK`), la suite completa (`OK`), y `/tmp/cse-i18n-snapshot.sh /tmp/cse-i18n-despues && diff -r /tmp/cse-i18n-antes /tmp/cse-i18n-despues && echo IGUAL`.
Expected: `OK`, `OK`, `IGUAL`.

- [ ] **Step 5: Commit**

```bash
git add skills/plugin-to-agentskills/scripts tests/test_i18n_extraccion.py
git commit -m "Mueve hallazgos de portabilidad, adaptaciones y motivos al catalogo es

Estos textos aparecian en resumen.json y en el informe pero no en la parte
de seguridad que cubria el diseno inicial. Las llaves literales de
\${CLAUDE_PLUGIN_ROOT} se escapan en la plantilla y una prueba lo fija.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Consola y errores de `convert.py`, y la salida de `inspect`

**Files:**
- Modify: `skills/plugin-to-agentskills/scripts/convert.py` (`resolve_source`, `imprimir_inspect`, `ejecutar`, `main`)
- Modify: `skills/plugin-to-agentskills/scripts/exporter/i18n/es.json`
- Test: `tests/test_i18n_extraccion.py`

**Interfaces:**
- Consumes: `t`.
- Produces: claves `consola.*` y `error.*`.

| Clave | Origen | Campos |
|---|---|---|
| `consola.clonando` | `resolve_source` `[info] clonando {} ...` | `{origen}` |
| `consola.skills_encontradas` | `[info] {} skill(s) encontradas.` | `{n}` |
| `consola.skill_riesgo` | `  · {:<40} riesgo={}` — **la alineación `{:<40}` se queda en el código**; el catálogo solo lleva `riesgo={riesgo}` | `{riesgo}` |
| `consola.inspect.nombre_original` | `   nombre original: {}` | `{nombre}` |
| `consola.inspect.descripcion` | `   descripción: {} bytes{}` | `{bytes}`, `{aviso}` |
| `consola.inspect.sin_activacion` | `  ⚠ SIN criterio de activación` | — |
| `consola.inspect.cuerpo` | `   cuerpo: ~{} tokens` | `{tokens}` |
| `consola.inspect.ficheros` | `   ficheros: {}{}` | `{n}`, `{extra}` |
| `consola.inspect.incluye_scripts` | ` (incluye scripts/)` | — |
| `consola.inspect.capacidades` / `.capacidades_ninguna` | `   capacidades exigidas:` / `…: ninguna` | — |
| `consola.inspect.senales` / `.senales_ninguna` | `   señales:` / `   señales: ninguna` | — |
| `consola.inspect.ambiguo` | `   ⚠ Exige capacidades y no dice cuándo cargarse: …` | — |
| `consola.bloqueado` | `[bloqueado] {}: {} en {}:{}. No se escriben sus artefactos.` | `{skill}`, `{regla}`, `{fichero}`, `{linea}` |
| `consola.ok_salida` | `[ok] Salida en: {}` | `{ruta}` |
| `consola.ok.zip`, `.zip_detalle`, `.carpeta_borrada`, `.carpeta`, `.carpeta_detalle`, `.informe` | las líneas `<skill>.zip →`, etc. de `ejecutar` ~l.1110–1123 | según cada una |
| `consola.aviso_riesgo_alto` | `[aviso] Riesgo alto en: {}. Lee el informe antes de subirlas.` | `{skills}` |
| `error.perfil_invalido` | `[error] perfil de destino inválido: {}` | `{detalle}` |
| `error.destino_desconocido` | `[error] destino desconocido: {}. Disponibles: {}` | `{desconocidos}`, `{disponibles}` |
| `error.zip_only_sin_zip` | el párrafo de `--zip-only no tiene sentido…` | `{objetivo}` |
| `error.origen_invalido` | `[error] '{}' no existe como ruta ni parece una URL…` | `{origen}` |
| `error.clon_timeout` | `[error] el clon superó los {} s…` | `{segundos}` |
| `error.clon_fallo` | `[error] git clone falló:\n{}\n\nSi el repositorio es privado…` | `{salida}` |
| `error.sin_skills` | `[error] No se encontró ningún SKILL.md…` | — |
| `error.only_sin_coincidencia` | `[error] --only no coincidió con ninguna skill…` | `{disponibles}` |

Además, **todo otro `print(...)`/`sys.exit("[error]...")` de `convert.py`, `empaquetado.py`, `perfiles.py` y `frontmatter.py`**, que se localiza con:

Run: `grep -nE 'print\(|sys\.exit\(|raise .*Error\(' skills/plugin-to-agentskills/scripts/convert.py skills/plugin-to-agentskills/scripts/exporter/*.py`

Cada literal visible para el usuario recibe su clave `consola.*` o `error.*`. Los mensajes de **excepciones internas** que solo ven los desarrolladores (`ReglaInvalida`, `PerfilInvalido` dentro del propio cargador) **se quedan en español fijo**: son diagnóstico del repositorio, no salida para el usuario, y `main` ya los envuelve con `error.perfil_invalido`.

El texto de `--help` y de los `help=` de `argparse` **no se traduce** (spec §4).

- [ ] **Step 1: Escribir la prueba que falla**

Añadir a `tests/test_i18n_extraccion.py`:

```python
class Consola(unittest.TestCase):

    def test_estan_las_claves_de_consola_y_error(self):
        es = claves("es")
        esperadas = ["consola.clonando", "consola.skills_encontradas",
                     "consola.skill_riesgo", "consola.ok_salida", "consola.bloqueado",
                     "consola.aviso_riesgo_alto", "error.destino_desconocido",
                     "error.zip_only_sin_zip", "error.sin_skills",
                     "error.only_sin_coincidencia", "error.origen_invalido",
                     "error.clon_timeout", "error.clon_fallo"]
        self.assertEqual(set(esperadas) - set(es), set())

    def test_no_quedan_prefijos_de_mensaje_sin_traducir(self):
        # Todo `[error]`, `[info]`, `[aviso]`, `[ok]` o `[bloqueado]` que el
        # usuario ve nace de una clave; el prefijo vive dentro del catalogo.
        import re
        origen = (RAIZ_SCRIPTS / "convert.py").read_text(encoding="utf-8")
        sueltos = re.findall(r'["\']\[(?:error|info|aviso|ok|bloqueado)\]', origen)
        # Unica excepcion fija: el error de idioma desconocido de main().
        self.assertEqual(len(sueltos), 1, sueltos)
```

- [ ] **Step 2: Ejecutar y comprobar que falla**

Run: el comando de la Tarea 3 Step 2.
Expected: `FAILED`.

- [ ] **Step 3: Sustituir**

Patrón:

```python
# antes
print("[info] clonando {} ...".format(src))
# despues
print(t("consola.clonando", origen=src))
```

```python
# antes
sys.exit("[error] el clon superó los {} s y se ha cancelado.".format(TIMEOUT_CLON))
# despues
sys.exit(t("error.clon_timeout", segundos=TIMEOUT_CLON))
```

`imprimir_inspect` conserva las alineaciones `{:<24}` y `{:<20}` en el código y solo traduce las etiquetas. Importar `from exporter.i18n import t` arriba de `convert.py`; **el `i18n` ya importado en la Tarea 2 sigue en uso** para `fijar_idioma`.

- [ ] **Step 4: Ejecutar pruebas, suite y comparación**

Run: Step 2 (`OK`), suite (`OK`), `/tmp/cse-i18n-snapshot.sh /tmp/cse-i18n-despues && diff -r /tmp/cse-i18n-antes /tmp/cse-i18n-despues && echo IGUAL`.
Expected: `OK`, `OK`, `IGUAL` (incluye los `.stdout` y `.stderr`).

- [ ] **Step 5: Commit**

```bash
git add skills/plugin-to-agentskills/scripts tests/test_i18n_extraccion.py
git commit -m "Mueve la consola, inspect y los errores de convert.py al catalogo es

Los mensajes de consola y de error eran lo unico que el usuario lee sin
abrir el informe. Las alineaciones de columna se quedan en el codigo para
no depender de la longitud de cada traduccion.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Seguridad: hallazgos estructurales, reglas y peligros de los perfiles

**Files:**
- Modify: `skills/plugin-to-agentskills/scripts/exporter/seguridad/estructural.py` (8 llamadas a `_h(...)`: l.118, 131, 159, 191, 243, 315, 324, 339, 353)
- Modify: `skills/plugin-to-agentskills/scripts/exporter/seguridad/patrones.py` (l.184–190)
- Modify: `skills/plugin-to-agentskills/scripts/exporter/compatibilidad.py` y `informes.py` (los `peligro["titulo"]`/`["mitigacion"]`)
- Modify: `skills/plugin-to-agentskills/scripts/exporter/i18n/es.json`
- Test: `tests/test_i18n_extraccion.py`, `tests/test_seg_estructural.py` (solo si alguna aserción dependía de la forma)

**Interfaces:**
- Consumes: `t`, `t_opcional`.
- Produces: claves `estructural.<id>[.<variante>].{titulo,mitigacion}` en `es.json`; contrato de sobrescritura `regla.<ID>.{titulo,detalle,mitigacion}` y `peligro.<id>.{titulo,detalle,mitigacion}` en los demás catálogos.

- [ ] **Step 1: Escribir las pruebas que fallan**

Añadir a `tests/test_i18n_extraccion.py`:

```python
class Seguridad(unittest.TestCase):

    def test_es_json_no_lleva_claves_de_regla_ni_de_peligro(self):
        # Review: el espanol de reglas y peligros vive en reglas.json y en
        # targets/*.json; duplicarlo aqui lo haria divergir.
        malas = [k for k in claves("es") if k.startswith(("regla.", "peligro."))]
        self.assertEqual(malas, [])

    def test_los_hallazgos_estructurales_tienen_texto_en_es(self):
        import re
        origen = (RAIZ_SCRIPTS / "exporter" / "seguridad" / "estructural.py"
                  ).read_text(encoding="utf-8")
        usadas = set(re.findall(r't\("(estructural\.[a-z0-9_.\-]+)"', origen))
        self.assertTrue(usadas, "estructural.py no usa t()")
        self.assertEqual(usadas - set(claves("es")), set())

    def test_t_opcional_aplica_a_titulo_y_mitigacion_de_las_reglas(self):
        import tempfile
        from exporter import i18n
        from exporter.seguridad import patrones
        reglas = patrones.cargar_reglas()
        regla = reglas[0]
        tmp = Path(tempfile.mkdtemp())
        (tmp / "es.json").write_text(json.dumps(
            {"_meta": {"idioma": "es", "nombre": "x"}}), encoding="utf-8")
        (tmp / "en.json").write_text(json.dumps(
            {"_meta": {"idioma": "en", "nombre": "x"},
             "regla." + regla["id"] + ".titulo": "TITLE-EN"}), encoding="utf-8")
        anterior = i18n.DIRECTORIO
        self.addCleanup(lambda: (setattr(i18n, "DIRECTORIO", anterior),
                                 i18n._cache.clear(), i18n.fijar_idioma("es")))
        i18n.DIRECTORIO = tmp
        i18n._cache.clear()
        i18n.fijar_idioma("en")
        self.assertEqual(patrones.titulo_de(regla), "TITLE-EN")
        # Sin sobrescritura para la mitigacion: queda el espanol de origen.
        self.assertEqual(patrones.mitigacion_de(regla), regla["mitigacion"])
```

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: el comando de la Tarea 3 Step 2.
Expected: `FAILED` (no existe `titulo_de`/`mitigacion_de`; `estructural.py` no usa `t()`).

- [ ] **Step 3: Reglas de `reglas.json`**

En `patrones.py`, añadir tras `RUTA_REGLAS`:

```python
from exporter.i18n import t_opcional


def titulo_de(regla) -> str:
    return t_opcional("regla.{}.titulo".format(regla["id"]), regla["titulo"])


def detalle_de(regla) -> str:
    return t_opcional("regla.{}.detalle".format(regla["id"]), regla["detalle"])


def mitigacion_de(regla) -> str:
    return t_opcional("regla.{}.mitigacion".format(regla["id"]), regla["mitigacion"])
```

Y en el `Hallazgo(...)` de la l.~190: `titulo=titulo_de(r), mitigacion=mitigacion_de(r)`. `reglas.json` **no se toca**.

- [ ] **Step 4: Hallazgos estructurales**

Cada llamada `_h(..., titulo, mitigacion)` de `estructural.py` pasa a `_h(..., t("estructural.<ID>.titulo", ...), t("estructural.<ID>.mitigacion", ...))`. Las dos llamadas que comparten `SEC-DEP-SIN-FIJAR-002` (l.159 y l.191) usan **variantes**: `estructural.SEC-DEP-SIN-FIJAR-002.pyproject.titulo` y `….npm.titulo` (o las que correspondan según el fichero que analiza cada una; leer ambas llamadas y nombrar la variante por el tipo de fichero). Los campos con datos (`{fichero}`, `{paquete}`…) se nombran según lo que interpole el literal actual. El `id` del hallazgo **no cambia**.

Importar `from exporter.i18n import t`.

- [ ] **Step 5: Peligros de los perfiles**

Los peligros viven en `targets/*.json` en español. Donde el código los lee:

- `compatibilidad.py`: `peligro["titulo"]` → `t_opcional("peligro.{}.titulo".format(peligro["id"]), peligro["titulo"])`.
- `informes.py` (bloque «Mitigación» del detalle por destino): `p["mitigacion"]` → `t_opcional("peligro.{}.mitigacion".format(p["id"]), p["mitigacion"])`.

`resumen.json` solo lleva `[p["id"] for p in ev.peligros]`: no cambia.

- [ ] **Step 6: Ejecutar pruebas, suite y comparación**

Run: Step 2 (`OK`), suite (`OK`), `/tmp/cse-i18n-snapshot.sh /tmp/cse-i18n-despues && diff -r /tmp/cse-i18n-antes /tmp/cse-i18n-despues && echo IGUAL`; y `python3 tests/generar_golden.py && git diff --stat tests/golden tests/golden-seguridad`.
Expected: `OK`, `OK`, `IGUAL`, y el `git diff --stat` **vacío**. Si no está vacío, hay un literal mal copiado: corregirlo, no regenerar.

- [ ] **Step 7: Los cuatro validadores del CI**

Run:
```bash
python3 .github/validate_plugin.py . ; echo "codigo=$?"
python3 .github/validar_estatico.py . ; echo "codigo=$?"
python3 -m venv /tmp/venv-cse && /tmp/venv-cse/bin/pip install --quiet jsonschema
/tmp/venv-cse/bin/python .github/validar_perfiles.py . ; echo "codigo=$?"
/tmp/venv-cse/bin/python .github/validar_reglas.py . ; echo "codigo=$?"
```
Expected: cuatro `codigo=0`.

- [ ] **Step 8: Commit**

```bash
git add skills/plugin-to-agentskills/scripts tests/test_i18n_extraccion.py
git commit -m "Hace traducibles los hallazgos de seguridad y los peligros de los perfiles

reglas.json y targets/*.json siguen siendo la fuente del espanol, porque su
esquema y sus validadores los leen; los demas idiomas los sobrescriben por
clave. Los hallazgos estructurales, que no tenian donde vivir, pasan a
es.json. El espanol sale igual y los golden no se regeneran.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Validador de catálogos `validar_idiomas.py` y paso de CI

**Files:**
- Create: `.github/validar_idiomas.py`
- Modify: `.github/workflows/validar.yml`
- Test: `tests/test_validar_idiomas.py`

**Interfaces:**
- Consumes: la estructura de `es.json`, `reglas.json`, `targets/*.json`.
- Produces: `main(raiz: Path) -> int` en `.github/validar_idiomas.py`; `comprobar(raiz) -> list` (lista de errores, vacía si todo bien) para poder probarlo.

El validador comprueba, para cada catálogo `L` distinto de `es`:

1. mismas claves que `es.json` **más** las `regla.*`/`peligro.*` que correspondan (sección «Reglas y peligros» abajo);
2. mismos marcadores `{nombre}` por clave (conjunto igual), obtenidos con `string.Formatter().parse`;
3. ninguna plantilla vacía;
4. `_meta.idioma` igual al nombre del fichero y `_meta.nombre` no vacío;
5. cada clave `regla.<ID>.<campo>` apunta a una regla que existe y con `campo` ∈ {`titulo`,`detalle`,`mitigacion`}; cada `peligro.<id>.<campo>`, a un peligro que existe en algún perfil;
6. **completitud de reglas y peligros**: para cada regla de `reglas.json` y cada peligro de los perfiles, los tres textos están presentes en `L`;
7. `es.json` **no** lleva claves `regla.*` ni `peligro.*`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `tests/test_validar_idiomas.py`:

```python
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


def copia():
    """Copia minima del repositorio con solo lo que mira el validador."""
    tmp = Path(tempfile.mkdtemp())
    for rel in ["skills/plugin-to-agentskills/scripts/exporter/i18n",
                "skills/plugin-to-agentskills/scripts/exporter/targets",
                "skills/plugin-to-agentskills/scripts/exporter/seguridad/reglas.json"]:
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


class Validador(unittest.TestCase):

    def setUp(self):
        self.tmp = copia()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.dir = self.tmp / I18N

    def errores(self):
        return validar.comprobar(self.tmp)

    def test_el_repositorio_actual_es_valido(self):
        self.assertEqual(validar.comprobar(RAIZ), [])

    def test_clave_de_menos(self):
        for f in self.dir.glob("*.json"):
            if f.stem == "es":
                continue
            datos = leer(f)
            datos.pop(next(k for k in datos if k.startswith("informe.")))
            escribir(f, datos)
            break
        else:
            self.skipTest("todavia no hay catalogos distintos de es")
        self.assertTrue(any("falta" in e for e in self.errores()), self.errores())

    def test_clave_de_mas(self):
        otros = [f for f in self.dir.glob("*.json") if f.stem != "es"]
        if not otros:
            self.skipTest("todavia no hay catalogos distintos de es")
        datos = leer(otros[0])
        datos["informe.no_existe"] = "x"
        escribir(otros[0], datos)
        self.assertTrue(any("sobra" in e for e in self.errores()), self.errores())

    def test_marcador_distinto(self):
        otros = [f for f in self.dir.glob("*.json") if f.stem != "es"]
        if not otros:
            self.skipTest("todavia no hay catalogos distintos de es")
        datos = leer(otros[0])
        clave = next(k for k, v in leer(self.dir / "es.json").items()
                     if "{origen}" in str(v))
        datos[clave] = datos[clave].replace("{origen}", "{origin}")
        escribir(otros[0], datos)
        self.assertTrue(any("marcador" in e for e in self.errores()), self.errores())

    def test_plantilla_vacia(self):
        otros = [f for f in self.dir.glob("*.json") if f.stem != "es"]
        if not otros:
            self.skipTest("todavia no hay catalogos distintos de es")
        datos = leer(otros[0])
        datos[next(k for k in datos if k.startswith("informe."))] = "  "
        escribir(otros[0], datos)
        self.assertTrue(any("vacía" in e for e in self.errores()), self.errores())

    def test_meta_no_coincide_con_el_fichero(self):
        escribir(self.dir / "zz.json",
                 dict(leer(self.dir / "es.json"), _meta={"idioma": "qq", "nombre": "Z"}))
        self.assertTrue(any("_meta" in e for e in self.errores()), self.errores())

    def test_regla_inexistente(self):
        escribir(self.dir / "zz.json", dict(
            leer(self.dir / "es.json"), _meta={"idioma": "zz", "nombre": "Z"},
            **{"regla.SEC-NO-EXISTE-001.titulo": "x"}))
        self.assertTrue(any("SEC-NO-EXISTE-001" in e for e in self.errores()),
                        self.errores())

    def test_es_no_lleva_claves_de_regla(self):
        es = leer(self.dir / "es.json")
        es["regla.SEC-EXEC-REMOTO-001.titulo"] = "x"
        escribir(self.dir / "es.json", es)
        self.assertTrue(any("es.json" in e and "regla" in e for e in self.errores()),
                        self.errores())

    def test_regla_sin_traducir_en_otro_idioma(self):
        otros = [f for f in self.dir.glob("*.json") if f.stem != "es"]
        if not otros:
            self.skipTest("todavia no hay catalogos distintos de es")
        datos = leer(otros[0])
        datos.pop(next(k for k in datos if k.startswith("regla.")))
        escribir(otros[0], datos)
        self.assertTrue(any("regla." in e for e in self.errores()), self.errores())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: `python3 -m unittest discover -s tests -t tests -p "test_validar_idiomas.py" > /tmp/val.log 2>&1; echo "codigo=$?"; grep -E "^(OK|FAILED|Ran |FileNotFound)" /tmp/val.log`
Expected: error por no existir `.github/validar_idiomas.py`.

- [ ] **Step 3: Implementar el validador**

Crear `.github/validar_idiomas.py` (solo biblioteca estándar; comentarios sin acentos, mensajes con acentos):

```python
#!/usr/bin/env python3
"""Valida los catalogos de idioma de exporter/i18n/.

Un catalogo distinto de `es` es valido si tiene las mismas claves y los
mismos marcadores que `es.json`, mas la traduccion completa de cada regla de
seguridad y de cada peligro de los perfiles de destino. Asi un idioma
incompleto rompe el CI en vez de degradar en silencio al usuario.

Solo biblioteca estandar: no necesita jsonschema.
"""

import json
import string
import sys
from pathlib import Path

I18N = Path("skills/plugin-to-agentskills/scripts/exporter/i18n")
TARGETS = Path("skills/plugin-to-agentskills/scripts/exporter/targets")
REGLAS = Path("skills/plugin-to-agentskills/scripts/exporter/seguridad/reglas.json")
CAMPOS = ("titulo", "detalle", "mitigacion")


def _marcadores(plantilla: str) -> set:
    return {campo for _, campo, _, _ in string.Formatter().parse(plantilla) if campo}


def _leer(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


def comprobar(raiz: Path) -> list:
    errores = []
    catalogos = {}
    for ruta in sorted((raiz / I18N).glob("*.json")):
        try:
            catalogos[ruta.stem] = _leer(ruta)
        except ValueError as e:
            errores.append("{}: JSON inválido ({})".format(ruta.name, e))
    if "es" not in catalogos:
        return errores + ["falta es.json, el catálogo de referencia"]

    reglas = {r["id"] for r in _leer(raiz / REGLAS)["reglas"]}
    peligros = set()
    for ruta in sorted((raiz / TARGETS).glob("*.json")):
        if not ruta.name.startswith("_"):
            peligros |= {p["id"] for p in _leer(ruta).get("peligros", [])}

    esperadas_extra = set()
    for rid in reglas:
        esperadas_extra |= {"regla.{}.{}".format(rid, c) for c in CAMPOS}
    for pid in peligros:
        esperadas_extra |= {"peligro.{}.{}".format(pid, c) for c in CAMPOS}

    base = {k: v for k, v in catalogos["es"].items() if k != "_meta"}
    for k in base:
        if k.startswith(("regla.", "peligro.")):
            errores.append("es.json: lleva la clave {} (regla/peligro: el español "
                           "vive en reglas.json y en targets/)".format(k))

    for codigo, datos in catalogos.items():
        meta = datos.get("_meta")
        if (not isinstance(meta, dict) or meta.get("idioma") != codigo
                or not str(meta.get("nombre", "")).strip()):
            errores.append("{}.json: _meta debe llevar idioma='{}' y un nombre".format(
                codigo, codigo))
        if codigo == "es":
            continue

        propias = {k: v for k, v in datos.items() if k != "_meta"}
        esperadas = set(base) | esperadas_extra
        for k in sorted(esperadas - set(propias)):
            errores.append("{}.json: falta la clave {}".format(codigo, k))
        for k in sorted(set(propias) - esperadas):
            errores.append("{}.json: sobra la clave {}".format(codigo, k))
        for k, v in propias.items():
            if not isinstance(v, str) or not v.strip():
                errores.append("{}.json: la plantilla {} está vacía".format(codigo, k))
                continue
            try:
                m_prop = _marcadores(v)
            except ValueError as e:
                errores.append("{}.json: {} no es una plantilla válida ({})".format(
                    codigo, k, e))
                continue
            if k in base and m_prop != _marcadores(base[k]):
                errores.append("{}.json: los marcadores de {} no coinciden con es "
                               "({} frente a {})".format(
                                   codigo, k, sorted(m_prop), sorted(_marcadores(base[k]))))
    return errores


def main(raiz: Path) -> int:
    errores = comprobar(raiz)
    for e in errores:
        print("[error] " + e, file=sys.stderr)
    if errores:
        return 1
    n = len([p for p in (raiz / I18N).glob("*.json")])
    print("{} catálogo(s) de idioma válidos.".format(n))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
```

Nota: la clave `regla.*` de **reglas con id que mencionan 'peligro' en `es.json`** se detecta en el mismo bucle; el test `test_es_no_lleva_claves_de_regla` comprueba el texto `es.json` + `regla`.

- [ ] **Step 4: Ejecutar pruebas y validador**

Run: Step 2; después `python3 .github/validar_idiomas.py . ; echo "codigo=$?"`.
Expected: `OK`; `1 catálogo(s) de idioma válidos.` y `codigo=0` (solo existe `es`).

- [ ] **Step 5: Paso de CI**

En `.github/workflows/validar.yml`, tras el paso «Validar reglas de seguridad y su cobertura por fixtures»:

```yaml
      - name: Validar los catálogos de idioma
        run: python3 .github/validar_idiomas.py .
```

- [ ] **Step 6: Commit**

```bash
git add .github/validar_idiomas.py .github/workflows/validar.yml tests/test_validar_idiomas.py
git commit -m "Anade el validador de catalogos de idioma y su paso de CI

Un catalogo con una clave de menos, de mas o con un marcador distinto
degradaria en silencio al usuario de ese idioma. El validador lo convierte
en un fallo de CI y exige la traduccion completa de reglas y peligros.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Catálogo inglés (`en.json`)

**Files:**
- Create: `skills/plugin-to-agentskills/scripts/exporter/i18n/en.json`
- Test: `tests/test_idiomas_cli.py`

**Interfaces:**
- Consumes: todas las claves de `es.json` (Tareas 3–6) y las reglas/peligros de `reglas.json` y `targets/*.json`.

**Método.** `en.json` se construye con el validador como guía: tiene que pasar `python3 .github/validar_idiomas.py .` sin errores. Lo lleva:

- `_meta`: `{"idioma": "en", "nombre": "English"}`.
- Todas las claves de `es.json`, traducidas.
- `regla.<ID>.{titulo,detalle,mitigacion}` por **cada** regla de `reglas.json` (22 textos de titulo, detalle y mitigacion) y `peligro.<id>.{titulo,detalle,mitigacion}` por cada peligro de los perfiles (4).

**Reglas de traducción** (valen también para `fr.json`):

1. **Los marcadores `{campo}` se copian idénticos**; el validador lo exige. Las llaves literales siguen duplicadas (`${{CLAUDE_PLUGIN_ROOT}}`).
2. Los emojis, las comillas de código (backticks), `**negritas**` y el formato Markdown se conservan tal cual.
3. **Glosario fijo** — el mismo término siempre se traduce igual:

| es | en | fr |
|---|---|---|
| hallazgo | finding | constat |
| mitigación | mitigation | mesure corrective |
| riesgo | risk | risque |
| nivel de riesgo | risk level | niveau de risque |
| cadena de suministro | supply chain | chaîne d'approvisionnement |
| destino (plataforma) | target | cible |
| skill | skill | skill |
| paquete | package | paquet |
| ámbito | scope | périmètre |
| confianza | confidence | confiance |
| bloqueado | blocked | bloqué |
| compatible con adaptación | compatible with adaptation | compatible avec adaptation |
| degradado | degraded | dégradé |
| no verificable | not verifiable | non vérifiable |
| no compatible | not compatible | non compatible |

   Los valores de `nivel.*` (en): low, moderate, high, critical, not assessable; (fr): faible, modéré, élevé, critique, non évaluable. `severidad.*` (en): critical, high, medium, low; (fr): critique, haute, moyenne, basse.
4. **Nunca** afirmar que el repositorio «es malicioso» (`malicious`/`malveillant`). Se dice «patterns commonly associated with…», «indicators», «potentially». Hay una prueba que lo verifica (Tarea 9).
5. **No citar literalmente patrones peligrosos** en `regla.*.detalle` ni `mitigacion` (Review Focus 7): se describen con palabras («downloads a script from the network and passes it straight to the interpreter»). `i18n/*.json` tiene ámbito `exportado`; una frase de inyección de prompt o la combinación descarga-e-interpreta en claro bloquea la autoexportación.
6. Un texto que en español es una frase completa sigue siéndolo; no se resume ni se amplía.

**Ejemplos** (el resto sigue el mismo criterio):

```json
{
  "_meta": {"idioma": "en", "nombre": "English"},
  "informe.titulo": "# Portability and security report",
  "informe.seguridad.titulo": "## Package security",
  "informe.seguridad.nivel": "**Risk level:** {nivel}",
  "nivel.alto": "high",
  "regla.SEC-EXEC-REMOTO-001.titulo": "Downloads remote content and runs it",
  "regla.SEC-EXEC-REMOTO-001.detalle": "A script is downloaded from the network and handed straight to the interpreter, with no hash or signature check. Whoever controls that domain controls what runs on your machine, today and at any point in the future.",
  "regla.SEC-EXEC-REMOTO-001.mitigacion": "Replace it with a versioned dependency that has a verifiable hash, or download and review the script before running it."
}
```

- [ ] **Step 1: Escribir las pruebas que fallan**

Añadir a `tests/test_idiomas_cli.py`:

```python
class Ingles(unittest.TestCase):

    def export(self, fixture, *extra):
        tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, tmp)
        r = correr("export", str(FIXTURES / fixture), "--out", tmp,
                   "--anular-revision-seguridad", "--lang", "en", *extra)
        informe = (Path(tmp) / "INFORME-PORTABILIDAD.md")
        return r, (informe.read_text(encoding="utf-8") if informe.exists() else "")

    def test_el_informe_sale_en_ingles(self):
        r, informe = self.export("repo-descarga-remota")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("# Portability and security report", informe)
        self.assertIn("**Risk level:**", informe)
        self.assertNotIn("Nivel de riesgo", informe)
        self.assertNotIn("Seguridad del paquete", informe)

    def test_la_regla_sale_traducida(self):
        _, informe = self.export("repo-descarga-remota")
        self.assertIn("Downloads remote content and runs it", informe)
        self.assertNotIn("Descarga contenido remoto", informe)

    def test_la_consola_sale_en_ingles(self):
        r, _ = self.export("repo-descarga-remota")
        self.assertNotIn("[info] ", r.stdout.replace("[info] 1 skill", ""))
        self.assertRegex(r.stdout, r"\[info\] \d+ skill\(s\) found")

    def test_los_errores_salen_en_ingles(self):
        r = correr("inspect", "/no/existe/seguro", "--lang", "en")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("no existe como ruta", r.stderr + r.stdout)
```

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: `python3 -m unittest discover -s tests -t tests -p "test_idiomas_cli.py" > /tmp/cli.log 2>&1; echo "codigo=$?"; grep -E "^(OK|FAILED|Ran )" /tmp/cli.log`
Expected: `FAILED` (`xx` desconocido: no existe `en.json`).

- [ ] **Step 3: Escribir `en.json`**

Recorrer `es.json` clave a clave y los 26 textos de reglas/peligros siguiendo las reglas de traducción. Para listar lo que falta en cualquier momento: `python3 .github/validar_idiomas.py .` (imprime cada clave ausente).

- [ ] **Step 4: Validador y pruebas**

Run: `python3 .github/validar_idiomas.py . ; echo "codigo=$?"` → `codigo=0`; después Step 2 → `OK`; después la suite completa → `OK`.

- [ ] **Step 5: Comprobar la autoexportación (Review Focus 7)**

Run: `python3 skills/plugin-to-agentskills/scripts/convert.py export . --only plugin-to-agentskills --anular-revision-seguridad --out /tmp/cse-auto > /tmp/auto.log 2>&1; echo "codigo=$?"; grep -c "bloqueado" /tmp/auto.log`
Expected: `codigo=0` y `0`. Si hay bloqueo: reformular la frase del catálogo en palabras, **sin ampliar la exención de `_es_el_catalogo`**.

- [ ] **Step 6: Commit**

```bash
git add skills/plugin-to-agentskills/scripts/exporter/i18n/en.json tests/test_idiomas_cli.py
git commit -m "Anade el catalogo en ingles

Traduce el informe, la consola, los errores y las 22 reglas y 4 peligros.
Las frases que describen patrones peligrosos se redactan con palabras: el
catalogo viaja dentro de la skill y un literal bloquearia la
autoexportacion.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Catálogo francés (`fr.json`) y pruebas transversales

**Files:**
- Create: `skills/plugin-to-agentskills/scripts/exporter/i18n/fr.json`
- Create: `tests/test_idiomas_golden.py`
- Modify: `tests/generar_golden.py`
- Create: `tests/golden-i18n/en/*.json`, `tests/golden-i18n/fr/*.json`
- Test: `tests/test_idiomas_cli.py`

**Interfaces:**
- Consumes: el catálogo de la Tarea 8 como modelo de claves; el glosario de la Tarea 8.

- [ ] **Step 1: Escribir las pruebas que fallan**

Añadir a `tests/test_idiomas_cli.py`:

```python
class Frances(unittest.TestCase):

    def test_el_informe_sale_en_frances(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = correr("export", str(FIXTURES / "repo-descarga-remota"), "--out", tmp,
                       "--anular-revision-seguridad", "--lang", "fr")
            informe = (Path(tmp) / "INFORME-PORTABILIDAD.md").read_text(encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("**Niveau de risque :**", informe)
        self.assertNotIn("Nivel de riesgo", informe)
        self.assertNotIn("Risk level", informe)
```

Crear `tests/test_idiomas_golden.py`:

```python
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ayuda import RAIZ, RAIZ_SCRIPTS

CONVERT = RAIZ_SCRIPTS / "convert.py"
FIXTURES = RAIZ / "tests" / "fixtures"
GOLDEN = RAIZ / "tests" / "golden-i18n"
IDIOMAS = ("en", "fr")
# Un fixture de portabilidad y uno de seguridad bastan: los golden de es ya
# cubren todos; aqui se comprueba que el idioma no altera nada mas que el texto.
CASOS = ["repo-descarga-remota", "repo-escalada"]
FECHA = "2026-08-08"

CAMPOS_DE_TEXTO = {"titulo", "mitigacion", "mensaje", "motivos", "adaptaciones"}


def exportar(fixture, idioma, destino):
    return subprocess.run(
        [sys.executable, str(CONVERT), "export", str(FIXTURES / fixture),
         "--out", str(destino), "--anular-revision-seguridad", "--lang", idioma],
        capture_output=True, text=True, cwd=str(RAIZ),
        env=dict(os.environ, CSE_FECHA=FECHA))


def resumen(fixture, idioma):
    tmp = tempfile.mkdtemp()
    try:
        r = exportar(fixture, idioma, Path(tmp))
        assert r.returncode == 0, r.stderr
        datos = json.loads((Path(tmp) / "resumen.json").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmp)
    datos["origen"] = "<origen>"
    return datos


def sin_texto(nodo):
    """Quita los campos de texto libre; deja claves y vocabularios cerrados."""
    if isinstance(nodo, dict):
        return {k: sin_texto(v) for k, v in nodo.items() if k not in CAMPOS_DE_TEXTO}
    if isinstance(nodo, list):
        return [sin_texto(x) for x in nodo]
    return nodo


class Golden(unittest.TestCase):

    def test_cada_idioma_produce_su_resumen_esperado(self):
        for idioma in IDIOMAS:
            for caso in CASOS:
                with self.subTest(idioma=idioma, caso=caso):
                    esperado = json.loads(
                        (GOLDEN / idioma / (caso + ".json")).read_text(encoding="utf-8"))
                    self.assertEqual(resumen(caso, idioma), esperado,
                                     "Si es deseado: python3 tests/generar_golden.py")


class ResumenEstable(unittest.TestCase):
    """Review Focus 5: resumen.json solo cambia de idioma en sus textos."""

    def test_misma_forma_y_mismos_vocabularios_en_todos_los_idiomas(self):
        for caso in CASOS:
            base = sin_texto(resumen(caso, "es"))
            for idioma in IDIOMAS:
                with self.subTest(idioma=idioma, caso=caso):
                    self.assertEqual(sin_texto(resumen(caso, idioma)), base)


class Redaccion(unittest.TestCase):
    """Restriccion 7: nunca «este repositorio es malicioso», en ningun idioma."""

    PROHIBIDAS = {
        "es": r"(?:este|el) repositorio es malicios",
        "en": r"(?:this|the) (?:repository|repo) is malicious",
        "fr": r"(?:ce|le) d[ée]p[ôo]t est malveillant",
    }

    def test_ninguna_plantilla_lo_afirma(self):
        for codigo, patron in self.PROHIBIDAS.items():
            ruta = RAIZ_SCRIPTS / "exporter" / "i18n" / (codigo + ".json")
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            for clave, texto in datos.items():
                if clave == "_meta":
                    continue
                with self.subTest(idioma=codigo, clave=clave):
                    self.assertIsNone(re.search(patron, texto, re.I), texto)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: `python3 -m unittest discover -s tests -t tests -p "test_idiomas_*.py" > /tmp/idi.log 2>&1; echo "codigo=$?"; grep -E "^(OK|FAILED|Ran )" /tmp/idi.log`
Expected: `FAILED`.

- [ ] **Step 3: Escribir `fr.json`**

Mismo método y reglas de traducción que la Tarea 8 (glosario, marcadores idénticos, sin citar patrones, sin «malveillant»). `_meta`: `{"idioma": "fr", "nombre": "Français"}`. Convenciones del francés: espacio fino antes de `:`, `;`, `?`, `!` (usar el espacio normal es aceptable; se mantiene el mismo criterio en todo el fichero) y comillas `« »`. Ejemplos:

```json
{
  "_meta": {"idioma": "fr", "nombre": "Français"},
  "informe.titulo": "# Rapport de portabilité et de sécurité",
  "informe.seguridad.titulo": "## Sécurité du paquet",
  "informe.seguridad.nivel": "**Niveau de risque :** {nivel}",
  "nivel.alto": "élevé",
  "regla.SEC-EXEC-REMOTO-001.titulo": "Télécharge du contenu distant et l'exécute"
}
```

Guía: `python3 .github/validar_idiomas.py .` lista lo que falta.

- [ ] **Step 4: Regenerar los golden de idioma (primera y única vez)**

Añadir a `tests/generar_golden.py`, **al final** de `main()` antes del `return 0`:

```python
    from test_idiomas_golden import CASOS, IDIOMAS, GOLDEN as GOLDEN_I18N, resumen  # noqa: E402
    for idioma in IDIOMAS:
        (GOLDEN_I18N / idioma).mkdir(parents=True, exist_ok=True)
        for caso in CASOS:
            (GOLDEN_I18N / idioma / (caso + ".json")).write_text(
                json.dumps(resumen(caso, idioma), ensure_ascii=False, indent=2,
                           sort_keys=True) + "\n", encoding="utf-8")
            print("regenerado", idioma, caso)
```

Run: `python3 tests/generar_golden.py && git status --short tests/golden tests/golden-seguridad tests/golden-i18n`
Expected: **solo** aparecen ficheros nuevos bajo `tests/golden-i18n/`. Si `tests/golden/` o `tests/golden-seguridad/` aparecen modificados, algo cambió el español: parar y encontrar por qué.

Leer los cuatro golden nuevos **entero**, con ojos de hablante: comprobar que no hay español, que los vocabularios de `resumen.json` siguen en español (`"severidad": "alta"`) y que las frases tienen sentido.

- [ ] **Step 5: Ejecutar pruebas, suite y validadores**

Run: Step 2 (`OK`), la suite completa (`OK`), `python3 .github/validar_idiomas.py .` (`2` catálogos… `3 catálogo(s)`), `python3 .github/validar_estatico.py .`.
Expected: todo en verde.

- [ ] **Step 6: Autoexportación**

Run: el comando del Step 5 de la Tarea 8.
Expected: `codigo=0`, `0` bloqueos.

- [ ] **Step 7: Commit**

```bash
git add skills/plugin-to-agentskills/scripts/exporter/i18n/fr.json \
        tests/test_idiomas_golden.py tests/test_idiomas_cli.py \
        tests/generar_golden.py tests/golden-i18n
git commit -m "Anade el catalogo frances y las pruebas transversales de idioma

Un golden por idioma sobre un fixture de portabilidad y otro de seguridad,
una prueba de que resumen.json solo cambia en sus textos, y la de redaccion
en los tres idiomas.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 10: `--lang auto` (detección opt-in del idioma del sistema)

**Files:**
- Modify: `skills/plugin-to-agentskills/scripts/exporter/i18n/__init__.py`
- Modify: `skills/plugin-to-agentskills/scripts/convert.py`
- Test: `tests/test_idiomas_cli.py`

**Interfaces:**
- Consumes: `idiomas_disponibles`, `normalizar_codigo`, `IDIOMA_BASE`.
- Produces: `detectar_del_entorno(entorno=None) -> str`. `idioma_pedido` devuelve ya el código resuelto cuando se pide `auto`.

**Por qué es opt-in:** `LANG` en macOS suele valer `en_US.UTF-8` aunque el usuario trabaje en español, y en procesos lanzados desde una aplicación gráfica puede no existir. Como valor por defecto cambiaría el idioma de quien no lo pidió y haría los golden dependientes de la máquina. Como valor explícito, `--lang auto` o `CSE_LANG=auto`, nadie se lleva una sorpresa. No se consulta la configuración del sistema operativo (en macOS exigiría lanzar un proceso externo, y el único permitido es `git clone`).

- [ ] **Step 1: Escribir las pruebas que fallan**

Añadir a `tests/test_idiomas_cli.py`:

```python
class Auto(unittest.TestCase):

    def test_toma_el_primer_locale_significativo(self):
        self.assertEqual(i18n.detectar_del_entorno({"LANG": "fr_FR.UTF-8"}), "fr")

    def test_lc_all_manda_sobre_lang(self):
        self.assertEqual(
            i18n.detectar_del_entorno({"LC_ALL": "en_GB.UTF-8", "LANG": "fr_FR.UTF-8"}), "en")

    def test_c_y_posix_se_saltan(self):
        self.assertEqual(
            i18n.detectar_del_entorno({"LC_ALL": "C", "LANG": "fr_FR.UTF-8"}), "fr")
        self.assertEqual(i18n.detectar_del_entorno({"LANG": "POSIX"}), "es")

    def test_idioma_sin_catalogo_cae_a_espanol(self):
        self.assertEqual(i18n.detectar_del_entorno({"LANG": "de_DE.UTF-8"}), "es")

    def test_sin_variables_es_espanol(self):
        self.assertEqual(i18n.detectar_del_entorno({}), "es")

    def test_auto_se_resuelve_en_idioma_pedido(self):
        self.assertEqual(i18n.idioma_pedido("auto", {"LANG": "fr_FR.UTF-8"}), "fr")
        self.assertEqual(i18n.idioma_pedido(None, {"CSE_LANG": "auto", "LANG": "en_US.UTF-8"}), "en")

    def test_auto_en_el_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = correr("export", str(FIXTURES / "repo-descarga-remota"), "--out", tmp,
                       "--anular-revision-seguridad", "--lang", "auto",
                       entorno={"LANG": "fr_FR.UTF-8", "LC_ALL": ""})
            informe = (Path(tmp) / "INFORME-PORTABILIDAD.md").read_text(encoding="utf-8")
        self.assertIn("Niveau de risque", informe)

    def test_sin_auto_la_variable_lang_no_cambia_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            correr("export", str(FIXTURES / "repo-descarga-remota"), "--out", tmp,
                   "--anular-revision-seguridad", entorno={"LANG": "fr_FR.UTF-8"})
            informe = (Path(tmp) / "INFORME-PORTABILIDAD.md").read_text(encoding="utf-8")
        self.assertIn("Nivel de riesgo", informe)
```

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: `python3 -m unittest discover -s tests -t tests -p "test_idiomas_cli.py" > /tmp/cli.log 2>&1; echo "codigo=$?"; grep -E "^(OK|FAILED|Ran )" /tmp/cli.log`
Expected: `FAILED`.

- [ ] **Step 3: Implementar**

En `exporter/i18n/__init__.py`, sustituir `idioma_pedido` por:

```python
VARIABLES_DE_LOCALE = ("LC_ALL", "LC_MESSAGES", "LANG")


def detectar_del_entorno(entorno=None) -> str:
    """El idioma del locale del entorno, o el base si no hay catalogo.

    Respeta la precedencia POSIX (LC_ALL, LC_MESSAGES, LANG). La primera
    variable con valor decide, salvo `C` y `POSIX`, que significan «sin
    idioma» y se saltan. Si el idioma que dice no tiene catalogo, gana el
    base: no se salta a la siguiente variable, porque eso mezclaria idiomas.
    """
    entorno = os.environ if entorno is None else entorno
    for variable in VARIABLES_DE_LOCALE:
        valor = (entorno.get(variable) or "").strip()
        if not valor or valor.upper() in ("C", "POSIX") or valor.upper().startswith("C."):
            continue
        codigo = normalizar_codigo(valor)
        return codigo if codigo in idiomas_disponibles() else IDIOMA_BASE
    return IDIOMA_BASE


def idioma_pedido(flag, entorno=None) -> str:
    """Que idioma se pidio: el flag, si no CSE_LANG, si no el base.

    `auto` se resuelve aqui contra el entorno. Una variable vacia cuenta
    como ausente. No valida: eso lo hace fijar_idioma.
    """
    entorno = os.environ if entorno is None else entorno
    pedido = flag or entorno.get("CSE_LANG") or IDIOMA_BASE
    if pedido.strip().lower() == "auto":
        return detectar_del_entorno(entorno)
    return pedido
```

En `convert.py`, actualizar el `help=` de `--lang` para mencionar `auto`:

```python
        p.add_argument("--lang", dest="lang", default=None, metavar="CODIGO",
                       help="idioma de los informes y mensajes: es (por defecto), en, fr, "
                            "o auto para usar el del sistema. También se lee de la "
                            "variable CSE_LANG")
```

- [ ] **Step 4: Ejecutar pruebas y suite**

Run: Step 2 y la suite completa.
Expected: `OK`, `OK`.

- [ ] **Step 5: Commit**

```bash
git add skills/plugin-to-agentskills/scripts tests/test_idiomas_cli.py
git commit -m "Anade --lang auto para usar el idioma del sistema

Es opt-in a proposito: LANG en macOS suele ser en_US aunque el usuario
trabaje en espanol, y como valor por defecto cambiaria el idioma de quien
no lo pidio. Respeta la precedencia POSIX y no consulta nada fuera del
entorno, porque el unico proceso externo permitido es git clone.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 11: La conversación de Claude y la documentación

**Files:**
- Modify: `skills/plugin-to-agentskills/SKILL.md`
- Modify: `commands/exportar-skills.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/guia.html` (solo una línea; ver Step 3)
- Test: `tests/test_distribucion.py` y los validadores existentes

**Interfaces:**
- Consumes: el flag `--lang` y los idiomas `es|en|fr|auto`.

**Cuidado con el ámbito `exportado` (trampa 3 de `AGENTS.md`):** todo lo de `skills/plugin-to-agentskills/` viaja en el artefacto. Aquí se describe el comportamiento **con palabras**; ninguna frase de inyección de prompt ni el patrón descargar-y-ejecutar en claro.

- [ ] **Step 1: `SKILL.md`**

Añadir, después de «Paso 0» y antes de lo que sigue, una sección (en español: la lee Claude, no el usuario):

```markdown
## Idioma de la respuesta

Si el usuario pide un idioma, o te escribe en uno distinto del español, **respóndele en
ese idioma** durante toda la conversación y pasa al conversor el flag `--lang <código>`.
Los códigos disponibles son `es`, `en` y `fr`; `--lang auto` usa el idioma del sistema.

- El conversor traduce el informe, la consola y los mensajes de error. **Tú traduces tu
  conversación**, y citas tal cual los nombres de artefactos (`INFORME-PORTABILIDAD.md`,
  `resumen.json`, `<skill>.zip`) y los valores de `resumen.json`, que siguen en español.
- Si el idioma pedido no está entre los disponibles, dilo, ofrece el español o el más
  cercano y **no inventes una traducción del informe**: el conversor sólo ofrece los
  idiomas que tiene.
- Para saber cuáles hay: `python3 "$CONV" inspect . --lang xx` lista los disponibles en el
  mensaje de error.
```

En el frontmatter, ampliar la `description` con disparadores en inglés y francés. Mantenerla **dentro del presupuesto** que el propio conversor valida sobre sí mismo (≤ 490 bytes para la carpeta de Mistral). Comprobarlo:

Run: `python3 skills/plugin-to-agentskills/scripts/convert.py inspect . --only plugin-to-agentskills 2>&1 | grep -E "descripción:"` — o, si `inspect` choca con los fixtures, `python3 -c "import re,sys; t=open('skills/plugin-to-agentskills/SKILL.md',encoding='utf-8').read(); d=re.search(r'^description:\s*(.+)$', t, re.M).group(1); print(len(d.encode('utf-8')))"`
Expected: ≤ 850 (límite del zip; lo que exceda se recorta con aviso en el informe). Si supera 490, acortar los ejemplos en español para dejar sitio a los de en/fr.

Disparadores a añadir: `"export this plugin"`, `"exporte ce plugin"`.

- [ ] **Step 2: `commands/exportar-skills.md`**

Añadir al final de la lista numerada:

```markdown
7. Responde al usuario en el idioma en que te escribió, o en el que pida, y pasa
   `--lang <código>` al conversor (`es`, `en`, `fr` o `auto`). Los nombres de artefactos y
   los valores de `resumen.json` se citan tal cual.
```

Ajustar `argument-hint` solo si hace falta: `<url-del-repo-o-ruta-local> [--lang es|en|fr]`.

- [ ] **Step 3: `README.md`, `AGENTS.md`, `docs/guia.html`**

- `README.md`: en la tabla de opciones añadir `--lang CODIGO` (`es` por defecto, `en`, `fr`, `auto`; también `CSE_LANG`), y un párrafo «Añadir un idioma» (soltar `xx.json` en `exporter/i18n/`, pasar `validar_idiomas.py`). Incluir la advertencia de que las traducciones al inglés y al francés las ha redactado una IA y conviene revisarlas antes de depender de ellas. Documentar que `--help` sigue en español.
- `AGENTS.md`: (a) sustituir «**355 pruebas**» por el número real tras esta tarea (sacarlo de `grep -E "^Ran " /tmp/suite.log`); (b) añadir el validador a «Los cuatro validadores del CI» y retitular «Los cinco validadores»; (c) en «Mapa rápido del código» añadir `i18n/` con una línea; (d) una **trampa nueva**: «Los textos visibles viven en `exporter/i18n/*.json`, salvo los de `reglas.json` y `targets/*.json`, que son el español de origen y se sobrescriben por clave».
- `docs/guia.html`: **una** línea que diga que se puede pedir el idioma. **No escribir ejemplos de patrones peligrosos** (trampa 3: `.html` se analiza con todas las reglas).

- [ ] **Step 4: Validadores y suite**

Run:
```bash
python3 -m unittest discover -s tests -t tests > /tmp/suite.log 2>&1; echo "codigo=$?"
grep -E "^(OK|FAILED|Ran )" /tmp/suite.log
python3 .github/validate_plugin.py . ; echo "codigo=$?"
python3 .github/validar_estatico.py . ; echo "codigo=$?"
python3 .github/validar_idiomas.py . ; echo "codigo=$?"
/tmp/venv-cse/bin/python .github/validar_perfiles.py . ; echo "codigo=$?"
/tmp/venv-cse/bin/python .github/validar_reglas.py . ; echo "codigo=$?"
python3 skills/plugin-to-agentskills/scripts/convert.py export . --only plugin-to-agentskills --anular-revision-seguridad --out /tmp/cse-auto > /tmp/auto.log 2>&1; echo "autoexport=$?"
```
Expected: todo `0` y `OK`; `autoexport=0`.

- [ ] **Step 5: Comprobar que el catálogo viaja en la rama `plugin`**

Run: `grep -n "INCLUIR" -A12 .github/construir_distribucion.py | head -25`
Expected: la lista blanca incluye `skills` (el catálogo cuelga de ahí). Si lista ficheros concretos y no el directorio, añadir `exporter/i18n/`.

- [ ] **Step 6: Commit**

```bash
git add skills/plugin-to-agentskills/SKILL.md commands/exportar-skills.md README.md AGENTS.md docs/guia.html
git commit -m "Documenta --lang y le dice a Claude que responda en el idioma pedido

El conversor traduce lo que genera; la conversacion la traduce Claude, asi
que SKILL.md y el comando se lo indican. La descripcion de la skill suma
disparadores en ingles y frances sin salirse del presupuesto de bytes.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Auto-revisión

**Cobertura del spec (con §9):**

| Requisito | Tarea |
|---|---|
| §1 criterio 1: `--lang en`/`fr` en los tres subcomandos; sin flag, byte a byte igual | 2, 3–6 (comparación contra la captura), 8, 9 |
| §1 criterio 2: añadir un idioma sin tocar código | 1 (`test_un_idioma_nuevo_se_descubre…`), 7 |
| §1 criterio 3: validador de CI | 7 |
| §1 criterio 4: la conversación de Claude | 11 |
| §2 qué se traduce / qué no | 3–6; prosa de vocabularios (§9.6) en 3 |
| §3.1–3.3 catálogo, `t()`, autodescubrimiento | 1 |
| §3.4 + §9.2 reglas y peligros por sobrescritura | 6, 8, 9 |
| §4 flag, `CSE_LANG`, error, `--help` en español | 2 |
| §9.4 `--lang auto` | 10 |
| §9.5 normalización de códigos | 1, 2 |
| §5 `SKILL.md` y comando | 11 |
| §6.1 validador | 7 |
| §6.2 golden por idioma, CLI, redacción, estático | 2, 8, 9 |
| §6.3 restricción de ámbito `exportado` | 8 Step 5, 9 Step 6, 11 Step 4 |
| §7 riesgos 1–4 | 8 y 9 (autoexport), traducciones (README, Tarea 11), 7, fases del plan |

**Review Focus:** 1 → T4; 2 → T1; 3 → T2; 4 → T1/T2; 5 → T9; 6 → T7; 7 → T8/T9/T11; 8 → T2.

**Tipos y firmas coherentes:** `t(clave, **datos)`, `t_opcional(clave, defecto)`, `fijar_idioma(codigo) -> str`, `idioma_pedido(flag, entorno=None)`, `detectar_del_entorno(entorno=None)`, `IdiomaDesconocido(codigo, disponibles)`, `comprobar(raiz) -> list` se usan con los mismos nombres de la Tarea 1 a la 11. `titulo_de`/`mitigacion_de`/`detalle_de` se definen en la Tarea 6 y no se usan antes.

**Limitaciones conocidas que el plan no oculta:**
- Las tablas de claves de las Tareas 3–5 dan el **origen** del literal, no repiten su texto: está verbatim en el código y su corrección la fija la comparación byte a byte contra la captura previa. Sin esa comparación en verde, ninguna de esas tareas está terminada.
- Las traducciones al inglés y al francés (Tareas 8 y 9) las redacta quien ejecute el plan; el validador asegura que estén completas y con los mismos marcadores, **no** que sean buenas. Recomendada una revisión humana del francés y del texto de seguridad.
- `--help` queda en español (spec §4).
