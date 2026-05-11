"""Transformación: limpieza, normalización de tipos y catálogos canónicos."""

from datetime import date, datetime
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Catálogos canónicos (DQ-3)
# ---------------------------------------------------------------------------

ESTADO_CLIENTE_MAP: dict[str, str] = {
    "activo": "Activo",
    "inactivo": "Inactivo",
    "bloqueado": "Bloqueado",
    "suspendido": "Suspendido",
    "pendiente": "Pendiente",
    "en revision": "EnRevision",
    "enrevision": "EnRevision",
}

ESTADO_CREDITO_MAP: dict[str, str] = {
    "activo": "Activo",
    "mora": "Mora",
    "vencido": "Vencido",
    "pagado": "Pagado",
    "cancelado": "Cancelado",
    "rechazado": "Rechazado",
}

ESTADO_PAGO_MAP: dict[str, str] = {
    "exitoso": "Exitoso",
    "success": "Exitoso",
    "pendiente": "Pendiente",
    "fallido": "Fallido",
    "reversado": "Reversado",
}

TIPO_DOCUMENTO_MAP: dict[str, str] = {
    "cc": "CC",
    "ce": "CE",
    "nit": "NIT",
}


def _normalize_catalog(value: str, mapping: dict[str, str]) -> tuple[str, bool]:
    """Normaliza un valor contra un catálogo canónico.

    Args:
        value: Valor original a normalizar.
        mapping: Diccionario {valor_lower → canónico}.

    Returns:
        Tupla (valor_canonico, es_valido). Si no hay mapeo, devuelve el
        original y es_valido=False.
    """
    key = value.strip().lower()
    if key in mapping:
        return mapping[key], True
    return value.strip(), False


def _parse_date(value: str) -> date | None:
    """Intenta parsear una fecha en múltiples formatos comunes.

    Args:
        value: String con la fecha a parsear.

    Returns:
        Objeto date si el parseo tuvo éxito, None si el valor está vacío
        o no es parseable.
    """
    if not value or not value.strip():
        return None
    # Normaliza separadores mixtos
    normalized = value.strip().replace("/", "-")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue
    return None  # Fecha no parseable → DQ-5/DQ-6 la atrapa


def _safe_numeric(value: str) -> float | None:
    """Convierte un string a float; retorna None si está vacío o es inválido.

    Args:
        value: String numérico a convertir.

    Returns:
        float o None.
    """
    if not value or not value.strip():
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Transformaciones por entidad
# ---------------------------------------------------------------------------

