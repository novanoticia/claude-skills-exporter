# Portabilidad Claude → Perplexity / Mistral / otros

Consulta este fichero cuando haya que reescribir una skill a mano o explicar por qué
un aviso del informe importa.

## 1. Qué acepta cada destino

> Los datos de esta tabla son la copia legible de `scripts/exporter/targets/*.json`, que
> es la fuente de verdad. El CI sólo comprueba, por contención, que la **etiqueta** y el
> **presupuesto de `description`** de cada perfil aparezcan escritos en algún sitio del
> README o de este fichero: no verifica la ruta de instalación, ni las capacidades, ni que
> las celdas digan lo mismo que el JSON. La tabla recoge sólo tres de los cinco destinos;
> ChatGPT y claude.ai tienen perfil propio (`chatgpt.json`, `claude-ai.json`) y comparten
> el zip de 850 bytes. Lo que sigue viviendo sólo aquí es la evidencia narrativa: qué se
> observó, en qué ejecución y por qué importa.

| | Perplexity Computer | Mistral Vibe Work | Claude Code |
|---|---|---|---|
| Ruta de instalación | `perplexity.ai/computer/skills` → Create skill → Upload a skill | `chat.mistral.ai/work` → Context → Skills → New Skill | Copiar la carpeta a `~/.claude/skills/`, o instalar el plugin con `/plugin install` |
| Formato | **`.zip`** con la carpeta de la skill en su raíz | **la carpeta**, con `SKILL.md` dentro | Carpeta con `SKILL.md` |
| Presupuesto de `description` | 850 bytes | 490 bytes | 1024 bytes |
| Varias skills a la vez | No — **una por zip** | No — una por vez | Sí |
| Ficheros auxiliares | Sí, dentro del zip | Sí — conserva subcarpetas y cualquier extensión (`.md`, `.py`, `.yaml`) | Sí |
| Ejecuta `scripts/` | Sí — y llega al Mac vía `osascript` | **No** — hay shell, pero sin Python | Sí |
| Límite de tiempo por llamada | ~90 s (comprobado) | — (no ejecuta) | Sin límite práctico |
| Frontmatter mínimo | `name`, `description` | `name`, `description` | `name`, `description` |
| Frontmatter cerrado | Sí — cualquier clave fuera de `name`, `description`, `license`, `compatibility` y `metadata` es error duro | Sí | No — admite claves propias de Claude |

Claude Code instala en modo `directorio_local` y el conversor no fabrica un artefacto
propio para él: se lleva la misma carpeta que Mistral, con la descripción de 490 bytes.
El presupuesto de un artefacto lo escribe el destino más estrecho de los que comparten ese
modo de instalación, no el más generoso.

**El `.zip` y la carpeta no son intercambiables.** Llevan exactamente los mismos ficheros,
pero la `description` del frontmatter se compacta al presupuesto de cada destino: 850
bytes en el zip, 490 en la carpeta. Descomprimir el zip **no** produce la carpeta de
Mistral — la descripción que sale es la larga.

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

La severidad ya no es una propiedad del patrón: la declara el perfil del destino. En
Perplexity Computer, `applescript` y `lote-destructivo` disparan los dos el peligro
`perplexity-corte-90s`, de severidad **alta**, así que una skill que los contenga sale
**no compatible** con este destino. La severidad «media» que muestra `inspect` es sólo la
reserva que se usa mientras no se ha elegido destino.

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

El conversor detecta estos patrones (`scripts`, `home-tilde`, `estado-persistente`) e
incrusta el aviso en el `SKILL.md` exportado, pero la gravedad la pone el destino, no el
patrón: en Mistral Vibe Work `home-tilde` dispara `mistral-home-es-raiz` y
`estado-persistente` dispara `mistral-estado-no-persiste`, ambos de severidad **alta**, y
`scripts/` choca además con `scripts.ejecutar: no`. El veredicto para Mistral es **no
compatible**, no «riesgo medio».

## 2. Frontmatter

