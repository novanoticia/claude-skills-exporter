---
description: Exporta las skills de un repositorio de Claude a paquetes para Perplexity y Mistral
argument-hint: <url-del-repo-o-ruta-local>
---

Exporta las skills del repositorio `$1` al estándar abierto Agent Skills.

Sigue la skill `plugin-to-agentskills` de este plugin. En concreto:

1. Ejecuta `python3 ${CLAUDE_PLUGIN_ROOT}/skills/plugin-to-agentskills/scripts/convert.py $1 --out ./dist-agentskills --per-skill`
2. Lee `dist-agentskills/INFORME-PORTABILIDAD.md`.
3. Resume: cuántas skills salieron, cuáles tienen riesgo alto y qué habría que
   reescribir a mano antes de subirlas.
4. Recuerda al usuario que los `commands/`, `agents/`, `hooks/` y servidores MCP del
   plugin original **no** se exportan, y dile qué fichero sube a cada plataforma.
