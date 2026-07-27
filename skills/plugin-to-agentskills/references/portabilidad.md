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
| Ejecuta `scripts/` | Sí — y llega al Mac vía `osascript` | **No** — hay shell, pero sin Python | Sí |
| Límite de tiempo por llamada | ~90 s (comprobado) | — (no ejecuta) | Sin límite práctico |
| Frontmatter mínimo | `name`, `description` | `name`, `description` | `name`, `description` |

**Sólo existe un artefacto: el `.zip`.** Es válido tal cual para Perplexity. Para
Mistral, el único paso es descomprimirlo y subir la carpeta resultante. No hay ninguna
conversión intermedia, ni un «formato Mistral» distinto que haya que generar aparte:
el conversor deja las dos formas juntas por comodidad, nada más.

### Lo comprobado en Perplexity Computer

Observado en una ejecución real de `email-triage` sobre un buzón de 358 correos:

- **Ejecuta los `scripts/` y además alcanza el Mac del usuario.** Tenía disponibles
  `osascript` y acceso a Mail.app: leyó buzones, contó correos y movió mensajes entre
  carpetas. No es un sandbox aislado como cabría suponer.
- **Corta cada llamada en torno a 90 segundos.** Con un buzón grande, cada movimiento
  sincroniza contra iCloud y el lote no termina. El agente tuvo que partirlo en trozos.
- **Un lote cortado a mitad deja el trabajo inconsistente.** Es el fallo importante: el
  script de archivado se llevó unos 64 correos que no estaban en el lote evaluado, y un
  filtro de fecha que debía cortar en junio movió también correos de julio. Se detectó
  y se revirtió a mano, pero sólo porque la sesión seguía viva.

**Consecuencia para exportar:** una skill que modifique cosas en bloque necesita, para
sobrevivir aquí, tres propiedades que en Claude podía permitirse no tener:

1. **Trozos pequeños**, dimensionados para terminar dentro del límite de tiempo.
2. **Verificación después de cada trozo**, releyendo el estado real en vez de fiarse de
   que la operación devolvió éxito.
3. **No dar por bueno el filtro.** Comprobar qué elementos se han tocado, no cuántos se
   pretendía tocar.

El conversor marca `applescript` en riesgo medio y `lote-destructivo` en riesgo **alto**
justo por esto.

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

### El orden: primero cuándo, después qué

No basta con que la descripción mencione los disparadores en alguna parte. Tienen que ir
**delante**, por dos razones distintas:

1. Si hay que recortar, lo que se pierde es la cola. Una descripción que empieza contando
   qué hace la skill y termina diciendo cuándo activarla queda inservible en cuanto pasa
   del límite: sobrevive lo decorativo.
2. Aunque quepa entera, el destino decide con lo primero que lee.

El conversor lo hace automáticamente: trocea la descripción en frases —respetando comillas
y paréntesis, porque los disparadores suelen ir entrecomillados— y adelanta las que
contienen marcas de activación (`Cárgala cuando`, `Actívalo cuando`, `cuando el usuario`,
`se activa con`, `Use when`, `when the user`…). Lo hace **antes** de recortar.

Ejemplo real, `email-triage`. Antes:

> Triaje inteligente de correo electrónico: analiza bandejas… *(4 frases describiendo el
> funcionamiento)* … Actívalo cuando el usuario diga "filtra mi correo", "revisa mi
> bandeja"…

Recortado sin reordenar, se perdía entera la última frase — la única que importa. Después
de reordenar, el recorte se lleva `Incluye calibración estadística…` y la lista de
disparadores queda intacta.

**Lo que el conversor no puede hacer:** inventar disparadores que no están. Si la
descripción no dice en ningún momento cuándo cargar la skill, sale el aviso
`description-sin-activacion` con riesgo **alto** y hay que reescribirla a mano. Rellenar
ese hueco automáticamente sería fabricar criterios de activación que el autor nunca
escribió, y una skill que se carga cuando no debe es peor que una que no se carga.

Con `--keep-description-order` se desactiva el reordenado, por si en algún caso rompe el
hilo del texto.

Reglas prácticas:

- Empieza por *"Cárgala cuando…"* / *"Use when…"*.
- Describe la **intención del usuario**, con las palabras que él usaría.
- Por debajo de ~350 caracteres. Perplexity presupuesta ~100 tokens por skill en su
  índice, y ese coste lo pagan todos los usuarios en todas las sesiones.
- Incluye dos o tres ejemplos de frases reales.
- Máximo duro: 1024. **Y se mide en bytes UTF-8, no en caracteres.**

### El límite de 1024 se mide en bytes

Comprobado subiendo `email-triage.zip` a Perplexity Computer:

```
failed to parse skill file: invalid skill description:
description exceeds maximum length of 1024 characters
```

Aunque el mensaje diga *characters*, la cuenta es en bytes. Esa descripción tenía
1063 caracteres — pero **1085 bytes**, porque cada tilde, cada `ñ` y cada `¿` ocupan
dos, y cada `—` ocupa tres. Un texto en español se pasa del límite unos 20-30 bytes
antes de lo que sugiere contar letras. El conversor recorta a 980 para dejar margen.

**Y los dos destinos fallan distinto:**

| | Qué pasa si la descripción se pasa |
|---|---|
| Perplexity Computer | **Rechaza el zip entero.** No importa nada más de la skill: no se instala |
| Mistral Vibe Work | Acepta la subida y **te deja abreviarla a mano** en el panel de la skill |

Es decir: en Mistral es un inconveniente, en Perplexity es un bloqueo. Si sólo pruebas
en Mistral, no te enteras de que tu skill no es instalable en el otro.

**Cuidado con lo que se pierde al recortar.** El conversor corta por el último final de
frase que quepa, nunca a mitad de palabra. Pero eso conserva el principio de la
descripción — que suele decir *qué hace* la skill — y tira el final, que suele ser donde
está el *"Actívalo cuando el usuario diga…"*. Justo lo que decide si la skill se carga.
Si ves el aviso `description-larga`, reescribe la descripción a mano: no te fíes del
recorte automático, que sólo garantiza que el fichero sea válido.

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
