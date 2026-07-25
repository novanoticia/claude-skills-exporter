---
name: plugin-to-agentskills
description: Cárgala cuando el usuario dé una URL o ruta de un repositorio con un plugin o skills de Claude y quiera exportarlas, convertirlas o empaquetarlas para otra plataforma — Perplexity Computer, Mistral Vibe Work, ChatGPT u otro agente compatible con Agent Skills. Se activa con "exporta este plugin", "conviértelo para Perplexity", "hazme el zip para Mistral", "¿es portable esta skill?", "/exportar-skills".
license: MIT
---

# Exportar skills de un plugin de Claude al estándar Agent Skills

Convierte las skills de un repositorio de Claude en paquetes instalables en otras
plataformas, auditando de paso qué se romperá al salir de Claude.

## Lo que hay que entender antes de tocar nada

Un **plugin de Claude no es portable como unidad**. Empaqueta cinco cosas y sólo
una viaja:

| Componente | ¿Portable? |
|---|---|
| `skills/` (carpeta + `SKILL.md`) | **Sí** — es el estándar abierto Agent Skills |
| `commands/` (slash commands) | No — no hay equivalente directo |
| `agents/` (subagentes) | No |
| `mcpServers` | No — el destino no tendrá esos servidores conectados |
| `hooks/` | No |

Si el usuario dice "convierte mi plugin", **dilo explícitamente**: se exportan las
skills, el resto se queda. No lo dejes implícito.

Y cada destino instala distinto:

- **Perplexity Computer** — `perplexity.ai/computer/skills` → *Create skill* → *Upload a
  skill* → sube un `.zip` o un `.md`. Espera **una skill por zip**, con la carpeta de la
  skill en la raíz.
- **Mistral Vibe Work** — `chat.mistral.ai/work` → *Context* → *Skills* → *New Skill*.
  Es un **formulario**: Título, Descripción y el cuerpo del `SKILL.md` pegado, más
  ficheros adjuntos opcionales. No hay instalador de zip equivalente.

Por eso la salida trae las dos formas.

## Paso 0: localiza el conversor antes de nada

El shell no siempre alcanza el directorio del plugin. En Claude Code sí; en Cowork y
otros entornos con shell aislado, **no** — `${CLAUDE_PLUGIN_ROOT}` no resuelve allí.
No des por hecho el primer caso: comprueba y cae al segundo.

```bash
CONV=""
# 1. Ruta del plugin (Claude Code)
if [ -n "$CLAUDE_PLUGIN_ROOT" ] && \
   [ -f "$CLAUDE_PLUGIN_ROOT/skills/plugin-to-agentskills/scripts/convert.py" ]; then
  CONV="$CLAUDE_PLUGIN_ROOT/skills/plugin-to-agentskills/scripts/convert.py"
fi
# 2. Si no, clona el propio repositorio del plugin en un temporal
if [ -z "$CONV" ]; then
  [ -d /tmp/cse ] || git clone --depth 1 \
    https://github.com/novanoticia/claude-skills-exporter /tmp/cse
  CONV=/tmp/cse/skills/plugin-to-agentskills/scripts/convert.py
fi
python3 "$CONV" --help    # verifica antes de seguir
```

Recuerda que cada llamada al shell puede ser independiente: si `$CONV` se pierde entre
llamadas, vuelve a resolverlo o usa la ruta literal que obtuviste.

El segundo camino no es un apaño. La herramienta necesita `git` de todas formas para
clonar el repositorio que va a convertir, así que si `git` falta, el trabajo no se
puede hacer por ninguna vía.

## Flujo

1. **Pide el origen** si no lo dio: URL del repo o ruta local. Si es un repo privado,
   necesitará `git` autenticado o descargarlo a mano.
2. **Ejecuta el conversor** con la ruta resuelta en el paso 0:

   ```bash
   python3 "$CONV" <url-o-ruta> --out ./dist-agentskills
   ```

   Añade `--per-skill` para generar además un zip por skill (lo que Perplexity espera
   de verdad). Añade `--only nombre1 nombre2` para exportar sólo algunas.

3. **Lee `INFORME-PORTABILIDAD.md`** y resume al usuario: cuántas skills salieron,
   cuáles tienen riesgo alto y por qué. No te limites a decir "listo".
4. **Entrega los ficheros** y di qué sube dónde.

## Qué hace el conversor

- Encuentra todos los `SKILL.md` del repo (sin descender dentro de una skill ya
  detectada, para no confundir `references/` con skills nuevas).
- Normaliza el nombre a minúsculas-con-guiones y lo alinea con la carpeta.
- Retira del frontmatter las claves que sólo existen en Claude (`allowed-tools`,
  `model`, `argument-hint`…) y deja el par mínimo `name` + `description`.
- Reescribe `${CLAUDE_PLUGIN_ROOT}/...` como rutas relativas a la skill.
- Audita el cuerpo y **escribe los avisos dentro del propio `SKILL.md`**, para que el
  agente de destino sepa que hay instrucciones que no podrá cumplir y lo diga en vez
  de inventarse el resultado.
- Empaqueta: zip único, carpeta `skills/` sin comprimir, `mistral/` con el texto listo
  para pegar, e informe.

## Gotchas

- **El zip único puede no instalarse en Perplexity.** Perplexity espera la carpeta de
  *una* skill en la raíz del zip. Si el usuario pidió un zip global, dáselo, pero avisa
  y ofrécele `--per-skill`. Si falla la subida, esa es la causa.
- **La descripción es el 80% del resultado.** Si una skill trae una descripción del tipo
  "esta skill hace X", el destino casi nunca la cargará. La descripción debe decir
  *cuándo* activarse. Ofrécete a reescribir las peores; el informe las marca como
  `description-densa` o `sin-description`.
- **Riesgo alto ≠ inservible.** Una skill que llama a herramientas MCP puede seguir
  siendo útil como procedimiento escrito. Lo grave es que el agente finja haberlas
  usado. Por eso el aviso incrustado dice explícitamente que no simule resultados.
- **Los `scripts/` viajan pero no su entorno.** Perplexity Computer puede ejecutarlos en
  su sandbox; Mistral no lo garantiza. Revisa las dependencias declaradas antes de
  prometer que funcionará.
- **Sin `skills/` no hay nada que exportar.** Si el repo es un plugin de sólo comandos
  o sólo MCP, el conversor aborta. Es el resultado correcto: díselo al usuario en vez
  de fabricar un zip vacío.
- **No inventes el paso de subida.** Si el usuario pregunta por una plataforma que no
  está en `references/portabilidad.md`, búscalo o admite que no lo sabes.
- **`python3 convert.py` a secas no funciona** salvo que estés dentro de la carpeta
  `scripts/`. Usa siempre la ruta resuelta en el paso 0.

## Referencias

- `references/portabilidad.md` — tabla completa de incompatibilidades y cómo reescribir
  cada patrón a mano.
