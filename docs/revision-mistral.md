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

## Límites

Es una segunda opinión barata, no un detector fiable. Una cita válida no
demuestra un defecto y «sin hallazgos» no demuestra que el código sea correcto.
Contrasta los avisos con los tests y el código antes de pedir a Claude que
repare nada.
