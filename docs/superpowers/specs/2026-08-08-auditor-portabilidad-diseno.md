# Auditor de portabilidad: perfiles de destino, estados y `audit`/`inspect`

**Fecha:** 2026-08-08
**Repositorio:** `novanoticia/claude-skills-exporter`
**Punto de partida:** commit `c7ed7ac`
**Origen:** propuesta *«Auditor de portabilidad y seguridad»* (documento externo)

---

## 1. Qué problema resuelve

El conversor emite hoy **un único veredicto de riesgo por skill** — alta, media o baja —
que pretende valer para cinco destinos con capacidades distintas. No puede ser verdad en
todos a la vez. `email-triage` funciona entera en Claude Code y queda inerte en Mistral
Vibe Work, que no tiene Python; un solo número tiene que elegir, y elige el pesimismo.

Además, el conocimiento sobre los destinos vive triplicado y sin fecha:

| Dónde | Qué guarda |
|---|---|
| Constantes de `convert.py` | `BUDGET_MISTRAL`, `BUDGET_PERPLEXITY`, severidades de los patrones |
| `references/portabilidad.md` | La prosa con la evidencia empírica |
| `README.md` | Las tablas de destinos y presupuestos |

Tres sitios que deben concordar a mano, ninguno con fecha de verificación ni nivel de
confianza. Añadir un destino significó editar Python, prosa y tablas por separado.

Esta rebanada convierte ese conocimiento en **datos versionados con evidencia**, y el
veredicto único en una **matriz por destino**.

## 2. Alcance

### Entra

- Perfiles de destino como JSON versionado, con evidencia fechada y caducable.
- Motor de compatibilidad de dos canales: capacidades y peligros de conducta.
- Estados de compatibilidad por par *skill × destino*.
- Subcomandos `inspect` y `audit`; `export` pasa a ser un modo más.
- Reorganización de `convert.py` en un paquete hermano, sin cambiar su ruta.
- Fixtures, pruebas con *golden files* y verificación cruzada en CI.
- Arreglo de la fuga por enlaces simbólicos (§8.1).

### No entra

- **El motor de seguridad.** Queda para la rebanada siguiente. Aquí sólo se reserva el
  campo `bloqueo_seguridad` en el modelo y en el schema, siempre a `null`.
- Destinos nuevos. Se modelan los cinco que el repositorio ya soporta.
- Generación automática de documentación desde los perfiles.
- Cualquier cambio en el modo de instalación del propio plugin.

### Decisiones cerradas antes de diseñar

| Decisión | Elegido | Motivo |
|---|---|---|
| Dónde vive la seguridad | Reglas deterministas aquí; juicio semántico en `github-plugin-analyzer-ia-v4` | Cada herramienta promete lo que su régimen de verdad permite: aquí reproducibilidad, allí criterio |
| Primera rebanada | Cimientos: datos, estados y `audit`/`inspect` | La seguridad necesita dónde escribir sus hallazgos; al revés se construye el informe dos veces |
| Estructura | Paquete hermano con `convert.py` como entrada | Preserva el «Paso 0» y el arranque sin instalación desde un clon en `/tmp` |
| Formato de perfiles | JSON con JSON Schema | Único formato que da validación gratis sin dependencias en ejecución; el parser de YAML casero ya causó un fallo real |
| Triplicación | Datos verificados en CI, prosa a mano | La evidencia empírica de `portabilidad.md` es narrativa; generarla la empobrecería |
| Motor | Híbrido: capacidades + peligros de conducta | `estado-persistente` no es «no puede escribir»: Mistral escribe y *miente*. Una matriz pura lo aplanaría |

## 3. Arquitectura

