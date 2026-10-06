"""Utilidades compartidas por las pruebas.

El paquete `exporter` no se instala: vive junto a convert.py y se importa
porque Python pone el directorio del script en sys.path[0]. Las pruebas no
se ejecutan desde ahí, así que replican ese gesto a mano.
"""

import os
import sys
from pathlib import Path

# Una CSE_LANG puesta en el shell del desarrollador cambiaria el idioma de
# todos los conversores que lanzan las pruebas y rompería los golden.
os.environ.pop("CSE_LANG", None)

RAIZ = Path(__file__).resolve().parent.parent
RAIZ_SCRIPTS = RAIZ / "skills" / "plugin-to-agentskills" / "scripts"


def importar_exporter() -> None:
    ruta = str(RAIZ_SCRIPTS)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
