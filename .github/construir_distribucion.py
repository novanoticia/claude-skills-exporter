#!/usr/bin/env python3
"""
Construye la distribucion del plugin: solo lo que se instala.

El directorio de plugins de Claude analiza el repositorio entero. Aqui conviven
el plugin y su banco de pruebas, que es malicioso a proposito (tests/fixtures/
lleva binarios falsos y patrones de descarga y ejecucion) y la documentacion de
diseno que describe esos patrones (docs/). Nada de eso se instala, pero retiene
la publicacion. Este script copia a un directorio limpio solo lo que el usuario
recibe; el CI publica ese directorio en la rama `plugin`.

Es una lista blanca: lo que no aparece en INCLUIR no viaja. Despues de copiar,
verifica que no se ha colado ningun fichero binario ni nada de tests/ o docs/.

Uso:  python3 .github/construir_distribucion.py DESTINO [raiz-del-repo]
Sale con codigo 1 si la distribucion no pasa la verificacion.
"""

import shutil
import sys
from pathlib import Path

# Rutas relativas a la raiz del repositorio. Directorios o ficheros.
INCLUIR = [
    ".claude-plugin",
    "commands",
    "skills",
    "plugin.json",
    "README.md",
    "LICENSE",
]

# Nunca deben aparecer en la distribucion, por mucho que cambie INCLUIR.
PROHIBIDOS = ("tests", "docs", ".github", ".git")

IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


def es_binario(ruta):
    """Un fichero cuenta como binario si tiene un byte nulo o no es UTF-8."""
    datos = ruta.read_bytes()
    if b"\x00" in datos:
        return True
    try:
        datos.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def construir(raiz, destino):
    raiz = Path(raiz).resolve()
    destino = Path(destino).resolve()
    if destino == raiz or raiz in destino.parents:
        raise SystemExit("[error] el destino no puede estar dentro del repositorio.")
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    for rel in INCLUIR:
        origen = raiz / rel
        if not origen.exists():
            raise SystemExit("[error] falta {} en el repositorio.".format(rel))
        if origen.is_dir():
            shutil.copytree(origen, destino / rel, ignore=IGNORAR)
        else:
            shutil.copy2(origen, destino / rel)
    return destino


def verificar(destino):
    """Devuelve la lista de problemas; vacia si la distribucion es limpia."""
    problemas = []
    destino = Path(destino)
    for ruta in sorted(destino.rglob("*")):
        rel = ruta.relative_to(destino)
        if rel.parts[0] in PROHIBIDOS:
            problemas.append("{}: esta ruta no debe distribuirse".format(rel))
        elif ruta.is_symlink():
            problemas.append("{}: enlace simbólico".format(rel))
        elif ruta.is_file() and es_binario(ruta):
            problemas.append("{}: fichero binario".format(rel))
    if not (destino / ".claude-plugin" / "plugin.json").is_file():
        problemas.append(".claude-plugin/plugin.json: falta el manifiesto")
    return problemas


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    raiz = argv[2] if len(argv) > 2 else "."
    destino = construir(raiz, argv[1])
    problemas = verificar(destino)
    for p in problemas:
        print("::error::{}".format(p))
    if problemas:
        print("\nFALLO: la distribución no es limpia.")
        return 1
    n = sum(1 for f in destino.rglob("*") if f.is_file())
    print("OK: distribución en {} ({} ficheros).".format(destino, n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
