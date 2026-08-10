#!/usr/bin/env python3
"""Comprueba que el conversor sigue sin ejecutar nada de lo que analiza.

Es la garantia que hace seguro apuntar esta herramienta al repositorio de un
desconocido. El unico proceso externo del programa es el `git clone` de
`resolve_source`; todo lo demas es lectura de ficheros y expresiones
regulares.

Un nombre prohibido puede llegar a ejecutarse de tres formas, y las tres se
comprueban aqui porque ninguna implica a las otras:

    os.system(...)                     como atributo
    system(...)                        como nombre simple, tras un import
    from os import system as arrancar  en el import, que es lo unico que
                                       caza el caso con alias -ahi la
                                       llamada ya no se llama como ningun
                                       nombre de la lista-

Esto vivia incrustado en el YAML del workflow, y por eso llevaba tiempo
comprobando menos de lo que su nombre prometia: solo miraba la primera de
las tres formas, y nadie podia ejecutarlo sin extraerlo a mano. Como fichero
tiene pruebas, que es lo que evita que vuelva a pudrirse en silencio.

Solo biblioteca estandar, a proposito: asi corre en el CI antes de instalar
nada y la suite puede importarlo sin dependencias.
"""

import ast
import sys
from pathlib import Path

# El arbol que se publica como skill. Es el unico codigo que acaba en manos
# de otra persona, y por tanto el unico sobre el que esta garantia importa.
SUBARBOL = "skills/plugin-to-agentskills/scripts"

# `subprocess.run` es el `git clone` de resolve_source. Es la unica pareja
# permitida, y se declara como pareja y no como nombre suelto para que un
# `run` cualquiera de otro modulo no herede el permiso.
PERMITIDO = {("subprocess", "run")}

PROHIBIDO = {"system", "popen", "Popen", "call", "check_output",
             "check_call", "spawnl", "spawnv", "execv", "execve",
             "eval", "exec"}

# De estos modulos no se importa nada a granel: un `import *` mete cualquiera
# de los nombres de arriba sin que ninguno aparezca escrito.
MODULOS_DE_PROCESO = {"os", "subprocess", "pty", "popen2", "commands"}


def infracciones(raiz) -> list:
    """Las llamadas e imports no permitidos, como texto legible y ordenado."""
    raiz = Path(raiz)
    malos = []
    for p in sorted((raiz / SUBARBOL).rglob("*.py")):
        rel = p.relative_to(raiz)
        arbol = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if isinstance(n, ast.ImportFrom):
                for alias in n.names:
                    if alias.name in PROHIBIDO:
                        malos.append("{}:{} -> from {} import {}".format(
                            rel, n.lineno, n.module, alias.name))
                    elif alias.name == "*" and n.module in MODULOS_DE_PROCESO:
                        malos.append("{}:{} -> from {} import *".format(
                            rel, n.lineno, n.module))
                continue
            if not isinstance(n, ast.Call):
                continue
            if isinstance(n.func, ast.Attribute):
                base = getattr(n.func.value, "id", None)
                if (n.func.attr in PROHIBIDO
                        or (base == "subprocess"
                            and (base, n.func.attr) not in PERMITIDO)):
                    malos.append("{}:{} -> {}.{}".format(
                        rel, n.lineno, base, n.func.attr))
            elif isinstance(n.func, ast.Name) and n.func.id in PROHIBIDO:
                malos.append("{}:{} -> {}()".format(rel, n.lineno, n.func.id))
    return malos


def main(raiz: Path) -> int:
    malos = infracciones(raiz)
    if malos:
        print("[error] llamadas a procesos externos no permitidas:", file=sys.stderr)
        for m in malos:
            print("  " + m, file=sys.stderr)
        return 1
    print("Analisis estatico: ningun proceso externo fuera de "
          "subprocess.run(git clone).")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
