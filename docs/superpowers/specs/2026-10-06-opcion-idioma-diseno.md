# Opción de idioma (`--lang`): diseño

Fecha: 2026-10-06 · Estado: pendiente de revisión

## 1. Objetivo

Que quien ejecute el plugin pueda recibir **toda la información en su idioma**: el
informe, el resumen de consola, los hallazgos de seguridad, los mensajes de error y la
conversación de Claude. Idiomas iniciales: **español (por defecto), inglés y francés**.
Añadir un idioma nuevo debe costar **un solo fichero**.

### Criterios de éxito

1. `convert.py <subcomando> ... --lang en` produce informe, consola y errores en inglés; con
   `fr`, en francés; sin el flag, **byte a byte idéntico a hoy** (los golden en español no
   cambian).
2. Añadir `de.json` a `exporter/i18n/` hace que `--lang de` funcione sin tocar código.
3. Un validador en CI falla si algún catálogo difiere del español en claves o en marcadores.
4. Claude responde al usuario en el idioma pedido cuando se usa la skill o `/exportar-skills`.

### Fuera de alcance

- Traducir `README.md`, `docs/guia.html` y los documentos de `docs/superpowers/`.
- Traducir las instrucciones que lee Claude (`SKILL.md`, comando): siguen en español.
- Detección automática del idioma del sistema operativo.

## 2. Qué se traduce y qué no

| Se traduce | No se traduce (contrato) |
|---|---|
| Cuerpo y títulos de `INFORME-PORTABILIDAD.md` | Nombres de artefactos: `INFORME-PORTABILIDAD.md`, `resumen.json`, `<skill>.zip`, `<skill>/` |
| Resumen impreso en consola | Vocabularios cerrados (familia, dimensión, severidad, confianza, ámbito, nivel) |
| `titulo`, `detalle` y `mitigacion` de cada regla y de los hallazgos estructurales | Claves de `resumen.json` e ids de regla (`SEC-…`) |
| Textos de recomendación del veredicto | Códigos de salida |
| Mensajes de error y avisos | Nombres de destino (`chatgpt`, `claude-ai`…) |
| Etiquetas de estado de compatibilidad | Contenido de las skills exportadas |

Regla práctica: **si una máquina lo lee, no se traduce; si lo lee una persona, sí.**

Una consecuencia a vigilar: hoy una prueba busca la subcadena literal
`**Nivel de riesgo:** alto` (spec de seguridad §8). Con `--lang en` el informe diría
`**Risk level:** high`. Las pruebas de ese tipo se ejecutan por idioma, y la cadena
literal se mantiene sólo para `es`.

## 3. Arquitectura

```
exporter/
  i18n/
    __init__.py     t(), idioma_activo(), idiomas_disponibles(), fijar_idioma()
    es.json         catálogo de referencia (fuente de verdad de las claves)
    en.json
    fr.json
```

### 3.1 Catálogo

Un JSON plano: `clave -> plantilla`. Las plantillas usan `str.format` con campos con nombre.

```json
{
  "_meta": {"idioma": "es", "nombre": "Español"},
  "informe.seguridad.titulo": "Seguridad del paquete",
  "informe.seguridad.nivel": "**Nivel de riesgo:** {nivel}",
  "regla.SEC-EXEC-REMOTO-001.titulo": "Descarga contenido remoto y lo ejecuta"
}
```

- `_meta.nombre` es el nombre del idioma en su propia lengua (para el mensaje de error de
  idioma desconocido).
- Claves jerárquicas con punto, agrupadas por prefijo: `informe.*`, `consola.*`, `error.*`,
  `estado.*`, `dimension.*`, `recomendacion.*`, `regla.<ID>.{titulo,detalle,mitigacion}`,
  `estructural.<id>.{titulo,detalle,mitigacion}`.
- Las cadenas con plural (por ejemplo «1 hallazgo» / «3 hallazgos») se resuelven con
  **dos claves**, `…​.uno` y `…​.otros`, y un parámetro `n`. No se construye ninguna
  gramática.

### 3.2 API

```python
t(clave: str, **datos) -> str
```

1. Busca la clave en el catálogo del idioma activo.
2. Si falta, busca en `es` (**degradación silenciosa en ejecución**; el CI impide que ocurra).
3. Si falta también en `es`, lanza `KeyError` con la clave: es un error de programación.

El idioma activo es **estado de módulo**, fijado una vez con `fijar_idioma(codigo)` al
arrancar `main()`. Pasar el idioma como parámetro por todas las funciones tocaría decenas de
firmas por poco beneficio, y el programa es de un solo hilo y un solo proceso.

### 3.3 Autodescubrimiento

