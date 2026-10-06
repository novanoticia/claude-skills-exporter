# Tarea: hacer este repositorio multiidioma

Quiero que cualquier persona que use este proyecto pueda recibir toda la información
que genera en su idioma, y que añadir un idioma nuevo cueste lo mínimo. Trabaja por
fases y no pases a la siguiente sin cerrar la anterior.

## Datos de este repositorio (rellénalo yo; si algo queda vacío, pregúntamelo)

- Idiomas a soportar: [p. ej. es, en, fr]
- Idioma por defecto actual: [p. ej. es]
- Alcance: [solo lo que genera el programa | + conversación del agente | + documentación]
- Restricciones particulares que ya conozco: [versión mínima del lenguaje, dependencias
  prohibidas, convenciones de idioma en código/comentarios, CI, etc.]

## Reglas de trabajo

- Lee primero el README, AGENTS.md/CLAUDE.md, la configuración de CI y las pruebas.
  Las convenciones de este repositorio mandan sobre todo lo que diga este prompt.
- Si usas skills de brainstorming, planes o TDD, aplícalas. Si no, sigue el mismo
  orden: entender, diseñar, planificar, pruebas primero, implementar, revisar.
- No hagas push, merge ni publiques nada sin que te lo pida. Prepara un PR.
- Commits según las convenciones del repositorio (idioma, estilo, atribución).
- Lo que no sea de este objetivo (refactors, estilo, bugs ajenos) se anota, no se hace.

## Fase 1 — Descubrir (solo lectura)

1. Identifica qué tipo de proyecto es (CLI, librería, servidor web, app móvil, plugin,
   skill, bot…), su lenguaje y si ya tiene alguna infraestructura de i18n. **Si la
   tiene, o el ecosistema tiene una estándar** (gettext, i18next, ICU/MessageFormat,
   Rails I18n, strings.xml, ARB…), úsala en lugar de inventar la tuya.
2. Haz un inventario de todos los textos que llegan a una persona y clasifícalos:
   - A. Texto para personas generado por el programa: informes, consola, errores,
     avisos, mensajes, plantillas de correo, etiquetas de interfaz.
   - B. **Contratos de máquina que NO se traducen**: claves JSON/YAML, nombres de
     fichero y de artefacto, códigos de salida, identificadores, vocabularios cerrados
     (estados, severidades…), nombres de comandos y opciones, formatos de log que
     alguien parsea. Los valores de un vocabulario cerrado se muestran traducidos en
     prosa para personas, pero se emiten sin traducir en los formatos de máquina.
   - C. Contenido del usuario o datos de entrada: no se toca.
   - D. Documentación.
   - E. Texto que el programa escribe dentro de artefactos que otros consumen.
   - F. Lógica que depende del idioma del texto (regex sobre lenguaje natural,
     detectores, ordenación, formatos de fecha y número, plurales).
3. Anota qué hace especial a este repositorio: pruebas con golden files, escaneo de
   su propio contenido, validadores de CI, límites de tamaño, versión mínima del
   lenguaje, dependencias prohibidas, servidores concurrentes, etc.

Entrega un resumen corto: lo que has encontrado, tu clasificación y cualquier punto
donde este repositorio se salga de lo que cubre este prompt.

## Fase 2 — Pregúntame solo lo que es mío

Una pregunta por mensaje, con tu recomendación primero: idiomas y por defecto; si la
conversación del agente y la documentación entran; si los artefactos generados se
traducen; si quiero detección automática del idioma del sistema (recomiéndala solo
como opción explícita, nunca por defecto); quién revisará las traducciones. Escribe
de vuelta lo que has entendido y espera mi corrección antes de diseñar.

## Fase 3 — Diseño (adáptalo al proyecto; no apliques esto a ciegas)

- **El idioma por defecto no cambia nada**: su salida debe quedar idéntica, byte a
  byte. Ese es el criterio de éxito más importante.
- Selección del idioma: ajuste explícito > variable de entorno > por defecto. Acepta
  códigos con forma de locale (`EN`, `en-US`, `fr_FR.UTF-8`). Un código desconocido o
  **vacío** es un error de uso, en el idioma por defecto y con la lista de disponibles;
  una variable de entorno vacía cuenta como ausente.
- Si no hay librería estándar: un catálogo por idioma (un fichero por idioma) y una
  función `t(clave, **datos)`. Si falta una clave, cae al idioma por defecto; si falta
  también ahí, es un error de programación. Añadir un idioma debe ser soltar un
  fichero que se autodescubre.
- **Estado del idioma**: en un programa de un solo proceso vale un idioma global fijado
  al arrancar. En un servidor concurrente es un error: el idioma va por petición o
  por contexto.
- Plantillas: solo campos con nombre. Las llaves literales se escapan, y el dato que se
  interpola nunca se vuelve a interpretar como plantilla. No concatenes frases ni
  construyas texto con trozos traducidos; usa una clave por frase completa. Para
  plurales usa el mecanismo del ecosistema o dos claves (`.uno`/`.otros`).
- Textos que viven en datos de configuración (reglas, perfiles, catálogos de
  contenido): su idioma original se queda donde está, y los demás idiomas lo
  sobrescriben por clave. Así hay un único origen por texto y por idioma.
