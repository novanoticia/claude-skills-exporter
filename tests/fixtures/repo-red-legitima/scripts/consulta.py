import subprocess
import urllib.request

FUENTE = "https://datos.ejemplo.invalid/tipos.json"


def descargar():
    with urllib.request.urlopen(FUENTE, timeout=10) as r:
        return r.read()


def rama():
    return subprocess.run(["git", "status"], capture_output=True)
