# Auditor de portabilidad — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir el veredicto único de riesgo por skill en una matriz de compatibilidad por destino, con los perfiles de destino como datos JSON versionados y con evidencia fechada.

**Architecture:** `scripts/convert.py` se adelgaza a CLI y conserva su ruta exacta; la lógica pasa a un paquete hermano `scripts/exporter/` que Python importa gracias a que `sys.path[0]` es el directorio del script. Los cinco destinos pasan de constantes de Python a `exporter/targets/*.json` validados contra un schema. El motor cruza dos canales —capacidades declaradas y peligros de conducta observados— para emitir un estado por par *skill × destino*.

**Tech Stack:** Python 3.8+, sólo biblioteca estándar en ejecución. `unittest` para pruebas. `jsonschema` **sólo** en CI. GitHub Actions.

## Global Constraints

- **Python 3.8+ y sólo biblioteca estándar en ejecución.** Nada de `pip install` en el camino del usuario: el conversor debe arrancar desde un clon en `/tmp`.
- **`skills/plugin-to-agentskills/scripts/convert.py` no cambia de ruta.** Lo referencian el «Paso 0» del `SKILL.md`, el comando `/exportar-skills` y dos pasos del workflow de CI.
- **`python3 convert.py <origen>` sin subcomando sigue exportando.** Compatibilidad hacia atrás obligatoria.
- **Identificadores en ASCII, texto en español.** Sin `ñ` ni tildes en nombres de función, clase o variable (`Senal`, no `Señal`). Comentarios, mensajes e informes, en español.
- **`jsonschema` sólo en CI y pruebas.** Nunca importado desde `exporter/`.
- **Nombres de artefactos de salida invariables:** `<skill>.zip`, `<skill>/`, `INFORME-PORTABILIDAD.md`, `resumen.json`.
- **Mensajes de commit en español**, sujeto imperativo corto y cuerpo explicando el porqué, siguiendo el estilo del repositorio. Terminar con:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
- **Vocabularios cerrados.** Capacidad: `si`, `si_con_confirmacion`, `parcial`, `no`, `desconocido`. Confianza: `oficial`, `oficial-incompleto`, `observado`, `comunidad`, `no-verificado`. Severidad: `alta`, `media`, `baja`. Estado: `compatible`, `compatible_con_adaptacion`, `degradado`, `no_compatible`, `no_verificable`.
- **`bloqueo_seguridad` siempre `null`.** Existe en el modelo y el schema; ninguna regla lo emite en esta rebanada.
- Rama de trabajo: `auditor-portabilidad`. No hacer push salvo petición explícita de Pablo.
- **Los números de línea de este plan se refieren a `convert.py` tal como estaba antes de la tarea 1** (832 líneas). Cada extracción los desplaza. Trátalos como una pista de dónde mirar, no como una dirección: **localiza los bloques por contenido**. Si lo que encuentras no coincide con lo que dice el plan, informa de la discrepancia en tu informe en lugar de forzar el encaje.

---

## Estructura de ficheros resultante

| Fichero | Responsabilidad |
|---|---|
| `scripts/convert.py` | Sólo CLI: argparse, subcomandos, orquestación, códigos de salida |
| `scripts/exporter/__init__.py` | Vacío, marca el paquete |
| `scripts/exporter/frontmatter.py` | Parseo y serialización del frontmatter YAML mínimo |
| `scripts/exporter/descripcion.py` | Troceo en frases, reordenado, compactado y recorte de la `description` |
| `scripts/exporter/modelo.py` | Dataclasses y vocabularios: `Senal`, `SkillPortatil`, `Estado`, `Evaluacion` |
| `scripts/exporter/deteccion.py` | Patrones → señales con ubicación `fichero:linea` |
| `scripts/exporter/perfiles.py` | Carga y valida `targets/*.json` |
| `scripts/exporter/compatibilidad.py` | Motor: señales × perfil → estado |
| `scripts/exporter/empaquetado.py` | Copia sin seguir enlaces, escritura del `SKILL.md`, zip, límites de paquete |
| `scripts/exporter/informes.py` | Informe Markdown con matriz y `resumen.json` |
| `scripts/exporter/targets/_schema.json` | JSON Schema del perfil de destino |
| `scripts/exporter/targets/*.json` | Un perfil por destino |
| `tests/` | `unittest`, fixtures y *golden files* |

---

## Task 1: Andamiaje del paquete y extracción de `frontmatter.py`

**Files:**
- Create: `skills/plugin-to-agentskills/scripts/exporter/__init__.py`
- Create: `skills/plugin-to-agentskills/scripts/exporter/frontmatter.py`
- Create: `tests/ayuda.py`
- Create: `tests/test_frontmatter.py`
- Modify: `skills/plugin-to-agentskills/scripts/convert.py:136-232`, `:408-414`
- Modify: `.github/workflows/validar.yml`

**Interfaces:**
- Consumes: nada.
- Produces: `exporter.frontmatter.split_frontmatter(text: str) -> tuple[dict, str, str]`, `parse_simple_yaml(raw: str) -> dict`, `unquote(v: str) -> str`, `yaml_escape(v: str) -> str`. También `tests.ayuda.RAIZ_SCRIPTS: Path` y `tests.ayuda.importar_exporter() -> None`, que todas las tareas posteriores usan para importar el paquete desde las pruebas.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/ayuda.py`:

```python
"""Utilidades compartidas por las pruebas.

El paquete `exporter` no se instala: vive junto a convert.py y se importa
porque Python pone el directorio del script en sys.path[0]. Las pruebas no
se ejecutan desde ahí, así que replican ese gesto a mano.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RAIZ_SCRIPTS = RAIZ / "skills" / "plugin-to-agentskills" / "scripts"


def importar_exporter() -> None:
    ruta = str(RAIZ_SCRIPTS)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
```

**No crear `tests/__init__.py`.** Las pruebas se ejecutan siempre con
`discover -s tests -t tests`, que pone `tests/` como directorio de nivel superior; si
`tests/` fuera además un paquete, `from ayuda import …` dejaría de resolver al invocar un
módulo suelto. Para ejecutar uno solo:
`python3 -m unittest discover -s tests -t tests -p "test_X.py"`.

Crear `tests/test_frontmatter.py`:

```python
import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.frontmatter import (  # noqa: E402
    parse_simple_yaml,
    split_frontmatter,
    yaml_escape,
)


class ParseoDeFrontmatter(unittest.TestCase):

    def test_separa_frontmatter_y_cuerpo(self):
        fm, _, cuerpo = split_frontmatter(
            "---\nname: mi-skill\ndescription: Hola\n---\n# Titulo\n")
        self.assertEqual(fm["name"], "mi-skill")
        self.assertEqual(fm["description"], "Hola")
        self.assertEqual(cuerpo, "# Titulo\n")

    def test_sin_frontmatter_devuelve_texto_intacto(self):
        fm, _, cuerpo = split_frontmatter("# Solo cuerpo\n")
        self.assertEqual(fm, {})
        self.assertEqual(cuerpo, "# Solo cuerpo\n")

    def test_metadata_anidado_sobrevive_como_mapa(self):
        # Regresion del fallo corregido en e3307b3: un `metadata:` con claves
        # dentro se perdia entero porque se asumia que toda clave sin valor
        # abria una lista.
        fm = parse_simple_yaml("name: x\nmetadata:\n  version: '4.1'\n  autor: Pablo\n")
        self.assertEqual(fm["metadata"], {"version": "4.1", "autor": "Pablo"})

    def test_lista_sigue_siendo_lista(self):
        fm = parse_simple_yaml("depends:\n  - una\n  - otra\n")
        self.assertEqual(fm["depends"], ["una", "otra"])


class Serializacion(unittest.TestCase):

    def test_entrecomilla_lo_que_rompe_el_yaml(self):
        self.assertEqual(yaml_escape("con: dos puntos"), '"con: dos puntos"')

    def test_deja_en_crudo_lo_inocuo(self):
        self.assertEqual(yaml_escape("mi-skill"), "mi-skill")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar la prueba y comprobar que falla**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -v
```

Esperado: FAIL con `ModuleNotFoundError: No module named 'exporter'`.

- [ ] **Step 3: Crear el paquete y mover el código**

Crear `skills/plugin-to-agentskills/scripts/exporter/__init__.py` vacío.

Crear `skills/plugin-to-agentskills/scripts/exporter/frontmatter.py` con esta cabecera, seguida de las funciones movidas **literalmente** desde `convert.py`:

```python
"""Parseo y serializacion del frontmatter YAML minimo de un SKILL.md.

Parser de nivel superior, sin PyYAML: soporta `clave: valor`, escalares en
bloque (| >), listas y mapas anidados de un nivel. No pretende cubrir YAML
entero, sino exactamente lo que aparece en un SKILL.md real.
"""

from __future__ import annotations

import re
```

Mover verbatim desde `convert.py`, en este orden y sin cambiar una línea:
- `split_frontmatter` — líneas 140-155
- `parse_simple_yaml` — líneas 157-217
- `unquote` — líneas 219-224
- `yaml_escape` — líneas 408-414

Borrar esas cuatro funciones de `convert.py` y, junto a los demás `import`, añadir:

```python
from exporter.frontmatter import split_frontmatter, yaml_escape
```

Importar **sólo** lo que `convert.py` llama. `unquote` y `parse_simple_yaml` las usa `frontmatter.py` internamente; añadirlas aquí sería un import muerto.

- [ ] **Step 4: Ejecutar las pruebas y comprobar que pasan**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -v
```

Esperado: PASS, sin fallos ni errores.

- [ ] **Step 5: Comprobar que el conversor sigue funcionando desde `/tmp`**

Es el invariante que más fácil se rompe con esta reorganización, así que se verifica ya:

```bash
rm -rf /tmp/cse-prueba && cp -R "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" /tmp/cse-prueba && python3 /tmp/cse-prueba/skills/plugin-to-agentskills/scripts/convert.py /tmp/cse-prueba --out /tmp/salida-prueba && test -f /tmp/salida-prueba/INFORME-PORTABILIDAD.md && echo "ARRANCA DESDE /tmp: OK"
```

Esperado: `ARRANCA DESDE /tmp: OK`.

- [ ] **Step 6: Añadir las pruebas al CI**

En `.github/workflows/validar.yml`, después del paso «Validar manifiestos, skills y comandos», insertar:

```yaml
      - name: Pruebas unitarias
        run: python3 -m unittest discover -s tests -t tests -v

      - name: El conversor arranca desde una copia aislada
        run: |
          cp -R . /tmp/cse-aislado
          python3 /tmp/cse-aislado/skills/plugin-to-agentskills/scripts/convert.py \
            /tmp/cse-aislado --out /tmp/salida-aislada
          test -f /tmp/salida-aislada/INFORME-PORTABILIDAD.md
          echo "Arranca sin instalacion desde una ruta ajena al repositorio."
```

- [ ] **Step 7: Commit**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && git checkout -b auditor-portabilidad && git add tests .github/workflows/validar.yml skills/plugin-to-agentskills/scripts/ && git commit -m "$(cat <<'EOF'
Extrae el frontmatter a un paquete hermano de convert.py

Primer paso de la reorganizacion: convert.py se queda como punto de
entrada y la logica baja a exporter/. Se importa sin instalar nada porque
Python coloca el directorio del script en sys.path[0], que es justo el
gesto que hace el «Paso 0» de la skill al clonar en /tmp.

Se estrena tests/ con la regresion del fallo de e3307b3: un `metadata:`
con claves dentro se perdia entero, y eso hacia que toda skill exportada
con `version` la emitiera al nivel superior y el destino la rechazara.

El CI comprueba ademas que el conversor arranca desde una copia fuera del
repositorio. Es el invariante que esta reorganizacion pone en riesgo.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Extraer `descripcion.py`

**Files:**
- Create: `skills/plugin-to-agentskills/scripts/exporter/descripcion.py`
- Create: `tests/test_descripcion.py`
- Modify: `skills/plugin-to-agentskills/scripts/convert.py:226-406`

**Interfaces:**
- Consumes: nada de tareas anteriores.
- Produces: `exporter.descripcion.nbytes(s: str) -> int`, `split_sentences(text: str) -> list`, `reorder_description(desc: str) -> tuple[str, bool]`, `compact_description(desc: str, budget: int) -> str`, `clamp_description(desc: str, budget: int) -> str`, `tiene_activacion(desc: str) -> bool`, y las constantes `ACTIVATION_RX`, `MAX_TRIGGER_EXAMPLES`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/test_descripcion.py`:

```python
import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.descripcion import (  # noqa: E402
    clamp_description,
    compact_description,
    nbytes,
    reorder_description,
    split_sentences,
    tiene_activacion,
)


class ConteoEnBytes(unittest.TestCase):

    def test_las_tildes_cuentan_doble(self):
        # El limite de 1024 se mide en bytes UTF-8, no en caracteres: es la
        # causa de que Perplexity rechazara un zip con 1063 caracteres.
        self.assertEqual(len("cárgala"), 7)
        self.assertEqual(nbytes("cárgala"), 8)


class TroceoEnFrases(unittest.TestCase):

    def test_no_rompe_dentro_de_comillas(self):
        frases = split_sentences('Cárgala cuando el usuario diga "¿es importante?". Hace cosas.')
        self.assertEqual(len(frases), 2)

    def test_no_rompe_en_abreviaturas(self):
        frases = split_sentences("Usa datos, p. ej. correos. Después informa.")
        self.assertEqual(len(frases), 2)


class Reordenado(unittest.TestCase):

    def test_adelanta_la_frase_de_activacion(self):
        texto, movido = reorder_description(
            "Analiza bandejas de correo. Actívalo cuando el usuario diga «filtra mi correo».")
        self.assertTrue(movido)
        self.assertTrue(texto.startswith("Actívalo cuando"))

    def test_no_inventa_activacion_si_no_la_hay(self):
        texto, movido = reorder_description("Esta skill genera informes. Y tablas.")
        self.assertFalse(movido)
        self.assertEqual(texto, "Esta skill genera informes. Y tablas.")


class Recorte(unittest.TestCase):

    def test_nunca_corta_a_mitad_de_palabra(self):
        largo = "Cárgala cuando el usuario lo pida. " + ("palabra " * 200)
        salida = clamp_description(largo, 490)
        self.assertLessEqual(nbytes(salida), 490)
        self.assertFalse(salida.endswith("palab"))

    def test_compactar_conserva_el_criterio_de_activacion(self):
        largo = ("Analiza bandejas con calibración estadística y modelos de prioridad. "
                 "Actívalo cuando el usuario diga «filtra mi correo», «revisa mi bandeja», "
                 "«qué correos importan» o «limpia el buzón». " + ("Relleno. " * 60))
        salida = compact_description(largo, 490)
        self.assertLessEqual(nbytes(salida), 490)
        self.assertIn("Actívalo cuando", salida)


class DeteccionDeActivacion(unittest.TestCase):

    def test_reconoce_disparadores_en_espanol_e_ingles(self):
        self.assertTrue(tiene_activacion("Cárgala cuando el usuario pida algo."))
        self.assertTrue(tiene_activacion("Use this skill when the user asks."))

    def test_una_descripcion_que_solo_describe_no_tiene_activacion(self):
        self.assertFalse(tiene_activacion("Esta skill genera informes financieros."))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar la prueba y comprobar que falla**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -p "test_descripcion.py" -v
```

Esperado: FAIL con `ModuleNotFoundError: No module named 'exporter.descripcion'`.

- [ ] **Step 3: Crear el módulo con el código movido**

Crear `skills/plugin-to-agentskills/scripts/exporter/descripcion.py` con cabecera:

```python
"""La description es el unico campo que el destino lee para decidir si carga
la skill, y lo paga en tokens en cada sesion.

