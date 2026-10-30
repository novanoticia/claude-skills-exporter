# Revisión de PR con Mistral

El workflow `Mistral PR Review` analiza el diff y las reglas de `REVIEW.md`,
`AGENTS.md` o `CLAUDE.md`, en ese orden. No ejecuta el conversor ni los fixtures
del PR, no aplica parches, no crea commits y no fusiona cambios. Las reparaciones
siguen a cargo de Claude y del mantenedor.

## Configuración

En Settings → Secrets and variables → Actions:

1. Añade el secreto `MISTRAL_API_KEY` con la clave de tu cuenta de API.
2. Opcionalmente, añade la variable `MISTRAL_MODEL`; por defecto se utiliza
   `mistral-large-latest`.

La instalación no copia ni permite leer claves de otros repositorios. Si falta
la clave, Actions muestra «revisión omitida»; eso no cuenta como evaluación.
Los PR de forks no reciben el secreto.

El script se ejecuta desde la rama predeterminada, con permiso de lectura de
contenido y de publicación de comentarios. Solo lee objetos Git del PR. Por ello
la función queda activa después de fusionar esta instalación: durante su propio
PR el paso se omite si el script aún no existe en la rama predeterminada.

## Informes y límites

Se ejecuta al abrir, actualizar, editar, reabrir o marcar listo un PR. Cada
resultado crea un comentario nuevo con el SHA, el modelo y un enlace al intento
de Actions. El perfil del proveedor es [Mistral AI](https://github.com/mistralai).
Los resultados anteriores no se sobrescriben; un push cancela la ejecución
anterior en curso. Una ejecución cancelada antes de publicar no deja informe.

El modelo debe aportar escenarios comprobados por lectura o pendientes, además
de sus hallazgos. Las citas se contrastan literalmente con el diff enviado.
Las rutas de las comprobaciones admiten renombrados puros, permisos y binarios.
Una respuesta inválida o un error de API hace fallar el check y deja un informe;
no equivale a haber encontrado un defecto del programa. El resumen de Actions
se escribe antes de publicar el comentario para conservarlo si falla GitHub.

El diff se limita a 150.000 caracteres, la guía a 20.000 y el contexto Python a
10.000 por archivo y 40.000 en total. Se excluyen los golden generados de
`tests/golden/`, `tests/golden-seguridad/` y `tests/golden-i18n/`. Los fixtures
siguen siendo datos de prueba inertes: no se ejecutan por el revisor.

Los textos visibles del revisor de CI están en
`.github/scripts/mistral_review_es.json`, separados de los catálogos del programa
exportado. Los scripts de revisión no se distribuyen dentro de la skill.

Las pruebas locales simulan Mistral y GitHub. Validan formato, contexto,
transporte y conservación del historial; no la calidad del juicio del modelo.
Una cita válida no demuestra un defecto y «sin hallazgos» no demuestra que el
código sea correcto. Contrasta los avisos con los tests y el código antes de
pedir a Claude que repare nada.
