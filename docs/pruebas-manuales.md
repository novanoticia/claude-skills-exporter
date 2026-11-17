# Pruebas manuales en los destinos

Registro de lo que se ha comprobado **a mano** en cada plataforma, con fecha. Es la fuente
que citan los perfiles (`skills/plugin-to-agentskills/scripts/exporter/targets/*.json`)
cuando marcan un modo de instalación como `probada: true`.

Cada entrada separa lo **observado** de lo que **no** demuestra. Una prueba vale para la
fecha, la cuenta y la superficie en que se hizo: la interfaz cambia sin aviso.

---

## ChatGPT web · zip de una skill · 2026-11-17

**Entorno:** `chatgpt.com`, cuenta Plus, navegador en macOS. Zips generados por el
conversor desde `tests/fixtures/skill-minima` y `tests/fixtures/skill-description-larga`.

### Ruta

**Complementos → Habilidades → Añadir → Subir desde tu ordenador.** El menú «Añadir»
ofrece además «Crear con chat» y «Crear con el editor». El diálogo de subida dice:
«Arrastra y suelta un archivo .zip/.skill o SKILL.md» y «Tamaño máximo: 780 MiB por
archivo», y avisa de que las habilidades de terceros conllevan mayores riesgos.

La ruta que documenta la ayuda de OpenAI (*Plugins → Skills → Create → Upload from your
computer*) es la misma con otros nombres en la interfaz en español.

### Observado

| Prueba | Resultado |
|---|---|
| Subir `minima.zip` tal como sale del conversor | ✅ «Habilidad cargada». Aparece en «Instaladas» y en «Creadas por mí» |
| Qué añade ChatGPT al paquete | `agents/openai.yaml` y `assets/icon.svg`, que el zip no traía |
| Invocación explícita: elegir `minima` y escribir «pásame esta fecha a ISO: 17 de noviembre de 2026» | ✅ Respuesta `2026-11-17` |
| Descripción con comillas, en el formato anterior al PR 29 | ❌ Se mostraba con barras literales (`diga \"pásame…\"`) y el editor contaba 183 caracteres en vez de 179. El lector de ChatGPT no decodifica los escapes de las comillas dobles de YAML |
| La misma skill exportada después del PR 29 | ✅ Descripción sin barras; el editor marca **179 / 500** |
| Subir `description-larga.zip`, con una descripción de 528 caracteres | ✅ «Habilidad cargada», con la descripción completa. El límite de 500 caracteres es del editor, no de la subida |
| Nombre mostrado | ChatGPT presenta `description-larga` como «description larga»; el campo *Nombre* conserva el guion |

### Lo que esta prueba no demuestra

- **La activación automática.** En todas las pruebas se eligió la skill a mano. Una
  conversación sin elegirla respondió bien a la misma petición, pero sin indicar que
  usara la skill, y cualquier modelo convierte esa fecha sin ayuda.
- **Los límites de 500 ficheros y 25 MiB por fichero.** Siguen siendo los de la API de
  Skills de OpenAI; la interfaz solo anuncia el tamaño máximo del archivo subido.
- **Qué pasa con una descripción que pase de 500 caracteres al usarla**: se acepta y se
  muestra entera, pero no se ha comprobado cómo afecta a la activación.
- **Otras cuentas o espacios de trabajo.** La ayuda de OpenAI condiciona la función al
  producto, a la cuenta y al espacio de trabajo.

### Sin explicar

A las 11:51, la descripción de `minima` apareció **en inglés** en la lista de
habilidades, cuando a las 11:41 estaba en español. Entre medias se usaron Skill Creator
y Plugin Creator en la app de escritorio. No se sabe si alguna de esas herramientas
reescribió la skill de la cuenta.

---

## App de escritorio de ChatGPT/Codex (macOS) · 2026-11-17

No corresponde a ningún perfil del conversor; se anota porque se confunde fácilmente
con la anterior.

| Prueba | Resultado |
|---|---|
| Complementos → Añadir → «Subir archivo comprimido del complemento», con `minima.zip` o `description-larga.zip` | ❌ «Plugin archive must contain `.codex-plugin/plugin.json`, `.agent-plugin/plugin.json`, `.claude-plugin/plugin.json`, or plugin content such as `skills/*/SKILL.md`, `.mcp.json`, or `.app.json`» |
| El mismo contenido con forma de plugin (`skills/minima/SKILL.md` en la raíz del zip) | ✅ Crea el complemento «minima» (versión 1.0.0, categoría *Other*, 1 habilidad). La descripción se muestra con las comillas bien, también en el formato anterior al PR 29 |
| Invocación explícita (`@minima pásame esta fecha a ISO…`) | ✅ Respuesta `2026-11-17` |
| Habilidades → Añadir | Solo «Crear habilidad» y «Grabar una habilidad»: no hay subida de zip |

La app y la web muestran catálogos distintos: la web, las habilidades de la cuenta; la
app, además, los complementos de los *marketplaces* añadidos en ese equipo. Es una
hipótesis por lo que se ve en pantalla, sin confirmar.