```
skills/plugin-to-agentskills/
├── SKILL.md                       actualizada: inspect / audit / export
├── references/
│   └── portabilidad.md            prosa a mano; el CI verifica sus cifras
└── scripts/
    ├── convert.py                 ENTRADA. Ruta sin cambios. CLI delgada
    └── exporter/
        ├── __init__.py
        ├── frontmatter.py         split_frontmatter, parse_simple_yaml, yaml_escape
        ├── descripcion.py         split_sentences, reorder, compact, clamp
        ├── deteccion.py           PATTERNS → señales con id, ubicación y muestra
        ├── modelo.py              SkillPortátil, Señal, Resultado, estados
        ├── perfiles.py            carga y valida targets/*.json
        ├── compatibilidad.py      motor: señales × perfil → estado
        ├── empaquetado.py         copia, zip, escritura del SKILL.md
        ├── informes.py            markdown + json
        └── targets/
            ├── _schema.json
            ├── chatgpt.json
            ├── claude-ai.json
            ├── claude-code.json
            ├── mistral-vibe-work.json
            └── perplexity-computer.json
```

Tres invariantes que la reorganización debe conservar:

1. **`scripts/convert.py` mantiene su ruta exacta.** El «Paso 0» de la skill, el comando
   `/exportar-skills` y los dos pasos del workflow de CI siguen funcionando sin tocarse.
2. **Arranca desde un clon en `/tmp` sin instalar nada.** Al ejecutar
   `python3 ruta/convert.py`, Python coloca `ruta/` como `sys.path[0]`, de modo que
   `import exporter.perfiles` resuelve sin `pip`, sin `-m` y sin `PYTHONPATH`. Sólo
   biblioteca estándar, Python 3.8+.
3. **`convert.py <origen>` sin subcomando sigue exportando.** Si el primer argumento no
   es `inspect`, `audit` ni `export`, se interpreta como `export`.

`targets/` va dentro del paquete a propósito: cuando el repositorio se exporta a sí mismo
—cosa que el CI hace en cada push— los perfiles viajan con él.

## 4. El perfil de destino

