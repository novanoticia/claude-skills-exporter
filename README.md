# Claude Skills Exporter

Coge un repositorio con un plugin (o unas skills) de Claude, extrae las skills,
**audita qué se romperá fuera de Claude** y las empaqueta para instalarlas en
**ChatGPT**, **Perplexity Computer** y **Mistral Vibe Work**.

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

Esta herramienta no arregla eso: lo **hace visible**. Cada skill exportada lleva
incrustado un aviso que le dice al agente de destino qué instrucciones no va a poder
cumplir, para que lo declare en vez de simular el resultado.

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

Sólo necesita Python 3.8+ y `git`. Sin dependencias externas.

| Opción | Qué hace |
|---|---|
| `--out DIR` | Directorio de salida (por defecto `./dist-agentskills`) |
| `--only a b c` | Exporta sólo esas skills |
| `--zip-only` | Deja sólo los `.zip` — se pierde la variante para Mistral |
| `--keep-description-order` | No reordena la descripción (por defecto, la activación va primero) |

## Qué genera

Dos artefactos por skill, con los mismos ficheros pero **distinta descripción**: cada
destino tiene su presupuesto y la `description` se compacta para caber en él.

```
dist-agentskills/
├── mi-skill.zip               → ChatGPT, claude.ai y Perplexity (description ≤ 850 bytes)
├── mi-skill/                  → Mistral      (description ≤ 490 bytes)
│   ├── SKILL.md
│   └── references/ scripts/ ...
├── otra-skill.zip
├── otra-skill/
├── INFORME-PORTABILIDAD.md    qué se adaptó y qué se romperá
└── resumen.json               lo mismo, en formato máquina
```

## Dónde se sube cada cosa

| Destino | Qué subir | `description` | Ruta |
|---|---|---|---|
| **ChatGPT** | `mi-skill.zip` — **tal cual**, sin tocar | ≤ 1024 caracteres | Con `Work` activado, en **Complementos** (ver la nota) |
| **Perplexity Computer** | `mi-skill.zip` — **tal cual**, sin tocar | ≤ 850 B | `perplexity.ai/computer/skills` → *Create skill* → *Upload a skill* |
| **Mistral Vibe Work** | `mi-skill/` — la **carpeta** | ≤ 490 B | `chat.mistral.ai/work` → *Context* → *Skills* → *New Skill* |
| **Claude Code** | `mi-skill/` | — | Copiar a `~/.claude/skills/` |
| **claude.ai** | `mi-skill.zip` | ≤ 1024 caracteres | *Ajustes* → *Capacidades* → *Skills* → *Subir skill* |

> **Para ChatGPT sirve el mismo `.zip` de Perplexity**, sin volver a exportar: su tope
> es de 1024 caracteres y el zip trae la descripción de 850 bytes, así que cabe de
> sobra. Exige además que el zip contenga **una única carpeta en la raíz** y **un solo
> `SKILL.md`** — que es exactamente lo que genera esta herramienta. Sus otros límites
> (50 MB de zip, 500 ficheros, 25 MB por fichero descomprimido) quedan muy lejos para
> una skill normal. Está en el **plan gratuito**, con límites de uso.
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

Cada hallazgo se clasifica en 🔴 alto (no funcionará), 🟡 medio (funcionará degradado)
o 🔵 bajo (cosmético).

## Contribuir

Los issues y pull requests son bienvenidos, sobre todo los que aporten comportamiento
observado en un destino concreto: qué acepta, qué rechaza y con qué mensaje de error.
Buena parte de lo que audita esta herramienta procede de fallos reales al subir skills,
no de la documentación de las plataformas.

Cada `push` y cada pull request sobre `main` ejecuta
[`.github/workflows/validar.yml`](.github/workflows/validar.yml), que comprueba lo que
rompe la carga del plugin en silencio:

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

Para lanzarlo en local antes de abrir un pull request:

```bash
python3 .github/validate_plugin.py .
```

Esta comprobación importa más de lo habitual porque el marketplace se sincroniza solo y
no hay versión fija: un manifiesto roto llegaría a quien tenga el plugin instalado en el
mismo `push`.

## Limitaciones conocidas

- No convierte comandos, agentes ni MCP: no hay equivalente en el destino.
- El parser de YAML es mínimo (sin PyYAML). Frontmatter muy exótico puede leerse mal;
  revisa el resultado.
- La detección de patrones es por expresión regular: puede haber falsos positivos.
  Trátalos como avisos para revisar, no como veredictos.
- Repositorios privados: necesitas `git` ya autenticado, o descarga el repo a mano y
  pásale la ruta local.

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
