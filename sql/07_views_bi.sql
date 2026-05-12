-- =============================================================================
-- 07_views_bi.sql
-- Vistas analíticas para consumo BI: 6 KPIs + vista segura de PII.
-- Las vistas regulares usan CREATE OR REPLACE.
-- Las materializadas usan IF NOT EXISTS (el ETL llama REFRESH tras la carga).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. bi.vw_cartera_vigente — KPI: Cartera activa por segmento y producto
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW bi.vw_cartera_vigente AS
SELECT
    dc.segmento,
    dp.nombre                           AS producto,
    COUNT(fc.credito_id)                AS num_creditos,
    SUM(fc.monto_aprobado)              AS monto_total,
    AVG(fc.tasa_interes_mensual)        AS tasa_promedio,
    AVG(fc.plazo_meses)                 AS plazo_promedio_meses
FROM dwh.fact_credito           fc
JOIN dwh.dim_cliente            dc  ON fc.cliente_sk        = dc.cliente_sk
JOIN dwh.dim_producto           dp  ON fc.producto_sk       = dp.producto_sk
JOIN dwh.dim_estado_credito     dec ON fc.estado_credito_sk = dec.estado_credito_sk
WHERE dec.es_activo = TRUE
GROUP BY dc.segmento, dp.nombre;

-- -----------------------------------------------------------------------------
-- 2. bi.vw_morosidad_por_producto — KPI: Tasa de mora
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW bi.vw_morosidad_por_producto AS
SELECT
    dp.nombre                           AS producto,
    COUNT(fc.credito_id)                AS total_creditos,
    COUNT(CASE WHEN dec.es_mora THEN 1 END)             AS creditos_mora,
    COUNT(CASE WHEN dec.nombre = 'Vencido' THEN 1 END)  AS creditos_vencidos,
    ROUND(
        COUNT(CASE WHEN dec.es_mora THEN 1 END) * 100.0
        / NULLIF(COUNT(fc.credito_id), 0), 2
    )                                   AS tasa_mora_pct,
    AVG(CASE WHEN dec.es_mora THEN fc.dias_mora END)    AS dias_mora_promedio
FROM dwh.fact_credito           fc
JOIN dwh.dim_producto           dp  ON fc.producto_sk       = dp.producto_sk
JOIN dwh.dim_estado_credito     dec ON fc.estado_credito_sk = dec.estado_credito_sk
GROUP BY dp.nombre;

-- -----------------------------------------------------------------------------
-- 3. bi.vw_efectividad_canal — KPI: Tasa de aprobación por canal
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW bi.vw_efectividad_canal AS
SELECT
    dca.nombre                          AS canal,
    COUNT(fc.credito_id)                AS total_solicitudes,
    COUNT(CASE WHEN dec.nombre != 'Rechazado' THEN 1 END) AS aprobados,
    ROUND(
        COUNT(CASE WHEN dec.nombre != 'Rechazado' THEN 1 END) * 100.0
        / NULLIF(COUNT(fc.credito_id), 0), 2
    )                                   AS tasa_aprobacion_pct,
    AVG(CASE WHEN dec.nombre != 'Rechazado' THEN fc.monto_aprobado END)
                                        AS ticket_promedio_aprobado
FROM dwh.fact_credito           fc
JOIN dwh.dim_canal              dca ON fc.canal_sk           = dca.canal_sk
JOIN dwh.dim_estado_credito     dec ON fc.estado_credito_sk  = dec.estado_credito_sk
GROUP BY dca.nombre;

