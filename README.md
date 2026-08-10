# Claude Skills Exporter

Coge un repositorio con un plugin (o unas skills) de Claude, extrae las skills,
**audita, destino por destino, qué se romperá fuera de Claude** y las empaqueta para
instalarlas en **ChatGPT**, **claude.ai**, **Claude Code**, **Mistral Vibe Work** y
**Perplexity Computer**.

> **Compatible con [Agent Plugins 1.0.0](https://agent-plugins.org/specification)** —
> el formato portátil de empaquetado de la Agentic AI Foundation (OpenAI, Amazon,
> Microsoft, Cursor y Vercel, con Google como *core maintainer*). Este repositorio
> es a la vez un plugin conforme a esa especificación y la herramienta que lleva
> otros plugins hacia ella. Las skills que produce validan contra el conjunto
> cerrado de frontmatter de [Agent Skills](https://agentskills.io/specification),
> que es lo que ChatGPT, claude.ai y la Skills API exigen para aceptar una subida.

👉 **Si no manejas GitHub, empieza por la [guía de uso](docs/guia.html)** — descárgala y
ábrela con doble clic en el navegador. Cubre instalar la herramienta, exportar un
repositorio y subir el resultado a cada plataforma.

Para publicar y mantener tu propia copia del repositorio —subirlo a GitHub, instalarlo
desde el marketplace, publicar cambios, aplicar parches— hay una
[guía de mantenimiento](docs/mantenimiento.html) aparte.

## La advertencia importante

Un plugin de Claude **no es portable como unidad**. Empaqueta cinco cosas y sólo una
viaja al estándar abierto Agent Skills:

| Componente | ¿Se exporta? |
|---|---|
| `skills/` | ✅ Sí |
| `commands/` | ❌ No |
| `agents/` (subagentes) | ❌ No |
| Servidores MCP | ❌ No |
| `hooks/` | ❌ No |

Esta herramienta no arregla eso: lo **hace visible**. Cuando hay algo que declarar, la
skill exportada lleva incrustado un aviso que le dice al agente de destino qué
instrucciones no va a poder cumplir, para que lo declare en vez de simular el resultado.
Si no hubo adaptaciones ni hallazgos, el `SKILL.md` sale limpio, sin nota.

## Instalación

```
/plugin marketplace add https://github.com/novanoticia/claude-skills-exporter
/plugin install claude-skills-exporter@pablo-skills-tools
/reload-plugins
```

Lo que va después de la arroba, `pablo-skills-tools`, es el nombre del **marketplace**
(campo `name` de `.claude-plugin/marketplace.json`), no un usuario de GitHub.

### Cómo se invoca con `/`

Una vez instalado, el plugin aporta un comando y una skill. Los comandos de plugin van
**namespaced**, con el nombre del plugin delante y dos puntos:

| Qué escribes | Qué hace |
|---|---|
| `/claude-skills-exporter:exportar-skills <url-o-ruta>` | Exporta las skills del repositorio indicado. Es la forma canónica. |
| `/exportar-skills <url-o-ruta>` | Atajo. Funciona igual, salvo que otro plugin instalado use ya ese nombre. |
| `/claude-skills-exporter:plugin-to-agentskills` | Carga la skill directamente, sin pasar por el comando. Útil para preguntar por portabilidad sin exportar nada. |

Ejemplos:

```
/claude-skills-exporter:exportar-skills https://github.com/usuario/repo
/exportar-skills ~/proyectos/mi-plugin
/exportar-skills .
```

Escribe `/` y empieza a teclear `expor` para que el autocompletado lo ofrezca. Si no
aparece, ejecuta `/reload-plugins`.

También funciona en lenguaje natural, sin barra: *«exporta las skills de este repo para
ChatGPT»* o *«¿es portable esta skill?»*. La skill se activa sola porque su
`description` lleva esos disparadores.

### Actualizar

Los manifiestos de este plugin **no fijan `version`**: Claude Code usa entonces el hash
del commit como identificador, de modo que cada publicación cuenta como versión nueva.
Con «Sincronizar automáticamente» activado en el marketplace, las actualizaciones llegan
solas. Para forzarlas:

```
/plugin marketplace update pablo-skills-tools
/plugin update claude-skills-exporter
/reload-plugins
```

La contrapartida de no fijar versión: llegan todos los commits, no sólo los que alguien
haya marcado como release.

## Uso

### Sin instalar nada

```bash
python3 skills/plugin-to-agentskills/scripts/convert.py https://github.com/usuario/repo \
    --out ./dist-agentskills
```

Sólo necesita Python 3.8+. Sin dependencias externas; `git` sólo hace falta si el origen
es una URL de repositorio, no si ya tienes la carpeta descargada.

| Opción | Qué hace |
|---|---|
| `--out DIR` | Directorio de salida (por defecto `./dist-agentskills`). **Se borra entero** antes de escribir |
| `--force` | Vaciar `--out` aunque no lo haya escrito esta herramienta. Pierdes lo que hubiera dentro |
| `--only a b c` | Exporta sólo esas skills |
| `--zip-only` | Deja sólo los `.zip` — se pierde la variante para Mistral. Con un destino que sólo instala carpeta (`--target mistral-vibe-work`) es **error** y aborta: no quedaría ningún artefacto de skill |
| `--target a b` | En `audit`, qué destinos evaluar; en `export`, qué artefactos producir — la auditoría sigue cubriendo los cinco |
| `--fail-on {ninguno,degradado,no_compatible}` | Devuelve código 2 si algún estado alcanza ese umbral. Útil en CI |
| `--keep-description-order` | No reordena la descripción — y con ello desactiva también la compactación: sólo queda el recorte duro por el final |

> ⚠️ **`--out` se borra entero** antes de cada exportación: lo que haya dentro se pierde.
> Para que no pueda llevarse por delante nada tuyo, `export` se niega a vaciar un
> directorio que tenga contenido y no lleve la marca `.cse-salida` que esta herramienta
> escribe. Un directorio vacío, inexistente o ya usado como salida se reutiliza sin
> preguntar; para cualquier otro hace falta `--force`. Y nunca acepta un `--out` que sea
> el propio origen o que lo contenga, ni siquiera con `--force`: eso borraría el
> repositorio que iba a leer.

## Los tres modos

| Comando | Qué hace | ¿Escribe ficheros? |
|---|---|---|
| `convert.py inspect <origen>` | Qué contiene la skill y qué exige, sin elegir destino | No |
| `convert.py audit <origen>` | Matriz de compatibilidad por destino | No |
| `convert.py export <origen>` | Audita y empaqueta | Sí |

`convert.py <origen>` sin subcomando sigue exportando, como siempre.

### Códigos de salida

| Código | Cuándo |
|---|---|
| `0` | Nada que reportar. También `inspect`, que no evalúa destinos y siempre sale con 0 |
| `1` | Error de uso o de entrada: el origen no existe, no contiene ningún `SKILL.md`, `--target` desconocido, `--only` sin coincidencias, dos skills que reclaman el mismo nombre, o un `--out` que la herramienta se niega a borrar |
| `2` | Se ha alcanzado el umbral de `--fail-on`, **o** el nivel de riesgo de seguridad no es `bajo` |
| `3` | Sólo en `export`: el *gate* de seguridad ha impedido escribir los artefactos de al menos una skill |

Dos matices que cuestan un rato descubrir a base de pruebas:

- El **2 por riesgo de seguridad** no depende de `--fail-on`. `audit` y `export` lo
  devuelven en cuanto el nivel deja de ser `bajo`, aunque no hayas pedido ningún umbral.
- `--anular-revision-seguridad` **suprime** ese 2, además de evitar el 3. Es deliberado:
  la anulación ya queda escrita en el informe, y devolver además ≠ 0 después de habértela
  pedido sólo enseña a ignorar el código de salida. Con la anulación sólo sobrevive el
  código de `--fail-on`.

**Usarlo en CI.** `--fail-on degradado` devuelve código 2 si alguna skill queda en
`degradado`, `no verificable` o `no compatible` en algún destino; `--fail-on no_compatible`
sólo con el peor estado. Combínalo con `audit`, que no escribe ficheros:

```bash
python3 convert.py audit . --target perplexity-computer --fail-on no_compatible
```

## Qué genera

Dos artefactos por skill, con los mismos ficheros pero **distinta descripción**: cada
destino tiene su presupuesto y la `description` se compacta para caber en él.

```
dist-agentskills/
├── mi-skill.zip               → ChatGPT, claude.ai y Perplexity (description ≤ 850 bytes)
├── mi-skill/                  → Mistral, Claude Code (description ≤ 490 bytes)
│   ├── SKILL.md
│   └── references/ scripts/ ...
├── otra-skill.zip
├── otra-skill/
├── INFORME-PORTABILIDAD.md    qué se adaptó y qué se romperá
└── resumen.json               lo mismo, en formato máquina
```

`resumen.json` es la salida para máquinas y tiene contrato: lleva `report_version` (hoy
`"3.0"`) y valida contra
[`exporter/resumen.schema.json`](skills/plugin-to-agentskills/scripts/exporter/resumen.schema.json)
en cada `push`. Desde la 3.0 trae además un bloque `seguridad` de nivel superior —nivel de
riesgo, recomendación de instalación, las tres dimensiones y la lista completa de hallazgos
con su `fichero:línea`— y `bloqueo_seguridad` ya puede no ser `null`. Es además el único
artefacto que trae los hallazgos completos —severidad, código y el `fichero:línea` donde se
vio cada señal—: el informe en Markdown se queda en la matriz y los motivos.

## Dónde se sube cada cosa

| Destino | Qué subir | `description` | Ruta |
|---|---|---|---|
| **ChatGPT** | `mi-skill.zip` — **tal cual**, sin tocar | ≤ 1024 caracteres | Con `Work` activado, en **Complementos** (ver la nota) |
| **Perplexity Computer** | `mi-skill.zip` — **tal cual**, sin tocar | ≤ 850 B | `perplexity.ai/computer/skills` → *Create skill* → *Upload a skill* |
| **Mistral Vibe Work** | `mi-skill/` — la **carpeta** | ≤ 490 B | `chat.mistral.ai/work` → *Context* → *Skills* → *New Skill* |
| **Claude Code** | `mi-skill/` — la **carpeta** | ≤ 490 B de hecho | Copiar a `~/.claude/skills/`, o instalar el plugin con `/plugin install` |
| **claude.ai** | `mi-skill.zip` | ≤ 1024 caracteres | *Ajustes* → *Capacidades* → *Skills* → *Subir skill* |

> **El presupuesto lo escribe el destino más estrecho de cada modo de instalación**, no
> el de cada plataforma: la carpeta es una sola y la marca Mistral con sus 490 B, aunque
> Claude Code admita los 1024 caracteres del estándar.

> **Para ChatGPT sirve el mismo `.zip` de Perplexity**, sin volver a exportar: su tope
> es de 1024 caracteres y el zip trae la descripción de 850 bytes, así que cabe de
> sobra. Exige además que el zip contenga **una única carpeta en la raíz** y **un solo
> `SKILL.md`** — que es exactamente lo que genera esta herramienta. Sus otros límites
> (50 MB de zip, 500 ficheros, 25 MB por fichero descomprimido) quedan muy lejos para
> una skill normal — pero la herramienta los comprueba: si un zip los superara, saldría
> el hallazgo `limite-de-paquete` en el informe. Está en el **plan gratuito**, con
> límites de uso.
>
> **Sobre la ruta exacta en ChatGPT, honestamente: no la hemos verificado para un zip
> suelto.** Lo que sí está comprobado a mano es instalar un *repositorio* como
> complemento —activar `Work` en el selector, ir a **Complementos** y añadirlo por
> nombre o por URL—. Para un `.zip` de una skill aislada, que es lo que produce esta
> herramienta, mira la gestión de complementos con `Work` activado y consulta la
> documentación de ChatGPT si la interfaz ha cambiado. Preferimos decir esto a repetir
> unos pasos concretos que ya nos salieron mal una vez.

> **No son intercambiables.** Descomprimir el `.zip` **no** da la carpeta de Mistral: la
> descripción que sale es la larga. Si sólo conservas el zip y luego quieres subirlo a
> Mistral, vuelve a exportar.

> **Una skill por zip.** Perplexity espera encontrar la carpeta de *una sola* skill en
> la raíz del zip; un zip con varias falla o sólo reconoce una. Por eso no se genera
> ningún zip global.

## Qué audita

El veredicto ya no es único por skill: es **uno por destino**. Una skill cuya
lógica vive en `scripts/` es `no compatible` en Mistral Vibe Work, que no tiene
Python, y `compatible` en Perplexity Computer, que sí lo ejecuta. Los destinos
se declaran en `skills/plugin-to-agentskills/scripts/exporter/targets/*.json`,
con la fecha en que se comprobó cada dato y una fecha de revisión: cuando esa
fecha vence, el estado degrada a `no verificable` en vez de seguir afirmando.

- Frontmatter ausente, incompleto o con claves que sólo existen en Claude.
- Descripciones que describen *qué hace* la skill en vez de *cuándo* activarla — la
  causa nº 1 de que una skill importada no se cargue nunca. Aquí no se limita a avisar:
  **reordena la descripción para que los disparadores vayan delante**, porque es lo que
  el destino lee para decidir y lo primero que debe sobrevivir a un recorte. Si no hay
  ningún disparador que adelantar, lo marca en riesgo alto en vez de inventarse uno.
- Rutas `${CLAUDE_PLUGIN_ROOT}` (las reescribe).
- Llamadas a herramientas MCP, subagentes (`Task tool`), comandos con namespace,
  hooks y herramientas propias de Claude.
- Dependencias del entorno que el destino no reproduce: rutas al home del usuario y
  estado acumulado en disco entre pasos (logs, cachés, registros para deshacer). En
  Mistral Vibe Work esas escrituras pueden reportar éxito y no persistir.
- Tamaño del cuerpo frente al presupuesto de contexto recomendado.

Cada hallazgo conserva su severidad —alta (no funcionará), media (funcionará degradado),
baja (cosmético)—, pero el informe ya no los pinta con iconos: los emojis son ahora el
estado **por destino** de la matriz — 🟢 compatible, 🟡 adaptación, 🟠 degradado,
🔵 no verificable, 🔴 no compatible. Los hallazgos, con su código y su `fichero:línea`,
viven en `resumen.json` y en las notas que se incrustan al final del `SKILL.md` exportado,
agrupados en «Probablemente no funcione en este entorno» y «Funcionará, pero con
limitaciones».

## Qué audita de seguridad

Además de la portabilidad, la herramienta responde a una pregunta distinta: **qué puede
hacer este paquete si lo instalas**. Para eso recorre el repositorio **entero**, no sólo las
carpetas de skill — un `postinstall` malicioso en `package.json` no pertenece a ninguna
skill, y hasta ahora era invisible.

Cada hallazgo nace con un **ámbito**, y de ahí cuelga lo que ocurre:

| Ámbito | Qué significa | Qué provoca |
|---|---|---|
| `exportado` | El fichero viaja dentro del `.zip` o la carpeta | Se **bloquea** la escritura de ese artefacto |
| `paquete` | Se queda en el repositorio | Sale en cabecera del informe; código de salida 2, pero los artefactos se escriben |

El bloqueo es **por skill**: una skill limpia se exporta aunque su vecina esté bloqueada. Y
`--anular-revision-seguridad` permite exportar igualmente, dejando constancia escrita en el
informe.

Cuatro familias de reglas —permisos y acciones, cadena de suministro, ofuscación y conducta
de prompt— más comprobaciones estructurales sobre manifiestos, binarios y archivos
comprimidos, que **se señalan y nunca se abren**.

> **La familia de conducta de prompt cubre sólo formulaciones conocidas.** Reconocer una
> inyección reformulada exige un juicio semántico que esta herramienta no hace y no pretende
> hacer. Lo declara en cada informe donde aparece.

## Contribuir

Los issues y pull requests son bienvenidos, sobre todo los que aporten comportamiento
observado en un destino concreto: qué acepta, qué rechaza y con qué mensaje de error.
Buena parte de lo que audita esta herramienta procede de fallos reales al subir skills,
no de la documentación de las plataformas.

Cada `push` y cada pull request sobre `main` ejecuta
[`.github/workflows/validar.yml`](.github/workflows/validar.yml), que comprueba lo que
rompe la carga del plugin en silencio —y algo más—:

- Los manifiestos parsean como JSON y tienen los campos obligatorios.
- El nombre del plugin coincide entre `plugin.json` y `marketplace.json`, y el `source`
  apunta a un directorio existente.
- Cada `SKILL.md` tiene frontmatter con `name` y `description`, en kebab-case y con el
  nombre igual al de su carpeta.
- Los `.py` compilan.
- **El conversor se ejecuta de verdad** sobre este mismo repositorio y produce un `.zip`,
  su carpeta y el informe. Compilar sólo detecta errores de sintaxis: una constante
  renombrada pasa el `py_compile` y revienta en ejecución.
- Las descripciones generadas respetan el presupuesto de cada destino (490 y 850 bytes).
- Los perfiles de `targets/*.json` validan contra `_schema.json`, y su etiqueta y su
  presupuesto aparecen citados en el README o en `portabilidad.md`: cambiar una cifra en
  el JSON y no en la prosa hace fallar el CI.
- **El análisis sigue siendo estático**: un `ast` recorre `scripts/` y falla si aparece
  cualquier proceso externo que no sea el `subprocess.run(git clone)` del origen.
- `resumen.json` valida contra `resumen.schema.json`.
- Pasan las pruebas unitarias de `tests/`, incluidos los golden files.
- El conversor arranca desde una copia del repositorio en otra ruta, sin instalación.

Para lanzarlo en local antes de abrir un pull request:

```bash
python3 .github/validate_plugin.py .
python3 -m pip install --quiet jsonschema && python3 .github/validar_perfiles.py .
```

Esta comprobación importa más de lo habitual porque el marketplace se sincroniza solo y
no hay versión fija: un manifiesto roto llegaría a quien tenga el plugin instalado en el
mismo `push`.

Si tocas un perfil de `targets/*.json` y regeneras los golden, fija la fecha con
`CSE_FECHA=AAAA-MM-DD python3 tests/generar_golden.py`: sin ella, en cuanto la fecha real
supere el `revisar_tras` de un perfil, los veredictos pasan de `compatible` a `no
verificable` y el CI se pone en rojo sin que nadie haya tocado una línea.

## Limitaciones conocidas

- No convierte comandos, agentes ni MCP: no hay equivalente en el destino.
- El parser de YAML es mínimo (sin PyYAML). Frontmatter muy exótico puede leerse mal;
  revisa el resultado.
- La detección de patrones es por expresión regular: puede haber falsos positivos.
  Trátalos como avisos para revisar, no como veredictos.
- Repositorios privados: necesitas `git` ya autenticado, o descarga el repo a mano y
  pásale la ruta local.
- **El origen tiene techo.** Se aborta el análisis si el árbol pasa de **200 MB** o de
  **20 000 ficheros**, y el `git clone` se cancela a los **300 segundos**. No se sigue
  ningún enlace simbólico al medir. Si necesitas convertir un monorepo, apunta a la
  subcarpeta que contenga las skills.
- **No se pedirán credenciales nunca.** El clon se lanza con `GIT_TERMINAL_PROMPT=0`: un
  repositorio privado falla de inmediato en vez de dejar el proceso colgado esperando una
  contraseña. Autentica `git` antes, o descarga el repo a mano y pásale la ruta.

## Autoría y licencia

Creado por **Pablo Rodríguez López** ([@novanoticia](https://github.com/novanoticia)).

Publicado bajo licencia **MIT** — ver [LICENSE](LICENSE). Puedes usarlo, modificarlo,
integrarlo en otro proyecto y redistribuirlo, incluso comercialmente. La única condición
es **conservar el aviso de copyright y el texto de la licencia** en las copias o partes
sustanciales que distribuyas. Si reutilizas el conversor dentro de otra herramienta,
basta con mantener la cabecera del fichero y acompañarlo del `LICENSE`.

---

*Documentación y código elaborados con asistencia de IA. Requieren revisión humana
antes de usarse en producción.*
