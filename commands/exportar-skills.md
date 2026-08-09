---
description: Audita la portabilidad de las skills de un repositorio de Claude hacia cinco destinos (ChatGPT, claude.ai, Claude Code, Mistral Vibe Work y Perplexity Computer) y las empaqueta
argument-hint: <url-del-repo-o-ruta-local>
---

Exporta las skills del repositorio `$1` al estándar abierto Agent Skills.

Sigue la skill `plugin-to-agentskills` de este plugin, **empezando por su «Paso 0:
localiza el conversor»**. No asumas que `${CLAUDE_PLUGIN_ROOT}` resuelve en este
entorno: en shells aislados no lo hace, y hay que caer al clon del repositorio.

Después:

1. Ejecuta el conversor: `python3 "$CONV" $1 --out ./dist-agentskills`
2. Lee `dist-agentskills/INFORME-PORTABILIDAD.md`.
3. Resume, leyendo la matriz de compatibilidad: cuántas skills salieron y, para cada una,
   en qué destinos queda `compatible`, en cuáles sólo `compatible con adaptación`, en
   cuáles `degradado` o `no verificable`, y en cuáles `no compatible`; y qué habría que
   reescribir a mano antes de subirlas.
4. Recuerda al usuario que los `commands/`, `agents/`, `hooks/` y servidores MCP del
   plugin original **no** se exportan, y que los enlaces simbólicos que haya dentro de una
   skill se omiten al empaquetar —con aviso en el informe—: copiar su contenido metería en
   el paquete ficheros de fuera de la skill.
5. Dile qué sube dónde: el `<skill>.zip` **tal cual** a los destinos que instalan por zip
   —Perplexity Computer, claude.ai y ChatGPT—; la **carpeta** `<skill>/` a los que instalan
   por directorio —Mistral Vibe Work y Claude Code—. Advierte de que **no son
   intercambiables**: llevan los mismos ficheros, pero la descripción se recorta al
   presupuesto más estrecho de cada modo de instalación (850 bytes en el zip, 490 en la
   carpeta), así que descomprimir el zip no sirve para Mistral.
6. Si el usuario sólo quiere saber dónde puede subir la skill, sin paquetes, usa el
   subcomando `audit`: `python3 "$CONV" audit $1` —opcionalmente con `--target <destino> …`—.
   Imprime la matriz por pantalla y no escribe ningún fichero. Hay también un `inspect`,
   que dice qué contiene y qué exige cada skill sin elegir destino.
7. Antes de entregar los ficheros, lee la sección «## Seguridad del paquete» al principio
   de `dist-agentskills/INFORME-PORTABILIDAD.md`: nivel de riesgo, recomendación de
   instalación y, si los hay, los hallazgos con su `fichero:línea`. Menciónalo aunque el
   usuario sólo haya preguntado por portabilidad —es la pregunta que no sabe que necesita
   hacer—. Si el código de salida fue `3`, dilo explícitamente: alguna skill no se exportó
   por un hallazgo grave dentro de lo que se iba a empaquetar, y `--anular-revision-
   seguridad` no es el primer recurso — lee antes el hallazgo, el fichero y la línea.
