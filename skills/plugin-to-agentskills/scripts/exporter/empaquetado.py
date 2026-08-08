"""Copia y empaquetado de la skill exportada.

La copia NO sigue enlaces simbolicos. shutil.copytree con symlinks=False
—su valor por defecto— copia el CONTENIDO de lo apuntado, no el enlace: una
skill con un enlace a ~/.ssh/id_rsa o a un .env vería ese contenido dentro
del .zip que despues se sube a una plataforma ajena. Poner symlinks=True
tampoco basta, porque zipfile.write() vuelve a seguirlo al empaquetar. La
unica salida segura es omitirlos y avisar.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

from exporter.modelo import Senal


def copiar_skill(src: Path, dest: Path, ignorar: set) -> list:
    """Copia el arbol omitiendo enlaces simbolicos y nombres ignorados.

    Devuelve una Senal por cada enlace omitido.
    """
    src, dest = Path(src), Path(dest)
    senales = []
    for base, dirs, ficheros in os.walk(str(src)):
        dirs[:] = [d for d in dirs
                   if d not in ignorar and not os.path.islink(os.path.join(base, d))]
        for d in sorted(os.listdir(base)):
            ruta = os.path.join(base, d)
            if os.path.isdir(ruta) and os.path.islink(ruta):
                senales.append(_senal_enlace(ruta, src))
        relativa = os.path.relpath(base, str(src))
        destino_base = dest if relativa == "." else dest / relativa
        destino_base.mkdir(parents=True, exist_ok=True)
        for nombre in sorted(ficheros):
            if nombre in ignorar:
                continue
            origen = os.path.join(base, nombre)
            if os.path.islink(origen):
                senales.append(_senal_enlace(origen, src))
                continue
            (destino_base / nombre).write_bytes(Path(origen).read_bytes())
    return senales


def _senal_enlace(ruta: str, raiz: Path) -> Senal:
    relativa = os.path.relpath(ruta, str(raiz))
    try:
        apunta = os.readlink(ruta)
    except OSError:
        apunta = "(ilegible)"
    return Senal(
        "enlace-simbolico", relativa,
        "enlace a {}".format(apunta), "alta")


def zip_dir(src: Path, dest_zip: Path, arc_prefix: str = "") -> None:
    """Empaqueta el arbol. Una skill por zip, con su carpeta en la raiz."""
    dest_zip = Path(dest_zip)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(Path(src).rglob("*")):
            if p.is_symlink() or not p.is_file():
                continue
            arc = Path(arc_prefix) / p.relative_to(src) if arc_prefix else p.relative_to(src)
            z.write(p, arc.as_posix())


def comprobar_limites(zip_path: Path, perfil) -> list:
    """Compara el paquete con los limites que declara el destino.

    Un limite a null significa que el destino no lo publica, y entonces no se
    comprueba. No es lo mismo que un limite infinito, pero es lo unico
    afirmable.
    """
    avisos = []
    tam_max = perfil.limite("zip_max_bytes")
    n_max = perfil.limite("ficheros_max")
    f_max = perfil.limite("fichero_max_bytes")

    tam = Path(zip_path).stat().st_size
    if tam_max is not None and tam > tam_max:
        avisos.append("El zip ocupa {} bytes y {} admite {}.".format(
            tam, perfil.label, tam_max))
    with zipfile.ZipFile(zip_path) as z:
        info = z.infolist()
    if n_max is not None and len(info) > n_max:
        avisos.append("El zip lleva {} ficheros y {} admite {}.".format(
            len(info), perfil.label, n_max))
    if f_max is not None:
        for i in info:
            if i.file_size > f_max:
                avisos.append("«{}» ocupa {} bytes descomprimido y {} admite {}.".format(
                    i.filename, i.file_size, perfil.label, f_max))
    return avisos
