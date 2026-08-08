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

**El `.zip` y la carpeta no son intercambiables.** Llevan los mismos ficheros, pero la
descripción del frontmatter se ajusta al presupuesto de cada destino. Descomprimir el zip
**no** produce la carpeta de Mistral: su descripción sería demasiado larga.

| Destino | Qué subir | Presupuesto de `description` | Dónde |
|---|---|---|---|
| **Perplexity Computer** | el `.zip` **tal cual** — una skill por zip, con la carpeta de la skill en la raíz | ≤ 850 bytes | `perplexity.ai/computer/skills` → *Create skill* → *Upload a skill* |
| **Mistral Vibe Work** | la **carpeta** `<skill>/` | ≤ 490 bytes | `chat.mistral.ai/work` → *Context* → *Skills* → *New Skill* |

Si el usuario sólo tiene el `.zip` y quiere subirlo a Mistral, dile que vuelva a exportar:
descomprimirlo le dará una descripción de hasta 850 bytes.

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

El conversor tiene tres modos. Elige según lo que el usuario pida — no asumas que
quiere paquetes si sólo pregunta por portabilidad.

| Comando | Qué hace | ¿Escribe ficheros? |
|---|---|---|
| `convert.py inspect <origen>` | Qué contiene la skill y qué exige, sin elegir destino | No |
| `convert.py audit <origen>` | Matriz de compatibilidad por destino | No |
| `convert.py export <origen>` | Audita y empaqueta | Sí |

`convert.py <origen>` sin subcomando sigue exportando, como siempre.

1. **Pide el origen** si no lo dio: URL del repo o ruta local. Si es un repo privado,
   necesitará `git` autenticado o descargarlo a mano.
2. **Decide el modo:**
   - Si sólo quiere saber qué trae la skill (frontmatter, tamaño, patrones detectados),
     sin pensar todavía en un destino: `inspect`.
   - Si pregunta **"¿es portable?"**, **"¿puedo subir esto a X?"** o quiere la matriz
     de compatibilidad sin generar nada en disco: `audit`. No escribe ficheros.
   - Si quiere los paquetes para subir: `export` (o el modo por defecto, sin
     subcomando).
3. **Ejecuta el conversor** con la ruta resuelta en el paso 0, por ejemplo para exportar:

   ```bash
   python3 "$CONV" <url-o-ruta> --out ./dist-agentskills
   ```

   Deja en `dist-agentskills/` un `<skill>.zip` (Perplexity, claude.ai, ChatGPT) y una
   carpeta `<skill>/` (Mistral) por cada skill. Añade `--only nombre1 nombre2` para
   exportar sólo algunas. `--zip-only` borra las carpetas y **con ellas la variante de
   Mistral**: úsalo sólo si el usuario dice que va a Perplexity y a ningún otro sitio.
   `--target` (en `audit` y `export`) restringe a qué destinos se audita o empaqueta.

4. **Lee el informe** (`INFORME-PORTABILIDAD.md` en `export`, la salida por terminal en
   `audit`) y resume al usuario: la matriz por destino, cuáles tienen riesgo alto y por
   qué. No te limites a decir "listo".
5. **Entrega los ficheros** (si los hay) y di qué sube dónde.

## Qué hace el conversor

- Encuentra todos los `SKILL.md` del repo (sin descender dentro de una skill ya
  detectada, para no confundir `references/` con skills nuevas).
- Normaliza el nombre a minúsculas-con-guiones y lo alinea con la carpeta.
- Retira del frontmatter las claves que sólo existen en Claude (`allowed-tools`,
  `model`, `argument-hint`…) y deja el par mínimo `name` + `description`.
- **Reordena la descripción: primero CUÁNDO cargar la skill, después qué hace.** Trocea
  en frases (sin romper dentro de comillas ni paréntesis), detecta las que marcan
  activación —`Cárgala cuando`, `Actívalo cuando`, `cuando el usuario`, `Use when`…— y
  las pone delante. Va antes del recorte a propósito: si hay que cortar, se pierde lo
  prescindible. Con `--keep-description-order` se desactiva.
- Reescribe `${CLAUDE_PLUGIN_ROOT}/...` como rutas relativas a la skill.
- Audita el cuerpo y **escribe los avisos dentro del propio `SKILL.md`**, para que el
  agente de destino sepa que hay instrucciones que no podrá cumplir y lo diga en vez
  de inventarse el resultado.
- **Compacta la descripción al presupuesto de cada destino**, en bytes UTF-8: 490 para la
  carpeta de Mistral, 850 para el zip de Perplexity. Poda primero los ejemplos
  entrecomillados —deja como mucho cuatro— y después las frases que sólo cuentan qué hace
  la skill, hasta que cabe. El resultado es siempre un párrafo: primero cuándo activarse,
  después para qué sirve. Nunca corta a mitad de frase.
