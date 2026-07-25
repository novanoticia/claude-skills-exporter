# Claude Skills Exporter

Coge un repositorio con un plugin (o unas skills) de Claude, extrae las skills,
**audita qué se romperá fuera de Claude** y las empaqueta para instalarlas en
**Perplexity Computer** y **Mistral Vibe Work**.

👉 **Si no manejas GitHub, empieza por la [guía paso a paso](docs/guia.html)** —
ábrela con doble clic en tu navegador.

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

`pablo-skills-tools` es el nombre del **marketplace** (campo `name` de
`.claude-plugin/marketplace.json`), no el usuario de GitHub. El repositorio debe ser
público para que `marketplace add` pueda descargarlo sin autenticación.

Después:

```
/claude-skills-exporter:exportar-skills https://github.com/usuario/repo
```

O pídeselo en lenguaje natural: *"exporta las skills de este repo para Perplexity"*.

### Actualizar

Tres pasos. El primero no es opcional:

```bash
# 1. Subir la versión en .claude-plugin/plugin.json y marketplace.json
#    "version": "1.0.0"  →  "1.0.1"

# 2. Publicar
git add -A && git commit -m "v1.0.1: …" && git push
```

```
# 3. Refrescar en Claude Code
/plugin marketplace update pablo-skills-tools
/plugin update claude-skills-exporter
/reload-plugins
```

Claude Code detecta actualizaciones comparando el campo `version`. Si no lo cambias,
sirve la copia cacheada y `/plugin update` responde *"already at the latest version"*
por muchos commits que hayas subido.

Si prefieres no tocar el número en cada cambio, **borra** el campo `version` de ambos
manifiestos: entonces se usa el identificador del commit y cada `git push` cuenta como
versión nueva. Cómodo mientras desarrollas; mala idea si alguien más depende del plugin.

## Uso

### Sin instalar nada

```bash
python3 skills/plugin-to-agentskills/scripts/convert.py https://github.com/usuario/repo \
    --out ./dist-agentskills --per-skill
```

Sólo necesita Python 3.8+ y `git`. Sin dependencias externas.

| Opción | Qué hace |
|---|---|
| `--out DIR` | Directorio de salida (por defecto `./dist-agentskills`) |
| `--per-skill` | Genera además un `.zip` por skill — **lo que Perplexity espera de verdad** |
| `--only a b c` | Exporta sólo esas skills |

## Qué genera

```
dist-agentskills/
├── <repo>-agentskills.zip     zip único con todas las skills
├── skills/                    las mismas skills sin comprimir
├── zips/                      un zip por skill (con --per-skill)
├── mistral/                   texto listo para pegar en el formulario de Mistral
├── INFORME-PORTABILIDAD.md    qué se adaptó y qué se romperá
└── resumen.json               lo mismo, en formato máquina
```

## Dónde se sube cada cosa

| Destino | Fichero | Ruta |
|---|---|---|
| **Perplexity Computer** | `zips/<skill>.zip` | `perplexity.ai/computer/skills` → *Create skill* → *Upload a skill* |
| **Mistral Vibe Work** | `mistral/<skill>.md` (copiar y pegar) | `chat.mistral.ai/work` → *Context* → *Skills* → *New Skill* |
| **Claude Code** | `skills/<skill>/` | Copiar a `~/.claude/skills/` |

> **Nota sobre el zip único:** Perplexity espera la carpeta de *una* skill en la raíz
> del zip. El zip global sirve como copia de seguridad y para importar a mano, pero si
> la subida falla, usa los de `zips/`.

## Qué audita

- Frontmatter ausente, incompleto o con claves que sólo existen en Claude.
- Descripciones que describen *qué hace* la skill en vez de *cuándo* activarla — la
  causa nº 1 de que una skill importada no se cargue nunca.
- Rutas `${CLAUDE_PLUGIN_ROOT}` (las reescribe).
- Llamadas a herramientas MCP, subagentes (`Task tool`), comandos con namespace,
  hooks y herramientas propias de Claude.
- Tamaño del cuerpo frente al presupuesto de contexto recomendado.

Cada hallazgo se clasifica en 🔴 alto (no funcionará), 🟡 medio (funcionará degradado)
o 🔵 bajo (cosmético).

## Limitaciones conocidas

- No convierte comandos, agentes ni MCP: no hay equivalente en el destino.
- El parser de YAML es mínimo (sin PyYAML). Frontmatter muy exótico puede leerse mal;
  revisa el resultado.
- La detección de patrones es por expresión regular: puede haber falsos positivos.
  Trátalos como avisos para revisar, no como veredictos.
- Repositorios privados: necesitas `git` ya autenticado, o descarga el repo a mano y
  pásale la ruta local.

## Licencia

MIT. Ver [LICENSE](LICENSE).

---

*Documentación y código elaborados con asistencia de IA. Requieren revisión humana
antes de usarse en producción.*