Este modulo hace tres cosas en orden: adelanta las frases que dicen CUANDO
cargar la skill, poda los ejemplos entrecomillados sobrantes y recorta al
presupuesto del destino. El orden importa: si hay que cortar, se pierde lo
prescindible y sobrevive el criterio de activacion.
"""

from __future__ import annotations

import re
```

Mover verbatim desde `convert.py`:
- `ACTIVATION_RX` — líneas 228-238
- `ABBREV` — líneas 240-241
- `split_sentences` — líneas 244-292
- `reorder_description` — líneas 295-311
- `QUOTED_RX` — línea 314
- `nbytes` — líneas 317-318
- `MAX_TRIGGER_EXAMPLES` — línea 321
- `trim_quoted_examples` — líneas 324-345
- `compact_description` — líneas 348-384
- `clamp_description` — líneas 387-405

En `compact_description` y `clamp_description`, sustituir el valor por defecto `budget: int = BUDGET_DEFAULT` por `budget: int`: el presupuesto pasa a venir siempre del perfil, y un valor por defecto invitaría a olvidarlo.

Añadir al final la función nueva, que hoy está duplicada como llamada suelta a `ACTIVATION_RX.search` en `audit_and_adapt`:

```python
def tiene_activacion(desc: str) -> bool:
    """¿Dice la descripcion en algun momento CUANDO cargar la skill?

    Si no lo dice, el destino casi nunca la activara. No se puede arreglar
    automaticamente sin inventar criterios que el autor nunca escribio.
    """
    return bool(ACTIVATION_RX.search(desc))
```

Borrar de `convert.py` todo lo movido y añadir el import:

```python
from exporter.descripcion import (
    ACTIVATION_RX,
    clamp_description,
    compact_description,
    nbytes,
    reorder_description,
    tiene_activacion,
)
```

En `audit_and_adapt`, sustituir las dos apariciones de `if not ACTIVATION_RX.search(res.description):` por `if not tiene_activacion(res.description):`. Las llamadas a `compact_description` y `clamp_description` ya pasan el presupuesto explícito, así que no cambian.

- [ ] **Step 4: Ejecutar las pruebas y comprobar que pasan**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -v
```

Esperado: PASS, sin fallos ni errores.

- [ ] **Step 5: Comprobar que la salida no ha cambiado**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 skills/plugin-to-agentskills/scripts/convert.py . --out /tmp/salida-t2 && grep -c "description:" /tmp/salida-t2/plugin-to-agentskills/SKILL.md
```

Esperado: `1`, y ningún error.

- [ ] **Step 6: Commit**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && git add -A && git commit -m "$(cat <<'EOF'
Extrae el tratamiento de la description a su propio modulo

Es la parte con mas logica del conversor y la que decide el 80% del
resultado, asi que merece pruebas propias: troceo en frases que respeta
comillas y abreviaturas, reordenado de la activacion al frente, y recorte
que nunca parte una palabra.

Se retira el valor por defecto de `budget`. A partir de la siguiente tarea
el presupuesto lo declara el perfil del destino, y un valor por defecto
invitaria a olvidarlo y a recortar contra el destino equivocado.

`tiene_activacion()` sustituye a la llamada suelta a ACTIVATION_RX que
estaba escrita a mano dentro de audit_and_adapt.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `modelo.py` — vocabularios, dataclasses e inferencia de capacidades

**Files:**
- Create: `skills/plugin-to-agentskills/scripts/exporter/modelo.py`
- Create: `tests/test_modelo.py`

**Interfaces:**
- Consumes: nada.
- Produces: `exporter.modelo.Estado` (constantes y `Estado.peor(estados)`), `Senal` dataclass `(id, ubicacion, muestra, severidad_base)`, `Capacidad` dataclass `(nombre, nivel)` con `nivel in {"requerida", "opcional"}`, `SkillPortatil` dataclass, `Evaluacion` dataclass, `CAPACIDAD_POR_SENAL: dict`, `capacidades_de(senales, tiene_scripts) -> list[Capacidad]`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/test_modelo.py`:

```python
import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.modelo import (  # noqa: E402
    Capacidad,
    Estado,
    Senal,
    capacidades_de,
)


class PrecedenciaDeEstados(unittest.TestCase):

    def test_no_compatible_gana_a_todo(self):
        self.assertEqual(
            Estado.peor([Estado.COMPATIBLE, Estado.NO_COMPATIBLE, Estado.DEGRADADO]),
            Estado.NO_COMPATIBLE)

    def test_no_verificable_gana_a_degradado(self):
        self.assertEqual(
            Estado.peor([Estado.DEGRADADO, Estado.NO_VERIFICABLE]),
            Estado.NO_VERIFICABLE)

    def test_sin_estados_es_compatible(self):
        self.assertEqual(Estado.peor([]), Estado.COMPATIBLE)


class InferenciaDeCapacidades(unittest.TestCase):

    def test_mcp_exige_cliente_mcp(self):
        caps = capacidades_de([Senal("mcp-tool", "SKILL.md:12", "mcp__gmail__buscar", "alta")],
                              tiene_scripts=False)
        self.assertIn(Capacidad("mcp.cliente", "requerida"), caps)

    def test_estado_persistente_exige_escribir_no_una_capacidad_propia(self):
        # El hibrido en accion: la capacidad es escribir, que Mistral SI tiene.
        # Que la escritura no sobreviva es un peligro, no una capacidad ausente.
        caps = capacidades_de([Senal("estado-persistente", "SKILL.md:40", ">> log.jsonl", "media")],
                              tiene_scripts=False)
        self.assertIn(Capacidad("filesystem.escribir", "requerida"), caps)
        self.assertNotIn("filesystem.persistencia", [c.nombre for c in caps])

    def test_carpeta_scripts_exige_ejecutarlos(self):
        caps = capacidades_de([], tiene_scripts=True)
        self.assertEqual(caps, [Capacidad("scripts.ejecutar", "requerida")])

    def test_los_comandos_con_namespace_son_opcionales(self):
        caps = capacidades_de([Senal("slash-plugin", "SKILL.md:5", "/mi-plugin:comando", "media")],
                              tiene_scripts=False)
        self.assertEqual(caps, [Capacidad("comandos.namespace", "opcional")])

    def test_las_senales_cosmeticas_no_exigen_nada(self):
        caps = capacidades_de([Senal("claude-brand", "SKILL.md:3", "Claude Code", "baja")],
                              tiene_scripts=False)
        self.assertEqual(caps, [])

    def test_no_duplica_capacidades_repetidas(self):
        caps = capacidades_de([
            Senal("mcp-tool", "SKILL.md:12", "mcp__a__b", "alta"),
            Senal("mcp-tool", "SKILL.md:30", "mcp__c__d", "alta"),
        ], tiene_scripts=False)
        self.assertEqual(caps, [Capacidad("mcp.cliente", "requerida")])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar la prueba y comprobar que falla**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -p "test_modelo.py" -v
```

Esperado: FAIL con `ModuleNotFoundError: No module named 'exporter.modelo'`.

- [ ] **Step 3: Escribir la implementación mínima**

Crear `skills/plugin-to-agentskills/scripts/exporter/modelo.py`:

```python
"""Vocabularios cerrados y estructuras del modelo intermedio.

El modelo intermedio describe lo que una skill ES y EXIGE, sin referencia a
ningun destino. Cruzarlo con un perfil es cosa de compatibilidad.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class Estado:
    """Estados de compatibilidad, de mejor a peor."""

    COMPATIBLE = "compatible"
    COMPATIBLE_CON_ADAPTACION = "compatible_con_adaptacion"
    DEGRADADO = "degradado"
    NO_VERIFICABLE = "no_verificable"
    NO_COMPATIBLE = "no_compatible"

    # Precedencia: el peor gana. Un unico impedimento real pesa mas que
    # cualquier cantidad de cosas que si funcionan.
    ORDEN = [COMPATIBLE, COMPATIBLE_CON_ADAPTACION, DEGRADADO,
             NO_VERIFICABLE, NO_COMPATIBLE]

    @classmethod
    def peor(cls, estados) -> str:
        peor = cls.COMPATIBLE
        for e in estados:
            if cls.ORDEN.index(e) > cls.ORDEN.index(peor):
                peor = e
        return peor


# Niveles con que un perfil declara una capacidad.
NIVELES_CAPACIDAD = {"si", "si_con_confirmacion", "parcial", "no", "desconocido"}

# Niveles de confianza de la evidencia.
CONFIANZAS = {"oficial", "oficial-incompleto", "observado", "comunidad", "no-verificado"}

SEVERIDADES = {"alta", "media", "baja"}


@dataclass(frozen=True)
class Senal:
    """Un patron detectado en el cuerpo de la skill, con donde se vio."""

    id: str
    ubicacion: str      # "references/guia.md:42"
    muestra: str
    severidad_base: str  # solo la usa `inspect`, que corre sin destino


@dataclass(frozen=True)
class Capacidad:
    nombre: str
    nivel: str          # "requerida" | "opcional"


@dataclass
class SkillPortatil:
    """Lo que una skill es y exige, con independencia del destino."""

    nombre: str
    nombre_original: str
    carpeta: str
    descripcion: str
    descripcion_bytes: int = 0
    tiene_activacion: bool = False
    cuerpo_tokens: int = 0
    claves_retiradas: list = field(default_factory=list)
    claves_a_metadata: list = field(default_factory=list)
    ficheros: list = field(default_factory=list)
    tiene_scripts: bool = False
    senales: list = field(default_factory=list)
    capacidades: list = field(default_factory=list)
    adaptaciones: list = field(default_factory=list)


@dataclass
class Evaluacion:
    """Resultado de cruzar una SkillPortatil con un perfil de destino."""

    destino: str
    modo_instalacion: str
    estado: str
    motivos: list = field(default_factory=list)
    peligros: list = field(default_factory=list)
    bloqueo_seguridad: object = None   # reservado: siempre None en esta rebanada


# De senal detectada a capacidad exigida. Las senales que no aparecen aqui no
# exigen nada: o se adaptan solas (plugin-root se reescribe) o son cosmeticas.
CAPACIDAD_POR_SENAL = {
    "mcp-tool":           [("mcp.cliente", "requerida")],
    "applescript":        [("applescript", "requerida"), ("shell.ejecutar", "requerida")],
    "subagent":           [("subagentes", "requerida")],
    "hooks":              [("hooks", "requerida")],
    "home-tilde":         [("home.resolver", "requerida")],
    "estado-persistente": [("filesystem.escribir", "requerida")],
    "skill-tool":         [("skills.anidadas", "requerida")],
    "slash-plugin":       [("comandos.namespace", "opcional")],
}


def capacidades_de(senales, tiene_scripts: bool) -> list:
    """Deriva las capacidades que la skill exige, sin repetir ninguna."""
    vistas, salida = set(), []

    def anadir(nombre: str, nivel: str) -> None:
        if nombre in vistas:
            return
        vistas.add(nombre)
        salida.append(Capacidad(nombre, nivel))

    if tiene_scripts:
        anadir("scripts.ejecutar", "requerida")
    for s in senales:
        for nombre, nivel in CAPACIDAD_POR_SENAL.get(s.id, []):
            anadir(nombre, nivel)
    return salida
```

- [ ] **Step 4: Ejecutar las pruebas y comprobar que pasan**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -v
```

Esperado: PASS, sin fallos ni errores.

- [ ] **Step 5: Commit**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && git add -A && git commit -m "$(cat <<'EOF'
Anade el modelo intermedio y la inferencia de capacidades

El modelo describe lo que una skill ES y EXIGE sin mencionar destino
alguno; cruzarlo con un perfil viene despues. Separarlo permite que
`inspect` sea util sin elegir destino.

La tabla senal -> capacidad deja fuera a proposito lo que no es una
capacidad: plugin-root se reescribe solo, y claude-md o claude-brand son
cosmeticos.

`estado-persistente` infiere `filesystem.escribir`, no una capacidad de
persistencia inventada. Mistral SI escribe: lo que falla es que la
escritura no sobrevive, y eso es un peligro de conducta que declara el
perfil, no una capacidad ausente. Es la distincion que sostiene todo el
diseno de dos canales.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `deteccion.py` — señales con ubicación

**Files:**
- Create: `skills/plugin-to-agentskills/scripts/exporter/deteccion.py`
- Create: `tests/test_deteccion.py`
- Modify: `skills/plugin-to-agentskills/scripts/convert.py:87-134`, `:530-545`

**Interfaces:**
- Consumes: `exporter.modelo.Senal`.
- Produces: `exporter.deteccion.PATRONES: list`, `EXPLICACIONES: dict[str, str]`, `detectar(texto: str, ruta: str) -> list[Senal]`, `detectar_en_arbol(dir: Path) -> list[Senal]`, `CLAUDE_TOOL_NAMES: list`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/test_deteccion.py`:

```python
import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.deteccion import detectar  # noqa: E402