- Empaqueta cada skill en un `<skill>.zip` (con la carpeta de la skill en su raíz) y deja
  al lado la carpeta con la variante corta, más el informe.

## Gotchas

- **El veredicto es por destino, no por skill.** El informe trae una matriz: la
  misma skill puede ser `compatible` en Perplexity y `no compatible` en Mistral.
  Si el usuario pregunta «¿es portable?», la respuesta correcta empieza por
  «¿a dónde?».
- **`no verificable` no es `compatible`.** Significa que el perfil del destino no
  declara esa capacidad, o que su evidencia ha caducado. Dilo tal cual: no lo
  redondees a favor.
- **Nunca un zip con todas las skills dentro.** Perplexity espera la carpeta de *una*
  skill en la raíz del zip. Un zip global falla o sólo reconoce una. El conversor ya
  genera uno por skill; no los agrupes tú después.
- **Mistral quiere la carpeta, no el zip — y no vale descomprimirlo.** Las dos variantes
  llevan los mismos ficheros pero distinta `description`: 490 bytes en la carpeta, 850 en
  el zip. Descomprimir el zip da la descripción larga. Es la trampa más fácil de esta
  herramienta, precisamente porque antes sí eran idénticos.
- **Mistral valida que el markdown *sea* un `SKILL.md`, no que hable de uno.** Si le
  subes un documento con los campos troceados para copiar y pegar, responde *"sube un
  archivo Markdown válido de skill"*. Nunca fabriques ese intermediario: lo que quiere
  es el `SKILL.md` real, con su frontmatter, dentro de su carpeta.
- **Mistral conserva el árbol completo.** Comprobado: mantiene `references/` y
  `scripts/` como carpetas reales y admite `.py` y `.yaml`, no sólo markdown. Así que
  sube la carpeta entera; no hay que extraer el `SKILL.md` ni aplanar nada.
- **La descripción es el 80% del resultado, y el orden importa tanto como el contenido.**
  El conversor ya adelanta las frases de activación, pero **no puede inventar las que no
  existen**. Si una descripción sólo dice "esta skill hace X", sale el aviso
  `description-sin-activacion` en riesgo alto: ahí hay que reescribir a mano, empezando
  por los disparadores con las palabras que usaría el usuario. Ofrécete a hacerlo.
- **El límite de 1024 de la descripción se mide en bytes, no en caracteres.** Comprobado:
  Perplexity rechaza el zip entero con *"exceeds maximum length of 1024 characters"* ante
  una descripción de 1063 caracteres pero 1085 bytes — en español las tildes cuentan
  doble. El conversor recorta a 980 y corta por frase, pero eso conserva el principio
  (*qué hace*) y tira el final (*cuándo activarla*). Si ves `description-larga`, ofrécete
  a reescribirla tú: el recorte sólo garantiza que el fichero sea válido, no que sirva.
  Mistral, en cambio, acepta la subida y deja abreviarla a mano — así que probar sólo
  allí oculta el problema.
- **Riesgo alto ≠ inservible.** Una skill que llama a herramientas MCP puede seguir
  siendo útil como procedimiento escrito. Lo grave es que el agente finja haberlas
  usado. Por eso el aviso incrustado dice explícitamente que no simule resultados.
- **Los `scripts/` viajan pero no su entorno.** Perplexity Computer puede ejecutarlos en
  su sandbox; **Mistral no tiene Python** (comprobado), así que los `.py` llegan pero no
  se ejecutan. Si la lógica de la skill vive en un script, avisa al usuario: sólo
  funcionará allí si el `SKILL.md` trae un procedimiento manual equivalente.
- **Perplexity Computer corta cada llamada a los ~90 s.** Comprobado: ejecuta los
  `scripts/` e incluso alcanza aplicaciones del Mac del usuario vía AppleScript, pero un
  lote largo se queda a medias. En una ejecución real eso movió 64 correos que no tocaba y aplicó mal un
  filtro de fecha. Si la skill modifica cosas en bloque, avísalo: necesita trozos
  pequeños y verificación releyendo el estado después de cada uno. Avisos
  `applescript` (medio) y `lote-destructivo` (alto).
- **El estado en disco tampoco viaja.** Reproducido en dos ejecuciones: en Mistral, el
  anexado a un fichero reporta éxito y luego el fichero no está. Lo grave no es la
  pérdida, sino que el agente **reconstruye el registro de memoria** y sigue como si nada
  — un historial inventado con aspecto de real. Si la skill lleva log, caché o registro
  para deshacer, dilo al exportarla. El conversor lo marca como `estado-persistente`.
- **La tilde no apunta al home del usuario allí.** La variable de entorno del home vale
  `/`, así que una ruta que empiece por tilde-barra acaba escribiendo en la raíz con doble
  barra. El conversor lo marca como `home-tilde`; en el destino hay que sustituirla por
  una ruta relativa a la skill.
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
