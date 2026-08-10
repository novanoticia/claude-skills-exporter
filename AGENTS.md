# AGENTS.md

Lo que hay que saber antes de tocar nada. Escrito para quien llega sin contexto.

## Qué es esto

Un plugin de Claude Code que extrae las skills de un repositorio, audita su
**portabilidad** a otras plataformas de IA (ChatGPT, claude.ai, Perplexity Computer,
Mistral Vibe Work, Claude Code), audita su **seguridad** recorriendo el árbol entero, y
las empaqueta en el estándar abierto Agent Skills.

Todo el programa vive en `skills/plugin-to-agentskills/scripts/`. El punto de entrada es
`convert.py`, con tres subcomandos: `inspect` (qué exige la skill), `audit` (matriz de
compatibilidad, no escribe nada) y `export` (audita y empaqueta).

## Cómo ejecutar las pruebas

**Usa exactamente esta forma.** Varias pruebas lanzan `convert.py` por `subprocess` y su
stdout tapa el resumen de `unittest`; y encadenar con `&&` detrás de una tubería enmascara
los fallos, porque el estado de salida pasa a ser el de `tail`.

```bash
python3 -m unittest discover -s tests -t tests > /tmp/suite.log 2>&1; echo "codigo=$?"
grep -E "^(OK|FAILED|Ran )" /tmp/suite.log
```

Hoy son **349 pruebas** y salen todas en verde. Si ves menos, algo no se está
descubriendo.

### Los cuatro validadores del CI

```bash
python3 .github/validate_plugin.py .      # manifiestos, skills y comandos
python3 .github/validar_estatico.py .     # que el conversor no ejecuta nada de lo que analiza
```

Los otros dos necesitan `jsonschema`, que **no** se puede instalar con `pip install` a
secas en un Mac reciente (PEP 668). Usa un entorno virtual efímero:

```bash
python3 -m venv /tmp/venv-cse && /tmp/venv-cse/bin/pip install --quiet jsonschema
/tmp/venv-cse/bin/python .github/validar_perfiles.py .   # perfiles vs. documentación
/tmp/venv-cse/bin/python .github/validar_reglas.py .     # reglas y su cobertura por fixtures
```

## Restricciones innegociables

Vienen del diseño. Romper cualquiera rompe el CI.

1. **Python 3.8+ y sólo biblioteca estándar en ejecución.** Nunca importes `jsonschema`
   desde `exporter/`. Sólo el CI y los validadores de `.github/` pueden usarlo.
2. **El análisis es estrictamente estático.** No se ejecuta, no se instala y no se
   descomprime nada. El único proceso externo del programa es el `git clone` de
   `resolve_source`. Lo comprueba `.github/validar_estatico.py`, que mira las llamadas por
   atributo, las llamadas por nombre simple y los `import` que traen esos nombres.
3. **Identificadores en ASCII, prosa en español.** Sin `ñ` ni tildes en nombres de función,
   clase o variable. Los comentarios y *docstrings* del código van **sin acentos**: así
   están todos los módulos. En cambio, **todo texto visible para el usuario** —títulos y
   mitigaciones de hallazgos, informes, mensajes de error— va en español **con acentuación
   correcta**.
4. **Nombres de artefactos invariables:** `<skill>.zip`, `<skill>/`,
   `INFORME-PORTABILIDAD.md`, `resumen.json`.
5. **Vocabularios cerrados.** Familia: `permisos_y_acciones`, `cadena_de_suministro`,
   `ofuscacion`, `conducta_de_prompt`. Dimensión: `tecnico`, `cadena_de_suministro`,
   `comportamiento`. Severidad: `critica`, `alta`, `media`, `baja`. Confianza: `alta`,
   `media`, `baja`. Ámbito: `exportado`, `paquete`. Nivel: `bajo`, `moderado`, `alto`,
   `critico`, `no_evaluable`. **No inventes valores nuevos.**
6. **`tests/__init__.py` no debe existir.**
7. **Redacción del informe:** nunca «este repositorio es malicioso». Un análisis estático
   no puede saber eso. Hay una prueba que lo verifica.
8. **Los fixtures deben ser inertes:** dominios en `.invalid` y claves manifiestamente
   falsas. GitHub pasa un escáner de secretos sobre los repositorios públicos.
9. **Mensajes de commit en español**, sujeto imperativo en tercera persona («Anade…», no
   «Anadir»), cuerpo explicando el **porqué**.

## Las cuatro trampas

Cuestan horas si no se saben.

### 1 · El comando de pruebas no muestra si pasó

Ver arriba. Redirige a un fichero y mira el código de salida por separado. Nunca
`... | tail && ...`.

### 2 · Ejecutar el conversor sobre este mismo repositorio no devuelve 0

Es correcto y deliberado. `tests/fixtures/` es un banco de pruebas malicioso a propósito,
y además contiene ocho skills que publican todas `name: fechas`. Los códigos reales:

| Comando sobre este repo | Código | Por qué |
|---|---|---|
| `export .` | **1** | ocho skills reclaman el mismo nombre publicado y aborta sin escribir |
| `audit .` | **1** | lo mismo: `audit` también indexa por nombre |
| `export . --only plugin-to-agentskills` | **2** | el nivel de riesgo del repo no es `bajo` |
| `export . --only plugin-to-agentskills --anular-revision-seguridad` | **0** | ✅ |

Es decir: **cualquier invocación sobre este repo necesita `--only plugin-to-agentskills`**
para no chocar con los fixtures, y `--anular-revision-seguridad` encima para devolver 0.
Así lo hacen los cuatro sitios que se auto-exportan (`validate_plugin.py`, dos pasos del
CI y `tests/test_seg_golden.EsteRepositorio`). **No "arregles" nada de esto.**

### 3 · La documentación dentro de `skills/` tiene ámbito `exportado`

Todo lo que cuelga de `skills/plugin-to-agentskills/` viaja dentro del artefacto. Si
escribes un patrón peligroso **en claro** ahí —el literal de descargar-un-script-y-
pasarlo-al-intérprete-en-la-misma-línea, por ejemplo—, el propio *gate* bloquea la
exportación de la herramienta: `plugin-to-agentskills.zip` deja de escribirse. Ya ha
pasado dos veces, la segunda dentro de una docstring que explicaba justamente ese patrón.

**En esa documentación los patrones se describen con palabras.** Los literales sólo pueden
vivir en `exporter/seguridad/reglas.json` —que el motor se salta a sí mismo, por identidad
de fichero— y en `tests/fixtures/`, que está fuera de toda skill.

Ojo además: desde que la lista de extensiones es un **veto** y no un permiso, un fichero
con extensión que ninguna regla declara (`.html`, por ejemplo) se analiza con **todas** las
reglas. Escribir un ejemplo de inyección de prompt en `docs/*.html` lo dispara.

### 4 · Tocar el motor de seguridad cambia los *golden files*

Hay dos juegos: `tests/golden/` (portabilidad) y `tests/golden-seguridad/` (seguridad).
Después de cualquier cambio en `exporter/seguridad/`:

```bash
python3 tests/generar_golden.py
git diff --stat tests/golden tests/golden-seguridad
```

**Revisa el diff antes de comitear.** Es la única señal de que un cambio en el motor no ha
alterado un veredicto que no querías tocar. Si un golden falla, entiende **por qué** antes
de regenerarlo: puede ser el fallo que buscabas.

Añadir un fixture de seguridad exige apuntarlo en `FIXTURES_SEG`, en
`tests/test_seg_golden.py`: de esa lista tiran tanto el generador de golden como
`validar_reglas.py`.

## Dónde está lo demás

| Documento | Qué contiene |
|---|---|
| `docs/superpowers/specs/2026-08-08-auditor-seguridad-diseno.md` | El diseño del auditor de seguridad. §4 el **ámbito**, §5 las reglas, §6 el motor de riesgo, §7 el *gate* |
| `docs/superpowers/specs/2026-08-08-auditor-portabilidad-diseno.md` | El diseño del auditor de portabilidad |
| `docs/superpowers/plans/2026-08-08-auditor-seguridad.md` | El plan ejecutado, con una sección final de **«Erratas de ejecución»**. No reintroduzcas esos defectos |
| `README.md` | Uso, opciones y la tabla de códigos de salida |
| `docs/guia.html` | La guía para quien no es técnico |

## Mapa rápido del código

```
skills/plugin-to-agentskills/scripts/
  convert.py              CLI, descubrimiento, adaptación, gate y escritura
  exporter/
    modelo.py             vocabularios cerrados y estructuras
    frontmatter.py        lectura del frontmatter YAML (parser propio)
    descripcion.py        reordenar, compactar y recortar la descripción
    deteccion.py          patrones de portabilidad (señales)
    compatibilidad.py     cruzar señales y capacidades con cada perfil
    perfiles.py           carga de exporter/targets/*.json
    empaquetado.py        copia, zip y límites de paquete
    informes.py           INFORME-PORTABILIDAD.md y resumen.json
    seguridad/
      recorrido.py        recorre el árbol y pone el ámbito a cada fichero
      patrones.py         aplica reglas.json
      estructural.py      lo que exige interpretar un fichero, no una regex
      riesgo.py           de hallazgos a nivel y recomendación
      reglas.json         el catálogo de patrones
```

Dos cosas que conviene saber de entrada:

- **`export` prepara los artefactos en un temporal y publica a `--out` sólo después de que
  el gate haya decidido.** No escribas nada directamente en `out` antes de ese punto.
- **`--out` se borra entero** antes de escribir, y por eso el conversor se niega a vaciar un
  directorio con contenido que no lleve su marca `.cse-salida`. `--force` lo salta.