- Artefactos generados que otra persona sube o lee (E): decide si el idioma elegido
  los afecta, documéntalo, y garantiza que no mezclan idiomas.
- Lógica que depende del idioma (F): comprueba que lo que el programa **aconseja** en
  cada idioma es algo que el propio programa **reconoce** en ese idioma. Si aconseja
  una frase que su detector rechaza, el usuario recibe el mismo aviso otra vez.
- Si el repositorio se analiza a sí mismo o los catálogos viajan dentro de un paquete
  que se audita, una traducción puede disparar sus propias reglas. Descríbelo con
  palabras en las traducciones y **no amplíes exenciones de seguridad** para arreglarlo.
- Si hay un agente que conversa (skill, prompt del sistema, comandos): indícale que
  responda en el idioma del usuario, que pase el ajuste de idioma al programa y que
  cite tal cual lo que es contrato de máquina. Si el idioma pedido no existe, que lo
  diga y no invente una traducción de la salida del programa.
- `--help` y los errores del parser de argumentos suelen construirse antes de conocer
  el idioma: decide si se traducen o se documenta la limitación.

## Fase 4 — Plan, línea base y TDD

1. Escribe un plan por tareas, cada una con su prueba, sus ficheros y su criterio de
   «hecho». Dime si el alcance real es mayor de lo que parecía.
2. **Antes de tocar nada, captura una línea base** de la salida en el idioma por
   defecto sobre casos representativos (todos los fixtures o ejemplos que haya, y
   todos los modos de ejecución, incluidos los caminos de error). Hazla determinista:
   rutas de salida fijas, fecha fija, y para binarios o zips compara el contenido, no
   el fichero. Tras **cada** tarea de extracción compara con ella: no puede cambiar
   nada.
3. **Extrae los textos con herramientas, no a mano**: un análisis del árbol sintáctico
   o un codemod que lea el literal real y lo sustituya por la llamada a `t()`. Así el
   texto del idioma por defecto es verbatim por construcción.
4. Pruebas primero y viéndolas fallar. Las imprescindibles: salida por idioma (golden o
   equivalente), el formato de máquina no cambia de forma entre idiomas, selección y
   normalización del código, error por idioma desconocido o vacío, que las variables
   de entorno del desarrollador no contaminan las pruebas, y una prueba que falle si
   queda un mensaje sin pasar por el catálogo.
5. **Validador de catálogos en el CI**: todos los idiomas con las mismas claves, los
   mismos marcadores y nada vacío; el idioma por defecto también (mismo tipo, no vacío);
   marcadores solo con nombre (`{}`, `{0}` y `{a.b}` pasan una comparación de
   conjuntos y fallan en ejecución); y traducción completa de lo que sobrescribe datos.
6. Suite completa y todos los validadores del CI en verde tras cada tarea.

## Fase 5 — Traducciones

- Antes de traducir, fija un glosario y úsalo siempre igual.
- Conserva idénticos los marcadores, los emojis y el formato. Respeta la tipografía de
  cada idioma. No traduzcas nombres de producto, comandos, opciones ni rutas.
- Si lo que traduces es seguridad, legal o médico, dilo en el informe final: lo has
  redactado tú y necesita revisión de una persona nativa.

## Fase 6 — Documentación y versión

README: cómo elegir idioma, qué se traduce y qué no, cómo añadir un idioma, limitaciones
conocidas y el aviso de que las traducciones las ha escrito una IA. En AGENTS.md o
CLAUDE.md: la regla de que no se escriben literales nuevos en el código y el comando
del validador. Sube la versión según semver (función nueva compatible = minor) si el
proyecto fija versión.

## Fase 7 — Revisión y entrega

1. Pasa una revisión independiente de toda la rama (con una skill de code-review o un
   subagente de contexto limpio). Pídele que mire explícitamente: llaves literales,
   datos con llaves, contaminación por entorno, códigos con forma de locale, forma del
   formato de máquina entre idiomas, catálogos incompletos, español u otro idioma
   mezclado en la salida (incluidos los artefactos generados), y consejos que el
   detector propio no reconoce.
2. Corrige lo crítico y lo importante con una prueba que falle antes. Lo menor se
   anota como pendiente.
3. Abre un PR. En la descripción: qué hace, cómo se verificó, qué no se traduce y
   por qué, y qué revisar a mano (sobre todo las traducciones).

## Informe final

Entrégame: decisiones que tomaste por mí y su coste si estaban mal, desviaciones de
este prompt y por qué, limitaciones conocidas, pendientes menores y la lista exacta de
comandos con los que verificaste cada cosa.

## Criterios de aceptación

- [ ] El idioma por defecto sale idéntico, comprobado contra la línea base.
- [ ] Todos los idiomas pedidos funcionan en todos los modos y caminos de error.
- [ ] Los formatos de máquina no cambian de forma ni de vocabulario entre idiomas.
- [ ] Un idioma nuevo se añade soltando un fichero, y el validador dice qué falta.
- [ ] Ningún texto visible queda fuera del catálogo ni mezcla idiomas.
- [ ] Suite y CI en verde; documentación y versión al día; revisión independiente hecha.