Sólo `name` y `description` son obligatorios. Y el frontmatter del estándar es un conjunto
**cerrado**: `name`, `description`, `license`, `compatibility` y `metadata`. Cualquier otra
clave al nivel superior no se ignora — el destino rechaza la skill entera («Unexpected
key(s) in SKILL.md frontmatter»).

```yaml
---
name: mi-skill              # minúsculas, guiones, = nombre de la carpeta
description: Cárgala cuando...   # condición de activación, no descripción del contenido
---
```

El conversor no va retirando claves una a una: conserva sólo las del conjunto cerrado y
descarta el resto. Estas son las que más suelen aparecer, y por qué se caen:

| Clave | Por qué se cae |
|---|---|
| `allowed-tools` / `allowed_tools` | Está en el estándar, pero su semántica es de Claude Code y fuera no significa nada: se retira igualmente |
| `model` | El destino elige su propio modelo |
| `argument-hint` | Pertenece a los slash commands, no a las skills |
| `disable-model-invocation` | Control de invocación propio de Claude |
| `user-invocable`, `context` | Idem |

`license`, `compatibility` y `metadata` se conservan al nivel superior: son del conjunto
cerrado del estándar. `version` y `depends` **no** — se bajan dentro de `metadata`,
fusionadas con el `metadata` de origen si lo hubiera, porque emitidas arriba hacen que el
destino rechace la skill entera:

```yaml
metadata:
  autor: Pablo
  version: 4.1
  depends:
    - otra-skill
```

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
hilo del texto. Pero desactiva algo más: sin él no hay compactación —ni poda de ejemplos
entrecomillados, ni priorización de la frase de activación—, sólo un recorte duro por el
final. Con la descripción de `email-triage` eso es exactamente el escenario del ejemplo de
arriba: la carpeta de Mistral se queda con las cuatro frases descriptivas y **pierde
entera** la frase «Actívalo cuando el usuario diga…». Úsalo sólo si vas a revisar a mano
lo que sale.

Reglas prácticas:

- Empieza por *"Cárgala cuando…"* / *"Use when…"*.
- Describe la **intención del usuario**, con las palabras que él usaría.
- Por debajo de ~350 caracteres. Perplexity presupuesta ~100 tokens por skill en su
  índice, y ese coste lo pagan todos los usuarios en todas las sesiones.
- Incluye dos o tres ejemplos de frases reales.
- Máximo duro: 1024, y **la unidad depende del destino**: Perplexity Computer lo mide en
  bytes UTF-8 (`tope_duro_description.unidad: bytes`); el estándar, ChatGPT, claude.ai,
  Mistral y Claude Code lo declaran en caracteres. Escribe pensando en bytes: es el
  criterio más estrecho y el único que se ha visto rechazar una subida.
- Presupuesto que aplica el conversor, por debajo del máximo y por destino: **490 bytes**
  en la carpeta de Mistral, **850** en el zip de Perplexity.

### El límite de 1024 se mide en bytes

Comprobado subiendo `email-triage.zip` a Perplexity Computer:

```
failed to parse skill file: invalid skill description:
description exceeds maximum length of 1024 characters
```

Aunque el mensaje diga *characters*, la cuenta es en bytes. Esa descripción tenía
1063 caracteres — pero **1085 bytes**, porque cada tilde, cada `ñ` y cada `¿` ocupan
dos, y cada `—` ocupa tres. Un texto en español se pasa del límite unos 20-30 bytes
antes de lo que sugiere contar letras. El conversor ya no recorta a un número fijo: toma
el presupuesto de los perfiles de destino, el más estrecho de los que aceptan cada modo de
instalación — 850 bytes para el zip (Perplexity, ChatGPT, claude.ai) y 490 para la carpeta
(Mistral). Los dos quedan muy por debajo del tope duro.

**Y los dos destinos fallan distinto:**

| | Qué pasa si la descripción se pasa |
|---|---|
| Perplexity Computer | **Rechaza el zip entero.** No importa nada más de la skill: no se instala |
| Mistral Vibe Work | Acepta la subida y **te deja abreviarla a mano** en el panel de la skill |