-- -----------------------------------------------------------------------------
-- 4. bi.vw_pagos_diarios — KPI: Recaudo mensual y tasa de fallo de pago
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW bi.vw_pagos_diarios AS
SELECT
    dt.anio,
    dt.mes,
    dt.nombre_mes,
    COUNT(fp.pago_id)                                   AS total_transacciones,
    SUM(CASE WHEN fp.estado_pago = 'Exitoso'
             THEN fp.monto_pago ELSE 0 END)             AS monto_recaudado,
    COUNT(CASE WHEN fp.estado_pago = 'Fallido' THEN 1 END)  AS pagos_fallidos,
    COUNT(CASE WHEN fp.estado_pago = 'Reversado' THEN 1 END) AS pagos_reversados,
    ROUND(
        COUNT(CASE WHEN fp.estado_pago = 'Fallido' THEN 1 END) * 100.0
        / NULLIF(COUNT(fp.pago_id), 0), 2
    )                                   AS tasa_fallo_pct,
    AVG(fp.monto_pago)                  AS monto_promedio_transaccion
FROM dwh.fact_pago  fp
JOIN dwh.dim_tiempo dt  ON fp.tiempo_pago_sk = dt.tiempo_sk
GROUP BY dt.anio, dt.mes, dt.nombre_mes
ORDER BY dt.anio, dt.mes;

-- -----------------------------------------------------------------------------
-- 5. bi.vw_cosecha_morosidad — KPI: Vintage / Cosecha de morosidad
-- Materializada: el ETL llama REFRESH MATERIALIZED VIEW tras la carga.
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS bi.vw_cosecha_morosidad AS
SELECT
    dt_des.anio                         AS anio_cosecha,
    dt_des.mes                          AS mes_cosecha,
    dp.nombre                           AS producto,
    COUNT(fc.credito_id)                AS total_creditos,
    COUNT(CASE WHEN dec.es_mora OR dec.nombre = 'Vencido' THEN 1 END)
                                        AS creditos_deteriorados,
    ROUND(
        COUNT(CASE WHEN dec.es_mora OR dec.nombre = 'Vencido' THEN 1 END) * 100.0
        / NULLIF(COUNT(fc.credito_id), 0), 2
    )                                   AS tasa_deterioro_pct,
    AVG(fc.monto_aprobado)              AS monto_promedio
FROM dwh.fact_credito           fc
JOIN dwh.dim_tiempo             dt_des  ON fc.tiempo_desembolso_sk  = dt_des.tiempo_sk
JOIN dwh.dim_producto           dp      ON fc.producto_sk            = dp.producto_sk
JOIN dwh.dim_estado_credito     dec     ON fc.estado_credito_sk      = dec.estado_credito_sk
GROUP BY dt_des.anio, dt_des.mes, dp.nombre
ORDER BY dt_des.anio, dt_des.mes, dp.nombre;

-- -----------------------------------------------------------------------------
-- 6. bi.vw_kpi_resumen — Una fila con los 7 KPIs actuales (materializada)
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS bi.vw_kpi_resumen AS
SELECT
    1::INT                                                          AS id,
    (SELECT COUNT(*)
     FROM dwh.fact_credito fc
     JOIN dwh.dim_estado_credito dec ON fc.estado_credito_sk = dec.estado_credito_sk
     WHERE dec.es_activo)                                           AS cartera_activa_count,

    (SELECT COALESCE(SUM(fc.monto_aprobado), 0)
     FROM dwh.fact_credito fc
     JOIN dwh.dim_estado_credito dec ON fc.estado_credito_sk = dec.estado_credito_sk
     WHERE dec.es_activo)                                           AS cartera_vigente_monto,

    (SELECT ROUND(
         COUNT(CASE WHEN dec.es_mora THEN 1 END) * 100.0
         / NULLIF(COUNT(*), 0), 2)
     FROM dwh.fact_credito fc
     JOIN dwh.dim_estado_credito dec ON fc.estado_credito_sk = dec.estado_credito_sk
    )                                                               AS tasa_mora_pct,

    (SELECT ROUND(AVG(fc.monto_aprobado), 0)
     FROM dwh.fact_credito fc
     JOIN dwh.dim_estado_credito dec ON fc.estado_credito_sk = dec.estado_credito_sk
     WHERE dec.nombre != 'Rechazado')                              AS ticket_promedio,

    (SELECT ROUND(
         COUNT(CASE WHEN dec.nombre != 'Rechazado' THEN 1 END) * 100.0
         / NULLIF(COUNT(*), 0), 2)
     FROM dwh.fact_credito fc
     JOIN dwh.dim_estado_credito dec ON fc.estado_credito_sk = dec.estado_credito_sk
    )                                                               AS tasa_aprobacion_pct,

    (SELECT COALESCE(SUM(fp.monto_pago), 0)
     FROM dwh.fact_pago fp
     WHERE fp.estado_pago = 'Exitoso')                             AS recaudo_total,

    (SELECT ROUND(
         COUNT(CASE WHEN fp.estado_pago = 'Fallido' THEN 1 END) * 100.0
         / NULLIF(COUNT(*), 0), 2)
     FROM dwh.fact_pago fp)                                        AS tasa_fallo_pago_pct;

