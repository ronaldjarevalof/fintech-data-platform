"""Carga de datos a las capas raw, stg y dwh de la base de datos.

Estrategia: full-load en cada ejecución.
  raw   → TRUNCATE + INSERT (todos los datos, incluyendo sucios)
  stg   → TRUNCATE + INSERT (solo registros válidos post-DQ)
  dwh   → TRUNCATE + INSERT en orden: dim_tiempo → dims → facts
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy.engine import Engine

from src.config import DIM_TIEMPO_DESDE, DIM_TIEMPO_HASTA
from src.db import get_connection
from src.transform import compute_dias_mora


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

_INTERNAL_COLS = {
    "_estado_cliente_valido", "_estado_credito_valido",
    "_estado_pago_valido", "_tipo_doc_valido",
}


def _drop_internal(df: pd.DataFrame) -> pd.DataFrame:
    """Elimina columnas internas de metadata usadas solo entre módulos."""
    return df.drop(columns=[c for c in _INTERNAL_COLS if c in df.columns])


def _to_sql(df: pd.DataFrame, table: str, schema: str, engine: Engine) -> int:
    """Inserta un DataFrame en la tabla indicada usando to_sql multi.

    Args:
        df: DataFrame a insertar.
        table: Nombre de la tabla destino.
        schema: Esquema PostgreSQL.
        engine: Engine SQLAlchemy.

    Returns:
        Número de filas insertadas.
    """
    if df.empty:
        return 0
    df.to_sql(
        table,
        engine,
        schema=schema,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500,
    )
    return len(df)


def _truncate(conn: Any, full_table: str) -> None:
    from sqlalchemy import text
    conn.execute(text(f"TRUNCATE TABLE {full_table} RESTART IDENTITY CASCADE"))


# ---------------------------------------------------------------------------
# Carga RAW
# ---------------------------------------------------------------------------

def load_raw(
    dfs: dict[str, pd.DataFrame], engine: Engine, run_id: str
) -> dict[str, int]:
    """Trunca las tablas raw y carga todos los datos crudos.

    Args:
        dfs: DataFrames crudos (salida de extract_all).
        engine: Engine SQLAlchemy.
        run_id: UUID de la ejecución.

    Returns:
        Dict con conteo de filas insertadas por entidad.
    """
    counts: dict[str, int] = {}
    with get_connection(engine) as conn:
        for entity, table in (
            ("clientes", "raw.raw_clientes"),
            ("creditos", "raw.raw_creditos"),
            ("pagos", "raw.raw_pagos"),
        ):
            _truncate(conn, table)

    for entity, (table_name, schema) in {
        "clientes": ("raw_clientes", "raw"),
        "creditos": ("raw_creditos", "raw"),
        "pagos": ("raw_pagos", "raw"),
    }.items():
        df = dfs[entity].copy()
        df = _drop_internal(df)
        # Elimina columnas flag_* que no existen en raw
        df = df.drop(columns=[c for c in df.columns if c.startswith("flag_")], errors="ignore")
        counts[entity] = _to_sql(df, table_name, schema, engine)

    return counts


# ---------------------------------------------------------------------------
# Carga STG
# ---------------------------------------------------------------------------

_STG_COLS_CLIENTES = [
    "cliente_id", "tipo_documento", "numero_documento", "nombres", "apellidos",
    "email", "telefono", "fecha_registro", "estado_cliente", "ciudad", "segmento",
    "fecha_nacimiento", "ingresos_mensuales", "flag_email_duplicado",
    "flag_doc_duplicado", "_ingested_at", "_source_file",
]
_STG_COLS_CREDITOS = [
    "credito_id", "cliente_id", "fecha_solicitud", "fecha_desembolso",
    "monto_aprobado", "plazo_meses", "tasa_interes_mensual", "estado_credito",
    "producto", "fecha_vencimiento", "canal", "_ingested_at", "_source_file",
]
_STG_COLS_PAGOS = [
    "pago_id", "credito_id", "fecha_pago", "monto_pago", "metodo_pago",
    "estado_pago", "referencia_transaccion", "flag_referencia_duplicada",
    "_ingested_at", "_source_file",
]


def load_staging(
    dfs: dict[str, pd.DataFrame], engine: Engine
) -> dict[str, int]:
    """Trunca las tablas stg y carga los registros válidos post-DQ.

    Args:
        dfs: DataFrames válidos (salida de validate_all).
        engine: Engine SQLAlchemy.

    Returns:
        Dict con conteo de filas insertadas por entidad.
    """
    counts: dict[str, int] = {}
    with get_connection(engine) as conn:
        for table in ("stg.stg_clientes", "stg.stg_creditos", "stg.stg_pagos"):
            _truncate(conn, table)

    # Clientes
    cl = _drop_internal(dfs["clientes"]).copy()
    if "flag_email_duplicado" not in cl.columns:
        cl["flag_email_duplicado"] = False
    if "flag_doc_duplicado" not in cl.columns:
        cl["flag_doc_duplicado"] = False
    cl_out = cl[[c for c in _STG_COLS_CLIENTES if c in cl.columns]]
    counts["clientes"] = _to_sql(cl_out, "stg_clientes", "stg", engine)

    # Créditos
    cr = _drop_internal(dfs["creditos"]).copy()
    cr_out = cr[[c for c in _STG_COLS_CREDITOS if c in cr.columns]]
    counts["creditos"] = _to_sql(cr_out, "stg_creditos", "stg", engine)

    # Pagos
    pg = _drop_internal(dfs["pagos"]).copy()
    if "flag_referencia_duplicada" not in pg.columns:
        pg["flag_referencia_duplicada"] = False
    pg_out = pg[[c for c in _STG_COLS_PAGOS if c in pg.columns]]
    counts["pagos"] = _to_sql(pg_out, "stg_pagos", "stg", engine)

    return counts


# ---------------------------------------------------------------------------
# Carga DQ errors
# ---------------------------------------------------------------------------

def load_dq_errors(dq_errors_df: pd.DataFrame, engine: Engine) -> int:
    """Inserta los errores de calidad en dq.dq_errors.

    Args:
        dq_errors_df: DataFrame con columnas de error DQ.
        engine: Engine SQLAlchemy.

    Returns:
        Número de registros insertados.
    """
    if dq_errors_df.empty:
        return 0
    return _to_sql(dq_errors_df, "dq_errors", "dq", engine)


# ---------------------------------------------------------------------------
# Generación del calendario para dim_tiempo
# ---------------------------------------------------------------------------

def _colombian_holidays(year: int) -> set[date]:
    """Calcula los festivos colombianos para un año dado.

    Args:
        year: Año a calcular.

    Returns:
        Conjunto de fechas festivas.
    """
    from datetime import timedelta

    def next_monday(d: date) -> date:
        """Ley Emiliani: mueve el festivo al lunes siguiente si no es lunes."""
        days_ahead = (7 - d.weekday()) % 7
        return d if days_ahead == 0 else d + timedelta(days=days_ahead)

    def easter(y: int) -> date:
        """Algoritmo de Meeus/Jones/Butcher para calcular Pascua."""
        a = y % 19
        b = y // 100
        c = y % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return date(y, month, day)

    holidays: set[date] = set()
    td = timedelta

    # Festivos fijos
    holidays |= {
        date(year, 1, 1),   # Año Nuevo
        date(year, 5, 1),   # Día del Trabajo
        date(year, 7, 20),  # Independencia
        date(year, 8, 7),   # Batalla de Boyacá
        date(year, 12, 8),  # Inmaculada Concepción
        date(year, 12, 25), # Navidad
    }

    # Ley Emiliani: lunes siguiente
    holidays |= {
        next_monday(date(year, 1, 6)),   # Reyes Magos
        next_monday(date(year, 3, 19)),  # San José
        next_monday(date(year, 6, 29)),  # San Pedro y San Pablo
        next_monday(date(year, 8, 15)),  # Asunción de la Virgen
        next_monday(date(year, 10, 12)), # Día de la Raza
        next_monday(date(year, 11, 1)),  # Todos los Santos
        next_monday(date(year, 11, 11)), # Independencia de Cartagena
    }

    # Semana Santa y festivos religiosos basados en Pascua
    e = easter(year)
    holidays |= {
        e - td(days=3),                        # Jueves Santo
        e - td(days=2),                        # Viernes Santo
        next_monday(e + td(days=39)),          # Ascensión del Señor
        next_monday(e + td(days=60)),          # Corpus Christi
        next_monday(e + td(days=68)),          # Sagrado Corazón
    }

    return holidays


def _generate_dim_tiempo() -> pd.DataFrame:
    """Genera el DataFrame completo del calendario de dim_tiempo.

    Returns:
        DataFrame con todos los campos de dim_tiempo para el rango
        configurado en DIM_TIEMPO_DESDE / DIM_TIEMPO_HASTA.
    """
    dates = pd.date_range(start=DIM_TIEMPO_DESDE, end=DIM_TIEMPO_HASTA, freq="D")

    nombre_mes_map = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }
    nombre_dia_map = {
        0: "Lunes", 1: "Martes", 2: "Miercoles", 3: "Jueves",
        4: "Viernes", 5: "Sabado", 6: "Domingo",
    }

    years = dates.year.unique()
    all_holidays: set[date] = set()
    for y in years:
        all_holidays |= _colombian_holidays(y)

    rows = []
    for d in dates:
        dt = d.date()
        rows.append({
            "tiempo_sk":    int(d.strftime("%Y%m%d")),
            "fecha":        dt,
            "anio":         d.year,
            "mes":          d.month,
            "dia":          d.day,
            "trimestre":    (d.month - 1) // 3 + 1,
            "semana_anio":  int(d.strftime("%V")),
            "nombre_mes":   nombre_mes_map[d.month],
            "nombre_dia":   nombre_dia_map[d.weekday()],
            "es_fin_semana": d.weekday() >= 5,
            "es_festivo_co": dt in all_holidays,
            "_loaded_at":   datetime.now(tz=timezone.utc),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Carga DWH
# ---------------------------------------------------------------------------

_PRODUCTOS_SEED = [
    ("MICRO", "Microcredito"),
    ("LIBRE_INV", "Libre inversion"),
    ("CAP_TRABAJO", "Capital trabajo"),
    ("CONSUMO", "Consumo"),
]

_CANALES_SEED = [
    ("ALIADO", "Aliado"),
    ("WEB", "Web"),
    ("APP", "App"),
]

_ESTADOS_CREDITO_SEED = [
    # (estado_id, nombre, es_activo, es_mora, es_terminado)
    ("ACTIVO",    "Activo",    True,  False, False),
    ("MORA",      "Mora",      False, True,  False),
    ("VENCIDO",   "Vencido",   False, False, False),
    ("PAGADO",    "Pagado",    False, False, True),
    ("CANCELADO", "Cancelado", False, False, True),
    ("RECHAZADO", "Rechazado", False, False, True),
]

_METODOS_PAGO_SEED = [
    # (metodo_id, nombre, tipo)
    ("PSE",           "PSE",           "digital"),
    ("EFECTY",        "Efecty",        "efectivo"),
    ("TRANSFERENCIA", "Transferencia", "bancario"),
    ("TARJETA",       "Tarjeta",       "digital"),
]

_PRODUCTO_NORM: dict[str, str] = {
    "microcredito":   "MICRO",
    "libre inversion": "LIBRE_INV",
    "capital trabajo": "CAP_TRABAJO",
    "consumo":        "CONSUMO",
}

_CANAL_NORM: dict[str, str] = {
    "aliado": "ALIADO",
    "web":    "WEB",
    "app":    "APP",
}

_ESTADO_CR_NORM: dict[str, str] = {
    "activo":    "ACTIVO",
    "mora":      "MORA",
    "vencido":   "VENCIDO",
    "pagado":    "PAGADO",
    "cancelado": "CANCELADO",
    "rechazado": "RECHAZADO",
}

_METODO_NORM: dict[str, str] = {
    "pse":           "PSE",
    "efecty":        "EFECTY",
    "transferencia": "TRANSFERENCIA",
    "tarjeta":       "TARJETA",
}


def _load_dim_seed(engine: Engine) -> None:
    """Inserta los registros semilla en las dimensiones de baja cardinalidad."""
    loaded_at = datetime.now(tz=timezone.utc)

    pd.DataFrame(
        [{"producto_id": pid, "nombre": n, "_loaded_at": loaded_at}
         for pid, n in _PRODUCTOS_SEED]
    ).to_sql("dim_producto", engine, schema="dwh", if_exists="append",
             index=False, method="multi")

    pd.DataFrame(
        [{"canal_id": cid, "nombre": n, "_loaded_at": loaded_at}
         for cid, n in _CANALES_SEED]
    ).to_sql("dim_canal", engine, schema="dwh", if_exists="append",
             index=False, method="multi")

    pd.DataFrame(
        [{"estado_id": eid, "nombre": n, "es_activo": a, "es_mora": m,
          "es_terminado": t, "_loaded_at": loaded_at}
         for eid, n, a, m, t in _ESTADOS_CREDITO_SEED]
    ).to_sql("dim_estado_credito", engine, schema="dwh", if_exists="append",
             index=False, method="multi")

    pd.DataFrame(
        [{"metodo_id": mid, "nombre": n, "tipo": tp, "_loaded_at": loaded_at}
         for mid, n, tp in _METODOS_PAGO_SEED]
    ).to_sql("dim_metodo_pago", engine, schema="dwh", if_exists="append",
             index=False, method="multi")


def _fetch_sk_map(engine: Engine, table: str, id_col: str, sk_col: str) -> dict[str, int]:
    """Carga un mapa {id_negocio → sk} desde una tabla de dimensión.

    Args:
        engine: Engine SQLAlchemy.
        table: Nombre completo de la tabla (schema.tabla).
        id_col: Columna de clave de negocio.
        sk_col: Columna de clave subrogada.

    Returns:
        Diccionario de lookup.
    """
    with engine.connect() as conn:
        from sqlalchemy import text
        rows = conn.execute(
            text(f"SELECT {id_col}, {sk_col} FROM {table}")
        ).fetchall()
    return {str(r[0]): int(r[1]) for r in rows}


def load_dwh(
    dfs: dict[str, pd.DataFrame],
    engine: Engine,
    fecha_corte: date,
) -> dict[str, int]:
    """Carga completa del modelo dimensional (truncate + insert).

    Orden de carga:
      1. Truncar hechos (primero por FK)
      2. Truncar y recargar dimensiones
      3. Cargar hechos con lookups de SK

    Args:
        dfs: DataFrames válidos post-DQ (salida de validate_all).
        engine: Engine SQLAlchemy.
        fecha_corte: Fecha para cálculo de días de mora.

    Returns:
        Dict con conteo de filas insertadas por tabla.
    """
    counts: dict[str, int] = {}
    loaded_at = datetime.now(tz=timezone.utc)

    # 1. Truncar en orden correcto (facts → dims)
    with get_connection(engine) as conn:
        for table in (
            "dwh.fact_pago",
            "dwh.fact_credito",
            "dwh.dim_cliente",
            "dwh.dim_producto",
            "dwh.dim_canal",
            "dwh.dim_estado_credito",
            "dwh.dim_metodo_pago",
            "dwh.dim_tiempo",
        ):
            _truncate(conn, table)

    # 2. dim_tiempo
    dt_df = _generate_dim_tiempo()
    counts["dim_tiempo"] = _to_sql(dt_df, "dim_tiempo", "dwh", engine)

    # 3. Dimensiones semilla
    _load_dim_seed(engine)

    # 4. dim_cliente
    cl = _drop_internal(dfs["clientes"]).copy()
    cl["_loaded_at"] = loaded_at
    dim_cl_cols = [
        "cliente_id", "tipo_documento", "numero_documento", "nombres",
        "apellidos", "email", "telefono", "fecha_registro", "estado_cliente",
        "ciudad", "segmento", "fecha_nacimiento", "ingresos_mensuales",
        "flag_email_duplicado", "flag_doc_duplicado", "_loaded_at",
    ]
    if "flag_email_duplicado" not in cl.columns:
        cl["flag_email_duplicado"] = False
    if "flag_doc_duplicado" not in cl.columns:
        cl["flag_doc_duplicado"] = False
    counts["dim_cliente"] = _to_sql(
        cl[[c for c in dim_cl_cols if c in cl.columns]],
        "dim_cliente", "dwh", engine,
    )

    # 5. Lookups de SK
    cliente_sk_map = _fetch_sk_map(engine, "dwh.dim_cliente", "cliente_id", "cliente_sk")
    producto_sk_map = _fetch_sk_map(engine, "dwh.dim_producto", "producto_id", "producto_sk")
    canal_sk_map = _fetch_sk_map(engine, "dwh.dim_canal", "canal_id", "canal_sk")
    estado_cr_sk_map = _fetch_sk_map(
        engine, "dwh.dim_estado_credito", "estado_id", "estado_credito_sk"
    )
    metodo_sk_map = _fetch_sk_map(
        engine, "dwh.dim_metodo_pago", "metodo_id", "metodo_pago_sk"
    )

    # 6. fact_credito
    cr = _drop_internal(dfs["creditos"]).copy()
    cr["cliente_sk"] = cr["cliente_id"].map(cliente_sk_map)
    cr["producto_sk"] = cr["producto"].str.lower().map(
        lambda v: producto_sk_map.get(_PRODUCTO_NORM.get(v, ""), None)
    )
    cr["canal_sk"] = cr["canal"].str.lower().map(
        lambda v: canal_sk_map.get(_CANAL_NORM.get(v, ""), None)
    )
    cr["estado_credito_sk"] = cr["estado_credito"].str.lower().map(
        lambda v: estado_cr_sk_map.get(_ESTADO_CR_NORM.get(v, ""), None)
    )
    cr["tiempo_solicitud_sk"] = cr["fecha_solicitud"].apply(
        lambda d: int(d.strftime("%Y%m%d")) if isinstance(d, date) else None
    )
    cr["tiempo_desembolso_sk"] = cr["fecha_desembolso"].apply(
        lambda d: int(d.strftime("%Y%m%d")) if isinstance(d, date) else None
    )
    cr["tiempo_vencimiento_sk"] = cr["fecha_vencimiento"].apply(
        lambda d: int(d.strftime("%Y%m%d")) if isinstance(d, date) else None
    )
    cr["dias_mora"] = cr.apply(
        lambda row: compute_dias_mora(
            row["estado_credito"], row["fecha_vencimiento"], fecha_corte
        ),
        axis=1,
    )
    cr["_loaded_at"] = loaded_at

    fact_cr_cols = [
        "credito_id", "cliente_sk", "producto_sk", "canal_sk",
        "estado_credito_sk", "tiempo_solicitud_sk", "tiempo_desembolso_sk",
        "tiempo_vencimiento_sk", "monto_aprobado", "plazo_meses",
        "tasa_interes_mensual", "dias_mora", "_loaded_at",
    ]
    # Descartar filas con SK nulo (no debería ocurrir post-DQ, pero defensivo)
    cr_fact = cr.dropna(subset=["cliente_sk", "producto_sk", "canal_sk", "estado_credito_sk"])
    counts["fact_credito"] = _to_sql(
        cr_fact[[c for c in fact_cr_cols if c in cr_fact.columns]],
        "fact_credito", "dwh", engine,
    )

    # Mapa credito_id → cliente_sk (para fact_pago)
    credito_cliente_map: dict[str, int] = dict(
        zip(cr["credito_id"], cr["cliente_sk"])
    )

    # 7. fact_pago
    pg = _drop_internal(dfs["pagos"]).copy()
    pg["cliente_sk"] = pg["credito_id"].map(credito_cliente_map)
    pg["metodo_pago_sk"] = pg["metodo_pago"].str.lower().map(
        lambda v: metodo_sk_map.get(_METODO_NORM.get(v, ""), None)
    )
    pg["tiempo_pago_sk"] = pg["fecha_pago"].apply(
        lambda d: int(d.strftime("%Y%m%d")) if isinstance(d, date) else None
    )
    pg["_loaded_at"] = loaded_at
    if "flag_referencia_duplicada" not in pg.columns:
        pg["flag_referencia_duplicada"] = False

    fact_pg_cols = [
        "pago_id", "credito_id", "cliente_sk", "metodo_pago_sk",
        "tiempo_pago_sk", "monto_pago", "estado_pago",
        "referencia_transaccion", "flag_referencia_duplicada", "_loaded_at",
    ]
    pg_fact = pg.dropna(subset=["cliente_sk", "metodo_pago_sk", "tiempo_pago_sk"])
    counts["fact_pago"] = _to_sql(
        pg_fact[[c for c in fact_pg_cols if c in pg_fact.columns]],
        "fact_pago", "dwh", engine,
    )

    return counts


# ---------------------------------------------------------------------------
# Refresco de vistas materializadas
# ---------------------------------------------------------------------------

def refresh_materialized_views(engine: Engine) -> None:
    """Refresca las vistas materializadas del esquema bi.

    Args:
        engine: Engine SQLAlchemy.
    """
    with get_connection(engine) as conn:
        from sqlalchemy import text
        conn.execute(text("REFRESH MATERIALIZED VIEW bi.vw_cosecha_morosidad"))
        conn.execute(text("REFRESH MATERIALIZED VIEW bi.vw_kpi_resumen"))