class Deteccion(unittest.TestCase):

    def test_registra_el_numero_de_linea(self):
        texto = "Primera linea\nSegunda linea\nUsa mcp__gmail__buscar aqui\n"
        senales = detectar(texto, "SKILL.md")
        self.assertEqual(len(senales), 1)
        self.assertEqual(senales[0].id, "mcp-tool")
        self.assertEqual(senales[0].ubicacion, "SKILL.md:3")

    def test_incluye_la_muestra_del_texto_encontrado(self):
        senales = detectar("Llama a mcp__gmail__buscar\n", "SKILL.md")
        self.assertIn("mcp__gmail__buscar", senales[0].muestra)

    def test_una_senal_por_id_y_linea_no_una_por_coincidencia(self):
        texto = "mcp__a__b y mcp__c__d en la misma linea\n"
        senales = detectar(texto, "SKILL.md")
        self.assertEqual(len(senales), 1)

    def test_varias_lineas_dan_varias_senales(self):
        texto = "mcp__a__b\nrelleno\nmcp__c__d\n"
        senales = detectar(texto, "SKILL.md")
        self.assertEqual([s.ubicacion for s in senales], ["SKILL.md:1", "SKILL.md:3"])

    def test_texto_limpio_no_produce_senales(self):
        self.assertEqual(detectar("Un procedimiento normal y corriente.\n", "SKILL.md"), [])

    def test_detecta_el_home_con_tilde(self):
        senales = detectar("Escribe en ~/.mi-skill/estado.jsonl\n", "SKILL.md")
        self.assertEqual([s.id for s in senales], ["home-tilde"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar la prueba y comprobar que falla**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -p "test_deteccion.py" -v
```

Esperado: FAIL con `ModuleNotFoundError: No module named 'exporter.deteccion'`.

- [ ] **Step 3: Escribir la implementación**

Crear `skills/plugin-to-agentskills/scripts/exporter/deteccion.py`:

```python
"""Patrones que delatan dependencias del entorno de Claude.

La deteccion es por expresion regular y puede dar falsos positivos: por eso
cada senal lleva su ubicacion exacta y una muestra del texto, para que quien
lea el informe pueda ir a mirarlo.

La severidad NO vive aqui. Vive en el perfil del destino, porque depende de
el: `applescript` es media en Perplexity Computer, que lo ejecuta con un
corte a los ~90 s, y alta en Mistral Vibe Work, que no lo ejecuta y deja la
skill inerte. La severidad de este modulo es solo la reserva que usa
`inspect`, que corre sin destino elegido.
"""

from __future__ import annotations

import os
import re

from exporter.modelo import Senal

# Ficheros de texto en los que tiene sentido buscar.
EXTENSIONES_TEXTO = {".md", ".txt", ".py", ".sh", ".yaml", ".yml", ".json", ".toml"}

CLAUDE_TOOL_NAMES = [
    "TodoWrite", "AskUserQuestion", "NotebookEdit", "SlashCommand",
    "ExitPlanMode", "WebFetch", "TaskCreate", "TaskUpdate", "ToolSearch",
]
```

A continuación, trasladar el bloque `PATTERNS` de `convert.py` líneas 92-134 renombrándolo a `PATRONES`, y **partiéndolo en dos**: las tuplas conservan `(id, regex, severidad_base)` y las explicaciones pasan a un diccionario aparte, porque a partir de ahora la explicación específica del destino la aporta el perfil.

```python
# (id, regex, severidad_base)
PATRONES = [
    ("plugin-root", re.compile(r"\$\{?CLAUDE_PLUGIN_ROOT\}?"), "alta"),
    ("mcp-tool", re.compile(r"\bmcp__[a-zA-Z0-9_\-]+"), "alta"),
    ("skill-tool", re.compile(r"\bSkill\s*\(\s*[\"'`]|\bSkill tool\b|\bherramienta Skill\b"), "alta"),
    ("subagent", re.compile(r"\bTask tool\b|\bsubagent_type\b|\bAgent tool\b|\bsubagente\b", re.I), "alta"),
    ("slash-plugin", re.compile(
        r"(?:^|[\s(`])/[a-z][a-z0-9]{2,}(?:-[a-z0-9]+)*:[a-z][a-z0-9]{2,}(?:-[a-z0-9]+)*\b"), "media"),
    ("hooks", re.compile(r"\bhooks?\.json\b|\bPreToolUse\b|\bPostToolUse\b"), "media"),
    ("applescript", re.compile(r"\bosascript\b|\btell\s+application\b", re.I), "media"),
    ("lote-destructivo", re.compile(
        r"\b(?:move|delete|borra|elimina|mueve|archiva)\b[^.\n]{0,60}\b(?:whose|todos|all|"
        r"cada|every|lote|batch|masiv)", re.I), "alta"),
    ("home-tilde", re.compile(r"(?<![\w/])(?:~/|\$HOME/)[\w.\-]"), "media"),
    ("estado-persistente", re.compile(r">>\s*[\"']?[~$./][^\s\"'|;)]*"), "media"),
    ("claude-md", re.compile(r"\bCLAUDE\.md\b"), "baja"),
    ("claude-brand", re.compile(r"\bClaude Code\b|\bCowork\b"), "baja"),
]

# Explicacion generica, valida sin destino. La especifica de cada plataforma
# la aporta el perfil en `peligros[].detalle`.
EXPLICACIONES = {
    "plugin-root": "Ruta ${CLAUDE_PLUGIN_ROOT}: solo existe dentro de un plugin de Claude Code.",
    "mcp-tool": "Invoca herramientas MCP por nombre; esos servidores no estaran conectados.",
    "skill-tool": "Invoca otras skills mediante la herramienta Skill de Claude.",
    "subagent": "Delega en subagentes via la herramienta Task, que no existe fuera de Claude Code.",
    "slash-plugin": "Referencia a comandos con namespace de plugin (/plugin:comando).",
    "hooks": "Depende de hooks del plugin, que no se exportan.",
    "applescript": "Usa AppleScript para llegar a aplicaciones del Mac.",
    "lote-destructivo": "Modifica o mueve elementos en bloque a partir de un filtro.",
    "home-tilde": "Lee o escribe en rutas con ~ o $HOME.",
    "estado-persistente": "Acumula estado con anexado (>>).",
    "claude-md": "Referencia a CLAUDE.md, convencion especifica de Claude Code.",
    "claude-brand": "Menciona el producto Claude por su nombre; conviene neutralizarlo.",
}


def detectar(texto: str, ruta: str) -> list:
    """Devuelve una Senal por cada par (patron, linea) que coincida.

    Una linea con dos llamadas MCP produce UNA senal, no dos: lo que importa
    para el informe es donde mirar, y la linea ya lo dice.
    """
    salida = []
    for numero, linea in enumerate(texto.splitlines(), start=1):
        for pid, rx, severidad in PATRONES:
            m = rx.search(linea)
            if m:
                salida.append(Senal(pid, "{}:{}".format(ruta, numero),
                                    m.group(0).strip()[:80], severidad))
    return salida


def detectar_en_arbol(raiz) -> list:
    """Recorre los ficheros de texto de una skill y acumula sus senales."""
    salida = []
    for base, _dirs, ficheros in os.walk(str(raiz)):
        for nombre in sorted(ficheros):
            ruta = os.path.join(base, nombre)
            if os.path.splitext(nombre)[1].lower() not in EXTENSIONES_TEXTO:
                continue
            if os.path.islink(ruta):
                continue
            with open(ruta, encoding="utf-8", errors="replace") as fh:
                texto = fh.read()
            relativa = os.path.relpath(ruta, str(raiz))
            salida.extend(detectar(texto, relativa))
    return salida
```

Nota sobre `slash-plugin`: al pasar de buscar sobre el texto completo a buscar línea a línea, la bandera `re.M` deja de hacer falta y se retira, porque `^` ya ancla al principio de cada línea que se le pasa.

En `convert.py`, borrar `PATTERNS` (líneas 92-134) y `CLAUDE_TOOL_NAMES` (líneas 87-90), y sustituir el bucle de `audit_and_adapt` (líneas 530-545) por:

```python
    for s in detectar_en_arbol(src_dir):
        res.findings.append(Finding(s.severidad_base, s.id,
                                    "{} Visto en {}: {}".format(
                                        EXPLICACIONES[s.id], s.ubicacion, s.muestra)))
```

Añadir el import correspondiente:

```python
from exporter.deteccion import CLAUDE_TOOL_NAMES, EXPLICACIONES, detectar_en_arbol
```

- [ ] **Step 4: Ejecutar las pruebas y comprobar que pasan**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -v
```

Esperado: PASS, sin fallos ni errores.

- [ ] **Step 5: Comprobar que el informe ahora cita ubicaciones**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 skills/plugin-to-agentskills/scripts/convert.py . --out /tmp/salida-t4 && grep -o "Visto en [^:]*:[0-9]*" /tmp/salida-t4/INFORME-PORTABILIDAD.md | head -3
```

Esperado: al menos una línea del tipo `Visto en SKILL.md:57`.

- [ ] **Step 6: Commit**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && git add -A && git commit -m "$(cat <<'EOF'
Las senales pasan a llevar fichero y linea, y la deteccion cubre el arbol

Antes se auditaba solo el cuerpo del SKILL.md y el aviso decia «Ejemplos:
mcp__a__b» sin decir donde. Ahora se recorre tambien references/ y
scripts/, y cada senal cita fichero:linea con una muestra del texto. La
deteccion es por regex y da falsos positivos: que el lector pueda ir a
mirarlo es parte del contrato.

La severidad se separa de la explicacion porque deja de ser propiedad del
patron. `applescript` es media en Perplexity, que lo ejecuta con corte a
los ~90 s, y alta en Mistral, que no lo ejecuta. A partir de la tarea 6 la
declara el perfil; la de aqui es la reserva que usa `inspect`, sin destino.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `perfiles.py`, el schema y los cinco destinos

**Files:**
- Create: `skills/plugin-to-agentskills/scripts/exporter/targets/_schema.json`
- Create: `skills/plugin-to-agentskills/scripts/exporter/targets/claude-code.json`
- Create: `skills/plugin-to-agentskills/scripts/exporter/targets/claude-ai.json`
- Create: `skills/plugin-to-agentskills/scripts/exporter/targets/chatgpt.json`
- Create: `skills/plugin-to-agentskills/scripts/exporter/targets/perplexity-computer.json`
- Create: `skills/plugin-to-agentskills/scripts/exporter/targets/mistral-vibe-work.json`
- Create: `skills/plugin-to-agentskills/scripts/exporter/perfiles.py`
- Create: `tests/test_perfiles.py`

**Interfaces:**
- Consumes: `exporter.modelo.NIVELES_CAPACIDAD`, `CONFIANZAS`, `SEVERIDADES`.
- Produces: `exporter.perfiles.Perfil` (atributos `id`, `label`, `datos`, y métodos `capacidad(nombre) -> str`, `presupuesto() -> int`, `modos() -> list`, `peligros_para(senal_id) -> list`, `caducado(hoy) -> bool`), `cargar_perfiles(directorio=None) -> dict`, `PerfilInvalido`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/test_perfiles.py`:

```python
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
```

- [ ] **Step 2: Ejecutar la prueba y comprobar que falla**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -p "test_perfiles.py" -v
```

Esperado: FAIL con `ModuleNotFoundError: No module named 'exporter.perfiles'`.

- [ ] **Step 3: Escribir el cargador**

Crear `skills/plugin-to-agentskills/scripts/exporter/perfiles.py`:

```python
"""Carga de los perfiles de destino.

Los perfiles son datos, no codigo: un JSON por destino en targets/. Anadir un
destino es escribir un fichero, no editar Python.

La validacion de aqui es la minima que el programa necesita para no romperse.
La validacion contra el JSON Schema completo la hace el CI, donde si se puede
instalar `jsonschema`.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

CLAVES_OBLIGATORIAS = ("id", "label", "instalacion", "formato",
                       "capacidades", "peligros", "evidencia")

DIRECTORIO_POR_DEFECTO = Path(__file__).resolve().parent / "targets"


class PerfilInvalido(Exception):
    """Un fichero de targets/ no se puede usar."""


class Perfil:

    def __init__(self, datos: dict):
        self.datos = datos
        self.id = datos["id"]
        self.label = datos["label"]

    def capacidad(self, nombre: str) -> str:
        """Nivel declarado, o 'desconocido' si el perfil no dice nada.

        Callar no es negar: una capacidad sin declarar produce no_verificable,
        nunca una conjetura.
        """
        return self.datos["capacidades"].get(nombre, "desconocido")

    def presupuesto(self) -> int:
        return int(self.datos["formato"]["presupuesto_description_bytes"])

    def modos(self) -> list:
        return list(self.datos["instalacion"]["modos"])

    def peligros_para(self, senal_id: str) -> list:
        return [p for p in self.datos["peligros"] if senal_id in p.get("dispara_con", [])]

    def limite(self, nombre: str):
        return self.datos.get("limites_paquete", {}).get(nombre)

    def caducado(self, hoy: datetime.date) -> bool:
        return datetime.date.fromisoformat(
            self.datos["evidencia"]["revisar_tras"]) < hoy

    def __repr__(self) -> str:
        return "<Perfil {}>".format(self.id)


def cargar_perfil(ruta: Path) -> Perfil:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PerfilInvalido("{}: JSON malformado en linea {}, columna {}: {}".format(
            ruta.name, e.lineno, e.colno, e.msg))
    faltan = [k for k in CLAVES_OBLIGATORIAS if k not in datos]
    if faltan:
        raise PerfilInvalido("{}: faltan claves obligatorias: {}".format(
            ruta.name, ", ".join(faltan)))
    return Perfil(datos)


def cargar_perfiles(directorio=None) -> dict:
    """Devuelve {id: Perfil} de todos los targets/*.json, salvo _schema.json."""
    directorio = Path(directorio) if directorio else DIRECTORIO_POR_DEFECTO
    perfiles = {}
    for ruta in sorted(directorio.glob("*.json")):
        if ruta.name.startswith("_"):
            continue
        perfil = cargar_perfil(ruta)
        if perfil.id != ruta.stem:
            raise PerfilInvalido(
                "{}: el id '{}' no coincide con el nombre del fichero".format(
                    ruta.name, perfil.id))
        perfiles[perfil.id] = perfil
    return perfiles
```

- [ ] **Step 4: Escribir el schema**

Crear `skills/plugin-to-agentskills/scripts/exporter/targets/_schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Perfil de destino",
  "type": "object",
  "required": ["schema_version", "id", "label", "instalacion", "formato",
               "capacidades", "peligros", "evidencia"],
  "additionalProperties": false,
  "properties": {
    "schema_version": { "const": 1 },
    "id": { "type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$" },
    "label": { "type": "string", "minLength": 1 },
    "instalacion": {
      "type": "object",
      "required": ["modos", "ruta_ui", "una_skill_por_subida"],
      "additionalProperties": false,
      "properties": {
        "modos": {
          "type": "array", "minItems": 1,
          "items": { "enum": ["zip", "carpeta", "directorio_local", "url_repositorio"] }
        },
        "ruta_ui": { "type": "string" },
        "una_skill_por_subida": { "type": "boolean" }
      }
    },
    "formato": {
      "type": "object",
      "required": ["acepta", "frontmatter_cerrado", "presupuesto_description_bytes",
                   "tope_duro_description", "conserva_arbol"],
      "additionalProperties": false,
      "properties": {
        "acepta": { "type": "array", "items": { "type": "string" } },
        "frontmatter_cerrado": { "type": "boolean" },
        "presupuesto_description_bytes": { "type": "integer", "minimum": 1 },
        "tope_duro_description": {
          "type": "object",
          "required": ["valor", "unidad"],
          "additionalProperties": false,
          "properties": {
            "valor": { "type": "integer", "minimum": 1 },
            "unidad": { "enum": ["bytes", "caracteres"] }
          }
        },
        "conserva_arbol": { "type": "boolean" }
      }
    },
    "limites_paquete": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "zip_max_bytes": { "type": ["integer", "null"], "minimum": 1 },
        "ficheros_max": { "type": ["integer", "null"], "minimum": 1 },
        "fichero_max_bytes": { "type": ["integer", "null"], "minimum": 1 }
      }
    },
    "capacidades": {
      "type": "object",
      "additionalProperties": {
        "enum": ["si", "si_con_confirmacion", "parcial", "no", "desconocido"]
      }
    },
    "peligros": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "dispara_con", "severidad", "titulo", "detalle",
                     "mitigacion", "evidencia"],
        "additionalProperties": false,
        "properties": {
          "id": { "type": "string" },
          "dispara_con": { "type": "array", "minItems": 1,
                           "items": { "type": "string" } },
          "severidad": { "enum": ["alta", "media", "baja"] },
          "titulo": { "type": "string" },
          "detalle": { "type": "string" },
          "mitigacion": { "type": "string" },
          "evidencia": { "$ref": "#/$defs/evidencia_breve" }
        }
      }
    },
    "evidencia": {
      "type": "object",
      "required": ["verificado_el", "revisar_tras", "confianza", "fuentes"],
      "additionalProperties": false,
      "properties": {
        "verificado_el": { "type": "string", "format": "date" },
        "revisar_tras": { "type": "string", "format": "date" },
        "confianza": { "$ref": "#/$defs/confianza" },
        "fuentes": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["titulo", "url"],
            "additionalProperties": false,
            "properties": {
              "titulo": { "type": "string" },
              "url": { "type": "string", "format": "uri" },
              "seccion": { "type": "string" }
            }
          }
        }
      }
    }
  },
  "$defs": {
    "confianza": {
      "enum": ["oficial", "oficial-incompleto", "observado", "comunidad", "no-verificado"]
    },
    "evidencia_breve": {
      "type": "object",
      "required": ["confianza", "verificado_el"],
      "additionalProperties": false,
      "properties": {
        "confianza": { "$ref": "#/$defs/confianza" },
        "verificado_el": { "type": "string", "format": "date" }
      }
    }
  }
}
```

- [ ] **Step 5: Escribir los cinco perfiles**

Los datos salen de `references/portabilidad.md` y del `README.md` actuales. Donde el documento no afirme nada, la capacidad va a `desconocido` — nunca a `no`.

`targets/mistral-vibe-work.json`:

```json
{
  "schema_version": 1,
  "id": "mistral-vibe-work",
  "label": "Mistral Vibe Work",
  "instalacion": {
    "modos": ["carpeta"],
    "ruta_ui": "chat.mistral.ai/work → Context → Skills → New Skill",
    "una_skill_por_subida": true
  },
  "formato": {
    "acepta": ["agent-skills"],
    "frontmatter_cerrado": true,
    "presupuesto_description_bytes": 490,
    "tope_duro_description": { "valor": 1024, "unidad": "caracteres" },
    "conserva_arbol": true
  },
  "limites_paquete": {
    "zip_max_bytes": null,
    "ficheros_max": null,
    "fichero_max_bytes": null
  },
  "capacidades": {
    "scripts.ejecutar": "no",
    "shell.ejecutar": "parcial",
    "filesystem.leer": "si",
    "filesystem.escribir": "si",
    "red.fetch": "desconocido",
    "mcp.cliente": "no",
    "applescript": "no",
    "subagentes": "no",
    "hooks": "no",
    "comandos.namespace": "no",
    "skills.anidadas": "no",
    "home.resolver": "no"
  },
  "peligros": [
    {
      "id": "mistral-estado-no-persiste",
      "dispara_con": ["estado-persistente"],
      "severidad": "alta",
      "titulo": "La escritura reporta éxito y el fichero puede no estar después",
      "detalle": "Reproducido en dos ejecuciones independientes: el anexado (>> fichero) devolvió éxito y luego el fichero tenía una sola línea, o no existía. Lo grave no es la pérdida: el agente reconstruye el registro de memoria y continúa como si nada, con un historial inventado que parece real.",
      "mitigacion": "Escribir el fichero entero de una vez en lugar de anexar, y releerlo para confirmar. Si falta, decirlo — nunca reconstruirlo de memoria.",
      "evidencia": { "confianza": "observado", "verificado_el": "2026-07-27" }
    },
    {
      "id": "mistral-home-es-raiz",
      "dispara_con": ["home-tilde"],
      "severidad": "alta",
      "titulo": "$HOME vale «/», así que ~/ escribe en la raíz",
      "detalle": "Comprobado en ejecución: la variable de entorno del home vale «/», de modo que ~/.mi-skill/ termina creando //.mi-skill/.",
      "mitigacion": "Usar rutas relativas a la carpeta de la skill, o pedir al usuario una ruta absoluta explícita.",
      "evidencia": { "confianza": "observado", "verificado_el": "2026-07-27" }
    }
  ],
  "evidencia": {
    "verificado_el": "2026-07-27",
    "revisar_tras": "2026-10-27",
    "confianza": "observado",
    "fuentes": [
      {
        "titulo": "Mistral Docs — Create your first Skill",
        "url": "https://docs.mistral.ai/getting-started/quickstarts/vibe-work/create-first-skill"
      }
    ]
  }
}
```

`targets/perplexity-computer.json`:

```json
{
  "schema_version": 1,
  "id": "perplexity-computer",
  "label": "Perplexity Computer",
  "instalacion": {
    "modos": ["zip"],
    "ruta_ui": "perplexity.ai/computer/skills → Create skill → Upload a skill",
    "una_skill_por_subida": true
  },
  "formato": {
    "acepta": ["agent-skills"],
    "frontmatter_cerrado": true,
    "presupuesto_description_bytes": 850,
    "tope_duro_description": { "valor": 1024, "unidad": "bytes" },
    "conserva_arbol": true
  },
  "limites_paquete": {
    "zip_max_bytes": null,
    "ficheros_max": null,
    "fichero_max_bytes": null
  },
  "capacidades": {
    "scripts.ejecutar": "si",
    "shell.ejecutar": "si",
    "filesystem.leer": "si",
    "filesystem.escribir": "si",
    "red.fetch": "si",
    "mcp.cliente": "no",
    "applescript": "si",
    "subagentes": "no",
    "hooks": "no",
    "comandos.namespace": "no",
    "skills.anidadas": "no",
    "home.resolver": "desconocido"
  },
  "peligros": [
    {
      "id": "perplexity-corte-90s",
      "dispara_con": ["applescript", "lote-destructivo"],
      "severidad": "alta",
      "titulo": "Cada llamada se corta en torno a los 90 segundos",
      "detalle": "Observado sobre un buzón de 358 correos: cada movimiento sincroniza contra iCloud y el lote no termina. Un lote cortado a mitad deja el trabajo inconsistente — el archivado se llevó unos 64 correos que no estaban en el lote evaluado, y un filtro que debía cortar en junio movió también correos de julio.",
      "mitigacion": "Procesar en trozos pequeños dimensionados para terminar dentro del límite, verificar releyendo el estado real después de cada trozo, y comprobar qué elementos se han tocado en vez de confiar en el filtro.",
      "evidencia": { "confianza": "observado", "verificado_el": "2026-07-27" }
    },
    {
      "id": "perplexity-descripcion-rechaza-zip",
      "dispara_con": [],
      "severidad": "media",
      "titulo": "Una descripción por encima del tope rechaza el zip entero",
      "detalle": "El tope de 1024 se mide en bytes UTF-8 aunque el mensaje de error diga «characters». Una descripción de 1063 caracteres pero 1085 bytes fue rechazada. En español cada tilde ocupa dos bytes y cada raya tres.",
      "mitigacion": "El conversor recorta a 850 bytes, con margen de sobra.",
      "evidencia": { "confianza": "observado", "verificado_el": "2026-07-27" }
    }
  ],
  "evidencia": {
    "verificado_el": "2026-07-27",
    "revisar_tras": "2026-10-27",
    "confianza": "observado",
    "fuentes": [
      {
        "titulo": "Perplexity — How to use Computer Skills",
        "url": "https://www.perplexity.ai/help-center/en/articles/13914413-how-to-use-computer-skills"
      },
      {
        "titulo": "Perplexity Research — Designing, Refining, and Maintaining Agent Skills",
        "url": "https://research.perplexity.ai/articles/designing-refining-and-maintaining-agent-skills-at-perplexity"
      }
    ]
  }
}
```

`targets/chatgpt.json`:

```json
{
  "schema_version": 1,
  "id": "chatgpt",
  "label": "ChatGPT",
  "instalacion": {
    "modos": ["url_repositorio", "zip"],
    "ruta_ui": "Con «Work» activado, en Complementos: buscar por nombre o añadir desde la URL del repositorio",
    "una_skill_por_subida": true
  },
  "formato": {
    "acepta": ["agent-skills", "agent-plugins"],
    "frontmatter_cerrado": true,
    "presupuesto_description_bytes": 850,
    "tope_duro_description": { "valor": 1024, "unidad": "caracteres" },
    "conserva_arbol": true
  },
  "limites_paquete": {
    "zip_max_bytes": 52428800,
    "ficheros_max": 500,
    "fichero_max_bytes": 26214400
  },
  "capacidades": {
    "scripts.ejecutar": "desconocido",
    "shell.ejecutar": "desconocido",
    "filesystem.leer": "desconocido",
    "filesystem.escribir": "desconocido",
    "red.fetch": "desconocido",
    "mcp.cliente": "no",
    "applescript": "no",
    "subagentes": "no",
    "hooks": "no",
    "comandos.namespace": "no",
    "skills.anidadas": "no",
    "home.resolver": "desconocido"
  },
  "peligros": [],
  "evidencia": {
    "verificado_el": "2026-08-07",
    "revisar_tras": "2026-11-07",
    "confianza": "oficial-incompleto",
    "fuentes": [
      {
        "titulo": "Agent Skills — Especificación",
        "url": "https://agentskills.io/specification"
      },
      {
        "titulo": "Agent Plugins 1.0.0 — Especificación",
        "url": "https://agent-plugins.org/specification"
      }
    ]
  }
}
```

`targets/claude-ai.json`:

```json
{
  "schema_version": 1,
  "id": "claude-ai",
  "label": "claude.ai",
  "instalacion": {
    "modos": ["zip"],
    "ruta_ui": "Ajustes → Capacidades → Skills → Subir skill",
    "una_skill_por_subida": true
  },
  "formato": {
    "acepta": ["agent-skills"],
    "frontmatter_cerrado": true,
    "presupuesto_description_bytes": 850,
    "tope_duro_description": { "valor": 1024, "unidad": "caracteres" },
    "conserva_arbol": true
  },
  "limites_paquete": {
    "zip_max_bytes": null,
    "ficheros_max": null,
    "fichero_max_bytes": null
  },
  "capacidades": {
    "scripts.ejecutar": "si",
    "shell.ejecutar": "si",
    "filesystem.leer": "si",
    "filesystem.escribir": "si",
    "red.fetch": "desconocido",
    "mcp.cliente": "no",
    "applescript": "no",
    "subagentes": "no",
    "hooks": "no",
    "comandos.namespace": "no",
    "skills.anidadas": "no",
    "home.resolver": "desconocido"
  },
  "peligros": [],
  "evidencia": {
    "verificado_el": "2026-08-07",
    "revisar_tras": "2026-11-07",
    "confianza": "oficial-incompleto",
    "fuentes": [
      {
        "titulo": "Agent Skills — Especificación",
        "url": "https://agentskills.io/specification"
      }
    ]
  }
}
```

`targets/claude-code.json`:

```json
{
  "schema_version": 1,
  "id": "claude-code",
  "label": "Claude Code",
  "instalacion": {
    "modos": ["directorio_local"],
    "ruta_ui": "Copiar la carpeta a ~/.claude/skills/, o instalar el plugin con /plugin install",
    "una_skill_por_subida": false
  },
  "formato": {
    "acepta": ["agent-skills", "claude-plugin"],
    "frontmatter_cerrado": false,
    "presupuesto_description_bytes": 1024,
    "tope_duro_description": { "valor": 1024, "unidad": "caracteres" },
    "conserva_arbol": true
  },
  "limites_paquete": {
    "zip_max_bytes": null,
    "ficheros_max": null,
    "fichero_max_bytes": null
  },
  "capacidades": {
    "scripts.ejecutar": "si",
    "shell.ejecutar": "si_con_confirmacion",
    "filesystem.leer": "si",
    "filesystem.escribir": "si_con_confirmacion",
    "red.fetch": "si",
    "mcp.cliente": "si",
    "applescript": "si_con_confirmacion",
    "subagentes": "si",
    "hooks": "si",
    "comandos.namespace": "si",
    "skills.anidadas": "si",
    "home.resolver": "si"
  },
  "peligros": [],
  "evidencia": {
    "verificado_el": "2026-08-07",
    "revisar_tras": "2026-11-07",
    "confianza": "oficial",
    "fuentes": [
      {
        "titulo": "Claude Code — Plugins reference",
        "url": "https://docs.claude.com/en/docs/claude-code/plugins-reference"
      }
    ]
  }
}
```

- [ ] **Step 6: Ejecutar las pruebas y comprobar que pasan**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -v
```

Esperado: PASS, sin fallos ni errores.

- [ ] **Step 7: Validar los perfiles contra el schema con `jsonschema`**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m pip install --quiet jsonschema && python3 - <<'PY'
import json, pathlib, jsonschema
d = pathlib.Path("skills/plugin-to-agentskills/scripts/exporter/targets")
esquema = json.loads((d / "_schema.json").read_text(encoding="utf-8"))
for p in sorted(d.glob("*.json")):
    if p.name.startswith("_"):
        continue
    jsonschema.validate(json.loads(p.read_text(encoding="utf-8")), esquema)
    print("OK", p.name)
PY
```

Esperado: cinco líneas `OK`.

- [ ] **Step 8: Commit**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && git add -A && git commit -m "$(cat <<'EOF'
Los cinco destinos pasan de constantes de Python a datos con evidencia

Hasta ahora BUDGET_MISTRAL y BUDGET_PERPLEXITY vivian en convert.py, las
capacidades en la prosa de portabilidad.md y las tablas en el README:
tres sitios que habia que hacer concordar a mano y ninguno con fecha.

Cada perfil declara ahora dos canales distintos. Las capacidades son
hechos declarativos, verificables leyendo documentacion. Los peligros son
hechos observacionales, solo accesibles ejecutando y mirando que pasa.
Tienen distinta fuente y distinta caducidad, y por eso llevan bloques de
evidencia independientes.

Donde no hay nada afirmable la capacidad va a «desconocido», nunca a «no».
Callar no es negar: en la tarea 6 eso produce no_verificable en vez de un
veredicto inventado. Por eso ChatGPT tiene casi todo en desconocido — su
sandbox no esta comprobado.

`revisar_tras` da al conocimiento una vida util de tres meses.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `compatibilidad.py` — el motor de estados

**Files:**
- Create: `skills/plugin-to-agentskills/scripts/exporter/compatibilidad.py`
- Create: `tests/test_compatibilidad.py`

**Interfaces:**
- Consumes: `exporter.modelo.{Estado, Evaluacion, SkillPortatil, Senal, Capacidad}`, `exporter.perfiles.Perfil`.
- Produces: `exporter.compatibilidad.evaluar(skill: SkillPortatil, perfil: Perfil, hoy: datetime.date) -> list[Evaluacion]` (una por modo de instalación), `ESTADO_POR_SEVERIDAD: dict`, `CAPACIDAD_SUFICIENTE: set`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/test_compatibilidad.py`:

```python
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
```

- [ ] **Step 2: Ejecutar la prueba y comprobar que falla**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -p "test_compatibilidad.py" -v
```

Esperado: FAIL con `ModuleNotFoundError: No module named 'exporter.compatibilidad'`.

- [ ] **Step 3: Escribir el motor**

Crear `skills/plugin-to-agentskills/scripts/exporter/compatibilidad.py`:

```python
"""Cruza lo que una skill exige con lo que un destino ofrece.

Dos canales, porque hay dos clases de hecho:

  - Capacidades: lo que el destino puede hacer. Presencia o ausencia.
  - Peligros de conducta: lo que el destino hace MAL teniendo la capacidad.

El segundo canal existe porque el primero no basta. Mistral Vibe Work
declara filesystem.escribir = «si» y es verdad: escribe. Lo que falla es que
la escritura no sobrevive y el agente reconstruye de memoria el registro
perdido. Por el canal de capacidades eso pasa la revision; solo el canal de
peligros lo detiene.
"""

from __future__ import annotations

import datetime

from exporter.modelo import Estado, Evaluacion

# Niveles con los que damos la capacidad por disponible. `parcial` no basta
# para una capacidad requerida: si solo funciona a medias, el resultado de la
# skill tambien.
CAPACIDAD_SUFICIENTE = {"si", "si_con_confirmacion"}

# Un peligro disparado contribuye este estado. Un peligro `alta` lleva a
# no_compatible aunque no falte ninguna capacidad: la skill se instala y se
# ejecuta, pero su consecuencia la hace inadecuada para ese destino.
ESTADO_POR_SEVERIDAD = {
    "alta": Estado.NO_COMPATIBLE,
    "media": Estado.DEGRADADO,
    "baja": Estado.COMPATIBLE,
}


def evaluar(skill, perfil, hoy: datetime.date) -> list:
    """Devuelve una Evaluacion por cada modo de instalacion del perfil."""
    motivos, peligros, estados = [], [], []

    # --- Canal 1: capacidades ---
    for cap in skill.capacidades:
        nivel = perfil.capacidad(cap.nombre)
        if nivel in CAPACIDAD_SUFICIENTE:
            continue
        if nivel == "desconocido":
            estados.append(Estado.NO_VERIFICABLE)
            motivos.append(
                "{}: el perfil no declara esta capacidad, asi que no se puede "
                "afirmar nada.".format(cap.nombre))
        elif cap.nivel == "requerida":
            estados.append(Estado.NO_COMPATIBLE)
            motivos.append(
                "{}: requerida por la skill y el destino la declara «{}».".format(
                    cap.nombre, nivel))
        else:
            estados.append(Estado.DEGRADADO)
            motivos.append(
                "{}: opcional, y el destino la declara «{}».".format(cap.nombre, nivel))

    # --- Canal 2: peligros de conducta ---
    vistos = set()
    for senal in skill.senales:
        for peligro in perfil.peligros_para(senal.id):
            if peligro["id"] in vistos:
                continue
            vistos.add(peligro["id"])
            peligros.append(peligro)
            estados.append(ESTADO_POR_SEVERIDAD[peligro["severidad"]])
            motivos.append("{} (visto en {}).".format(peligro["titulo"], senal.ubicacion))

    # --- Caducidad de la evidencia ---
    if perfil.caducado(hoy):
        estados.append(Estado.NO_VERIFICABLE)
        motivos.append(
            "La evidencia de este perfil venció el {} (revisar_tras) y no se ha "
            "vuelto a comprobar.".format(perfil.datos["evidencia"]["revisar_tras"]))

    # --- Adaptaciones aplicadas ---
    if skill.adaptaciones:
        estados.append(Estado.COMPATIBLE_CON_ADAPTACION)

    estado = Estado.peor(estados)
    return [Evaluacion(destino=perfil.id, modo_instalacion=modo, estado=estado,
                       motivos=list(motivos), peligros=list(peligros),
                       bloqueo_seguridad=None)
            for modo in perfil.modos()]
```

- [ ] **Step 4: Ejecutar las pruebas y comprobar que pasan**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -v
```

Esperado: PASS, sin fallos ni errores.

- [ ] **Step 5: Commit**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && git add -A && git commit -m "$(cat <<'EOF'
Anade el motor: senales por perfil dan un estado por destino

Sustituye el veredicto unico de riesgo por skill, que pretendia valer para
cinco destinos con capacidades distintas y por eso acababa siendo
pesimista en todos. Una skill con scripts/ es ahora no_compatible en
Mistral, que no tiene Python, y compatible en Perplexity, que si.

Los dos canales se ven en la prueba de estado-persistente: Mistral declara
filesystem.escribir = «si» y el canal de capacidades la deja pasar. Es el
peligro de conducta, con severidad alta, el que la detiene.

`desconocido` produce no_verificable, nunca una conjetura, y `parcial` no
basta para una capacidad requerida: si el destino solo cumple a medias, el
resultado de la skill tambien.

La caducidad degrada a no_verificable pero no rescata un no_compatible:
que el conocimiento envejezca no vuelve compatible lo que no lo era.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `empaquetado.py` y la fuga por enlaces simbólicos

**Files:**
- Create: `skills/plugin-to-agentskills/scripts/exporter/empaquetado.py`
- Create: `tests/test_empaquetado.py`
- Modify: `skills/plugin-to-agentskills/scripts/convert.py:558-563`, `:633-645`, `:679-686`

**Interfaces:**
- Consumes: `exporter.modelo.Senal`, `exporter.frontmatter.yaml_escape`, `exporter.perfiles.Perfil`.
- Produces: `exporter.empaquetado.copiar_skill(src: Path, dest: Path, ignorar: set) -> list[Senal]`, `zip_dir(src: Path, dest_zip: Path, arc_prefix: str) -> None`, `comprobar_limites(zip_path: Path, perfil: Perfil) -> list[str]`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/test_empaquetado.py`:

```python
import tempfile
import unittest
import zipfile
from pathlib import Path

from ayuda import importar_exporter

importar_exporter()

from exporter.empaquetado import comprobar_limites, copiar_skill, zip_dir  # noqa: E402
from exporter.perfiles import cargar_perfiles  # noqa: E402


class CopiaSinSeguirEnlaces(unittest.TestCase):

    def test_no_copia_el_contenido_de_un_enlace(self):
        # copytree con symlinks=False copia el CONTENIDO de lo apuntado. Un
        # enlace a ~/.ssh/id_rsa acabaria dentro del zip que se sube a
        # ChatGPT o a Perplexity.
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            secreto = raiz / "secreto.txt"
            secreto.write_text("CLAVE-PRIVADA-QUE-NO-DEBE-VIAJAR", encoding="utf-8")

            origen = raiz / "skill"
            origen.mkdir()
            (origen / "nota.md").write_text("contenido normal", encoding="utf-8")
            (origen / "trampa.txt").symlink_to(secreto)

            destino = raiz / "salida"
            senales = copiar_skill(origen, destino, ignorar=set())

            self.assertFalse((destino / "trampa.txt").exists())
            self.assertTrue((destino / "nota.md").exists())
            copiado = "".join(p.read_text(encoding="utf-8")
                              for p in destino.rglob("*") if p.is_file())
            self.assertNotIn("CLAVE-PRIVADA-QUE-NO-DEBE-VIAJAR", copiado)

            self.assertEqual(len(senales), 1)
            self.assertEqual(senales[0].id, "enlace-simbolico")
            self.assertEqual(senales[0].severidad_base, "alta")
            self.assertIn("trampa.txt", senales[0].ubicacion)

    def test_una_skill_sin_enlaces_no_produce_senales(self):
        with tempfile.TemporaryDirectory() as tmp:
            origen = Path(tmp) / "skill"
            (origen / "references").mkdir(parents=True)
            (origen / "references" / "guia.md").write_text("hola", encoding="utf-8")
            senales = copiar_skill(origen, Path(tmp) / "salida", ignorar=set())
            self.assertEqual(senales, [])
            self.assertTrue((Path(tmp) / "salida" / "references" / "guia.md").exists())

    def test_respeta_los_nombres_ignorados(self):
        with tempfile.TemporaryDirectory() as tmp:
            origen = Path(tmp) / "skill"
            (origen / "__pycache__").mkdir(parents=True)
            (origen / "__pycache__" / "x.pyc").write_bytes(b"\x00")
            (origen / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
            copiar_skill(origen, Path(tmp) / "salida", ignorar={"__pycache__", "SKILL.md"})
            self.assertFalse((Path(tmp) / "salida" / "__pycache__").exists())
            self.assertFalse((Path(tmp) / "salida" / "SKILL.md").exists())


class LimitesDePaquete(unittest.TestCase):

    def test_chatgpt_rechaza_demasiados_ficheros(self):
        perfil = cargar_perfiles()["chatgpt"]
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "grande.zip"
            with zipfile.ZipFile(z, "w") as zf:
                for i in range(501):
                    zf.writestr("f{}.txt".format(i), "x")
            avisos = comprobar_limites(z, perfil)
            self.assertTrue(any("ficheros" in a for a in avisos))

    def test_un_paquete_normal_no_produce_avisos(self):
        perfil = cargar_perfiles()["chatgpt"]
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "normal.zip"
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("SKILL.md", "---\nname: x\n---\n")
            self.assertEqual(comprobar_limites(z, perfil), [])

    def test_un_perfil_sin_limites_declarados_no_comprueba_nada(self):
        perfil = cargar_perfiles()["mistral-vibe-work"]
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "x.zip"
            with zipfile.ZipFile(z, "w") as zf:
                for i in range(600):
                    zf.writestr("f{}.txt".format(i), "x")
            self.assertEqual(comprobar_limites(z, perfil), [])


class Empaquetado(unittest.TestCase):

    def test_el_zip_lleva_la_carpeta_de_la_skill_en_la_raiz(self):
        with tempfile.TemporaryDirectory() as tmp:
            origen = Path(tmp) / "mi-skill"
            origen.mkdir()
            (origen / "SKILL.md").write_text("---\nname: mi-skill\n---\n", encoding="utf-8")
            z = Path(tmp) / "mi-skill.zip"
            zip_dir(origen, z, arc_prefix="mi-skill")
            with zipfile.ZipFile(z) as zf:
                self.assertEqual(zf.namelist(), ["mi-skill/SKILL.md"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar la prueba y comprobar que falla**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -p "test_empaquetado.py" -v
```

Esperado: FAIL con `ModuleNotFoundError: No module named 'exporter.empaquetado'`.

- [ ] **Step 3: Escribir el módulo**

Crear `skills/plugin-to-agentskills/scripts/exporter/empaquetado.py`:

```python
"""Copia y empaquetado de la skill exportada.

La copia NO sigue enlaces simbolicos. shutil.copytree con symlinks=False
—su valor por defecto— copia el CONTENIDO de lo apuntado, no el enlace: una
skill con un enlace a ~/.ssh/id_rsa o a un .env vería ese contenido dentro
del .zip que despues se sube a una plataforma ajena. Poner symlinks=True
tampoco basta, porque zipfile.write() vuelve a seguirlo al empaquetar. La
unica salida segura es omitirlos y avisar.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

from exporter.modelo import Senal


def copiar_skill(src: Path, dest: Path, ignorar: set) -> list:
    """Copia el arbol omitiendo enlaces simbolicos y nombres ignorados.

    Devuelve una Senal por cada enlace omitido.
    """
    src, dest = Path(src), Path(dest)
    senales = []
    for base, dirs, ficheros in os.walk(str(src)):
        dirs[:] = [d for d in dirs
                   if d not in ignorar and not os.path.islink(os.path.join(base, d))]
        for d in sorted(os.listdir(base)):
            ruta = os.path.join(base, d)
            if os.path.isdir(ruta) and os.path.islink(ruta):
                senales.append(_senal_enlace(ruta, src))
        relativa = os.path.relpath(base, str(src))
        destino_base = dest if relativa == "." else dest / relativa
        destino_base.mkdir(parents=True, exist_ok=True)
        for nombre in sorted(ficheros):
            if nombre in ignorar:
                continue
            origen = os.path.join(base, nombre)
            if os.path.islink(origen):
                senales.append(_senal_enlace(origen, src))
                continue
            (destino_base / nombre).write_bytes(Path(origen).read_bytes())
    return senales


def _senal_enlace(ruta: str, raiz: Path) -> Senal:
    relativa = os.path.relpath(ruta, str(raiz))
    try:
        apunta = os.readlink(ruta)
    except OSError:
        apunta = "(ilegible)"
    return Senal(
        "enlace-simbolico", relativa,
        "enlace a {}".format(apunta), "alta")


def zip_dir(src: Path, dest_zip: Path, arc_prefix: str = "") -> None:
    """Empaqueta el arbol. Una skill por zip, con su carpeta en la raiz."""
    dest_zip = Path(dest_zip)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(Path(src).rglob("*")):
            if p.is_symlink() or not p.is_file():
                continue
            arc = Path(arc_prefix) / p.relative_to(src) if arc_prefix else p.relative_to(src)
            z.write(p, arc.as_posix())


def comprobar_limites(zip_path: Path, perfil) -> list:
    """Compara el paquete con los limites que declara el destino.

    Un limite a null significa que el destino no lo publica, y entonces no se
    comprueba. No es lo mismo que un limite infinito, pero es lo unico
    afirmable.
    """
    avisos = []
    tam_max = perfil.limite("zip_max_bytes")
    n_max = perfil.limite("ficheros_max")
    f_max = perfil.limite("fichero_max_bytes")

    tam = Path(zip_path).stat().st_size
    if tam_max is not None and tam > tam_max:
        avisos.append("El zip ocupa {} bytes y {} admite {}.".format(
            tam, perfil.label, tam_max))
    with zipfile.ZipFile(zip_path) as z:
        info = z.infolist()
    if n_max is not None and len(info) > n_max:
        avisos.append("El zip lleva {} ficheros y {} admite {}.".format(
            len(info), perfil.label, n_max))
    if f_max is not None:
        for i in info:
            if i.file_size > f_max:
                avisos.append("«{}» ocupa {} bytes descomprimido y {} admite {}.".format(
                    i.filename, i.file_size, perfil.label, f_max))
    return avisos
```

- [ ] **Step 4: Ejecutar las pruebas y comprobar que pasan**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -v
```

Esperado: PASS, sin fallos ni errores.

- [ ] **Step 5: Sustituir la copia y el zip en `convert.py`**

En `audit_and_adapt`, reemplazar la llamada a `shutil.copytree` (líneas 558-563) por:

```python
    dest = out_dir / name
    if dest.exists():
        shutil.rmtree(dest)
    enlaces = copiar_skill(src_dir, dest, ignorar=set(IGNORED_DIRS) | {"SKILL.md"})
    for s in enlaces:
        res.findings.append(Finding("alta", "enlace-simbolico",
            "Se omitió un enlace simbólico al empaquetar: {} ({}). Copiar su "
            "contenido habría metido en el paquete un fichero de fuera de la "
            "skill.".format(s.ubicacion, s.muestra)))
```

Borrar la función `zip_dir` de `convert.py` (líneas 679-686) y añadir el import:

```python
from exporter.empaquetado import comprobar_limites, copiar_skill, zip_dir
```

- [ ] **Step 6: Comprobar de punta a punta que el enlace no viaja**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && rm -rf /tmp/fuga && mkdir -p /tmp/fuga/skills/prueba && printf 'CLAVE-PRIVADA\n' > /tmp/fuga/secreto.txt && printf -- '---\nname: prueba\ndescription: Cárgala cuando el usuario lo pida.\n---\n# Prueba\n' > /tmp/fuga/skills/prueba/SKILL.md && ln -s /tmp/fuga/secreto.txt /tmp/fuga/skills/prueba/trampa.txt && python3 skills/plugin-to-agentskills/scripts/convert.py /tmp/fuga --out /tmp/fuga-salida >/dev/null && (unzip -p /tmp/fuga-salida/prueba.zip '*' 2>/dev/null | grep -q "CLAVE-PRIVADA" && echo "FUGA: el secreto viajo" && exit 1 || echo "SIN FUGA: OK")
```

Esperado: `SIN FUGA: OK`.

- [ ] **Step 7: Commit**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && git add -A && git commit -m "$(cat <<'EOF'
Deja de copiar el contenido de los enlaces simbolicos al paquete

shutil.copytree usa symlinks=False por defecto, y eso no significa
«ignorar los enlaces» sino «copiar el contenido de lo que apuntan». Una
skill con un enlace a ~/.ssh/id_rsa, a un .env o a cualquier fichero fuera
de su arbol veia ese contenido dentro del .zip que despues se sube a
ChatGPT o a Perplexity. Estaba en produccion.

Poner symlinks=True no arregla nada: zipfile.write() vuelve a seguir el
enlace al empaquetar. La unica salida es omitirlos, y avisar de que se han
omitido para que nadie descubra en el destino que falta un fichero.

Se anade tambien la comprobacion de limites del paquete contra los que
declara el perfil: 50 MB, 500 ficheros y 25 MB por fichero en ChatGPT. Un
limite a null no se comprueba, porque «no publicado» no es «infinito».

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `informes.py` — matriz de compatibilidad y `resumen.json`

**Files:**
- Create: `skills/plugin-to-agentskills/scripts/exporter/informes.py`
- Create: `skills/plugin-to-agentskills/scripts/exporter/resumen.schema.json`
- Create: `tests/test_informes.py`
- Modify: `skills/plugin-to-agentskills/scripts/convert.py:688-735`

**Interfaces:**
- Consumes: `exporter.modelo.Estado`, `exporter.compatibilidad.evaluar`.
- Produces: `exporter.informes.informe_markdown(resultados: list, evaluaciones: dict, origen: str, perfiles: dict) -> str`, `resumen_json(resultados: list, evaluaciones: dict, origen: str) -> dict`, `ICONO: dict`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/test_informes.py`:

```python
import unittest

from ayuda import importar_exporter

importar_exporter()

from exporter.informes import informe_markdown, resumen_json  # noqa: E402
from exporter.modelo import Estado, Evaluacion  # noqa: E402
from exporter.perfiles import cargar_perfiles  # noqa: E402


class Resultado:
    """Doble minimo de SkillResult, lo justo para el informe."""

    def __init__(self, name):
        self.name = name
        self.description = "Cárgala cuando el usuario lo pida."
        self.src_dir = "skills/" + name
        self.findings = []
        self.adaptations = []
        self.extra_files = []


def evs(destino, estado, motivos=()):
    return [Evaluacion(destino=destino, modo_instalacion="zip", estado=estado,
                       motivos=list(motivos))]


class InformeMarkdown(unittest.TestCase):

    def setUp(self):
        self.perfiles = cargar_perfiles()
        self.res = [Resultado("email-triage")]
        self.evaluaciones = {
            "email-triage": {
                "mistral-vibe-work": evs("mistral-vibe-work", Estado.NO_COMPATIBLE,
                                         ["scripts.ejecutar: requerida y el destino la declara «no»."]),
                "perplexity-computer": evs("perplexity-computer", Estado.COMPATIBLE),
            }
        }

    def test_lleva_la_matriz_con_una_columna_por_destino(self):
        md = informe_markdown(self.res, self.evaluaciones, "./x", self.perfiles)
        self.assertIn("## Matriz de compatibilidad", md)
        self.assertIn("Mistral Vibe Work", md)
        self.assertIn("Perplexity Computer", md)

    def test_la_advertencia_de_probar_en_destino_es_obligatoria(self):
        md = informe_markdown(self.res, self.evaluaciones, "./x", self.perfiles)
        self.assertIn("Ningún veredicto sustituye a probar la skill en el destino.", md)

    def test_ningun_estado_aparece_sin_motivo(self):
        md = informe_markdown(self.res, self.evaluaciones, "./x", self.perfiles)
        self.assertIn("scripts.ejecutar", md)


class ResumenJson(unittest.TestCase):

    def setUp(self):
        self.res = [Resultado("email-triage")]
        self.evaluaciones = {
            "email-triage": {
                "claude-code": evs("claude-code", Estado.COMPATIBLE),
            }
        }

    def test_estructura_minima(self):
        d = resumen_json(self.res, self.evaluaciones, "./x")
        self.assertEqual(d["report_version"], "2.0")
        self.assertEqual(d["origen"], "./x")
        skill = d["skills"][0]
        self.assertEqual(skill["name"], "email-triage")
        self.assertEqual(skill["compatibilidad"]["claude-code"][0]["estado"], "compatible")

    def test_el_bloqueo_de_seguridad_va_reservado_a_null(self):
        d = resumen_json(self.res, self.evaluaciones, "./x")
        self.assertIsNone(d["skills"][0]["compatibilidad"]["claude-code"][0]["bloqueo_seguridad"])

    def test_es_serializable_y_estable(self):
        import json
        a = json.dumps(resumen_json(self.res, self.evaluaciones, "./x"), sort_keys=True)
        b = json.dumps(resumen_json(self.res, self.evaluaciones, "./x"), sort_keys=True)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar la prueba y comprobar que falla**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -p "test_informes.py" -v
```

Esperado: FAIL con `ModuleNotFoundError: No module named 'exporter.informes'`.

- [ ] **Step 3: Escribir el módulo**

Crear `skills/plugin-to-agentskills/scripts/exporter/informes.py`:

```python
"""Informe legible y resumen en JSON.

El informe se abre con la matriz porque es la respuesta que el usuario viene
a buscar: no «cuanto riesgo tiene esta skill», sino «donde puedo subirla».
"""

from __future__ import annotations

from exporter.modelo import Estado

ICONO = {
    Estado.COMPATIBLE: "🟢",
    Estado.COMPATIBLE_CON_ADAPTACION: "🟡",
    Estado.DEGRADADO: "🟠",
    Estado.NO_VERIFICABLE: "🔵",
    Estado.NO_COMPATIBLE: "🔴",
}

ETIQUETA = {
    Estado.COMPATIBLE: "compatible",
    Estado.COMPATIBLE_CON_ADAPTACION: "adaptación",
    Estado.DEGRADADO: "degradado",
    Estado.NO_VERIFICABLE: "no verificable",
    Estado.NO_COMPATIBLE: "no compatible",
}


def _celda(evaluaciones) -> str:
    if not evaluaciones:
        return "—"
    estado = Estado.peor([e.estado for e in evaluaciones])
    return "{} {}".format(ICONO[estado], ETIQUETA[estado])


def informe_markdown(resultados, evaluaciones, origen, perfiles) -> str:
    ids = sorted(perfiles)
    L = [
        "# Informe de portabilidad",
        "",
        "- **Origen:** `{}`".format(origen),
        "- **Skills analizadas:** {}".format(len(resultados)),
        "",
        "## Matriz de compatibilidad",
        "",
        "| Skill | " + " | ".join(perfiles[i].label for i in ids) + " |",
        "|---" * (len(ids) + 1) + "|",
    ]
    for r in resultados:
        celdas = [_celda(evaluaciones.get(r.name, {}).get(i, [])) for i in ids]
        L.append("| `{}` | {} |".format(r.name, " | ".join(celdas)))
    L += [
        "",
        "> Ningún veredicto sustituye a probar la skill en el destino.",
        "",
        "## Detalle por skill",
        "",
    ]
    for r in resultados:
        L += ["### `{}`".format(r.name), "",
              "- Origen: `{}`".format(r.src_dir),
              "- Descripción: {}".format(r.description[:300]), ""]
        if r.adaptations:
            L += ["**Adaptado automáticamente:**", ""]
            L += ["- {}".format(a) for a in r.adaptations]
            L.append("")
        for i in ids:
            for ev in evaluaciones.get(r.name, {}).get(i, []):
                if ev.estado == Estado.COMPATIBLE:
                    continue
                L.append("**{} · {} ({})** — {}".format(
                    ICONO[ev.estado], perfiles[i].label, ev.modo_instalacion,
                    ETIQUETA[ev.estado]))
                L.append("")
                L += ["- {}".format(m) for m in ev.motivos]
                for p in ev.peligros:
                    L.append("- *Mitigación:* {}".format(p["mitigacion"]))
                    L.append("  Evidencia: {} · verificado el {}.".format(
                        p["evidencia"]["confianza"], p["evidencia"]["verificado_el"]))
                L.append("")
    return "\n".join(L) + "\n"


def resumen_json(resultados, evaluaciones, origen) -> dict:
    return {
        "report_version": "2.0",
        "origen": origen,
        "skills": [
            {
                "name": r.name,
                "adaptaciones": list(r.adaptations),
                "hallazgos": [
                    {"severidad": f.severity, "codigo": f.code, "mensaje": f.message}
                    for f in r.findings
                ],
                "compatibilidad": {
                    destino: [
                        {
                            "modo_instalacion": ev.modo_instalacion,
                            "estado": ev.estado,
                            "motivos": list(ev.motivos),
                            "peligros": [p["id"] for p in ev.peligros],
                            "bloqueo_seguridad": ev.bloqueo_seguridad,
                        }
                        for ev in evs
                    ]
                    for destino, evs in sorted(evaluaciones.get(r.name, {}).items())
                },
            }
            for r in resultados
        ],
    }
```

- [ ] **Step 4: Escribir el schema del resumen**

Crear `skills/plugin-to-agentskills/scripts/exporter/resumen.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "resumen.json",
  "type": "object",
  "required": ["report_version", "origen", "skills"],
  "additionalProperties": false,
  "properties": {
    "report_version": { "const": "2.0" },
    "origen": { "type": "string" },
    "skills": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "adaptaciones", "hallazgos", "compatibilidad"],
        "additionalProperties": false,
        "properties": {
          "name": { "type": "string" },
          "adaptaciones": { "type": "array", "items": { "type": "string" } },
          "hallazgos": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["severidad", "codigo", "mensaje"],
              "additionalProperties": false,
              "properties": {
                "severidad": { "enum": ["alta", "media", "baja"] },
                "codigo": { "type": "string" },
                "mensaje": { "type": "string" }
              }
            }
          },
          "compatibilidad": {
            "type": "object",
            "additionalProperties": {
              "type": "array",
              "items": {
                "type": "object",
                "required": ["modo_instalacion", "estado", "motivos",
                             "peligros", "bloqueo_seguridad"],
                "additionalProperties": false,
                "properties": {
                  "modo_instalacion": {
                    "enum": ["zip", "carpeta", "directorio_local", "url_repositorio"]
                  },
                  "estado": {
                    "enum": ["compatible", "compatible_con_adaptacion", "degradado",
                             "no_verificable", "no_compatible"]
                  },
                  "motivos": { "type": "array", "items": { "type": "string" } },
                  "peligros": { "type": "array", "items": { "type": "string" } },
                  "bloqueo_seguridad": { "type": "null" }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

`bloqueo_seguridad` se declara `"type": "null"` a propósito: mientras no exista el motor de seguridad, cualquier otro valor es un error, y el schema lo detecta.

- [ ] **Step 5: Ejecutar las pruebas y comprobar que pasan**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -v
```

Esperado: PASS, sin fallos ni errores.

- [ ] **Step 6: Sustituir `write_report` en `convert.py`**

Borrar `write_report` (líneas 688-735). En `main`, sustituir el bloque que escribe el informe y `resumen.json` por:

```python
        perfiles = cargar_perfiles()
        hoy = datetime.date.today()
        evaluaciones = {}
        for r in results:
            skill = a_skill_portatil(r)
            evaluaciones[r.name] = {
                pid: evaluar(skill, perfil, hoy) for pid, perfil in perfiles.items()
            }

        (out / "INFORME-PORTABILIDAD.md").write_text(
            informe_markdown(results, evaluaciones, args.source, perfiles),
            encoding="utf-8")
        (out / "resumen.json").write_text(
            json.dumps(resumen_json(results, evaluaciones, args.source),
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
```

Añadir en `convert.py` la función puente, que construye el modelo intermedio a partir del `SkillResult` que ya se calcula:

```python
def a_skill_portatil(res) -> SkillPortatil:
    """Convierte el SkillResult del conversor en el modelo intermedio.

    Puente temporal: SkillResult existe desde antes del modelo y sigue siendo
    lo que manejan audit_and_adapt y el empaquetado.
    """
    skill = SkillPortatil(
        nombre=res.name, nombre_original=res.orig_name, carpeta=str(res.src_dir),
        descripcion=res.description, descripcion_bytes=nbytes(res.description),
        tiene_activacion=tiene_activacion(res.description),
        cuerpo_tokens=len(res.body) // CHARS_PER_TOKEN,
        ficheros=list(res.extra_files),
        tiene_scripts=any(f.startswith("scripts/") for f in res.extra_files),
        senales=list(res.senales), adaptaciones=list(res.adaptations))
    skill.capacidades = capacidades_de(skill.senales, skill.tiene_scripts)
    return skill
```

Para que exista `res.senales`, añadir el campo `senales: list = field(default_factory=list)` a `SkillResult` y, en `audit_and_adapt`, guardar en él el resultado de `detectar_en_arbol(src_dir)` además de convertirlo en `findings`.

Añadir los imports que faltan:

```python
import datetime

from exporter.compatibilidad import evaluar
from exporter.informes import informe_markdown, resumen_json
from exporter.modelo import SkillPortatil, capacidades_de
from exporter.perfiles import cargar_perfiles
```

- [ ] **Step 6b: Los presupuestos salen del perfil, no de constantes**

Es el paso que cierra el objetivo de la rebanada: mientras `BUDGET_MISTRAL` y
`BUDGET_PERPLEXITY` sigan escritos en `convert.py`, añadir un destino seguirá exigiendo
editar Python. Hay unos trece usos repartidos entre `audit_and_adapt`, el informe y los
mensajes finales de `main`.

Añadir a `exporter/perfiles.py`:

```python
def presupuesto_por_modo(perfiles: dict, modo: str) -> int:
    """El presupuesto mas restrictivo entre los destinos que aceptan ese modo.

    El artefacto es uno solo por modo —una carpeta, un zip— y tiene que valer
    para todos los destinos que lo admitan, asi que manda el mas estrecho.
    """
    presupuestos = [p.presupuesto() for p in perfiles.values() if modo in p.modos()]
    if not presupuestos:
        raise PerfilInvalido(
            "ningun perfil declara el modo de instalacion '{}'".format(modo))
    return min(presupuestos)
```

En `convert.py`: borrar `BUDGET_MISTRAL`, `BUDGET_PERPLEXITY` y `BUDGET_DEFAULT`, cargar
los perfiles una sola vez al principio de `main` y pasar los dos presupuestos a
`audit_and_adapt(skill_md, out_dir, presupuesto_carpeta, presupuesto_zip, reorder=True)`.
Sustituir cada uso de la constante por el parámetro correspondiente, incluidos los textos
de los avisos y los mensajes finales.

```python
    presupuesto_carpeta = presupuesto_por_modo(perfiles, "carpeta")   # Mistral: 490
    presupuesto_zip = presupuesto_por_modo(perfiles, "zip")           # el resto: 850
```

Los valores resultantes son idénticos a los de hoy, así que **la salida no debe cambiar**.
Ésa es justo la comprobación: si cambia, la derivación está mal.

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -c "
import sys; sys.path.insert(0,'skills/plugin-to-agentskills/scripts')
from exporter.perfiles import cargar_perfiles, presupuesto_por_modo
p = cargar_perfiles()
assert presupuesto_por_modo(p,'carpeta') == 490, presupuesto_por_modo(p,'carpeta')
assert presupuesto_por_modo(p,'zip') == 850, presupuesto_por_modo(p,'zip')
print('presupuestos derivados del perfil: 490 carpeta / 850 zip — OK')
" && grep -c "BUDGET_" skills/plugin-to-agentskills/scripts/convert.py
```

Esperado: el mensaje de OK y `0` usos de `BUDGET_`.

- [ ] **Step 7: Comprobar la matriz de punta a punta**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 skills/plugin-to-agentskills/scripts/convert.py . --out /tmp/salida-t8 && sed -n '/## Matriz/,/^$/p' /tmp/salida-t8/INFORME-PORTABILIDAD.md && python3 -c "import json;d=json.load(open('/tmp/salida-t8/resumen.json'));print(json.dumps(d['skills'][0]['compatibilidad'],ensure_ascii=False)[:400])"
```

Esperado: una tabla con cinco columnas de destino y un JSON con las cinco claves de destino.

- [ ] **Step 8: Commit**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && git add -A && git commit -m "$(cat <<'EOF'
El informe se abre con la matriz, no con un riesgo agregado

La pregunta que trae aqui al usuario no es «cuanto riesgo tiene esta
skill» sino «donde puedo subirla». Un unico numero que promedia cinco
destinos heterogeneos no responde ninguna de las dos.

resumen.json conserva el nombre para no romper a quien lo consuma, sube a
report_version 2.0 y valida contra schema. `bloqueo_seguridad` se declara
"type": "null": mientras no exista el motor de seguridad, cualquier otro
valor es un error y el schema lo detecta.

Ningun estado se imprime sin su motivo, y los peligros arrastran su
mitigacion y la fecha en que se comprobaron.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: CLI con `inspect`, `audit` y `export`

**Files:**
- Modify: `skills/plugin-to-agentskills/scripts/convert.py:756-832`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: `convert.construir_parser() -> argparse.ArgumentParser`, `convert.normalizar_argv(argv: list) -> list`, `convert.main(argv=None) -> int`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/test_cli.py`:

```python
import unittest

from ayuda import importar_exporter

importar_exporter()

import convert  # noqa: E402


class CompatibilidadHaciaAtras(unittest.TestCase):

    def test_una_ruta_suelta_se_interpreta_como_export(self):
        # `convert.py <origen>` funcionaba antes de existir los subcomandos.
        # El «Paso 0» de la skill y el comando /exportar-skills lo usan asi.
        self.assertEqual(normalizar(["./mi-plugin"]), ["export", "./mi-plugin"])

    def test_una_url_suelta_tambien(self):
        self.assertEqual(normalizar(["https://github.com/u/r", "--out", "d"]),
                         ["export", "https://github.com/u/r", "--out", "d"])

    def test_un_subcomando_explicito_se_respeta(self):
        self.assertEqual(normalizar(["audit", "./x"]), ["audit", "./x"])

    def test_las_opciones_de_ayuda_no_se_tocan(self):
        self.assertEqual(normalizar(["--help"]), ["--help"])


def normalizar(argv):
    return convert.normalizar_argv(argv)


class Parser(unittest.TestCase):

    def test_inspect_no_admite_target(self):
        p = convert.construir_parser()
        with self.assertRaises(SystemExit):
            p.parse_args(["inspect", "./x", "--target", "chatgpt"])

    def test_audit_admite_varios_targets(self):
        args = convert.construir_parser().parse_args(
            ["audit", "./x", "--target", "chatgpt", "claude-code"])
        self.assertEqual(args.target, ["chatgpt", "claude-code"])

    def test_fail_on_por_defecto_es_ninguno(self):
        args = convert.construir_parser().parse_args(["audit", "./x"])
        self.assertEqual(args.fail_on, "ninguno")

    def test_export_conserva_las_opciones_heredadas(self):
        args = convert.construir_parser().parse_args(
            ["export", "./x", "--out", "d", "--only", "a", "b", "--zip-only",
             "--keep-description-order"])
        self.assertEqual(args.out, "d")
        self.assertEqual(args.only, ["a", "b"])
        self.assertTrue(args.zip_only)
        self.assertTrue(args.keep_description_order)


class DestinoDesconocido(unittest.TestCase):

    def test_lista_los_ids_disponibles(self):
        codigo = convert.main(["audit", ".", "--target", "no-existe"])
        self.assertEqual(codigo, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar la prueba y comprobar que falla**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -p "test_cli.py" -v
```

Esperado: FAIL con `AttributeError: module 'convert' has no attribute 'normalizar_argv'`.

- [ ] **Step 3: Reescribir la CLI**

Sustituir `main()` en `convert.py` por:

```python
SUBCOMANDOS = ("inspect", "audit", "export")


def normalizar_argv(argv: list) -> list:
    """Antepone `export` cuando el primer argumento es un origen suelto.

    `convert.py <repo>` funcionaba antes de que existieran los subcomandos, y
    lo usan el «Paso 0» del SKILL.md, el comando /exportar-skills y el
    workflow de CI. Romperlo llegaria a todo el que tenga el plugin
    instalado en el mismo push, porque el marketplace esta en autosync.
    """
    if not argv or argv[0] in SUBCOMANDOS or argv[0].startswith("-"):
        return list(argv)
    return ["export"] + list(argv)


def construir_parser():
    ap = argparse.ArgumentParser(
        prog="convert.py",
        description="Audita y exporta skills de un plugin de Claude al estándar "
                    "abierto Agent Skills.")
    subs = ap.add_subparsers(dest="comando", required=True)

    def comun(p):
        p.add_argument("source", help="URL del repositorio o ruta local")
        p.add_argument("--fail-on", dest="fail_on", default="ninguno",
                       choices=["ninguno", "degradado", "no_compatible"],
                       help="devolver código 2 si algún estado alcanza este umbral")
        return p

    ins = comun(subs.add_parser(
        "inspect", help="qué contiene y qué exige la skill, sin elegir destino"))
    ins.add_argument("--keep-description-order", action="store_true",
                     help="no reordenar la descripción")

    aud = comun(subs.add_parser(
        "audit", help="matriz de compatibilidad; no escribe paquetes"))
    aud.add_argument("--target", nargs="*", default=None,
                     help="destinos a auditar (por defecto, todos)")
    aud.add_argument("--keep-description-order", action="store_true",
                     help="no reordenar la descripción")

    exp = comun(subs.add_parser("export", help="auditar y empaquetar"))
    exp.add_argument("--target", nargs="*", default=None,
                     help="restringe qué artefactos se producen; la auditoría "
                          "sigue cubriendo todos los destinos")
    exp.add_argument("--out", default="./dist-agentskills", help="directorio de salida")
    exp.add_argument("--only", nargs="*", default=None,
                     help="exportar sólo estas skills")
    exp.add_argument("--zip-only", action="store_true",
                     help="dejar sólo los .zip (pierdes la variante de carpeta)")
    exp.add_argument("--keep-description-order", action="store_true",
                     help="no reordenar la descripción")
    return ap


def codigo_por_umbral(evaluaciones, umbral: str) -> int:
    if umbral == "ninguno":
        return 0
    limite = Estado.ORDEN.index(
        Estado.DEGRADADO if umbral == "degradado" else Estado.NO_COMPATIBLE)
    for por_destino in evaluaciones.values():
        for evs in por_destino.values():
            for ev in evs:
                if Estado.ORDEN.index(ev.estado) >= limite:
                    return 2
    return 0


def main(argv=None) -> int:
    args = construir_parser().parse_args(normalizar_argv(
        sys.argv[1:] if argv is None else argv))

    try:
        perfiles = cargar_perfiles()
    except PerfilInvalido as e:
        print("[error] perfil de destino inválido: {}".format(e), file=sys.stderr)
        return 1

    elegidos = getattr(args, "target", None)
    if elegidos:
        desconocidos = [t for t in elegidos if t not in perfiles]
        if desconocidos:
            print("[error] destino desconocido: {}. Disponibles: {}".format(
                ", ".join(desconocidos), ", ".join(sorted(perfiles))), file=sys.stderr)
            return 1

    return ejecutar(args, perfiles, elegidos)
```

`ejecutar(args, perfiles, elegidos)` recoge el cuerpo del `main` anterior (líneas 771-830), con cuatro cambios:

1. `out` sólo se crea cuando `args.comando == "export"`; `inspect` y `audit` no escriben nada.
2. La escritura de zips y carpetas se salta los destinos no elegidos: con `--target mistral-vibe-work` se conserva sólo la carpeta, y con un destino cuyo modo sea `zip`, sólo el `.zip`.
3. **Tras escribir cada `.zip`, comprobar los límites del paquete** contra cada perfil que acepte el modo `zip`, y volcar los avisos en `res.findings`:

```python
            for pid, perfil in perfiles.items():
                if "zip" not in perfil.modos():
                    continue
                for aviso in comprobar_limites(out / "{}.zip".format(r.name), perfil):
                    r.findings.append(Finding("alta", "limite-de-paquete", aviso))
```

4. Devuelve `codigo_por_umbral(evaluaciones, args.fail_on)` en lugar de `0`.

Para `inspect`, añadir el impresor del modelo intermedio:

```python
def imprimir_inspect(skill) -> None:
    """Vuelca el modelo intermedio: lo que la skill es y exige, sin destino."""
    print("\n## {}".format(skill.nombre))
    if skill.nombre != skill.nombre_original:
        print("   nombre original: {}".format(skill.nombre_original))
    print("   descripción: {} bytes{}".format(
        skill.descripcion_bytes,
        "" if skill.tiene_activacion else "  ⚠ SIN criterio de activación"))
    print("   cuerpo: ~{} tokens".format(skill.cuerpo_tokens))
    print("   ficheros: {}{}".format(
        len(skill.ficheros), " (incluye scripts/)" if skill.tiene_scripts else ""))

    if skill.capacidades:
        print("   capacidades exigidas:")
        for c in skill.capacidades:
            print("     · {:<24} {}".format(c.nombre, c.nivel))
    else:
        print("   capacidades exigidas: ninguna")

    if skill.senales:
        print("   señales:")
        for s in skill.senales:
            print("     · {:<20} {}  {}".format(s.id, s.ubicacion, s.muestra))
    else:
        print("   señales: ninguna")

    ambiguo = [c.nombre for c in skill.capacidades if c.nivel == "requerida"]
    if ambiguo and not skill.tiene_activacion:
        print("   ⚠ Exige capacidades y no dice cuándo cargarse: revisa la "
              "descripción antes de auditar contra ningún destino.")
```

En `ejecutar`, cuando `args.comando == "inspect"`, llamar a `imprimir_inspect(a_skill_portatil(r))` por cada resultado y devolver `0` sin evaluar destinos ni escribir nada.

Añadir el import de `PerfilInvalido` y de `Estado`:

```python
from exporter.modelo import Estado, SkillPortatil, capacidades_de
from exporter.perfiles import PerfilInvalido, cargar_perfiles
```

- [ ] **Step 4: Ejecutar las pruebas y comprobar que pasan**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -v
```

Esperado: PASS, sin fallos ni errores.

- [ ] **Step 5: Comprobar los tres subcomandos y la compatibilidad hacia atrás**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 skills/plugin-to-agentskills/scripts/convert.py inspect . | head -20 && echo "--- audit ---" && python3 skills/plugin-to-agentskills/scripts/convert.py audit . | head -12 && echo "--- compat ---" && python3 skills/plugin-to-agentskills/scripts/convert.py . --out /tmp/salida-t9 >/dev/null && test -f /tmp/salida-t9/plugin-to-agentskills.zip && echo "COMPAT OK" && echo "--- destino malo ---" && (python3 skills/plugin-to-agentskills/scripts/convert.py audit . --target inventado; echo "codigo=$?")
```

Esperado: `inspect` lista señales con ubicación, `audit` muestra la matriz, `COMPAT OK`, y el destino inventado devuelve `codigo=1` listando los cinco ids.

- [ ] **Step 6: Commit**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && git add -A && git commit -m "$(cat <<'EOF'
Anade inspect y audit; export deja de ser lo unico que se puede hacer

El informe pasa a ser el producto y la exportacion un resultado
subordinado: `audit` responde donde se puede subir una skill sin escribir
un solo fichero, e `inspect` describe que exige sin elegir destino.

`convert.py <origen>` sin subcomando sigue exportando. No es cortesia: lo
usan el «Paso 0» del SKILL.md, el comando /exportar-skills y el workflow,
y con el marketplace en autosync y sin version fija, romperlo llegaria en
el mismo push a todo el que lo tenga instalado.

`export` NO bloquea por portabilidad. Una skill no_compatible con Mistral
es perfectamente exportable a Perplexity, asi que un bloqueo global no
tiene sentido cuando el veredicto es por destino. Para CI queda --fail-on,
que devuelve 2 sin dejar de escribir. El gate de verdad pertenece a la
rebanada de seguridad, donde la pregunta si es global al paquete.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Endurecer la obtención del repositorio

**Files:**
- Modify: `skills/plugin-to-agentskills/scripts/convert.py:741-754`
- Create: `tests/test_origen.py`

**Interfaces:**
- Consumes: nada.
- Produces: `convert.resolve_source(src: str, workdir: Path) -> Path`, `convert.comprobar_tamano(raiz: Path) -> None`, constantes `MAX_BYTES_REPO = 200 * 1024 * 1024`, `MAX_FICHEROS_REPO = 20000`, `TIMEOUT_CLON = 300`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/test_origen.py`:

```python
import tempfile
import unittest
from pathlib import Path

from ayuda import importar_exporter

importar_exporter()

import convert  # noqa: E402


class LimitesDeEntrada(unittest.TestCase):

    def test_un_repo_normal_pasa(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.md").write_text("hola", encoding="utf-8")
            convert.comprobar_tamano(Path(tmp))   # no debe lanzar

    def test_demasiados_ficheros_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = convert.MAX_FICHEROS_REPO
            convert.MAX_FICHEROS_REPO = 3
            try:
                for i in range(5):
                    (Path(tmp) / "f{}.txt".format(i)).write_text("x", encoding="utf-8")
                with self.assertRaises(SystemExit):
                    convert.comprobar_tamano(Path(tmp))
            finally:
                convert.MAX_FICHEROS_REPO = original

    def test_demasiado_grande_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = convert.MAX_BYTES_REPO
            convert.MAX_BYTES_REPO = 10
            try:
                (Path(tmp) / "grande.bin").write_bytes(b"x" * 100)
                with self.assertRaises(SystemExit):
                    convert.comprobar_tamano(Path(tmp))
            finally:
                convert.MAX_BYTES_REPO = original

    def test_no_cuenta_los_enlaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "real.bin"
            destino.write_bytes(b"x" * 1000)
            (Path(tmp) / "enlace.bin").symlink_to(destino)
            original = convert.MAX_BYTES_REPO
            convert.MAX_BYTES_REPO = 1500
            try:
                convert.comprobar_tamano(Path(tmp))   # 1000, no 2000
            finally:
                convert.MAX_BYTES_REPO = original


class OrigenInvalido(unittest.TestCase):

    def test_ni_ruta_ni_url_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                convert.resolve_source("no-existe-ni-es-url", Path(tmp))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar la prueba y comprobar que falla**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -p "test_origen.py" -v
```

Esperado: FAIL con `AttributeError: module 'convert' has no attribute 'comprobar_tamano'`.

- [ ] **Step 3: Escribir la implementación**

Sustituir `resolve_source` en `convert.py` por:

```python
# Limites defensivos sobre lo que se acepta analizar. No se descomprime nada
# ni se ejecuta nada, pero un repositorio absurdo puede agotar el disco.
MAX_BYTES_REPO = 200 * 1024 * 1024
MAX_FICHEROS_REPO = 20000
TIMEOUT_CLON = 300


def comprobar_tamano(raiz: Path) -> None:
    """Aborta si el arbol excede los limites. No sigue enlaces."""
    total, n = 0, 0
    for base, dirs, ficheros in os.walk(str(raiz)):
        dirs[:] = [d for d in dirs
                   if d != ".git" and not os.path.islink(os.path.join(base, d))]
        for nombre in ficheros:
            ruta = os.path.join(base, nombre)
            if os.path.islink(ruta):
                continue
            n += 1
            total += os.path.getsize(ruta)
            if n > MAX_FICHEROS_REPO:
                sys.exit("[error] El origen supera los {} ficheros. Se aborta el "
                         "análisis.".format(MAX_FICHEROS_REPO))
            if total > MAX_BYTES_REPO:
                sys.exit("[error] El origen supera los {} MB. Se aborta el "
                         "análisis.".format(MAX_BYTES_REPO // (1024 * 1024)))


def resolve_source(src: str, workdir: Path) -> Path:
    p = Path(src).expanduser()
    if p.exists():
        comprobar_tamano(p.resolve())
        return p.resolve()
    if not re.match(r"^(https?://|git@)", src):
        sys.exit("[error] '{}' no existe como ruta ni parece una URL de "
                 "repositorio.".format(src))
    target = workdir / "repo"
    print("[info] clonando {} ...".format(src))
    entorno = dict(os.environ)
    # Sin esto, un repositorio privado deja el proceso colgado esperando
    # credenciales que nadie va a teclear.
    entorno["GIT_TERMINAL_PROMPT"] = "0"
    try:
        r = subprocess.run(
            ["git", "clone", "--depth", "1", "--no-recurse-submodules", src, str(target)],
            capture_output=True, text=True, env=entorno, timeout=TIMEOUT_CLON)
    except subprocess.TimeoutExpired:
        sys.exit("[error] el clon superó los {} s y se ha cancelado.".format(TIMEOUT_CLON))
    if r.returncode != 0:
        sys.exit("[error] git clone falló:\n{}\n\nSi el repositorio es privado, "
                 "necesitas git ya autenticado, o descárgalo a mano y pasa la "
                 "ruta local.".format(r.stderr.strip()))
    comprobar_tamano(target)
    return target
```

- [ ] **Step 4: Ejecutar las pruebas y comprobar que pasan**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m unittest discover -s tests -t tests -v
```

Esperado: PASS, sin fallos ni errores.

- [ ] **Step 5: Commit**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && git add -A && git commit -m "$(cat <<'EOF'
Pone limites y tiempo maximo a lo que se acepta analizar

El clon era `git clone --depth 1` sin mas: sin timeout, sin limite de
tamano y con submodulos por defecto. Un repositorio privado dejaba el
proceso colgado esperando credenciales que nadie iba a teclear.

Ahora: GIT_TERMINAL_PROMPT=0 para que falle con un mensaje en vez de
esperar, --no-recurse-submodules, timeout de 300 s, y recuento de tamano
y ficheros con abandono limpio por encima de 200 MB o 20.000 ficheros.

El recuento no sigue enlaces simbolicos, por la misma razon que no los
sigue la copia: un enlace a / haria el arbol infinito.

Sigue sin descomprimirse ni ejecutarse nada. El unico subprocess del
programa es git clone.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Fixtures y *golden files*

**Files:**
- Create: `tests/fixtures/skill-minima/skills/minima/SKILL.md`
- Create: `tests/fixtures/skill-con-scripts/skills/con-scripts/SKILL.md`
- Create: `tests/fixtures/skill-con-scripts/skills/con-scripts/scripts/run.py`
- Create: `tests/fixtures/skill-con-mcp/skills/con-mcp/SKILL.md`
- Create: `tests/fixtures/skill-sin-activacion/skills/sin-activacion/SKILL.md`
- Create: `tests/fixtures/skill-description-larga/skills/description-larga/SKILL.md`
- Create: `tests/fixtures/skill-frontmatter-exotico/skills/frontmatter-exotico/SKILL.md`
- Create: `tests/fixtures/repo-sin-skills/commands/solo-comando.md`
- Create: `tests/golden/*.json` (uno por fixture con skills)
- Create: `tests/test_golden.py`
- Create: `tests/generar_golden.py`

**Interfaces:**
- Consumes: `convert.main`.
- Produces: `tests/generar_golden.py` como script regenerador, invocable con `python3 tests/generar_golden.py`.

- [ ] **Step 1: Escribir los fixtures**

`tests/fixtures/skill-minima/skills/minima/SKILL.md`:

```markdown
---
name: minima
description: Cárgala cuando el usuario pida convertir una fecha entre formatos, diga "pásame esta fecha a ISO" o "qué día de la semana fue". Convierte fechas entre representaciones habituales.
---

# Conversión de fechas

1. Pide la fecha de origen y el formato de destino.
2. Convierte y devuelve el resultado.
```

`tests/fixtures/skill-con-scripts/skills/con-scripts/SKILL.md`:

```markdown
---
name: con-scripts
description: Cárgala cuando el usuario pida analizar un CSV, diga "resume esta tabla" o "cuántas filas tiene". Analiza ficheros CSV y devuelve estadísticas básicas.
---

# Análisis de CSV

Ejecuta el script:

```bash
python3 scripts/run.py datos.csv
```
```

`tests/fixtures/skill-con-scripts/skills/con-scripts/scripts/run.py`:

```python
#!/usr/bin/env python3
"""Fixture: no hace nada real, solo existe para que la skill tenga scripts/."""
import sys

print("filas:", len(sys.argv))
```

`tests/fixtures/skill-con-mcp/skills/con-mcp/SKILL.md`:

```markdown
---
name: con-mcp
description: Cárgala cuando el usuario pida buscar en su correo, diga "busca ese email" o "encuentra el mensaje de". Busca mensajes usando el servidor MCP de correo.
---

# Búsqueda en correo

Llama a `mcp__gmail__buscar` con la consulta del usuario.
```

`tests/fixtures/skill-sin-activacion/skills/sin-activacion/SKILL.md`:

```markdown
---
name: sin-activacion
description: Esta skill genera informes financieros mensuales y comparativas de presupuesto contra realidad.
---

# Informes financieros

Genera el informe a partir de los datos aportados.
```

`tests/fixtures/skill-description-larga/skills/description-larga/SKILL.md`:

```markdown
---
name: description-larga
description: Analiza bandejas de correo electrónico con calibración estadística y modelos bayesianos de prioridad. Clasifica cada mensaje según urgencia, remitente y contexto histórico. Produce un informe con las acciones sugeridas y una estimación de confianza para cada una. Mantiene un registro de las decisiones anteriores para recalibrar los umbrales. Actívalo cuando el usuario diga "filtra mi correo", "revisa mi bandeja", "qué correos importan hoy", "limpia el buzón", "prioriza mis mensajes" o "haz triaje del correo".
---

# Triaje de correo

Procedimiento largo.
```

`tests/fixtures/skill-frontmatter-exotico/skills/frontmatter-exotico/SKILL.md`:

```markdown
---
name: frontmatter-exotico
description: Cárgala cuando el usuario pida auditar un repositorio, diga "analiza este repo" o "revisa este plugin". Audita repositorios y devuelve un informe estructurado.
version: '4.1'
allowed-tools: Read, Bash
model: opus
metadata:
  autor: Pablo
  revision: '3'
depends:
  - otra-skill
---

# Auditoría

Procedimiento.
```

`tests/fixtures/repo-sin-skills/commands/solo-comando.md`:

```markdown
---
description: Un plugin que sólo tiene comandos, sin ninguna skill que exportar
---

Haz algo.
```

- [ ] **Step 2: Escribir la prueba que falla**

Crear `tests/test_golden.py`:

```python
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ayuda import RAIZ, RAIZ_SCRIPTS

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = Path(__file__).resolve().parent / "golden"
CONVERT = RAIZ_SCRIPTS / "convert.py"

CON_SKILLS = ["skill-minima", "skill-con-scripts", "skill-con-mcp",
              "skill-sin-activacion", "skill-description-larga",
              "skill-frontmatter-exotico"]


def exportar(fixture: str, destino: Path):
    return subprocess.run(
        [sys.executable, str(CONVERT), "export", str(FIXTURES / fixture),
         "--out", str(destino)],
        capture_output=True, text=True, cwd=str(RAIZ))


def normalizar(resumen: dict) -> dict:
    """Quita lo que depende de la ruta temporal, no del contenido."""
    resumen["origen"] = "<origen>"
    return resumen


class GoldenFiles(unittest.TestCase):

    def test_cada_fixture_produce_su_resumen_esperado(self):
        for fixture in CON_SKILLS:
            with self.subTest(fixture=fixture):
                with tempfile.TemporaryDirectory() as tmp:
                    r = exportar(fixture, Path(tmp))
                    self.assertEqual(r.returncode, 0, r.stderr)
                    obtenido = normalizar(json.loads(
                        (Path(tmp) / "resumen.json").read_text(encoding="utf-8")))
                    esperado = json.loads(
                        (GOLDEN / (fixture + ".json")).read_text(encoding="utf-8"))
                    self.assertEqual(
                        obtenido, esperado,
                        "El resumen de {} ha cambiado. Si el cambio es deseado, "
                        "regenera con: python3 tests/generar_golden.py".format(fixture))


class Reproducibilidad(unittest.TestCase):

    def test_dos_ejecuciones_dan_el_mismo_resumen(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            exportar("skill-con-mcp", a)
            exportar("skill-con-mcp", b)
            self.assertEqual(
                (a / "resumen.json").read_text(encoding="utf-8"),
                (b / "resumen.json").read_text(encoding="utf-8"))


class RepoSinSkills(unittest.TestCase):

    def test_aborta_sin_fabricar_un_zip_vacio(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "salida"
            r = exportar("repo-sin-skills", destino)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("SKILL.md", r.stderr + r.stdout)
            self.assertEqual(list(destino.glob("*.zip")) if destino.exists() else [], [])


class CasosConcretos(unittest.TestCase):

    def leer(self, fixture):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        exportar(fixture, Path(tmp))
        return json.loads((Path(tmp) / "resumen.json").read_text(encoding="utf-8"))

    def test_scripts_no_compatible_en_mistral_compatible_en_perplexity(self):
        d = self.leer("skill-con-scripts")
        compat = d["skills"][0]["compatibilidad"]
        self.assertEqual(compat["mistral-vibe-work"][0]["estado"], "no_compatible")
        self.assertEqual(compat["perplexity-computer"][0]["estado"], "compatible")

    def test_mcp_no_compatible_fuera_de_claude_code(self):
        d = self.leer("skill-con-mcp")
        compat = d["skills"][0]["compatibilidad"]
        self.assertEqual(compat["claude-code"][0]["estado"], "compatible")
        for destino in ("chatgpt", "claude-ai", "mistral-vibe-work", "perplexity-computer"):
            self.assertEqual(compat[destino][0]["estado"], "no_compatible", destino)

    def test_sin_activacion_produce_hallazgo_alto(self):
        d = self.leer("skill-sin-activacion")
        codigos = [h["codigo"] for h in d["skills"][0]["hallazgos"]]
        self.assertIn("description-sin-activacion", codigos)

    def test_el_frontmatter_exotico_conserva_version_bajo_metadata(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        exportar("skill-frontmatter-exotico", Path(tmp))
        texto = (Path(tmp) / "frontmatter-exotico" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("metadata:", texto)
        self.assertIn("version:", texto)
        self.assertNotIn("\nversion:", texto.split("---")[1])
        self.assertNotIn("allowed-tools", texto)
        self.assertNotIn("model:", texto)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Escribir el regenerador**

Crear `tests/generar_golden.py`:

```python
#!/usr/bin/env python3
"""Regenera los golden files de tests/golden/.

Ejecutar SOLO cuando un cambio de comportamiento sea deseado, y revisar el
diff antes de commitear: ese diff es la unica senal de que un cambio en un
perfil de destino ha alterado informes anteriores.

    python3 tests/generar_golden.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ayuda import RAIZ, RAIZ_SCRIPTS  # noqa: E402
from test_golden import CON_SKILLS, FIXTURES, GOLDEN, normalizar  # noqa: E402


def main() -> int:
    GOLDEN.mkdir(exist_ok=True)
    for fixture in CON_SKILLS:
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [sys.executable, str(RAIZ_SCRIPTS / "convert.py"), "export",
                 str(FIXTURES / fixture), "--out", tmp],
                capture_output=True, text=True, cwd=str(RAIZ))
            if r.returncode != 0:
                print("[error] {}: {}".format(fixture, r.stderr), file=sys.stderr)
                return 1
            datos = normalizar(json.loads(
                (Path(tmp) / "resumen.json").read_text(encoding="utf-8")))
        (GOLDEN / (fixture + ".json")).write_text(
            json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print("regenerado", fixture)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Generar los golden y comprobar que las pruebas pasan**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 tests/generar_golden.py && python3 -m unittest discover -s tests -t tests -v
```

Esperado: seis líneas `regenerado`, y PASS con 98 pruebas.

- [ ] **Step 5: Revisar a mano lo que afirman los golden**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -c "
import json,pathlib
for p in sorted(pathlib.Path('tests/golden').glob('*.json')):
    d=json.loads(p.read_text(encoding='utf-8'))
    s=d['skills'][0]
    print(p.stem)
    for destino,evs in sorted(s['compatibilidad'].items()):
        print('   ',destino,'->',evs[0]['estado'])
"
```

Comprobar que cada línea es defendible con lo que dice `references/portabilidad.md`. Si alguna no lo es, el fallo está en el perfil, no en el golden: corregir el perfil y regenerar.

- [ ] **Step 6: Commit**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && git add -A && git commit -m "$(cat <<'EOF'
Anade fixtures y golden files: la reproducibilidad pasa a ser un test

Ocho mini-repositorios que caben en una pantalla, cada uno aislando un
caso: skill limpia, logica en scripts/, llamadas MCP, descripcion sin
disparadores, descripcion que no cabe en ningun destino, frontmatter con
version y metadata anidado, y un plugin sin skills.

Los golden guardan el resumen.json esperado de cada uno. Eso resuelve dos
requisitos de una vez: la reproducibilidad se comprueba sola, y un cambio
en un perfil de destino aparece como diff en el pull request en lugar de
alterar informes en silencio.

Regenerarlos es explicito —python3 tests/generar_golden.py— para que
actualizar el golden sea siempre una decision, nunca un efecto lateral.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: CI cruzado y documentación

**Files:**
- Modify: `.github/workflows/validar.yml`
- Create: `.github/validar_perfiles.py`
- Modify: `skills/plugin-to-agentskills/SKILL.md`
- Modify: `skills/plugin-to-agentskills/references/portabilidad.md`
- Modify: `commands/exportar-skills.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `exporter.perfiles.cargar_perfiles`.
- Produces: `.github/validar_perfiles.py`, invocable como `python3 .github/validar_perfiles.py .`, con código 0 si todo concuerda y 1 si no.

- [ ] **Step 1: Escribir el validador cruzado**

Crear `.github/validar_perfiles.py`:

```python
#!/usr/bin/env python3
"""Valida los perfiles de destino y su concordancia con la documentacion.

Dos comprobaciones distintas:

1. Cada targets/*.json valida contra _schema.json. Requiere `jsonschema`,
   que se puede instalar aqui porque esto solo corre en CI: el conversor
   sigue siendo solo-stdlib.

2. Los datos de cada perfil aparecen en la prosa. Por CONTENCION, no por
   parseo: no se intenta entender el texto, solo que la etiqueta, el
   presupuesto y la ruta de instalacion esten escritos en algun sitio. Si
   alguien cambia un presupuesto en el JSON y no en el README, falla.

La prosa se sigue escribiendo a mano a proposito. La evidencia empirica de
portabilidad.md es narrativa —«observado en una ejecucion real sobre un
buzon de 358 correos»— y generarla la empobreceria.
"""

import datetime
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("[error] falta jsonschema. En CI: pip install jsonschema", file=sys.stderr)
    sys.exit(1)

DOCS = [
    Path("README.md"),
    Path("skills/plugin-to-agentskills/references/portabilidad.md"),
]
TARGETS = Path("skills/plugin-to-agentskills/scripts/exporter/targets")


def main(raiz: Path) -> int:
    targets = raiz / TARGETS
    esquema = json.loads((targets / "_schema.json").read_text(encoding="utf-8"))
    textos = {d: (raiz / d).read_text(encoding="utf-8") for d in DOCS}
    hoy = datetime.date.today()
    errores, avisos = [], []

    perfiles = sorted(p for p in targets.glob("*.json") if not p.name.startswith("_"))
    if not perfiles:
        print("[error] no hay ningun perfil en targets/", file=sys.stderr)
        return 1

    for ruta in perfiles:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(datos, esquema)
        except jsonschema.ValidationError as e:
            errores.append("{}: {}".format(ruta.name, e.message))
            continue

        if datos["id"] != ruta.stem:
            errores.append("{}: el id '{}' no coincide con el fichero".format(
                ruta.name, datos["id"]))

        # Concordancia con la prosa, por contencion.
        label = datos["label"]
        presupuesto = str(datos["formato"]["presupuesto_description_bytes"])
        if not any(label in t for t in textos.values()):
            errores.append("{}: la etiqueta «{}» no aparece en la documentacion".format(
                ruta.name, label))
        if not any(presupuesto in t for t in textos.values()):
            errores.append(
                "{}: el presupuesto {} bytes no aparece en la documentacion. "
                "Si lo has cambiado en el JSON, cambialo tambien en el README y "
                "en portabilidad.md".format(ruta.name, presupuesto))

        revisar = datetime.date.fromisoformat(datos["evidencia"]["revisar_tras"])
        if revisar < hoy:
            avisos.append(
                "{}: la evidencia vencio el {}. `audit` degradara a no_verificable "
                "hasta que se vuelva a comprobar y se suba la fecha.".format(
                    ruta.name, revisar.isoformat()))

    for a in avisos:
        print("::warning:: {}".format(a))
    for e in errores:
        print("[error] {}".format(e), file=sys.stderr)
    if errores:
        return 1
    print("{} perfiles validos y concordantes con la documentacion.".format(len(perfiles)))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
```

- [ ] **Step 2: Ejecutarlo y comprobar que falla por documentación desactualizada**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 -m pip install --quiet jsonschema && python3 .github/validar_perfiles.py .
```

Esperado: FAIL, con errores del tipo `la etiqueta «claude.ai» no aparece en la documentacion` — la prosa todavía no menciona los cinco destinos con sus datos actuales.

- [ ] **Step 3: Actualizar la documentación**

En `README.md`, en la tabla «Dónde se sube cada cosa», comprobar que aparecen las cinco etiquetas exactas (`ChatGPT`, `claude.ai`, `Claude Code`, `Mistral Vibe Work`, `Perplexity Computer`) y los presupuestos `490`, `850` y `1024`. Añadir a la sección «Qué audita» el párrafo:

```markdown
El veredicto ya no es único por skill: es **uno por destino**. Una skill cuya
lógica vive en `scripts/` es `no compatible` en Mistral Vibe Work, que no tiene
Python, y `compatible` en Perplexity Computer, que sí lo ejecuta. Los destinos
se declaran en `skills/plugin-to-agentskills/scripts/exporter/targets/*.json`,
con la fecha en que se comprobó cada dato y una fecha de revisión: cuando esa
fecha vence, el estado degrada a `no verificable` en vez de seguir afirmando.
```

Y la sección de uso:

```markdown
## Los tres modos

| Comando | Qué hace | ¿Escribe ficheros? |
|---|---|---|
| `convert.py inspect <origen>` | Qué contiene la skill y qué exige, sin elegir destino | No |
| `convert.py audit <origen>` | Matriz de compatibilidad por destino | No |
| `convert.py export <origen>` | Audita y empaqueta | Sí |

`convert.py <origen>` sin subcomando sigue exportando, como siempre.
```

En `references/portabilidad.md`, añadir al principio de la sección 1:

```markdown
> Los datos de esta tabla son ahora la copia legible de
> `scripts/exporter/targets/*.json`, que es la fuente de verdad. El CI comprueba
> que concuerdan. Lo que sigue viviendo sólo aquí es la evidencia narrativa: qué
> se observó, en qué ejecución y por qué importa.
```

Y una sección nueva al final:

```markdown
## 9. Cómo añadir un destino

1. Escribir `scripts/exporter/targets/<id>.json` siguiendo `_schema.json`. El
   `id` debe coincidir con el nombre del fichero.
2. Declarar cada capacidad. **Lo que no se haya comprobado va a `desconocido`,
   nunca a `no`.** Callar no es negar: `desconocido` produce `no verificable`,
   que es la respuesta honesta; `no` produce `no compatible`, que es una
   afirmación.
3. Los peligros de conducta —lo que la plataforma hace mal *teniendo* la
   capacidad— van en `peligros[]`, enlazados por `dispara_con` al id de la señal.
4. Poner `evidencia.verificado_el` a hoy y `revisar_tras` a tres meses vista.
5. Añadir la etiqueta y el presupuesto a la tabla de la sección 1 y al README,
   o el CI fallará.
6. Regenerar los golden: `python3 tests/generar_golden.py`, y revisar el diff.

No hay que tocar Python.
```

En `SKILL.md`, sustituir la sección «Flujo» por una que contemple los tres modos, conservando íntegro el «Paso 0», y añadir a los *gotchas*:

```markdown
- **El veredicto es por destino, no por skill.** El informe trae una matriz: la
  misma skill puede ser `compatible` en Perplexity y `no compatible` en Mistral.
  Si el usuario pregunta «¿es portable?», la respuesta correcta empieza por
  «¿a dónde?».
- **`no verificable` no es `compatible`.** Significa que el perfil del destino no
  declara esa capacidad, o que su evidencia ha caducado. Dilo tal cual: no lo
  redondees a favor.
```

En `commands/exportar-skills.md`, añadir al final:

```markdown
6. Si el usuario sólo quiere saber dónde puede subir la skill, sin paquetes,
   usa `audit` en vez de `export`: no escribe ningún fichero.
```

- [ ] **Step 4: Volver a ejecutar el validador**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 .github/validar_perfiles.py .
```

Esperado: `5 perfiles validos y concordantes con la documentacion.`

- [ ] **Step 5: Añadir el paso al workflow**

En `.github/workflows/validar.yml`, después de «Validar manifiestos, skills y comandos»:

```yaml
      - name: Instalar dependencias de validacion
        run: python3 -m pip install --quiet jsonschema

      - name: Validar perfiles de destino y su concordancia con la documentacion
        run: python3 .github/validar_perfiles.py .

      - name: Validar el resumen.json contra su schema
        run: |
          python3 skills/plugin-to-agentskills/scripts/convert.py . --out /tmp/salida-ci
          python3 - <<'PY'
          import json, jsonschema, pathlib
          esquema = json.loads(pathlib.Path(
              "skills/plugin-to-agentskills/scripts/exporter/resumen.schema.json"
          ).read_text(encoding="utf-8"))
          datos = json.loads(pathlib.Path("/tmp/salida-ci/resumen.json").read_text(encoding="utf-8"))
          jsonschema.validate(datos, esquema)
          print("resumen.json valida contra su schema.")
          PY
```

- [ ] **Step 6: Comprobar la suite completa**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && python3 .github/validate_plugin.py . && python3 .github/validar_perfiles.py . && python3 -m unittest discover -s tests -t tests && python3 skills/plugin-to-agentskills/scripts/convert.py --help >/dev/null && python3 skills/plugin-to-agentskills/scripts/convert.py . --out /tmp/salida-final && test -f /tmp/salida-final/INFORME-PORTABILIDAD.md && test -n "$(ls /tmp/salida-final/*.zip)" && echo "TODO VERDE"
```

Esperado: `TODO VERDE`.

- [ ] **Step 7: Commit**

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && git add -A && git commit -m "$(cat <<'EOF'
El CI verifica que la prosa y los perfiles digan lo mismo

La comprobacion es por contencion, no por parseo: no intenta entender el
texto, solo que la etiqueta de cada destino y su presupuesto en bytes
esten escritos en el README y en portabilidad.md. Cambiar un presupuesto
en el JSON y olvidarlo en la prosa rompe el build.

La prosa se sigue escribiendo a mano a proposito. La evidencia de
portabilidad.md es narrativa —«observado en una ejecucion real sobre un
buzon de 358 correos»— y generarla desde un JSON la empobreceria. Lo que
se automatiza es la concordancia de los datos, no la redaccion.

La evidencia vencida avisa pero no rompe: la consecuencia real es en
ejecucion, donde audit degrada a no_verificable. Un build que se rompe
solo en una fecha, sin que nadie haya tocado nada, es una emboscada.

La documentacion explica ademas como anadir un destino sin tocar Python, y
por que lo no comprobado va a «desconocido» y nunca a «no».

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Verificación final contra los criterios de aceptación del spec

Ejecutar tras la tarea 12 y comprobar los diez criterios uno a uno:

```bash
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter" && cat <<'SH' > /tmp/aceptacion.sh
set -e
cd "/Users/pablorodriguezlopez/Desktop/claude-skills-exporter"
C=skills/plugin-to-agentskills/scripts/convert.py

echo "1. Salida con los nombres de siempre"
rm -rf /tmp/ac && python3 $C . --out /tmp/ac >/dev/null
test -f /tmp/ac/INFORME-PORTABILIDAD.md && test -f /tmp/ac/resumen.json
test -n "$(ls /tmp/ac/*.zip)" && test -d /tmp/ac/plugin-to-agentskills

echo "2. audit emite matriz"
python3 $C audit . | grep -q "Matriz de compatibilidad"

echo "3. Anadir destino no toca Python"
grep -rq "BUDGET_MISTRAL" skills/plugin-to-agentskills/scripts/ && exit 1 || true

echo "4. Todo estado cita su motivo"
python3 -c "
import json;d=json.load(open('/tmp/ac/resumen.json'))
for s in d['skills']:
  for destino,evs in s['compatibilidad'].items():
    for e in evs:
      assert e['estado']=='compatible' or e['motivos'], (s['name'],destino)
"

echo "5-6. desconocido y caducidad dan no_verificable"
python3 -m unittest discover -s tests -t tests -p "test_compatibilidad.py" -q

echo "7. Reproducible a fecha fija"
python3 -m unittest discover -s tests -t tests -p "test_golden.py" -q

echo "8. Sin fuga por enlaces"
python3 -m unittest discover -s tests -t tests -p "test_empaquetado.py" -q

echo "9. Arranca desde /tmp"
rm -rf /tmp/ac-aislado && cp -R . /tmp/ac-aislado
python3 /tmp/ac-aislado/$C /tmp/ac-aislado --out /tmp/ac-salida >/dev/null

echo "10. CI en verde"
python3 .github/validate_plugin.py .
python3 .github/validar_perfiles.py .
python3 -m unittest discover -s tests -t tests -q

echo "LOS DIEZ CRITERIOS: OK"
SH
bash /tmp/aceptacion.sh
```

Esperado: `LOS DIEZ CRITERIOS: OK`.
