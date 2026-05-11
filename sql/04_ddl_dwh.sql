-- =============================================================================
-- 04_ddl_dwh.sql
-- Modelo dimensional estrella: 6 dimensiones + 2 tablas de hechos.
-- SCD-1 en todas las dimensiones. Llaves subrogadas (_sk) BIGSERIAL.
-- Idempotente: seguro ejecutar múltiples veces.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- dwh.dim_tiempo  (calendario 2023-01-01 → 2027-12-31, precargada por el ETL)
-- tiempo_sk = YYYYMMDD (integer para joins rápidos sin índice de búsqueda)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_tiempo (
    tiempo_sk       INTEGER         NOT NULL,
    fecha           DATE            NOT NULL,
    anio            SMALLINT        NOT NULL,
    mes             SMALLINT        NOT NULL,
    dia             SMALLINT        NOT NULL,
    trimestre       SMALLINT        NOT NULL,
    semana_anio     SMALLINT        NOT NULL,
    nombre_mes      VARCHAR(20)     NOT NULL,
    nombre_dia      VARCHAR(20)     NOT NULL,
    es_fin_semana   BOOLEAN         NOT NULL,
    es_festivo_co   BOOLEAN         NOT NULL,
    _loaded_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_dim_tiempo    PRIMARY KEY (tiempo_sk),
    CONSTRAINT uq_dim_tiempo_fecha UNIQUE (fecha)
);

-- -----------------------------------------------------------------------------
-- dwh.dim_cliente
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_cliente (
    cliente_sk              BIGSERIAL,
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
    _loaded_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_dim_cliente       PRIMARY KEY (cliente_sk),
    CONSTRAINT uq_dim_cliente_id    UNIQUE (cliente_id)
);

-- -----------------------------------------------------------------------------
-- dwh.dim_producto  (baja cardinalidad, seed insertado por el ETL)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_producto (
    producto_sk     BIGSERIAL,
    producto_id     VARCHAR(30)     NOT NULL,
    nombre          VARCHAR(100)    NOT NULL,
    _loaded_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_dim_producto      PRIMARY KEY (producto_sk),
    CONSTRAINT uq_dim_producto_id   UNIQUE (producto_id)
);

-- -----------------------------------------------------------------------------
-- dwh.dim_canal  (baja cardinalidad, seed insertado por el ETL)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_canal (
    canal_sk        BIGSERIAL,
    canal_id        VARCHAR(20)     NOT NULL,
    nombre          VARCHAR(50)     NOT NULL,
    _loaded_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_dim_canal         PRIMARY KEY (canal_sk),
    CONSTRAINT uq_dim_canal_id      UNIQUE (canal_id)
);

-- -----------------------------------------------------------------------------
-- dwh.dim_estado_credito  (baja cardinalidad, seed insertado por el ETL)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_estado_credito (
    estado_credito_sk   BIGSERIAL,
    estado_id           VARCHAR(20)     NOT NULL,
    nombre              VARCHAR(50)     NOT NULL,
    es_activo           BOOLEAN         NOT NULL DEFAULT FALSE,
    es_mora             BOOLEAN         NOT NULL DEFAULT FALSE,
    es_terminado        BOOLEAN         NOT NULL DEFAULT FALSE,
    _loaded_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_dim_estado_credito    PRIMARY KEY (estado_credito_sk),
    CONSTRAINT uq_dim_estado_credito_id UNIQUE (estado_id)
);

-- -----------------------------------------------------------------------------
-- dwh.dim_metodo_pago  (baja cardinalidad, seed insertado por el ETL)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_metodo_pago (
    metodo_pago_sk  BIGSERIAL,
    metodo_id       VARCHAR(20)     NOT NULL,
    nombre          VARCHAR(50)     NOT NULL,
    tipo            VARCHAR(30),
    _loaded_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_dim_metodo_pago       PRIMARY KEY (metodo_pago_sk),
    CONSTRAINT uq_dim_metodo_pago_id    UNIQUE (metodo_id)
);