`idiomas_disponibles()` lista `exporter/i18n/*.json`, igual que `perfiles.py` hace con
`exporter/targets/*.json`. Un idioma es válido si su fichero existe y su `_meta` es legible.
Sólo biblioteca estándar (`json`, `pathlib`), compatible con Python 3.8.

### 3.4 Reglas de seguridad

`reglas.json` conserva todo lo que usa el motor (`id`, `familia`, `dimension`, `severidad`,
`confianza`, `patron`, `extensiones`) y **pierde** `titulo`, `detalle` y `mitigacion`, que
pasan a los catálogos con clave `regla.<ID>.*`. Razón: un único origen para cada texto, y
`reglas.json` sigue siendo la excepción documentada del `AGENTS.md` (trampa 3).

`patrones.py` y `estructural.py` dejan de fijar el texto al crear el `Hallazgo`: guardan la
**clave** y los datos, y el texto se resuelve al renderizar. Así el mismo veredicto puede
renderizarse en cualquier idioma, y `resumen.json` queda independiente del idioma.

> **Punto de decisión para la revisión:** hoy `Hallazgo` lleva `titulo` y `mitigacion` como
> cadenas y `resumen.json` las serializa. Con este diseño `resumen.json` pasa a llevar el
> `id_texto` (clave estable) **y** el texto en el idioma activo. Mantener el texto en
> `resumen.json` conserva la compatibilidad con quien ya lo consume; el campo nuevo no rompe
> a nadie. Propongo eso, salvo que prefieras quitar el texto.

## 4. Interfaz de línea de comandos

- `--lang CODIGO` en los tres subcomandos (`inspect`, `audit`, `export`). Por defecto `es`.
- Si no se pasa, se lee `CSE_LANG`. El flag tiene prioridad sobre la variable.
- Código desconocido: error de uso (el mismo código de salida que ya usan los argumentos
  inválidos), con el mensaje **en español** y la lista de idiomas disponibles
  (`es — Español, en — English, fr — Français`). No hay idioma al que traducirlo todavía.
- `--help` y `argparse` quedan en español en esta versión: sus cadenas las genera
  `argparse` al construir el parser, antes de conocer `--lang`. Se documenta como limitación
  conocida; resolverlo exigiría un pre-análisis de `sys.argv`, que se descarta por YAGNI.

## 5. La conversación de Claude

`SKILL.md` y `commands/exportar-skills.md` ganan una sección corta, en español (las lee
Claude, no el usuario):

- Si el usuario pide un idioma, o escribe en uno distinto del español, **responde en ese
  idioma** y pasa `--lang <código>` al conversor.
- Si el idioma pedido no está entre los disponibles, dilo y ofrece el más cercano o el
  español; no inventes una traducción de los informes.
- Los nombres de artefactos y los valores de los vocabularios cerrados se citan tal cual.

La descripción de `SKILL.md` suma disparadores en inglés y francés («export this plugin»,
«exporte ce plugin») para que se active igual cuando el usuario no escribe en español.
Hay que vigilar que no desborde el presupuesto de la descripción que el propio conversor
valida sobre sí mismo.

## 6. Validación y pruebas

### 6.1 Validador nuevo: `.github/validar_idiomas.py`

Sólo biblioteca estándar. Falla si, para cada catálogo respecto a `es.json`:

1. faltan claves o sobran claves;
2. los **marcadores** `{nombre}` no coinciden exactamente con los de `es` (conjunto igual);
3. alguna plantilla está vacía;
4. `_meta` falta o su `idioma` no coincide con el nombre del fichero;
5. alguna clave `regla.<ID>.*` apunta a una regla que no existe en `reglas.json`, o alguna
   regla de `reglas.json` carece de sus tres textos.

Se añade al CI junto a los cuatro validadores existentes, y a `AGENTS.md` como quinto.

### 6.2 Pruebas

- `tests/test_i18n.py`: `t()` con claves presentes, con fallback a `es`, con clave inexistente,
  con marcadores faltantes; autodescubrimiento; idioma desconocido.
- Golden: los existentes, **sin cambios** (criterio de éxito 1). Se añade un juego
  `tests/golden-i18n/{en,fr}/` para un fixture de portabilidad y uno de seguridad, y se
  apunta en el generador.
- `test_cli.py`: `--lang en` y `--lang fr` en los tres subcomandos, `CSE_LANG`, prioridad
  del flag, idioma inválido.
- Prueba de redacción (restricción 7): comprueba, **en todos los idiomas**, que ninguna
  plantilla afirma que el repositorio «es malicioso». Una lista corta de expresiones
  prohibidas por idioma.
- `validar_estatico.py` debe seguir en verde: el módulo `i18n` no ejecuta nada.

### 6.3 Restricciones del `AGENTS.md` que este diseño respeta

