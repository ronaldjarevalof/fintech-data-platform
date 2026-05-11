-- =============================================================================
-- 08_roles_grants.sql
-- Roles de acceso y permisos por capa.
-- Idempotente: CREATE ROLE IF NOT EXISTS.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Creación de roles (sin login; los usuarios reales reciben estos roles)
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etl_loader') THEN
        CREATE ROLE etl_loader;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bi_reader') THEN
        CREATE ROLE bi_reader;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analyst_readonly') THEN
        CREATE ROLE analyst_readonly;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dba_admin') THEN
        CREATE ROLE dba_admin;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'audit_reader') THEN
        CREATE ROLE audit_reader;
    END IF;
END
$$;

-- -----------------------------------------------------------------------------
-- etl_loader: opera las capas de ingesta y DWH
-- -----------------------------------------------------------------------------
GRANT USAGE ON SCHEMA raw TO etl_loader;
GRANT USAGE ON SCHEMA stg TO etl_loader;
GRANT USAGE ON SCHEMA dwh TO etl_loader;
GRANT USAGE ON SCHEMA dq  TO etl_loader;

GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE
    ON ALL TABLES IN SCHEMA raw TO etl_loader;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE
    ON ALL TABLES IN SCHEMA stg TO etl_loader;
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE
    ON ALL TABLES IN SCHEMA dwh TO etl_loader;
GRANT INSERT
    ON dq.dq_errors TO etl_loader;
GRANT SELECT, INSERT, UPDATE
    ON dq.etl_runs TO etl_loader;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA raw TO etl_loader;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA stg TO etl_loader;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA dwh TO etl_loader;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA dq  TO etl_loader;

-- -----------------------------------------------------------------------------
-- bi_reader: acceso a capa BI con datos de cliente enmascarados
-- -----------------------------------------------------------------------------
GRANT USAGE ON SCHEMA bi  TO bi_reader;
GRANT USAGE ON SCHEMA dwh TO bi_reader;

GRANT SELECT ON ALL TABLES IN SCHEMA bi TO bi_reader;

-- Acceso al DWH solo a través de vistas (no a tablas con PII directamente)
GRANT SELECT ON dwh.fact_credito       TO bi_reader;
GRANT SELECT ON dwh.fact_pago          TO bi_reader;
GRANT SELECT ON dwh.dim_producto       TO bi_reader;
GRANT SELECT ON dwh.dim_canal          TO bi_reader;
GRANT SELECT ON dwh.dim_estado_credito TO bi_reader;
GRANT SELECT ON dwh.dim_metodo_pago    TO bi_reader;
GRANT SELECT ON dwh.dim_tiempo         TO bi_reader;
-- dim_cliente: acceso solo vía vw_cliente_safe (PII enmascarado)
-- NO se otorga SELECT directo sobre dwh.dim_cliente a bi_reader

-- -----------------------------------------------------------------------------
-- analyst_readonly: consultas ad-hoc sobre DWH y BI
-- -----------------------------------------------------------------------------
GRANT USAGE ON SCHEMA dwh TO analyst_readonly;
GRANT USAGE ON SCHEMA bi  TO analyst_readonly;

GRANT SELECT ON ALL TABLES IN SCHEMA dwh TO analyst_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA bi  TO analyst_readonly;

-- -----------------------------------------------------------------------------
-- dba_admin: acceso total
-- -----------------------------------------------------------------------------
GRANT ALL ON SCHEMA raw, stg, dwh, bi, dq TO dba_admin;
GRANT ALL ON ALL TABLES    IN SCHEMA raw TO dba_admin;
GRANT ALL ON ALL TABLES    IN SCHEMA stg TO dba_admin;
GRANT ALL ON ALL TABLES    IN SCHEMA dwh TO dba_admin;
GRANT ALL ON ALL TABLES    IN SCHEMA bi  TO dba_admin;
GRANT ALL ON ALL TABLES    IN SCHEMA dq  TO dba_admin;
GRANT ALL ON ALL SEQUENCES IN SCHEMA raw TO dba_admin;
GRANT ALL ON ALL SEQUENCES IN SCHEMA stg TO dba_admin;
GRANT ALL ON ALL SEQUENCES IN SCHEMA dwh TO dba_admin;
GRANT ALL ON ALL SEQUENCES IN SCHEMA dq  TO dba_admin;

-- -----------------------------------------------------------------------------
-- audit_reader: solo lectura de tablas de calidad y runs
-- -----------------------------------------------------------------------------
GRANT USAGE ON SCHEMA dq TO audit_reader;
GRANT SELECT ON dq.dq_errors TO audit_reader;
GRANT SELECT ON dq.etl_runs  TO audit_reader;
