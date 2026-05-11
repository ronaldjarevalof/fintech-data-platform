-- =============================================================================
-- 01_schemas.sql
-- Creación de esquemas por capa arquitectural
-- Idempotente: seguro ejecutar múltiples veces
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS raw;   -- ingesta cruda sin transformación
CREATE SCHEMA IF NOT EXISTS stg;   -- datos limpios, tipos correctos, catálogos normalizados
CREATE SCHEMA IF NOT EXISTS dwh;   -- modelo dimensional estrella
CREATE SCHEMA IF NOT EXISTS bi;    -- vistas analíticas para consumo BI
CREATE SCHEMA IF NOT EXISTS dq;    -- errores de calidad de datos y registro de ejecuciones
