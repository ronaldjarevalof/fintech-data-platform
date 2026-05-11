-- =============================================================================
-- 03_ddl_staging.sql
-- Tablas de staging: datos tipados y limpios, post-normalización DQ-3.
-- Las columnas flag_* corresponden a DQ-7 (duplicados de negocio).
-- Idempotente: seguro ejecutar múltiples veces.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- stg.stg_clientes
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.stg_clientes (
    cliente_id              VARCHAR(20)     NOT NULL,
    tipo_documento          VARCHAR(10)     NOT NULL,
    numero_documento        VARCHAR(50),
    nombres                 VARCHAR(200)    NOT NULL,
    apellidos               VARCHAR(200),
    email                   VARCHAR(200),
    telefono                VARCHAR(30),
    fecha_registro          DATE,
    estado_cliente          VARCHAR(20)     NOT NULL,
    ciudad                  VARCHAR(100),
    segmento                VARCHAR(50),
    fecha_nacimiento        DATE,
    ingresos_mensuales      NUMERIC(18, 2),
    flag_email_duplicado    BOOLEAN         NOT NULL DEFAULT FALSE,
    flag_doc_duplicado      BOOLEAN         NOT NULL DEFAULT FALSE,
    _ingested_at            TIMESTAMPTZ     NOT NULL,
    _source_file            TEXT            NOT NULL,
    CONSTRAINT pk_stg_clientes PRIMARY KEY (cliente_id)
);

-- -----------------------------------------------------------------------------
-- stg.stg_creditos
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.stg_creditos (
    credito_id              VARCHAR(20)     NOT NULL,
    cliente_id              VARCHAR(20)     NOT NULL,
    fecha_solicitud         DATE            NOT NULL,
    fecha_desembolso        DATE,
    monto_aprobado          NUMERIC(18, 2)  NOT NULL,
    plazo_meses             INTEGER         NOT NULL,
    tasa_interes_mensual    NUMERIC(8, 4),
    estado_credito          VARCHAR(30)     NOT NULL,
    producto                VARCHAR(100)    NOT NULL,
    fecha_vencimiento       DATE,
    canal                   VARCHAR(50)     NOT NULL,
    _ingested_at            TIMESTAMPTZ     NOT NULL,
    _source_file            TEXT            NOT NULL,
    CONSTRAINT pk_stg_creditos PRIMARY KEY (credito_id)
);

-- -----------------------------------------------------------------------------
-- stg.stg_pagos
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg.stg_pagos (
    pago_id                     VARCHAR(20)     NOT NULL,
    credito_id                  VARCHAR(20)     NOT NULL,
    fecha_pago                  DATE            NOT NULL,
    monto_pago                  NUMERIC(18, 2)  NOT NULL,
    metodo_pago                 VARCHAR(50)     NOT NULL,
    estado_pago                 VARCHAR(30)     NOT NULL,
    referencia_transaccion      VARCHAR(100),
    flag_referencia_duplicada   BOOLEAN         NOT NULL DEFAULT FALSE,
    _ingested_at                TIMESTAMPTZ     NOT NULL,
    _source_file                TEXT            NOT NULL,
    CONSTRAINT pk_stg_pagos PRIMARY KEY (pago_id)
);
