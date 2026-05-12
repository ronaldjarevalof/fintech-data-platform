"""Extracción: lectura de CSV crudos → DataFrames con metadatos técnicos."""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import CSV_CLIENTES, CSV_CREDITOS, CSV_PAGOS

# Columnas mínimas requeridas por entidad. El pipeline falla rápido y con
# mensaje claro si el evaluador entrega un CSV con nombres distintos.
_REQUIRED_COLS: dict[str, set[str]] = {
    "clientes": {
        "cliente_id", "tipo_documento", "numero_documento", "nombres",
        "apellidos", "email", "telefono", "fecha_registro", "estado_cliente",
        "ciudad", "segmento",
    },
    "creditos": {
        "credito_id", "cliente_id", "fecha_solicitud", "fecha_desembolso",
        "monto_aprobado", "plazo_meses", "tasa_interes_mensual",
        "estado_credito", "producto", "fecha_vencimiento", "canal",
    },
    "pagos": {
        "pago_id", "credito_id", "fecha_pago", "monto_pago",
        "metodo_pago", "estado_pago", "referencia_transaccion",
    },
}


def _read_csv(path: Path) -> pd.DataFrame:
    """Lee un CSV como texto puro y añade columnas técnicas.

    Usa encoding utf-8-sig para tolerar archivos guardados desde Excel
    (UTF-8 con BOM), que de otro modo generarían un nombre de columna
    con el carácter \\ufeff al inicio.

    Args:
        path: Ruta al archivo CSV.

    Returns:
        DataFrame con todos los campos como str y columnas _ingested_at,
        _source_file añadidas.
    """
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df["_ingested_at"] = datetime.now(tz=timezone.utc)
    df["_source_file"] = path.name
    return df


def _validate_columns(entity: str, df: pd.DataFrame, path: Path) -> None:
    """Valida que el CSV tenga las columnas mínimas requeridas.

    Args:
        entity: Nombre de la entidad ('clientes', 'creditos', 'pagos').
        df: DataFrame leído del CSV.
        path: Ruta del archivo (para el mensaje de error).

    Raises:
        ValueError: Si faltan columnas requeridas.
    """
    required = _REQUIRED_COLS[entity]
    present = set(df.columns)
    missing = required - present
    if missing:
        raise ValueError(
            f"Columnas faltantes en {path.name}: {sorted(missing)}. "
            f"Columnas presentes: {sorted(present)}"
        )


def extract_all() -> dict[str, pd.DataFrame]:
    """Lee los tres CSV fuente y retorna un diccionario de DataFrames.

    Returns:
        Dict con claves 'clientes', 'creditos', 'pagos'.

    Raises:
        FileNotFoundError: Si alguno de los CSV no existe.
        ValueError: Si algún CSV no contiene las columnas requeridas.
    """
    sources = {
        "clientes": CSV_CLIENTES,
        "creditos": CSV_CREDITOS,
        "pagos": CSV_PAGOS,
    }
    for path in sources.values():
        if not path.exists():
            raise FileNotFoundError(f"Archivo fuente no encontrado: {path}")

    dfs: dict[str, pd.DataFrame] = {}
    for entity, path in sources.items():
        df = _read_csv(path)
        _validate_columns(entity, df, path)
        dfs[entity] = df

    return dfs
