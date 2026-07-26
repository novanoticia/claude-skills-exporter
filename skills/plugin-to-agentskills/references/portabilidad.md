# Portabilidad Claude → Perplexity / Mistral / otros

Consulta este fichero cuando haya que reescribir una skill a mano o explicar por qué
un aviso del informe importa.

## 1. Qué acepta cada destino

| | Perplexity Computer | Mistral Vibe Work | Claude Code |
|---|---|---|---|
| Ruta de instalación | `perplexity.ai/computer/skills` → Create skill → Upload a skill | `chat.mistral.ai/work` → Context → Skills → New Skill | `/plugin install` o carpeta `skills/` |
| Formato | **`.zip`** con la carpeta de la skill en su raíz | **la carpeta descomprimida**, con `SKILL.md` dentro | Carpeta con `SKILL.md` |
| Varias skills a la vez | No — **una por zip** | No — una por vez | Sí |
| Ficheros auxiliares | Sí, dentro del zip | Sí — conserva subcarpetas y cualquier extensión (`.md`, `.py`, `.yaml`) | Sí |
| Ejecuta `scripts/` | Sí, en su sandbox | **No** — hay shell, pero sin Python | Sí |
| Frontmatter mínimo | `name`, `description` | `name`, `description` | `name`, `description` |

**Sólo existe un artefacto: el `.zip`.** Es válido tal cual para Perplexity. Para
Mistral, el único paso es descomprimirlo y subir la carpeta resultante. No hay ninguna
conversión intermedia, ni un «formato Mistral» distinto que haya que generar aparte:
el conversor deja las dos formas juntas por comodidad, nada más.

### Lo comprobado en Mistral Vibe Work

- **Acepta la carpeta completa, con su árbol intacto.** Verificado en una skill con
  `SKILL.md` en la raíz, una carpeta `references/` con siete `.md`, una `scripts/` con
  varios `.py` y un `config.yaml` suelto: Mistral los muestra como carpetas reales, no
  aplanados ni descartados. No hay que subir sólo el `SKILL.md`.
- **No filtra por extensión.** Los `.py` y `.yaml` viajan igual que los `.md`.
- **Valida que el markdown *sea* un `SKILL.md`**, con su frontmatter, y no un documento
  que describa la skill. Un fichero con los campos troceados para copiar y pegar se
  rechaza con *«sube un archivo Markdown válido de skill»*. Por eso el conversor ya no
  genera ese intermediario.
- **El `SKILL.md` se convierte en el panel «Instrucciones»** de la skill, y la
  `description` del frontmatter es lo que se muestra como criterio de activación. Cada
  skill tiene además un interruptor de activación y un botón *Probar skill*.

- **No ejecuta los `scripts/`, aunque los guarde.** Comprobado en una ejecución real:
  Mistral tiene *algún* shell (crea directorios, escribe ficheros) pero **no tiene
  Python**. Los `.py` viajan como material de consulta, no como código ejecutable.
- **`~` no resuelve al home del usuario.** En esa misma ejecución `$HOME` era `/`, así
  que `~/.email-triage/` acabó creando `//.email-triage/`. Una skill que escriba en
  rutas con `~` fallará o escribirá en un sitio inesperado.
- **El estado en disco no persiste de forma fiable.** Reproducido en **dos ejecuciones
  independientes** de la misma skill: el anexado (`>> fichero`) reportó éxito y después
  el fichero tenía una sola línea, o directamente no existía. En ambos casos el agente
  acabó **reconstruyendo el registro de memoria** para poder continuar — funcionó porque
  la conversación seguía viva, pero en una sesión nueva ese estado ya no está.

**Dos consecuencias para exportar:**

1. Una skill cuya lógica viva en `scripts/` queda inerte en Mistral. Sólo sobrevive si el
   `SKILL.md` incluye un **procedimiento manual equivalente** al que el agente pueda caer
   cuando el script no arranque.
2. Una skill que dependa de un fichero de estado entre pasos (log, caché, historial,
   registro para deshacer) **no puede fiarse de él**. Y el modo de fallo es peor que el
   error: el agente rellena el hueco reconstruyendo el fichero de memoria, y sigue como
   si nada.

### Cómo escribir una skill que sobreviva a ese entorno

| En vez de… | Haz esto |
|---|---|
| `~/.mi-skill/estado.jsonl` | Una ruta relativa a la skill, o pedirle al usuario una ruta absoluta |
| `echo "..." >> log.jsonl` | Escribir el fichero **entero** de una vez; anexar es lo que falla |
| Dar por escrito lo que reportó éxito | Releer el fichero y comprobar que está lo que esperas |
| Asumir que el estado sigue ahí en la próxima sesión | Comprobar si existe; si no, decirlo — **nunca reconstruirlo de memoria** |

Esa última línea es la que más importa: si el estado se perdió, la respuesta correcta es
*"no encuentro el registro, no puedo deshacer"*, no un registro plausible inventado.

El conversor marca automáticamente estos patrones (`scripts`, `home-tilde`,
`estado-persistente`) como riesgo medio, e incrusta el aviso en el `SKILL.md` exportado.

## 2. Frontmatter

Sólo `name` y `description` son universales.

```yaml
---
name: mi-skill              # minúsculas, guiones, = nombre de la carpeta
description: Cárgala cuando...   # condición de activación, no descripción del contenido
---
```

Se retiran al exportar porque no existen fuera de Claude:

| Clave | Por qué se cae |
|---|---|
| `allowed-tools` / `allowed_tools` | La lista de herramientas permitidas es un concepto de Claude Code |
| `model` | El destino elige su propio modelo |
| `argument-hint` | Pertenece a los slash commands, no a las skills |
| `disable-model-invocation` | Control de invocación propio de Claude |
| `user-invocable`, `context` | Idem |

