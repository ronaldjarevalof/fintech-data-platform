-- =============================================================================
-- 05_ddl_dq.sql
-- Tablas de calidad de datos y registro de ejecuciones ETL
-- Idempotente: seguro ejecutar múltiples veces
-- =============================================================================

-- -----------------------------------------------------------------------------
-- dq.dq_errors
-- Registro de cada violación de regla de calidad.
-- payload_original almacena la fila cruda como JSONB para auditoría completa.
-- NUNCA se descarta silenciosamente: todo registro inválido llega aquí.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dq.dq_errors (
    error_id            BIGSERIAL,
    run_id              UUID        NOT NULL,
    regla_id            VARCHAR(10) NOT NULL,   -- DQ-1 … DQ-7
    tabla_origen        VARCHAR(50) NOT NULL,
    severidad           VARCHAR(10) NOT NULL,
    motivo              TEXT        NOT NULL,
    payload_original    JSONB       NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_dq_errors PRIMARY KEY (error_id),
    CONSTRAINT chk_dq_errors_severidad CHECK (severidad IN ('ERROR', 'WARNING'))
);

-- -----------------------------------------------------------------------------
-- dq.etl_runs
-- Una fila por ejecución del pipeline con conteos y estado final.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dq.etl_runs (
    run_id                  UUID        NOT NULL,
    started_at              TIMESTAMPTZ NOT NULL,
    finished_at             TIMESTAMPTZ,
    status                  VARCHAR(10) NOT NULL DEFAULT 'RUNNING',
    filas_raw_clientes      INTEGER,
    filas_raw_creditos      INTEGER,
    filas_raw_pagos         INTEGER,
    filas_stg_clientes      INTEGER,
    filas_stg_creditos      INTEGER,
    filas_stg_pagos         INTEGER,
    filas_dq_errors         INTEGER,
    filas_dim_cliente       INTEGER,
    filas_fact_credito      INTEGER,
    filas_fact_pago         INTEGER,
    error_message           TEXT,
    CONSTRAINT pk_etl_runs PRIMARY KEY (run_id),
    CONSTRAINT chk_etl_runs_status CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED'))
);
