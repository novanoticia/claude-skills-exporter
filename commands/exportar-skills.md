---
description: Exporta las skills de un repositorio de Claude a paquetes para Perplexity y Mistral
argument-hint: <url-del-repo-o-ruta-local>
---

Exporta las skills del repositorio `$1` al estándar abierto Agent Skills.

Sigue la skill `plugin-to-agentskills` de este plugin, **empezando por su «Paso 0:
localiza el conversor»**. No asumas que `${CLAUDE_PLUGIN_ROOT}` resuelve en este
entorno: en shells aislados no lo hace, y hay que caer al clon del repositorio.

Después:

1. Ejecuta el conversor: `python3 "$CONV" $1 --out ./dist-agentskills`
2. Lee `dist-agentskills/INFORME-PORTABILIDAD.md`.
3. Resume: cuántas skills salieron, cuáles tienen riesgo alto y qué habría que
   reescribir a mano antes de subirlas.
4. Recuerda al usuario que los `commands/`, `agents/`, `hooks/` y servidores MCP del
   plugin original **no** se exportan.
5. Dile qué sube dónde: el `<skill>.zip` **tal cual** a Perplexity Computer; para
   Mistral Vibe Work, ese mismo zip **descomprimido** — la carpeta `<skill>/` que el
   conversor ya deja al lado. No son dos formatos: es el mismo, abierto o cerrado.