Es decir: en Mistral es un inconveniente, en Perplexity es un bloqueo. Si sólo pruebas
en Mistral, no te enteras de que tu skill no es instalable en el otro.

**Cuidado con lo que se pierde al recortar.** El conversor compacta primero —adelanta las
frases de activación, poda los ejemplos entrecomillados sobrantes (deja unos cuatro y
resume el resto con «…») y descarta después las frases que sólo cuentan qué hace la
skill—, y sólo si aun así no cabe aplica el corte duro: por el último final de frase que
quepa, o por el último espacio con «…» si no hay ninguno razonable. Como el reordenado va
antes que el recorte, lo que sobrevive es el criterio de activación y lo que se pierde es
la parte descriptiva. Aun así, si ves el aviso `description-larga`, reescríbela a mano: el
recorte sólo garantiza que el fichero sea válido.

## 4. Patrones que hay que reescribir a mano

### `${CLAUDE_PLUGIN_ROOT}`
Se reescribe automáticamente como ruta relativa, pero **sólo en el cuerpo del `SKILL.md`**.
Las apariciones dentro de `references/`, `scripts/` o cualquier otro fichero del árbol no
se tocan: se reportan como señal `plugin-root` con su `fichero:línea` y hay que sustituirlas
a mano por la ruta relativa a la carpeta de la skill.

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
| `references/`, `scripts/`, `assets/` | Sin límite práctico, salvo donde el destino publique uno: ChatGPT declara 50 MB de zip, 500 ficheros y 25 MB por fichero, y el conversor los comprueba al empaquetar (aviso `limite-de-paquete`) | Sólo si el agente los abre |

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

El conversor conserva el modo de los ficheros al copiar (`os.chmod`), así que un
`scripts/*.sh` con `+x` llega al paquete ejecutable — que es lo que necesita Perplexity
Computer, el único destino que ejecuta `scripts/`.

## 7. Comprobación antes de subir

- [ ] El nombre del frontmatter es igual al de la carpeta, en minúsculas con guiones.
- [ ] La descripción dice *cuándo*, no *qué*, y baja de 350 caracteres.
- [ ] No queda ninguna referencia a `${CLAUDE_PLUGIN_ROOT}`, `mcp__`, `Task tool` sin aviso.
- [ ] Las rutas de `scripts/` y `references/` son relativas y los ficheros acompañan a la skill.
- [ ] No hay rutas con `~` ni `$HOME`.
- [ ] Si la skill guarda estado, comprueba que existe antes de usarlo y no lo reconstruye de memoria.
- [ ] El zip tiene la carpeta de la skill en la raíz (no un nivel extra de por medio),
      y contiene **una sola** skill.
- [ ] A Mistral le subes la carpeta, no el zip descomprimido: **no son lo mismo**.
- [ ] La descripción es un solo párrafo, sin listas ni saltos de línea.
- [ ] Se ha leído el `INFORME-PORTABILIDAD.md`.

## 8. Fuentes

- Agent Skills (estándar abierto): https://agentskills.io/home
- Perplexity — *How to use Computer Skills*: https://www.perplexity.ai/help-center/en/articles/13914413-how-to-use-computer-skills
- Perplexity Research — *Designing, Refining, and Maintaining Agent Skills*: https://research.perplexity.ai/articles/designing-refining-and-maintaining-agent-skills-at-perplexity
- Mistral Docs — *Create your first Skill*: https://docs.mistral.ai/getting-started/quickstarts/vibe-work/create-first-skill
- Claude Code — *Plugins reference*: https://docs.claude.com/en/docs/claude-code/plugins-reference

## 9. Cómo añadir un destino

1. Escribir `scripts/exporter/targets/<id>.json` siguiendo `_schema.json`. El
   `id` debe coincidir con el nombre del fichero.
