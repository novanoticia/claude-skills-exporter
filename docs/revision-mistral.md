# Revisión de PR con Mistral

El workflow `Mistral PR Review` (`.github/workflows/mistral-review.yml`) solo
**llama** al revisor compartido
[novanoticia/mistral-review](https://github.com/novanoticia/mistral-review),
que lee el diff y las reglas de `REVIEW.md`, `AGENTS.md` o `CLAUDE.md`, en ese
orden. No ejecuta el conversor ni los fixtures del PR, no aplica parches, no crea
commits y no fusiona cambios. Las reparaciones siguen a cargo de Claude y del
mantenedor.

Desde el 2026-11-15 el código, las pruebas y la documentación detallada del
revisor (citas, segunda solicitud, cortes por `length`, límites de tamaño,
secretos tachados) viven en ese repo; antes había aquí una copia propia en
`.github/scripts/`. Una mejora se hace allí una vez y llega a todos los repos.

## Configuración

En Settings → Secrets and variables → Actions:

1. Añade el secreto `MISTRAL_API_KEY` con la clave de tu cuenta de API.
2. Opcionalmente, añade la variable `MISTRAL_MODEL`; sin ella se usa el modelo
   por defecto del revisor compartido (`zai-glm-5-3-flash`).

Si falta la clave, Actions muestra «revisión omitida»; eso no cuenta como
evaluación. Los PR de forks no reciben el secreto. El check se llama ahora
`mistral-review / mistral-review`.

## Lo propio de este repo

Se excluyen los golden generados de `tests/golden/`, `tests/golden-seguridad/`
y `tests/golden-i18n/` (parámetro `excluded` del workflow). Los fixtures siguen
siendo datos de prueba inertes: el revisor no los ejecuta. Nada del revisor se
distribuye dentro de la skill.

## Contraste de revisiones de otras IAs

El workflow `Mistral Reply to AI Reviews` (`.github/workflows/mistral-reply.yml`)
llama a `reply.yml` del mismo revisor compartido. Cuando otra IA (Codex, Claude,
Copilot, CodeRabbit o Gemini) deja hallazgos en un PR, Mistral contrasta cada uno
leyendo el código y responde con un dictamen: de acuerdo, no se sostiene, ya
corregido o pendiente, con citas literales. Solo comenta: no aplica parches.
Además del código, envía a Mistral el texto de esos hallazgos.

Usa el mismo secreto y las mismas variables que la revisión. La variable
opcional `MISTRAL_REPLY_MODEL` elige otro modelo de Mistral solo para el
contraste. Aplica las mismas exclusiones que la revisión. También se puede lanzar a mano: **Actions → Mistral Reply to
AI Reviews → Run workflow**, con el número del PR y el id del comentario.

Los dos workflows están fijados en la misma versión del revisor: `@` de `uses:`
y `ref:` deben coincidir en ambos archivos. El dictamen es otra opinión
automatizada; compruébalo antes de actuar.

## Límites

Es una segunda opinión barata, no un detector fiable. Una cita válida no
demuestra un defecto y «sin hallazgos» no demuestra que el código sea correcto.
Contrasta los avisos con los tests y el código antes de pedir a Claude que
repare nada.