Un fichero por destino en `exporter/targets/`, validado contra `_schema.json`.

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
    "scripts.ejecutar":    "no",
    "shell.ejecutar":      "parcial",
    "filesystem.leer":     "si",
    "filesystem.escribir": "si",
    "red.fetch":           "desconocido",
    "mcp.cliente":         "no",
    "applescript":         "no",
    "subagentes":          "no",
    "hooks":               "no",
    "comandos.namespace":  "no",
    "home.resolver":       "no"
  },

  "peligros": [
    {
      "id": "mistral-estado-no-persiste",
      "dispara_con": ["estado-persistente"],
      "severidad": "alta",
      "titulo": "La escritura reporta éxito y el fichero puede no estar después",
      "detalle": "Reproducido en dos ejecuciones independientes: el anexado devolvió éxito y luego el fichero tenía una sola línea, o no existía. Lo grave no es la pérdida: el agente reconstruye el registro de memoria y continúa como si nada.",
      "mitigacion": "Escribir el fichero entero de una vez y releerlo para confirmar. Si falta, decirlo — nunca reconstruirlo de memoria.",
      "evidencia": { "confianza": "observado", "verificado_el": "2026-07-27" }
    }
  ],

  "evidencia": {
    "verificado_el": "2026-07-27",
    "revisar_tras":  "2026-10-27",
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

### Vocabularios cerrados y versionados

- **Nivel de capacidad:** `si` · `si_con_confirmacion` · `parcial` · `no` · `desconocido`
- **Confianza:** `oficial` · `oficial-incompleto` · `observado` · `comunidad` · `no-verificado`
- **Severidad de peligro:** `alta` · `media` · `baja`

`null` en `limites_paquete` significa «el destino no publica ese límite», y no se
comprueba. No es lo mismo que un límite infinito, pero sí es lo único afirmable.

### La severidad se muda del patrón al par

Hoy la severidad es propiedad del patrón: `applescript` es *media* siempre. Es falso. En
Perplexity Computer es media —se ejecuta, con el corte a los ~90 s— y en Mistral es
**alta**, porque no se ejecuta y la skill queda inerte.

A partir de aquí la severidad es propiedad del par *(señal × destino)*, declarada en
`peligros[].severidad` del perfil. La severidad del patrón sobrevive únicamente como
reserva para `inspect`, que corre sin destino.

### Caducidad

`revisar_tras` da al motor una forma de caducar conocimiento. Con esa fecha atrás, el
perfil deja de poder sostener un veredicto firme y las compatibilidades que dependan de
la capacidad afectada degradan a `no_verificable`. Evita el fallo típico: seguir
afirmando con seguridad algo comprobado hace año y medio contra una plataforma que ya
cambió.

`capacidades` y `peligros[]` llevan bloques `evidencia` independientes. Un destino puede
declarar `shell.ejecutar: "si"` con confianza `oficial` y, a la vez, un peligro sobre ese
mismo shell con confianza `observado`. Ese desajuste es información, no incoherencia.

## 5. Modelo intermedio

`inspect` produce un modelo agnóstico del destino: lo que la skill *es* y *exige*, antes
de compararlo con nada.

```
SkillPortátil
├── identidad        name, nombre original, carpeta, discrepancias
├── descripcion      texto, bytes, ¿tiene disparadores de activación?
├── frontmatter      claves del estándar / retiradas / bajadas a metadata
├── cuerpo           tokens estimados
├── recursos         ficheros, ¿scripts/?, ¿references/?, ¿assets/?
├── señales          [{id, ubicación fichero:línea, muestra}]
└── capacidades      inferidas de las señales: requeridas y opcionales
```

### De señal a capacidad

| Señal | Capacidad inferida | Nivel |
|---|---|---|
| `mcp-tool` | `mcp.cliente` | requerida |
| `applescript` | `applescript`, `shell.ejecutar` | requerida |
| `scripts/` presente | `scripts.ejecutar` | requerida |
| `subagent` | `subagentes` | requerida |
| `hooks` | `hooks` | requerida |
| `home-tilde` | `home.resolver` | requerida |
| `estado-persistente` | `filesystem.escribir` | requerida |
| `slash-plugin` | `comandos.namespace` | opcional |
| `plugin-root` | — se reescribe: es adaptación, no capacidad | — |
| `claude-md`, `claude-brand` | — cosmético | — |

La fila de `estado-persistente` es el híbrido funcionando. Infiere `filesystem.escribir`,
y Mistral la declara `"si"`: por el canal de capacidades, **pasa**. Es el canal de
peligros el que añade «escribe, pero la escritura no sobrevive, y el agente rellena el
hueco de memoria». Una matriz pura habría dado luz verde.

## 6. Estados de compatibilidad

Cinco valores, evaluados por par *skill × destino × modo de instalación*:

| Estado | Cuándo |
|---|---|
| `compatible` | No falta ninguna capacidad requerida, ningún peligro disparado, formato y modo de instalación encajan |
| `compatible_con_adaptacion` | Igual, pero el conversor cambió algo para que encajara: descripción recortada, rutas reescritas, claves bajadas a `metadata` |
| `degradado` | Falta una capacidad **opcional**, o se dispararon peligros que cambian el resultado sin impedir la instalación |
| `no_compatible` | Falta una capacidad **requerida**, o el formato o el modo de instalación no encajan |
| `no_verificable` | El perfil declara `desconocido` en algo que la skill requiere, o su `revisar_tras` ya pasó |

**Precedencia:** `no_compatible` › `no_verificable` › `degradado` ›
`compatible_con_adaptacion` › `compatible`.

Aparte, en su propio campo: `bloqueo_seguridad`, siempre `null` en esta rebanada.

### Qué estado produce cada peligro disparado

| Severidad del peligro | Estado que contribuye |
|---|---|
| `alta` | `no_compatible` |
| `media` | `degradado` |
| `baja` | Ninguno: nota informativa en el informe |

Un peligro `alta` lleva a `no_compatible` aunque no falte ninguna capacidad. Es el caso
de `mistral-estado-no-persiste`: la skill se instala y se ejecuta, pero su consecuencia
—que el agente reconstruya de memoria un registro perdido y siga como si nada— la hace
inadecuada para ese destino. Llamar a eso `degradado` sería quedarse corto ante quien
decide si subirla.

### Modo de instalación

El estado se evalúa por cada modo que el perfil declare en `instalacion.modos`. Los cinco
perfiles actuales declaran un único modo relevante para skills, así que la matriz tiene
una fila por destino. Cuando un perfil declare varios, el informe muestra una fila por
modo. No hay opción de CLI para elegirlo: se derivan todos del perfil.

### Dos desviaciones deliberadas de la propuesta

- **`bloqueado_por_seguridad` es un campo ortogonal, no un sexto valor del enum.** La
  propuesta exige que pueda coexistir con «técnicamente compatible»; como valor del mismo
  campo, no podría. Como campo aparte, un informe puede decir a la vez *compatible con
  Perplexity* y *bloqueado por seguridad*.
- **«Equivalente bajo condiciones» se elimina.** Se distinguía de `compatible` en que
  «todavía exige pruebas en el destino», y eso vale para todos los veredictos.
  Convertirlo en estado invita a leer `compatible` como «probado», algo que esta
  herramienta no puede afirmar. La advertencia pasa a la cabecera de todo informe.

## 7. CLI e informes

```bash
python3 convert.py inspect <origen>
python3 convert.py audit   <origen> [--target ID ...]
python3 convert.py export  <origen> [--target ID ...] [--out DIR] [--only ...] [--zip-only]
python3 convert.py <origen> [--out DIR]          # compat: equivale a export
```

- **`inspect`** — sin destino. Formatos, recursos, señales con ubicación, capacidades
  inferidas y ambigüedades que impiden auditar. No escribe paquetes.
- **`audit`** — sin `--target`, audita contra todos los perfiles y produce la matriz.
  No escribe paquetes.
- **`export`** — lo de hoy, más el informe con la matriz. Sin `--target` produce todos
  los artefactos, como ahora. Con `--target` restringe la salida a los que ese destino
  necesita: `--target mistral-vibe-work` deja sólo la carpeta,
  `--target perplexity-computer` deja sólo el `.zip`. La auditoría del informe sigue
  cubriendo todos los destinos en cualquier caso — restringir lo que se empaqueta no
  restringe lo que se audita.

Opciones heredadas sin cambios: `--out`, `--only`, `--zip-only`,
`--keep-description-order`.

### `export` no bloquea por portabilidad

La propuesta plantea `--only-if compatibility>=adaptable`. Aquí no se implementa: una
skill `no_compatible` con Mistral es perfectamente exportable a Perplexity, y un bloqueo
global carece de sentido cuando el veredicto es por destino. El *gate* de exportación
pertenece a la rebanada de seguridad, donde «¿deberías instalar esto?» sí es una
propiedad global del paquete.

Mientras tanto, para uso en CI:

`--fail-on {ninguno,degradado,no_compatible}` — por defecto `ninguno`, para no romper el
workflow actual.

**Códigos de salida:** `0` correcto · `1` error de uso o de entrada · `2` hallazgos por
encima del umbral de `--fail-on`.

### Artefactos

Mismos nombres que hoy, para no romper a ningún consumidor:

```
dist-agentskills/
├── <skill>.zip
├── <skill>/
├── INFORME-PORTABILIDAD.md
└── resumen.json          mismo nombre, contenido enriquecido, valida contra schema
```

El informe se abre con la matriz:

```markdown
## Matriz de compatibilidad

| Skill | ChatGPT | claude.ai | Perplexity | Mistral | Claude Code |
|---|---|---|---|---|---|
| `email-triage`     | 🟡 adaptación | 🟡 adaptación | 🟠 degradado | 🔴 no compatible | 🟢 compatible |
| `bayesian-compose` | 🟢 compatible | 🟢 compatible | 🟢 compatible | 🟢 compatible    | 🟢 compatible |

> Ningún veredicto sustituye a probar la skill en el destino.
```

*(Ejemplo ilustrativo del formato. Los veredictos reales salen del contenido de los
perfiles, que se escribe durante la implementación.)*

Debajo, por cada par que no sea `compatible`: qué falta, por qué, con qué evidencia y
fecha, y la mitigación concreta que declara el perfil.

Los avisos incrustados en el `SKILL.md` exportado se mantienen, y pasan a estar redactados
para el destino concreto al que va ese artefacto.

## 8. Robustez

### 8.1 Fuga por enlaces simbólicos (fallo vivo en producción)

```python
shutil.copytree(src_dir, dest, ignore=shutil.ignore_patterns(*IGNORED_DIRS, "SKILL.md"))
```

`copytree` usa `symlinks=False` por defecto: **copia el contenido de lo que apunta el
enlace**, no el enlace. Una skill con un symlink a `~/.ssh/id_rsa`, a un `.env` o a
cualquier fichero fuera del árbol vería ese contenido dentro del `.zip` que después se
sube a ChatGPT o a Perplexity. Poner `symlinks=True` no basta: `zipfile.write()` también
sigue el enlace al empaquetar.

**Arreglo:** omitir los enlaces simbólicos al copiar y emitir un hallazgo
`enlace-simbolico` de severidad alta, nombrando el fichero y su destino.

### 8.2 Límites de entrada

- `git clone --depth 1 --no-recurse-submodules`, con `GIT_TERMINAL_PROMPT=0` para que un
  repositorio privado falle con un mensaje en vez de colgarse pidiendo credenciales, y
  `timeout` en el `subprocess.run`.
- Tras clonar: recuento de tamaño total y de ficheros, con abandono limpio por encima del
  umbral (200 MB / 20 000 ficheros).
- Nada se descomprime, nada se ejecuta. El único `subprocess` del programa sigue siendo
  `git clone`, y hay un test que lo afirma.

### 8.3 Límites de salida

Cada `.zip` producido se comprueba contra `limites_paquete` del perfil — 50 MB, 500
ficheros y 25 MB por fichero en ChatGPT. Son datos del perfil, no constantes.

### 8.4 Errores

| Situación | Comportamiento |
|---|---|
| `--target xyz` inexistente | Error listando los ids disponibles |
| Perfil con JSON malformado | Aborta indicando fichero y posición |
| Repositorio sin `skills/` | Aborta limpio (como hoy) |
| Clon fallido | Mensaje de `git` más la causa probable |
| Capacidad `desconocido` en el perfil | `no_verificable`, nunca una conjetura |

## 9. Pruebas

### Fixtures

`tests/fixtures/`, mini-repositorios que caben en una pantalla:

| Fixture | Qué debe pasar |
|---|---|
| `skill-minima` | `compatible` en los cinco destinos |
| `skill-con-scripts` | `no_compatible` en Mistral, `compatible` en Perplexity |
| `skill-con-mcp` | `no_compatible` en todo lo que no sea Claude Code |
| `skill-sin-activacion` | Hallazgo alto `description-sin-activacion` |
| `skill-description-larga` | Recorte distinto por destino, con tildes contando doble |
| `skill-frontmatter-exotico` | `metadata` anidado y `version` sobreviven — regresión del fallo corregido en `e3307b3` |
| `skill-con-enlace` | El enlace se omite y sale el hallazgo |
| `repo-sin-skills` | Aborta limpio, sin zip vacío |

### Capas

1. **Unidad** por módulo: `descripcion`, `frontmatter`, `deteccion`, `compatibilidad`.
2. **Golden files.** Cada fixture lleva su `resumen.json` esperado, commiteado. Es el test
   de reproducibilidad, y resuelve además el requisito de que «los cambios de perfiles no
   rompan informes previos sin aviso»: al tocar un perfil, el golden cambia y el diff del
   pull request lo enseña.
3. **Validación de schema:** cada `targets/*.json` contra `_schema.json`, y `resumen.json`
   contra el suyo.

La regla de «sólo biblioteca estándar» vincula al **programa**, no a sus **pruebas**: el
CI corre en GitHub Actions, donde `pip install jsonschema` no llega a ningún usuario. El
schema se valida con un validador de verdad, sin escribir uno casero.

## 10. CI

Se añade a `.github/workflows/validar.yml`, conservando entero lo que ya hace:

- Validación de cada perfil contra el schema.
- `python3 -m unittest discover tests`.
- **Verificación cruzada documentación ↔ perfiles**, por contención y no por parseo de
  prosa: para cada perfil, comprobar que `references/portabilidad.md` y `README.md`
  contienen su etiqueta, su presupuesto en bytes y su ruta de instalación. Si cambia un
  presupuesto en el JSON y no en la prosa, falla. No intenta entender el texto: sólo que
  los datos aparezcan.
- **Evidencia caducada: avisa, no rompe.** Un `revisar_tras` vencido genera una anotación
  en el CI; la consecuencia real es en ejecución, donde `audit` degrada esa compatibilidad
  a `no_verificable`. La herramienta dice la verdad sola y el CI no rompe un build en una
  fecha sin que nadie haya tocado nada.

## 11. Criterios de aceptación

1. `python3 convert.py <repo> --out DIR` produce exactamente los mismos ficheros de
   salida que antes del cambio, con el informe enriquecido.
2. `python3 convert.py audit <repo>` emite una matriz con un estado por par
   *skill × destino*, y ningún estado aparece sin una razón legible.
3. Añadir un destino consiste en escribir un `targets/*.json` y su prosa; no se toca
   Python.
4. Cada estado `no_compatible` o `degradado` cita la capacidad o el peligro que lo causa,
   con su evidencia y su fecha de verificación.
5. Una capacidad `desconocido` produce `no_verificable`, nunca una conjetura.
6. Un perfil con `revisar_tras` vencido degrada a `no_verificable` las compatibilidades
   que dependan de él.
7. Ejecutar dos veces sobre el mismo repositorio produce `resumen.json` idéntico salvo
   metadatos de fecha. La reproducibilidad se afirma **a fecha fija**: el vencimiento de
   `revisar_tras` puede cambiar un veredicto entre dos ejecuciones separadas en el tiempo,
   y eso es intencionado. Las pruebas de *golden file* fijan la fecha para aislarlo.
8. Un fixture con enlace simbólico no filtra el contenido apuntado a ningún artefacto.
9. El conversor sigue arrancando desde un clon en `/tmp` con `python3 <ruta>/convert.py`,
   sin instalación ni dependencias.
10. `python3 .github/validate_plugin.py .` y el workflow completo pasan en verde.

## 12. Riesgos

| Riesgo | Mitigación |
|---|---|
| Falsa precisión: la inferencia de capacidades por regex parece más exacta de lo que es | Toda señal incluye ubicación y muestra, y el informe las llama heurísticas. `no_verificable` se usa de verdad, no como adorno |
| La reorganización rompe el «Paso 0» en shells aislados | Criterio de aceptación 9, con prueba explícita en CI ejecutando desde una copia en `/tmp` |
| El autosync del marketplace propaga un fallo de inmediato | Se conservan nombres, rutas y artefactos; el CI amplía cobertura antes de que el código cambie |
| Los perfiles envejecen en silencio | `revisar_tras` con consecuencia en ejecución y aviso en CI |
| El spec crece hacia la seguridad por arrastre | `bloqueo_seguridad` queda a `null` y sin regla que lo emita; no hay motor de seguridad en esta rebanada |

## 13. Lo que habilita para después

La rebanada de seguridad encuentra ya construido: el modelo intermedio donde escribir
hallazgos, el schema donde validarlos, los informes donde publicarlos, el campo
`bloqueo_seguridad` donde bloquear y los fixtures donde probarlo. Su trabajo será añadir
`seguridad.py` con las reglas estáticas —permisos, cadena de suministro, ofuscación,
secretos, patrones de prompt— y la regla de recomendación de instalación, más el *gate*
de `export`, que allí sí tiene sentido porque la pregunta es global al paquete.