2. Declarar cada capacidad. **Lo que no se haya comprobado va a `desconocido`,
   nunca a `no`.** Callar no es negar: `desconocido` produce `no verificable`,
   que es la respuesta honesta. `no` —y también `parcial`— produce `no compatible`
   si la skill declara esa capacidad como **requerida**, y `degradado` si sólo la
   marca como opcional; en los dos casos es una afirmación.
3. Los peligros de conducta —lo que la plataforma hace mal *teniendo* la
   capacidad— van en `peligros[]`, enlazados por `dispara_con` al id de la señal.
   **`dispara_con: []` significa «informativo»**: documenta un comportamiento de la
   plataforma que no depende de ninguna señal detectable, así que `peligros_para()` nunca
   lo devuelve y no afecta a ningún veredicto. Sirve como referencia para quien lea el
   perfil. Si esperabas que tu peligro disparase y no lo hace, mira aquí primero.
4. Poner `evidencia.verificado_el` a hoy y `revisar_tras` a tres meses vista.
5. Escribir la etiqueta y el presupuesto en la prosa. El CI (`.github/validar_perfiles.py`)
   los busca por contención en el README **o** en este fichero —basta con que aparezcan en
   uno de los dos, en cualquier sitio del texto— y falla si no los encuentra. Que la tabla
   de la sección 1 quede correcta es responsabilidad tuya: eso el CI no lo comprueba.
6. Regenerar los golden: `python3 tests/generar_golden.py`, y revisar el diff. Las pruebas
   fijan la fecha con `CSE_FECHA=AAAA-MM-DD`; si tu perfil nace con un `revisar_tras`
   anterior a esa fecha, saldrá `no verificable` en los golden.

No hay que tocar Python mientras el destino encaje en lo que ya existe: un modo de
instalación de los cuatro del schema (`zip`, `carpeta`, `directorio_local`,
`url_repositorio`) y capacidades del vocabulario ya definido. `export` sólo sabe fabricar
dos artefactos —el zip y la carpeta—, así que un modo nuevo, o una capacidad que ninguna
señal sepa exigir todavía, sí exige código.

## 10. Cómo añadir una regla de seguridad

1. Escribe la entrada en `exporter/seguridad/reglas.json`, respetando
   `exporter/seguridad/_schema.json`: `id` con el formato `SEC-<FAMILIA>-<NNN>`, `familia`,
   `dimension`, `severidad` y `confianza` de los vocabularios cerrados, `patron` como
   expresión regular de Python, y `titulo`, `detalle`, `mitigacion` y `extensiones` sin
   dejar ninguno vacío.
2. Elige `confianza` con honestidad. `alta` es para patrones que no admiten lectura
   inocente —descargar un script de la red y pasarlo directamente al intérprete, sin
   verificar hash ni firma—; `media` o `baja` para los que sí pueden tener una razón
   legítima. Si la regla es de la familia `conducta_de_prompt`, `confianza` es `media`
   siempre: el `SKILL.md` viaja íntegro al agente de destino y ahí el listón para bloquear
   es más bajo que en el resto (§5 del diseño).
3. **Añade un fixture en `tests/fixtures/` que la dispare** —o el CI falla:
   `.github/validar_reglas.py` exige al menos un fixture por regla—. Amplía la tabla de
   fixtures de seguridad con la fila nueva.
4. Regenera los *golden files*: `python3 tests/generar_golden.py`, y revisa el diff antes
   de comitear. Es la única señal de que la regla nueva no ha cambiado el veredicto de
   ningún fixture existente.

> **Describe los patrones aquí, no los escribas.** Todo lo que hay bajo
> `skills/plugin-to-agentskills/` tiene ámbito `exportado`, así que un patrón grave escrito
> en claro en esta documentación bloquea la exportación de la propia herramienta: el
> `.zip` deja de escribirse y `export` devuelve 3. Los patrones literales van en
> `reglas.json` —que el motor se salta a sí mismo— y en `tests/fixtures/`, que está fuera
> de toda skill. Aquí se explican con palabras.
