"""Extracción: lectura de CSV crudos → DataFrames con metadatos técnicos."""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import CSV_CLIENTES, CSV_CREDITOS, CSV_PAGOS


def _read_csv(path: Path) -> pd.DataFrame:
    """Lee un CSV como texto puro y añade columnas técnicas.

    Args:
        path: Ruta al archivo CSV.

    Returns:
        DataFrame con todos los campos como str y columnas _ingested_at,
        _source_file añadidas.
    """
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df["_ingested_at"] = datetime.now(tz=timezone.utc)
    df["_source_file"] = path.name
    return df


def extract_all() -> dict[str, pd.DataFrame]:
    """Lee los tres CSV fuente y retorna un diccionario de DataFrames.

    Returns:
        Dict con claves 'clientes', 'creditos', 'pagos'.

    Raises:
        FileNotFoundError: Si alguno de los CSV no existe.
    """
    for path in (CSV_CLIENTES, CSV_CREDITOS, CSV_PAGOS):
        if not path.exists():
            raise FileNotFoundError(f"Archivo fuente no encontrado: {path}")

    return {
        "clientes": _read_csv(CSV_CLIENTES),
        "creditos": _read_csv(CSV_CREDITOS),
        "pagos": _read_csv(CSV_PAGOS),
    }
