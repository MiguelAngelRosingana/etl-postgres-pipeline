"""Extracción: lee el CSV de origen sin interpretar nada."""
import hashlib
import logging
from pathlib import Path

import pandas as pd

from etl.transform import COLUMNAS

log = logging.getLogger(__name__)


def sha256_fichero(ruta: Path) -> str:
    """Huella del contenido: permite saber si un fichero ya se procesó."""
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def extraer(ruta: Path) -> pd.DataFrame:
    # Todo como texto y sin convertir vacíos en NaN: la validación decide qué es válido
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en {ruta.name}: {', '.join(faltan)}")
    log.info("Extraídas %d filas de %s", len(df), ruta.name)
    return df[COLUMNAS]
