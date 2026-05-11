"""Orquestador del pipeline ETL de FINTECH.

Flujo: extract → load_raw → transform → validate → load_stg →
       load_dq_errors → load_dwh → refresh_views → actualizar etl_runs
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import text

from src.config import FECHA_CORTE_ENV
from src.db import get_connection, get_engine
from src.extract import extract_all
from src.load import (
    load_dq_errors,
    load_dwh,
    load_raw,
    load_staging,
    refresh_materialized_views,
)
from src.logger import get_logger
from src.transform import compute_fecha_corte, transform_all
from src.validate import validate_all


def _register_run_start(conn, run_id: str, started_at: datetime) -> None:
    conn.execute(
        text(
            "INSERT INTO dq.etl_runs (run_id, started_at, status) "
            "VALUES (:run_id, :started_at, 'RUNNING')"
        ),
        {"run_id": run_id, "started_at": started_at},
    )


def _update_run_success(conn, run_id: str, counts: dict, finished_at: datetime) -> None:
    conn.execute(
        text(
            "UPDATE dq.etl_runs SET "
            "status = 'SUCCESS', "
            "finished_at = :finished_at, "
            "filas_raw_clientes = :rc, "
            "filas_raw_creditos = :rcr, "
            "filas_raw_pagos = :rp, "
            "filas_stg_clientes = :sc, "
            "filas_stg_creditos = :scr, "
            "filas_stg_pagos = :sp, "
            "filas_dq_errors = :dq, "
            "filas_dim_cliente = :dc, "
            "filas_fact_credito = :fc, "
            "filas_fact_pago = :fp "
            "WHERE run_id = :run_id"
        ),
        {
            "run_id": run_id,
            "finished_at": finished_at,
            "rc": counts.get("raw_clientes", 0),
            "rcr": counts.get("raw_creditos", 0),
            "rp": counts.get("raw_pagos", 0),
            "sc": counts.get("stg_clientes", 0),
            "scr": counts.get("stg_creditos", 0),
            "sp": counts.get("stg_pagos", 0),
            "dq": counts.get("dq_errors", 0),
            "dc": counts.get("dim_cliente", 0),
            "fc": counts.get("fact_credito", 0),
            "fp": counts.get("fact_pago", 0),
        },
    )


def _update_run_failed(conn, run_id: str, error_msg: str, finished_at: datetime) -> None:
    conn.execute(
        text(
            "UPDATE dq.etl_runs SET status = 'FAILED', "
            "finished_at = :finished_at, error_message = :msg "
            "WHERE run_id = :run_id"
        ),
        {"run_id": run_id, "finished_at": finished_at, "msg": error_msg[:2000]},
    )


def main() -> None:
    """Punto de entrada principal del pipeline ETL."""
    run_id = str(uuid.uuid4())
    logger = get_logger(run_id)
    engine = get_engine()
    started_at = datetime.now(tz=timezone.utc)
    counts: dict = {}

    logger.info("pipeline_start", fecha_corte_env=FECHA_CORTE_ENV)

    with get_connection(engine) as conn:
        _register_run_start(conn, run_id, started_at)

    try:
        # 1. Extract
        logger.info("step_extract_start")
        raw_dfs = extract_all()
        logger.info(
            "step_extract_done",
            clientes=len(raw_dfs["clientes"]),
            creditos=len(raw_dfs["creditos"]),
            pagos=len(raw_dfs["pagos"]),
        )

        # 2. Load raw
        logger.info("step_load_raw_start")
        raw_counts = load_raw(raw_dfs, engine)
        counts.update({f"raw_{k}": v for k, v in raw_counts.items()})
        logger.info("step_load_raw_done", **raw_counts)

        # 3. Transform
        logger.info("step_transform_start")
        transformed_dfs = transform_all(raw_dfs)
        logger.info("step_transform_done")

        # 4. Validate (7 reglas DQ)
        logger.info("step_validate_start")
        valid_dfs, dq_errors_df = validate_all(transformed_dfs, run_id)
        logger.info(
            "step_validate_done",
            dq_errors=len(dq_errors_df),
            clientes_validos=len(valid_dfs["clientes"]),
            creditos_validos=len(valid_dfs["creditos"]),
            pagos_validos=len(valid_dfs["pagos"]),
        )

        # 5. Load DQ errors
        dq_count = load_dq_errors(dq_errors_df, engine)
        counts["dq_errors"] = dq_count
        logger.info("step_load_dq_errors_done", registros=dq_count)

        # 6. Load staging
        logger.info("step_load_staging_start")
        stg_counts = load_staging(valid_dfs, engine)
        counts.update({f"stg_{k}": v for k, v in stg_counts.items()})
        logger.info("step_load_staging_done", **stg_counts)

        # 7. Determinar fecha de corte
        if FECHA_CORTE_ENV == "auto":
            fecha_corte: date = compute_fecha_corte(valid_dfs)
        else:
            fecha_corte = date.fromisoformat(FECHA_CORTE_ENV)
        logger.info("fecha_corte_determinada", fecha_corte=str(fecha_corte))

        # 8. Load DWH
        logger.info("step_load_dwh_start")
        dwh_counts = load_dwh(valid_dfs, engine, fecha_corte)
        counts.update(dwh_counts)
        logger.info("step_load_dwh_done", **dwh_counts)

        # 9. Refresh vistas materializadas (best-effort: no falla el pipeline)
        try:
            logger.info("step_refresh_views_start")
            refresh_materialized_views(engine)
            logger.info("step_refresh_views_done")
        except Exception as refresh_exc:
            logger.warning("step_refresh_views_failed", error=str(refresh_exc))

        # 10. Marcar ejecución como exitosa
        finished_at = datetime.now(tz=timezone.utc)
        with get_connection(engine) as conn:
            _update_run_success(conn, run_id, counts, finished_at)

        elapsed = (finished_at - started_at).total_seconds()
        logger.info("pipeline_success", elapsed_seconds=round(elapsed, 2), **counts)

    except Exception as exc:
        finished_at = datetime.now(tz=timezone.utc)
        logger.exception("pipeline_failed", error=str(exc))
        with get_connection(engine) as conn:
            _update_run_failed(conn, run_id, str(exc), finished_at)
        raise


if __name__ == "__main__":
    main()