-- Índices únicos para permitir REFRESH MATERIALIZED VIEW CONCURRENTLY
-- (sin bloqueo exclusivo de lectura durante el refresco del ETL).
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_cosecha_anio_mes_prod
    ON bi.vw_cosecha_morosidad (anio_cosecha, mes_cosecha, producto);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_kpi_resumen_id
    ON bi.vw_kpi_resumen (id);

-- -----------------------------------------------------------------------------
-- 7. bi.vw_cliente_safe — Enmascaramiento PII para capa BI
-- Campos enmascarados: numero_documento, email, telefono, nombre completo,
-- ingresos (reemplazado por rango)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW bi.vw_cliente_safe AS
SELECT
    cliente_sk,
    cliente_id,
    tipo_documento,
    -- numero_documento: muestra solo los últimos 4 dígitos
    CASE
        WHEN LENGTH(numero_documento) > 4
        THEN REPEAT('*', LENGTH(numero_documento) - 4)
             || RIGHT(numero_documento, 4)
        ELSE numero_documento
    END                                         AS numero_documento,
    -- nombre: solo primer nombre + inicial del apellido
    SPLIT_PART(nombres, ' ', 1)
        || CASE WHEN apellidos IS NOT NULL AND apellidos != ''
                THEN ' ' || LEFT(apellidos, 1) || '.'
                ELSE '' END                     AS nombre_display,
    -- email: j***@dominio.com
    CASE
        WHEN email LIKE '%@%'
        THEN LEFT(email, 1)
             || REPEAT('*', GREATEST(POSITION('@' IN email) - 2, 0))
             || SUBSTRING(email FROM POSITION('@' IN email))
        ELSE email
    END                                         AS email,
    -- telefono: ***-***-1234
    CASE
        WHEN LENGTH(COALESCE(telefono, '')) >= 4
        THEN REPEAT('*', LENGTH(telefono) - 4) || RIGHT(telefono, 4)
        ELSE telefono
    END                                         AS telefono,
    fecha_registro,
    estado_cliente,
    ciudad,
    segmento,
    -- ingresos: reemplazado por banda
    CASE
        WHEN ingresos_mensuales IS NULL        THEN 'Sin dato'
        WHEN ingresos_mensuales < 5000000      THEN '< 5M'
        WHEN ingresos_mensuales < 10000000     THEN '5M - 10M'
        WHEN ingresos_mensuales < 20000000     THEN '10M - 20M'
        ELSE '> 20M'
    END                                         AS rango_ingresos,
    flag_email_duplicado,
    flag_doc_duplicado
FROM dwh.dim_cliente;

-- -----------------------------------------------------------------------------
-- 8. Vistas regulares wrapper sobre las materializadas
-- Power BI no enumera vistas materializadas vía information_schema.tables;
-- estas vistas normales las exponen con el mismo contenido.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW bi.vw_kpi_resumen_pbi AS
    SELECT * FROM bi.vw_kpi_resumen;

CREATE OR REPLACE VIEW bi.vw_cosecha_morosidad_pbi AS
    SELECT * FROM bi.vw_cosecha_morosidad;