-- -----------------------------------------------------------------------------
-- dwh.fact_credito  (grano: 1 crédito)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.fact_credito (
    fact_credito_sk         BIGSERIAL,
    credito_id              VARCHAR(20)     NOT NULL,
    cliente_sk              BIGINT          NOT NULL,
    producto_sk             BIGINT          NOT NULL,
    canal_sk                BIGINT          NOT NULL,
    estado_credito_sk       BIGINT          NOT NULL,
    tiempo_solicitud_sk     INTEGER         NOT NULL,
    tiempo_desembolso_sk    INTEGER,
    tiempo_vencimiento_sk   INTEGER,
    monto_aprobado          NUMERIC(18, 2)  NOT NULL,
    plazo_meses             INTEGER         NOT NULL,
    tasa_interes_mensual    NUMERIC(8, 4),
    dias_mora               INTEGER         NOT NULL DEFAULT 0,
    _loaded_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_fact_credito              PRIMARY KEY (fact_credito_sk),
    CONSTRAINT uq_fact_credito_id           UNIQUE (credito_id),
    CONSTRAINT fk_fact_credito_cliente      FOREIGN KEY (cliente_sk)
        REFERENCES dwh.dim_cliente (cliente_sk),
    CONSTRAINT fk_fact_credito_producto     FOREIGN KEY (producto_sk)
        REFERENCES dwh.dim_producto (producto_sk),
    CONSTRAINT fk_fact_credito_canal        FOREIGN KEY (canal_sk)
        REFERENCES dwh.dim_canal (canal_sk),
    CONSTRAINT fk_fact_credito_estado       FOREIGN KEY (estado_credito_sk)
        REFERENCES dwh.dim_estado_credito (estado_credito_sk),
    CONSTRAINT fk_fact_credito_t_sol        FOREIGN KEY (tiempo_solicitud_sk)
        REFERENCES dwh.dim_tiempo (tiempo_sk),
    CONSTRAINT fk_fact_credito_t_des        FOREIGN KEY (tiempo_desembolso_sk)
        REFERENCES dwh.dim_tiempo (tiempo_sk),
    CONSTRAINT fk_fact_credito_t_venc       FOREIGN KEY (tiempo_vencimiento_sk)
        REFERENCES dwh.dim_tiempo (tiempo_sk)
);

-- -----------------------------------------------------------------------------
-- dwh.fact_pago  (grano: 1 transacción de pago)
-- credito_id almacenado como dimensión degenerada (natural key en la fila)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.fact_pago (
    fact_pago_sk                BIGSERIAL,
    pago_id                     VARCHAR(20)     NOT NULL,
    credito_id                  VARCHAR(20)     NOT NULL,
    cliente_sk                  BIGINT          NOT NULL,
    metodo_pago_sk              BIGINT          NOT NULL,
    tiempo_pago_sk              INTEGER         NOT NULL,
    monto_pago                  NUMERIC(18, 2)  NOT NULL,
    estado_pago                 VARCHAR(30)     NOT NULL,
    referencia_transaccion      VARCHAR(100),
    flag_referencia_duplicada   BOOLEAN         NOT NULL DEFAULT FALSE,
    _loaded_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_fact_pago             PRIMARY KEY (fact_pago_sk),
    CONSTRAINT uq_fact_pago_id          UNIQUE (pago_id),
    CONSTRAINT fk_fact_pago_cliente     FOREIGN KEY (cliente_sk)
        REFERENCES dwh.dim_cliente (cliente_sk),
    CONSTRAINT fk_fact_pago_metodo      FOREIGN KEY (metodo_pago_sk)
        REFERENCES dwh.dim_metodo_pago (metodo_pago_sk),
    CONSTRAINT fk_fact_pago_tiempo      FOREIGN KEY (tiempo_pago_sk)
        REFERENCES dwh.dim_tiempo (tiempo_sk)
);