def transform_clientes(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia y normaliza el DataFrame de clientes.

    - Normaliza estado_cliente al catálogo canónico.
    - Normaliza tipo_documento.
    - Parsea fechas (acepta formato YYYY/MM/DD además de YYYY-MM-DD).
    - Castea ingresos_mensuales a numérico.

    Args:
        df: DataFrame crudo de clientes (todos los campos como str).

    Returns:
        DataFrame transformado con nuevas columnas _estado_cliente_valido
        y _tipo_doc_valido como metadata interna para validate.py.
    """
    out = df.copy()

    # Limpieza de espacios
    for col in out.select_dtypes(include="object").columns:
        out[col] = out[col].str.strip()

    # Normalización estado_cliente
    results = out["estado_cliente"].apply(
        lambda v: _normalize_catalog(v, ESTADO_CLIENTE_MAP)
    )
    out["estado_cliente"] = results.apply(lambda t: t[0])
    out["_estado_cliente_valido"] = results.apply(lambda t: t[1])

    # Normalización tipo_documento
    results_doc = out["tipo_documento"].apply(
        lambda v: _normalize_catalog(v, TIPO_DOCUMENTO_MAP)
    )
    out["tipo_documento"] = results_doc.apply(lambda t: t[0])
    out["_tipo_doc_valido"] = results_doc.apply(lambda t: t[1])

    # Parseo de fechas
    out["fecha_registro"] = out["fecha_registro"].apply(_parse_date)
    out["fecha_nacimiento"] = out["fecha_nacimiento"].apply(_parse_date)

    # Numérico
    out["ingresos_mensuales"] = out["ingresos_mensuales"].apply(_safe_numeric)

    return out


def transform_creditos(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia y normaliza el DataFrame de créditos.

    - Normaliza estado_credito al catálogo canónico.
    - Parsea fechas.
    - Castea montos, plazo y tasa a numérico.

    Args:
        df: DataFrame crudo de créditos (todos los campos como str).

    Returns:
        DataFrame transformado con columna _estado_credito_valido.
    """
    out = df.copy()

    for col in out.select_dtypes(include="object").columns:
        out[col] = out[col].str.strip()

    results = out["estado_credito"].apply(
        lambda v: _normalize_catalog(v, ESTADO_CREDITO_MAP)
    )
    out["estado_credito"] = results.apply(lambda t: t[0])
    out["_estado_credito_valido"] = results.apply(lambda t: t[1])

    out["fecha_solicitud"] = out["fecha_solicitud"].apply(_parse_date)
    out["fecha_desembolso"] = out["fecha_desembolso"].apply(_parse_date)
    out["fecha_vencimiento"] = out["fecha_vencimiento"].apply(_parse_date)

    out["monto_aprobado"] = out["monto_aprobado"].apply(_safe_numeric)
    out["plazo_meses"] = out["plazo_meses"].apply(
        lambda v: int(float(v)) if v and v.strip() else None
    )
    out["tasa_interes_mensual"] = out["tasa_interes_mensual"].apply(_safe_numeric)

    return out


def transform_pagos(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia y normaliza el DataFrame de pagos.

    - Normaliza estado_pago al catálogo canónico (incluye 'success' → 'Exitoso').
    - Parsea fechas.
    - Castea monto_pago a numérico.

    Args:
        df: DataFrame crudo de pagos (todos los campos como str).

    Returns:
        DataFrame transformado con columna _estado_pago_valido.
    """
    out = df.copy()

    for col in out.select_dtypes(include="object").columns:
        out[col] = out[col].str.strip()

    results = out["estado_pago"].apply(
        lambda v: _normalize_catalog(v, ESTADO_PAGO_MAP)
    )
    out["estado_pago"] = results.apply(lambda t: t[0])
    out["_estado_pago_valido"] = results.apply(lambda t: t[1])

    out["fecha_pago"] = out["fecha_pago"].apply(_parse_date)
    out["monto_pago"] = out["monto_pago"].apply(_safe_numeric)

    return out


def transform_all(dfs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Aplica transformaciones a los tres DataFrames crudos.

    Args:
        dfs: Dict con claves 'clientes', 'creditos', 'pagos'.

    Returns:
        Dict con los mismos DataFrames transformados.
    """
    return {
        "clientes": transform_clientes(dfs["clientes"]),
        "creditos": transform_creditos(dfs["creditos"]),
        "pagos": transform_pagos(dfs["pagos"]),
    }


def compute_fecha_corte(dfs: dict[str, pd.DataFrame]) -> date:
    """Deriva la fecha de corte como el máximo de fechas en los datos.

    Args:
        dfs: Dict con DataFrames transformados.

    Returns:
        Fecha de corte (date).
    """
    candidates: list[date] = []
    for col in ("fecha_desembolso", "fecha_vencimiento", "fecha_solicitud"):
        if col in dfs["creditos"].columns:
            vals = dfs["creditos"][col].dropna()
            candidates.extend([v for v in vals if isinstance(v, date)])
    for col in ("fecha_pago",):
        if col in dfs["pagos"].columns:
            vals = dfs["pagos"][col].dropna()
            candidates.extend([v for v in vals if isinstance(v, date)])

    return max(candidates) if candidates else datetime.now().date()


def compute_dias_mora(estado: str, fecha_vencimiento: Any, fecha_corte: date) -> int:
    """Calcula días de mora para un crédito dado.

    Args:
        estado: Estado canónico del crédito.
        fecha_vencimiento: Fecha de vencimiento (date o None).
        fecha_corte: Fecha de referencia del cálculo.

    Returns:
        Días de mora (0 si el crédito no está en mora/vencido).
    """
    if estado not in ("Mora", "Vencido"):
        return 0
    if not isinstance(fecha_vencimiento, date):
        return 0
    delta = (fecha_corte - fecha_vencimiento).days
    return max(0, delta)
