-- =============================================================================
-- 06_indices.sql
-- Estrategia de índices: FKs en tablas de hechos, columnas de filtro frecuente
-- y business keys en staging. No indexar PKs (cubiertas por UNIQUE/PK).
-- Idempotente: seguro ejecutar múltiples veces.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- fact_credito: FKs y columnas de filtro analítico habitual
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_fact_credito_cliente_sk
    ON dwh.fact_credito (cliente_sk);

CREATE INDEX IF NOT EXISTS idx_fact_credito_producto_sk
    ON dwh.fact_credito (producto_sk);

CREATE INDEX IF NOT EXISTS idx_fact_credito_canal_sk
    ON dwh.fact_credito (canal_sk);

CREATE INDEX IF NOT EXISTS idx_fact_credito_estado_sk
    ON dwh.fact_credito (estado_credito_sk);

CREATE INDEX IF NOT EXISTS idx_fact_credito_t_solicitud
    ON dwh.fact_credito (tiempo_solicitud_sk);

CREATE INDEX IF NOT EXISTS idx_fact_credito_t_desembolso
    ON dwh.fact_credito (tiempo_desembolso_sk);

-- -----------------------------------------------------------------------------
-- fact_pago: FKs y credito_id (dimensión degenerada muy consultada)
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_fact_pago_cliente_sk
    ON dwh.fact_pago (cliente_sk);

CREATE INDEX IF NOT EXISTS idx_fact_pago_metodo_sk
    ON dwh.fact_pago (metodo_pago_sk);

CREATE INDEX IF NOT EXISTS idx_fact_pago_tiempo_sk
    ON dwh.fact_pago (tiempo_pago_sk);

CREATE INDEX IF NOT EXISTS idx_fact_pago_credito_id
    ON dwh.fact_pago (credito_id);

CREATE INDEX IF NOT EXISTS idx_fact_pago_estado
    ON dwh.fact_pago (estado_pago);

-- -----------------------------------------------------------------------------
-- dim_cliente: business key y columnas de filtro BI
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_dim_cliente_segmento
    ON dwh.dim_cliente (segmento);

CREATE INDEX IF NOT EXISTS idx_dim_cliente_ciudad
    ON dwh.dim_cliente (ciudad);

-- -----------------------------------------------------------------------------
-- dim_tiempo: filtros por período
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_dim_tiempo_anio_mes
    ON dwh.dim_tiempo (anio, mes);

-- -----------------------------------------------------------------------------
-- dq: búsqueda por ejecución y por regla
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_dq_errors_run_id
    ON dq.dq_errors (run_id);

CREATE INDEX IF NOT EXISTS idx_dq_errors_regla_id
    ON dq.dq_errors (regla_id);

-- -----------------------------------------------------------------------------
-- raw: business keys para diagnóstico rápido post-carga
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_raw_clientes_cliente_id
    ON raw.raw_clientes (cliente_id);

CREATE INDEX IF NOT EXISTS idx_raw_creditos_credito_id
    ON raw.raw_creditos (credito_id);

CREATE INDEX IF NOT EXISTS idx_raw_pagos_pago_id
    ON raw.raw_pagos (pago_id);