| Restricción | Cómo |
|---|---|
| Python 3.8+, sólo stdlib | `json` y `pathlib`; el validador tampoco usa `jsonschema` |
| Análisis estático | `i18n` sólo lee JSON |
| Identificadores ASCII, comentarios sin acentos | código en ASCII; los catálogos son datos y llevan la acentuación de su idioma |
| Nombres de artefactos invariables | no se traducen |
| Vocabularios cerrados | no se traducen ni se amplían |
| Redacción del informe | prueba en todos los idiomas |
| Fixtures inertes | no se añaden fixtures con contenido real |
| Documentación de `skills/` con ámbito `exportado` | los textos de reglas pasan de `reglas.json` (exento) a `i18n/*.json`; **hay que confirmar que el motor también se salta esos ficheros**, o los literales peligrosos de las mitigaciones dispararían el gate |

## 7. Riesgos

1. **Ámbito `exportado` de los catálogos.** Las `mitigacion` y `detalle` describen patrones
   peligrosos con palabras, no con literales (la regla ya se cumple hoy), pero `i18n/*.json`
   vive dentro de `skills/`. Mitigación: el plan debe comprobar primero con un catálogo
   mínimo que `export . --only plugin-to-agentskills` sigue devolviendo 0 con
   `--anular-revision-seguridad`, y, si hace falta, ampliar la exención por identidad de
   fichero a `exporter/i18n/`.
2. **Calidad del francés y del inglés.** Las escribo yo. Textos de seguridad: conviene
   revisión humana antes de publicar. Se deja constancia en el README.
3. **Deriva entre catálogos.** Cubierto por el validador (§6.1).
4. **Tamaño del cambio.** Hay unas 95 líneas de texto en `convert.py` más `informes.py`,
   `riesgo.py`, `estructural.py` y 22 reglas. Se divide en fases en el plan: infraestructura
   y `es` idéntico primero (golden intactos), luego `en`, luego `fr`, luego la capa de Claude.

## 8. Orden de implementación sugerido (para el plan)

1. `i18n/` + `t()` + `es.json` generado extrayendo los literales actuales; sustituir los
   literales por `t()`. **Criterio de parada:** suite completa y golden en verde sin regenerar.
2. Mover textos de `reglas.json` y `estructural.py` a claves. Misma comprobación.
3. `--lang`, `CSE_LANG` y selección de idioma en `main()`.
4. `en.json`, `fr.json` y `validar_idiomas.py` en CI.
5. Golden de `en`/`fr`, pruebas de CLI y de redacción.
6. `SKILL.md`, comando, `README.md` y `AGENTS.md`.

## 9. Enmiendas posteriores a la aprobación

Aparecieron al leer el código para escribir el plan. Ninguna cambia lo que ve el usuario;
todas simplifican la implementación o completan el alcance.

1. **Alcance de §2 ampliado.** El texto visible no sale sólo de las reglas de seguridad.
   También lo producen: los `Finding` de portabilidad y las adaptaciones (`convert.py`), las
   explicaciones de señales (`deteccion.py`), los motivos de compatibilidad
   (`compatibilidad.py`), los `peligros` de los perfiles `targets/*.json`, la consola de
   `inspect`/`export` y los mensajes de error. Todos pasan por el mismo `t()`.
2. **§3.4 sustituido: el español se queda donde está.** `reglas.json` y `targets/*.json`
   **conservan** `titulo`/`detalle`/`mitigacion`, porque el esquema de perfiles los exige y
   `validar_reglas.py`/`validar_perfiles.py` los leen. Los catálogos `en.json` y `fr.json`
   los **sobrescriben** con las claves `regla.<ID>.*` y `peligro.<id>.*`, y `es.json` no
   las lleva. Resultado: un único origen por texto y por idioma, y el español no se mueve.
3. **Sin `id_texto` en `resumen.json`.** `Hallazgo.id` ya es la clave estable. El texto se
   resuelve al **crear** el hallazgo (el idioma es estado de proceso), no al renderizar. La
   forma de `resumen.json` y su schema **no cambian**; sólo cambia el idioma del texto.
4. **§4 ampliado: `--lang auto`.** Detección del idioma del sistema, **opt-in**: lee
   `LC_ALL`, `LC_MESSAGES` y `LANG` del entorno y cae a español. No es el valor por defecto
   porque los terminales de macOS suelen tener `LANG=en_US.UTF-8` aunque el usuario trabaje
   en español, y porque convertiría los golden en dependientes de la máquina. Ya no está
   «fuera de alcance».
5. **Normalización del código de idioma.** `EN`, `en-US` y `fr_FR.UTF-8` se aceptan como
   `en`, `en` y `fr`.
6. **Los valores de los vocabularios cerrados sí se traducen en la prosa del informe**
   (`severidad **alta**` → `severity **high**`), no en `resumen.json`. Es la regla de §2:
   si lo lee una persona, se traduce.