`license`, `version`, `depends` y `metadata` se conservan: forman parte del estándar
abierto o son inocuos.

## 3. La descripción: el campo que decide todo

El destino no lee el cuerpo de la skill para decidir si cargarla. Lee **sólo la
descripción**, y la paga en tokens en cada sesión. Por eso:

| Mal | Bien |
|---|---|
| "Esta skill genera informes financieros." | "Cárgala cuando el usuario pida un informe financiero, un cierre mensual o una comparativa presupuesto-real." |
| "Ayuda con reuniones." | "Cárgala cuando el usuario pegue notas o una transcripción de reunión y pida un resumen o los acuerdos." |
| "Herramienta de análisis." | (No dice nada. Reescríbela entera.) |

Reglas prácticas:

- Empieza por *"Cárgala cuando…"* / *"Use when…"*.
- Describe la **intención del usuario**, con las palabras que él usaría.
- Por debajo de ~350 caracteres. Perplexity presupuesta ~100 tokens por skill en su
  índice, y ese coste lo pagan todos los usuarios en todas las sesiones.
- Incluye dos o tres ejemplos de frases reales.
- Máximo duro habitual: 1024 caracteres.

## 4. Patrones que hay que reescribir a mano

### `${CLAUDE_PLUGIN_ROOT}`
Se reescribe automáticamente como ruta relativa. Si queda alguno suelto, sustitúyelo
por la ruta relativa a la carpeta de la skill.

```diff
- python3 ${CLAUDE_PLUGIN_ROOT}/skills/mi-skill/scripts/run.py
+ python3 scripts/run.py
```

### Herramientas MCP (`mcp__servidor__accion`)
No hay arreglo automático. Opciones, de mejor a peor:

1. Reescribir el paso como instrucción neutral: *"consulta la base de datos de clientes
   con la herramienta que tengas disponible"*.
2. Sustituir por una llamada HTTP directa a la API, si la skill trae credenciales.
3. Marcar el paso como no disponible y decirle al agente que lo declare.

Lo que **no** debe hacerse es dejar la llamada tal cual sin aviso: el modelo tenderá a
narrar que la ejecutó.

### Subagentes (`Task tool`, `subagent_type`)
Colapsa el subagente en instrucciones en línea. Si la skill delegaba análisis pesado,
conviértelo en una sección del propio `SKILL.md` o en un fichero de `references/` que
se cargue bajo condición.

### Comandos con namespace (`/mi-plugin:comando`)
No existen fuera de Claude. Si el comando era esencial, incorpora su contenido a la
skill. Si era un atajo, elimina la referencia.

### Herramientas nombradas de Claude
`TodoWrite`, `AskUserQuestion`, `WebFetch`, `ToolSearch`, `ExitPlanMode`… Cámbialas por
la acción genérica: "pregunta al usuario", "busca en la web", "anota la tarea".

### Hooks
No se exportan. Si la skill dependía de un hook `PreToolUse` para validar algo, esa
validación tiene que pasar al cuerpo de la skill como instrucción explícita.

## 5. Tamaño

| Nivel | Presupuesto | Cuándo se paga |
|---|---|---|
| Índice (`name` + `description`) | ~100 tokens | Siempre, en cada sesión |
| Cuerpo del `SKILL.md` | <5.000 tokens | Al cargarse la skill |
| `references/`, `scripts/`, `assets/` | Sin límite práctico | Sólo si el agente los abre |

Si el cuerpo se pasa, mueve lo condicional a `references/` y deja en el `SKILL.md` una
línea del tipo *"si la API devuelve un error, lee `references/errores.md`"*.

## 6. Estructura recomendada de la skill exportada

```
mi-skill/
├── SKILL.md          # frontmatter + procedimiento (el hub)
├── references/       # documentación pesada, cargada bajo condición
├── scripts/          # código determinista que el agente ejecuta
└── assets/           # plantillas, esquemas, ejemplos de salida
```

## 7. Comprobación antes de subir

- [ ] El nombre del frontmatter es igual al de la carpeta, en minúsculas con guiones.
- [ ] La descripción dice *cuándo*, no *qué*, y baja de 350 caracteres.
- [ ] No queda ninguna referencia a `${CLAUDE_PLUGIN_ROOT}`, `mcp__`, `Task tool` sin aviso.
- [ ] Las rutas de `scripts/` y `references/` son relativas y los ficheros acompañan a la skill.
- [ ] No hay rutas con `~` ni `$HOME`.
- [ ] Si la skill guarda estado, comprueba que existe antes de usarlo y no lo reconstruye de memoria.
- [ ] El zip tiene la carpeta de la skill en la raíz (no un nivel extra de por medio),
      y contiene **una sola** skill.
- [ ] A Mistral le subes la carpeta, no el zip.
- [ ] Se ha leído el `INFORME-PORTABILIDAD.md`.

## 8. Fuentes

- Agent Skills (estándar abierto): https://agentskills.io/home
- Perplexity — *How to use Computer Skills*: https://www.perplexity.ai/help-center/en/articles/13914413-how-to-use-computer-skills
- Perplexity Research — *Designing, Refining, and Maintaining Agent Skills*: https://research.perplexity.ai/articles/designing-refining-and-maintaining-agent-skills-at-perplexity
- Mistral Docs — *Create your first Skill*: https://docs.mistral.ai/getting-started/quickstarts/vibe-work/create-first-skill
- Claude Code — *Plugins reference*: https://docs.claude.com/en/docs/claude-code/plugins-reference
