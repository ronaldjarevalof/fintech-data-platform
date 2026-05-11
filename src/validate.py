"""Validación de calidad de datos: implementa las 7 reglas DQ definidas.

Estrategias de tratamiento:
  - Corregir  → ya aplicado en transform.py
  - Marcar    → flag_* = True en el registro; el registro ENTRA al modelo
  - Aislar    → el registro NO entra al modelo; va a dq_errors con payload JSONB

Regla de oro: nunca descartar silenciosamente. Todo error queda en dq_errors.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_payload(row: pd.Series) -> dict[str, Any]:
    """Serializa una fila a dict JSON-serializable para payload_original."""
    result: dict[str, Any] = {}
    for k, v in row.items():
        if pd.isna(v) if not isinstance(v, (list, dict)) else False:
            result[k] = None
        elif isinstance(v, date):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


def _build_error(
    run_id: str,
    regla_id: str,
    tabla_origen: str,
    severidad: str,
    motivo: str,
    row: pd.Series,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "regla_id": regla_id,
        "tabla_origen": tabla_origen,
        "severidad": severidad,
        "motivo": motivo,
        "payload_original": json.dumps(_row_to_payload(row), default=str),
    }


# ---------------------------------------------------------------------------
# DQ-1: Unicidad de PK (cliente_id, credito_id, pago_id)
# Acción: Aislar duplicados (conservar primera aparición)
# ---------------------------------------------------------------------------

def dq1_pk_uniqueness(
    dfs: dict[str, pd.DataFrame], run_id: str
) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    """Detecta y aísla filas con PK duplicada en cada entidad.

    Args:
        dfs: DataFrames transformados.
        run_id: ID de la ejecución actual.

    Returns:
        Tupla (dfs_validos, errores).
    """
    pk_map = {"clientes": "cliente_id", "creditos": "credito_id", "pagos": "pago_id"}
    tabla_map = {"clientes": "raw_clientes", "creditos": "raw_creditos", "pagos": "raw_pagos"}
    valid: dict[str, pd.DataFrame] = {}
    errors: list[dict] = []

    for entity, pk_col in pk_map.items():
        df = dfs[entity]
        is_dup = df.duplicated(subset=[pk_col], keep="first")
        dup_df = df[is_dup]
        for _, row in dup_df.iterrows():
            errors.append(
                _build_error(
                    run_id, "DQ-1", tabla_map[entity], "ERROR",
                    f"{pk_col} duplicado: {row[pk_col]}", row,
                )
            )
        valid[entity] = df[~is_dup].copy()

    return valid, errors


# ---------------------------------------------------------------------------
# DQ-2: Integridad referencial
# creditos → clientes; pagos → creditos
# Acción: Aislar huérfanos
# ---------------------------------------------------------------------------

def dq2_referential_integrity(
    dfs: dict[str, pd.DataFrame], run_id: str
) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    """Detecta y aísla registros con FK que no tiene entidad padre.

    Args:
        dfs: DataFrames post-DQ1 (PKs ya deduplicadas).
        run_id: ID de la ejecución actual.

    Returns:
        Tupla (dfs_validos, errores).
    """
    valid_cliente_ids = set(dfs["clientes"]["cliente_id"].dropna())
    valid_credito_ids = set(dfs["creditos"]["credito_id"].dropna())
    errors: list[dict] = []

    # Créditos sin cliente válido
    creditos = dfs["creditos"]
    orphan_cr = ~creditos["cliente_id"].isin(valid_cliente_ids)
    for _, row in creditos[orphan_cr].iterrows():
        errors.append(
            _build_error(
                run_id, "DQ-2", "raw_creditos", "ERROR",
                f"cliente_id huérfano: {row['cliente_id']}", row,
            )
        )
    creditos_clean = creditos[~orphan_cr].copy()

    # Pagos sin crédito válido
    pagos = dfs["pagos"]
    valid_credito_ids_after = set(creditos_clean["credito_id"].dropna())
    orphan_pg = ~pagos["credito_id"].isin(valid_credito_ids_after)
    for _, row in pagos[orphan_pg].iterrows():
        errors.append(
            _build_error(
                run_id, "DQ-2", "raw_pagos", "ERROR",
                f"credito_id huérfano: {row['credito_id']}", row,
            )
        )
    pagos_clean = pagos[~orphan_pg].copy()

    return {
        "clientes": dfs["clientes"],
        "creditos": creditos_clean,
        "pagos": pagos_clean,
    }, errors


# ---------------------------------------------------------------------------
# DQ-3: Normalización de catálogos (valores no mapeables)
# La corrección ya ocurrió en transform.py; aquí se aíslan los no mapeables.
# Acción: Aislar registros con estado no reconocido
# ---------------------------------------------------------------------------

def dq3_catalog_normalization(
    dfs: dict[str, pd.DataFrame], run_id: str
) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    """Aísla registros cuyos valores de catálogo no pudieron normalizarse.

    Args:
        dfs: DataFrames post-DQ2.
        run_id: ID de la ejecución actual.

    Returns:
        Tupla (dfs_validos, errores).
    """
    errors: list[dict] = []

    # Clientes: estado_cliente inválido
    cl = dfs["clientes"]
    inv_cl = cl.get("_estado_cliente_valido", pd.Series(True, index=cl.index)) == False  # noqa: E712
    for _, row in cl[inv_cl].iterrows():
        errors.append(
            _build_error(
                run_id, "DQ-3", "raw_clientes", "WARNING",
                f"estado_cliente no reconocido: '{row['estado_cliente']}'", row,
            )
        )

    # Créditos: estado_credito inválido
    cr = dfs["creditos"]
    inv_cr = cr.get("_estado_credito_valido", pd.Series(True, index=cr.index)) == False  # noqa: E712
    for _, row in cr[inv_cr].iterrows():
        errors.append(
            _build_error(
                run_id, "DQ-3", "raw_creditos", "ERROR",
                f"estado_credito no reconocido: '{row['estado_credito']}'", row,
            )
        )

    # Pagos: estado_pago inválido
    pg = dfs["pagos"]
    inv_pg = pg.get("_estado_pago_valido", pd.Series(True, index=pg.index)) == False  # noqa: E712
    for _, row in pg[inv_pg].iterrows():
        errors.append(
            _build_error(
                run_id, "DQ-3", "raw_pagos", "WARNING",
                f"estado_pago no reconocido: '{row['estado_pago']}'", row,
            )
        )

    return {
        "clientes": cl[~inv_cl].copy(),
        "creditos": cr[~inv_cr].copy(),
        "pagos": pg[~inv_pg].copy(),
    }, errors


# ---------------------------------------------------------------------------
# DQ-4: Validación de dominio numérico
# monto_aprobado > 0, plazo_meses > 0, tasa 0–10%, monto_pago > 0
# Acción: Aislar fuera de rango
# ---------------------------------------------------------------------------

def dq4_domain_values(
    dfs: dict[str, pd.DataFrame], run_id: str
) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    """Aísla registros con valores numéricos fuera del dominio válido.

    Args:
        dfs: DataFrames post-DQ3.
        run_id: ID de la ejecución actual.

    Returns:
        Tupla (dfs_validos, errores).
    """
    errors: list[dict] = []

    # Créditos
    cr = dfs["creditos"].copy()
    bad_cr = (
        cr["monto_aprobado"].apply(lambda v: v is None or (isinstance(v, float) and v <= 0))
        | cr["plazo_meses"].apply(lambda v: v is None or (isinstance(v, (int, float)) and v <= 0))
        | cr["tasa_interes_mensual"].apply(
            lambda v: isinstance(v, float) and not (0 <= v <= 10)
        )
    )
    for _, row in cr[bad_cr].iterrows():
        motivo_parts = []
        if row["monto_aprobado"] is None or (isinstance(row["monto_aprobado"], float) and row["monto_aprobado"] <= 0):
            motivo_parts.append(f"monto_aprobado={row['monto_aprobado']}")
        if row["plazo_meses"] is None or (isinstance(row["plazo_meses"], (int, float)) and row["plazo_meses"] <= 0):
            motivo_parts.append(f"plazo_meses={row['plazo_meses']}")
        if isinstance(row["tasa_interes_mensual"], float) and not (0 <= row["tasa_interes_mensual"] <= 10):
            motivo_parts.append(f"tasa={row['tasa_interes_mensual']}")
        errors.append(
            _build_error(
                run_id, "DQ-4", "raw_creditos", "ERROR",
                "Valor fuera de dominio: " + "; ".join(motivo_parts), row,
            )
        )
    cr_clean = cr[~bad_cr].copy()

    # Pagos
    pg = dfs["pagos"].copy()
    bad_pg = pg["monto_pago"].apply(
        lambda v: v is None or (isinstance(v, float) and v <= 0)
    )
    for _, row in pg[bad_pg].iterrows():
        errors.append(
            _build_error(
                run_id, "DQ-4", "raw_pagos", "ERROR",
                f"monto_pago fuera de dominio: {row['monto_pago']}", row,
            )
        )
    pg_clean = pg[~bad_pg].copy()

    return {"clientes": dfs["clientes"], "creditos": cr_clean, "pagos": pg_clean}, errors


# ---------------------------------------------------------------------------
# DQ-5: Coherencia temporal
# fecha_desembolso >= fecha_solicitud, fecha_vencimiento >= fecha_desembolso
# También captura fechas inválidas (None por parse fallido)
# Acción: Aislar inconsistencias
# ---------------------------------------------------------------------------

def dq5_temporal_coherence(
    dfs: dict[str, pd.DataFrame], run_id: str
) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    """Aísla créditos con fechas incoherentes o inválidas.

    Args:
        dfs: DataFrames post-DQ4.
        run_id: ID de la ejecución actual.

    Returns:
        Tupla (dfs_validos, errores).
    """
    errors: list[dict] = []
    cr = dfs["creditos"]
    bad_rows: list[int] = []

    for idx, row in cr.iterrows():
        f_sol = row["fecha_solicitud"]
        f_des = row["fecha_desembolso"]
        f_venc = row["fecha_vencimiento"]
        motivo_parts = []

        if not isinstance(f_sol, date):
            motivo_parts.append("fecha_solicitud inválida o nula")
        if isinstance(f_des, date) and isinstance(f_sol, date) and f_des < f_sol:
            motivo_parts.append(
                f"fecha_desembolso ({f_des}) < fecha_solicitud ({f_sol})"
            )
        if isinstance(f_venc, date) and isinstance(f_des, date) and f_venc < f_des:
            motivo_parts.append(
                f"fecha_vencimiento ({f_venc}) < fecha_desembolso ({f_des})"
            )

        if motivo_parts:
            errors.append(
                _build_error(
                    run_id, "DQ-5", "raw_creditos", "ERROR",
                    "; ".join(motivo_parts), row,
                )
            )
            bad_rows.append(idx)

    # Pagos: fecha_pago inválida (parse fallido → None)
    pg = dfs["pagos"]
    bad_pg_idx: list[int] = []
    for idx, row in pg.iterrows():
        if not isinstance(row["fecha_pago"], date):
            errors.append(
                _build_error(
                    run_id, "DQ-5", "raw_pagos", "ERROR",
                    f"fecha_pago inválida: '{row.get('fecha_pago')}'", row,
                )
            )
            bad_pg_idx.append(idx)

    return {
        "clientes": dfs["clientes"],
        "creditos": cr.drop(index=bad_rows).copy(),
        "pagos": pg.drop(index=bad_pg_idx).copy(),
    }, errors


# ---------------------------------------------------------------------------
# DQ-6: No nulidad de campos críticos
# Créditos: fecha_solicitud, monto_aprobado (ya cubierto DQ-4/5)
# Créditos: tasa_interes_mensual nula
# Pagos: monto_pago, fecha_pago, credito_id
# Acción: Aislar registros incompletos
# ---------------------------------------------------------------------------

def dq6_not_null_critical(
    dfs: dict[str, pd.DataFrame], run_id: str
) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    """Aísla registros con campos críticos nulos.

    Args:
        dfs: DataFrames post-DQ5.
        run_id: ID de la ejecución actual.

    Returns:
        Tupla (dfs_validos, errores).
    """
    errors: list[dict] = []

    # Créditos: tasa_interes_mensual nula (H9)
    cr = dfs["creditos"]
    bad_cr = cr["tasa_interes_mensual"].isna()
    for _, row in cr[bad_cr].iterrows():
        errors.append(
            _build_error(
                run_id, "DQ-6", "raw_creditos", "ERROR",
                "tasa_interes_mensual nula", row,
            )
        )
    cr_clean = cr[~bad_cr].copy()

    # Pagos: credito_id vacío (edge case defensivo)
    pg = dfs["pagos"]
    bad_pg = pg["credito_id"].apply(lambda v: not v or str(v).strip() == "")
    for _, row in pg[bad_pg].iterrows():
        errors.append(
            _build_error(
                run_id, "DQ-6", "raw_pagos", "ERROR",
                "credito_id nulo o vacío", row,
            )
        )
    pg_clean = pg[~bad_pg].copy()

    return {"clientes": dfs["clientes"], "creditos": cr_clean, "pagos": pg_clean}, errors


# ---------------------------------------------------------------------------
# DQ-7: Duplicados de negocio (email cliente, referencia pago)
# Acción: Marcar con flag (el registro ENTRA al modelo)
# También detecta numero_documento duplicado → flag_doc_duplicado
# ---------------------------------------------------------------------------

def dq7_business_duplicates(
    dfs: dict[str, pd.DataFrame], run_id: str
) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    """Detecta duplicados de negocio y marca los registros con flags.

    Los registros marcados SÍ entran al modelo pero quedan registrados
    en dq_errors para auditoría.

    Args:
        dfs: DataFrames post-DQ6.
        run_id: ID de la ejecución actual.

    Returns:
        Tupla (dfs_con_flags, errores). Los DataFrames llevan flag_* activados.
    """
    errors: list[dict] = []

    # -- Clientes: email duplicado --
    cl = dfs["clientes"].copy()
    cl["flag_email_duplicado"] = False
    cl["flag_doc_duplicado"] = False

    email_dup = cl["email"].apply(lambda v: bool(v) and str(v).strip() != "")
    email_counts = cl.loc[email_dup, "email"].value_counts()
    dup_emails = set(email_counts[email_counts > 1].index)
    if dup_emails:
        mask = cl["email"].isin(dup_emails)
        cl.loc[mask, "flag_email_duplicado"] = True
        for _, row in cl[mask].iterrows():
            errors.append(
                _build_error(
                    run_id, "DQ-7", "raw_clientes", "WARNING",
                    f"email duplicado: {row['email']}", row,
                )
            )

    # -- Clientes: numero_documento duplicado (H3) --
    doc_valid = cl["numero_documento"].apply(lambda v: bool(v) and str(v).strip() != "")
    doc_counts = cl.loc[doc_valid, "numero_documento"].value_counts()
    dup_docs = set(doc_counts[doc_counts > 1].index)
    if dup_docs:
        mask_doc = cl["numero_documento"].isin(dup_docs)
        cl.loc[mask_doc, "flag_doc_duplicado"] = True
        for _, row in cl[mask_doc].iterrows():
            errors.append(
                _build_error(
                    run_id, "DQ-7", "raw_clientes", "WARNING",
                    f"numero_documento duplicado: {row['numero_documento']}", row,
                )
            )

    # -- Pagos: referencia_transaccion duplicada --
    pg = dfs["pagos"].copy()
    pg["flag_referencia_duplicada"] = False
    ref_valid = pg["referencia_transaccion"].apply(
        lambda v: bool(v) and str(v).strip() != ""
    )
    ref_counts = pg.loc[ref_valid, "referencia_transaccion"].value_counts()
    dup_refs = set(ref_counts[ref_counts > 1].index)
    if dup_refs:
        mask_ref = pg["referencia_transaccion"].isin(dup_refs)
        pg.loc[mask_ref, "flag_referencia_duplicada"] = True
        for _, row in pg[mask_ref].iterrows():
            errors.append(
                _build_error(
                    run_id, "DQ-7", "raw_pagos", "WARNING",
                    f"referencia_transaccion duplicada: {row['referencia_transaccion']}", row,
                )
            )

    return {"clientes": cl, "creditos": dfs["creditos"], "pagos": pg}, errors


# ---------------------------------------------------------------------------
# Orquestador de validaciones
# ---------------------------------------------------------------------------

def validate_all(
    dfs: dict[str, pd.DataFrame], run_id: str
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Aplica las 7 reglas DQ en secuencia y consolida los errores.

    Orden de aplicación:
      DQ-1 → DQ-2 → DQ-3 → DQ-4 → DQ-5 → DQ-6 → DQ-7

    Args:
        dfs: DataFrames transformados (salida de transform_all).
        run_id: UUID de la ejecución actual.

    Returns:
        Tupla (dfs_validos, dq_errors_df) donde dq_errors_df tiene las
        columnas run_id, regla_id, tabla_origen, severidad, motivo,
        payload_original.
    """
    all_errors: list[dict] = []

    dfs, errs = dq1_pk_uniqueness(dfs, run_id)
    all_errors.extend(errs)

    dfs, errs = dq2_referential_integrity(dfs, run_id)
    all_errors.extend(errs)

    dfs, errs = dq3_catalog_normalization(dfs, run_id)
    all_errors.extend(errs)

    dfs, errs = dq4_domain_values(dfs, run_id)
    all_errors.extend(errs)

    dfs, errs = dq5_temporal_coherence(dfs, run_id)
    all_errors.extend(errs)

    dfs, errs = dq6_not_null_critical(dfs, run_id)
    all_errors.extend(errs)

    dfs, errs = dq7_business_duplicates(dfs, run_id)
    all_errors.extend(errs)

    dq_errors_df = pd.DataFrame(all_errors) if all_errors else pd.DataFrame(
        columns=["run_id", "regla_id", "tabla_origen", "severidad", "motivo", "payload_original"]
    )

    return dfs, dq_errors_df
