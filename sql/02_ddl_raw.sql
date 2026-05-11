-- =============================================================================
-- 02_ddl_raw.sql
-- Tablas de ingesta cruda: almacenan filas exactamente como vienen del CSV.
-- Todos los campos de negocio son TEXT para evitar rechazos por tipo durante
-- la carga. La validación y el casteo ocurren en la capa stg.
-- Idempotente: seguro ejecutar múltiples veces.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- raw.raw_clientes
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.raw_clientes (
    _raw_id             BIGSERIAL,
    cliente_id          TEXT,
    tipo_documento      TEXT,
    numero_documento    TEXT,
    nombres             TEXT,
    apellidos           TEXT,
    email               TEXT,
    telefono            TEXT,
    fecha_registro      TEXT,
    estado_cliente      TEXT,
    ciudad              TEXT,
    segmento            TEXT,
    fecha_nacimiento    TEXT,
    ingresos_mensuales  TEXT,
    _ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _source_file        TEXT        NOT NULL,
    CONSTRAINT pk_raw_clientes PRIMARY KEY (_raw_id)
);

-- -----------------------------------------------------------------------------
-- raw.raw_creditos
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.raw_creditos (
    _raw_id                 BIGSERIAL,
    credito_id              TEXT,
    cliente_id              TEXT,
    fecha_solicitud         TEXT,
    fecha_desembolso        TEXT,
    monto_aprobado          TEXT,
    plazo_meses             TEXT,
    tasa_interes_mensual    TEXT,
    estado_credito          TEXT,
    producto                TEXT,
    fecha_vencimiento       TEXT,
    canal                   TEXT,
    _ingested_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _source_file            TEXT        NOT NULL,
    CONSTRAINT pk_raw_creditos PRIMARY KEY (_raw_id)
);

-- -----------------------------------------------------------------------------
-- raw.raw_pagos
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.raw_pagos (
    _raw_id                  BIGSERIAL,
    pago_id                  TEXT,
    credito_id               TEXT,
    fecha_pago               TEXT,
    monto_pago               TEXT,
    metodo_pago              TEXT,
    estado_pago              TEXT,
    referencia_transaccion   TEXT,
    _ingested_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _source_file             TEXT        NOT NULL,
    CONSTRAINT pk_raw_pagos PRIMARY KEY (_raw_id)
);
