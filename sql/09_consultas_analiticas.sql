-- =============================================================================
-- 09_consultas_analiticas.sql
-- 8 consultas analíticas sobre el modelo dimensional de TUMIPAY.
-- Ejecutar después de que el ETL haya cargado datos.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Q1. Distribución de cartera por segmento y producto
-- Muestra el monto total y número de créditos activos por segmento/producto.
-- -----------------------------------------------------------------------------
SELECT
    dc.segmento,
    dp.nombre                                   AS producto,
    COUNT(fc.credito_id)                        AS num_creditos,
    SUM(fc.monto_aprobado)                      AS monto_total,
    ROUND(AVG(fc.tasa_interes_mensual), 2)      AS tasa_promedio,
    ROUND(AVG(fc.plazo_meses), 1)               AS plazo_promedio
FROM dwh.fact_credito           fc
JOIN dwh.dim_cliente            dc  ON fc.cliente_sk        = dc.cliente_sk
JOIN dwh.dim_producto           dp  ON fc.producto_sk       = dp.producto_sk
JOIN dwh.dim_estado_credito     dec ON fc.estado_credito_sk = dec.estado_credito_sk
WHERE dec.nombre NOT IN ('Rechazado')
GROUP BY dc.segmento, dp.nombre
ORDER BY monto_total DESC;

-- -----------------------------------------------------------------------------
-- Q2. Top 10 clientes por monto total de créditos desembolsados
-- Excluye rechazados; incluye estado actual y ciudad.
-- -----------------------------------------------------------------------------
SELECT
    dc.cliente_id,
    dc.nombres || ' ' || COALESCE(dc.apellidos, '') AS nombre_cliente,
    dc.ciudad,
    dc.segmento,
    COUNT(fc.credito_id)                            AS num_creditos,
    SUM(fc.monto_aprobado)                          AS monto_total_desembolsado,
    ROUND(AVG(fc.tasa_interes_mensual), 2)          AS tasa_promedio
FROM dwh.fact_credito           fc
JOIN dwh.dim_cliente            dc  ON fc.cliente_sk        = dc.cliente_sk
JOIN dwh.dim_estado_credito     dec ON fc.estado_credito_sk = dec.estado_credito_sk
WHERE dec.nombre NOT IN ('Rechazado')
GROUP BY dc.cliente_id, dc.nombres, dc.apellidos, dc.ciudad, dc.segmento
ORDER BY monto_total_desembolsado DESC
LIMIT 10;

-- -----------------------------------------------------------------------------
-- Q3. Evolución mensual de desembolsos (2024-2025)
-- Volumen y monto total de créditos por mes de desembolso.
-- -----------------------------------------------------------------------------
SELECT
    dt.anio,
    dt.mes,
    dt.nombre_mes,
    COUNT(fc.credito_id)            AS creditos_desembolsados,
    SUM(fc.monto_aprobado)          AS monto_total,
    ROUND(AVG(fc.monto_aprobado))   AS ticket_promedio
FROM dwh.fact_credito       fc
JOIN dwh.dim_tiempo         dt  ON fc.tiempo_desembolso_sk = dt.tiempo_sk
JOIN dwh.dim_estado_credito dec ON fc.estado_credito_sk    = dec.estado_credito_sk
WHERE dec.nombre NOT IN ('Rechazado')
  AND dt.anio IN (2024, 2025)
GROUP BY dt.anio, dt.mes, dt.nombre_mes
ORDER BY dt.anio, dt.mes;

-- -----------------------------------------------------------------------------
-- Q4. Análisis de morosidad por producto y canal
-- Tasa de mora y días promedio de atraso.
-- -----------------------------------------------------------------------------
SELECT
    dp.nombre                                           AS producto,
    dca.nombre                                          AS canal,
    COUNT(fc.credito_id)                                AS total_creditos,
    COUNT(CASE WHEN dec.es_mora THEN 1 END)             AS en_mora,
    COUNT(CASE WHEN dec.nombre = 'Vencido' THEN 1 END)  AS vencidos,
    ROUND(
        COUNT(CASE WHEN dec.es_mora OR dec.nombre = 'Vencido' THEN 1 END) * 100.0
        / NULLIF(COUNT(fc.credito_id), 0), 2
    )                                                   AS tasa_deterioro_pct,
    COALESCE(ROUND(AVG(
        CASE WHEN dec.es_mora THEN fc.dias_mora END
    )), 0)                                              AS dias_mora_promedio
FROM dwh.fact_credito           fc
JOIN dwh.dim_producto           dp  ON fc.producto_sk       = dp.producto_sk
JOIN dwh.dim_canal              dca ON fc.canal_sk           = dca.canal_sk
JOIN dwh.dim_estado_credito     dec ON fc.estado_credito_sk  = dec.estado_credito_sk
GROUP BY dp.nombre, dca.nombre
ORDER BY tasa_deterioro_pct DESC;

-- -----------------------------------------------------------------------------
-- Q5. Tasa de recaudo y composición por método de pago
-- Monto recaudado, fallido y reversado por método.
-- -----------------------------------------------------------------------------
SELECT
    dmp.nombre                      AS metodo_pago,
    dmp.tipo,
    COUNT(fp.pago_id)               AS total_transacciones,
    SUM(CASE WHEN fp.estado_pago = 'Exitoso'
             THEN fp.monto_pago ELSE 0 END)     AS monto_exitoso,
    SUM(CASE WHEN fp.estado_pago = 'Fallido'
             THEN fp.monto_pago ELSE 0 END)     AS monto_fallido,
    SUM(CASE WHEN fp.estado_pago = 'Reversado'
             THEN fp.monto_pago ELSE 0 END)     AS monto_reversado,
    ROUND(
        COUNT(CASE WHEN fp.estado_pago = 'Exitoso' THEN 1 END) * 100.0
        / NULLIF(COUNT(fp.pago_id), 0), 2
    )                               AS tasa_exito_pct
FROM dwh.fact_pago      fp
JOIN dwh.dim_metodo_pago dmp ON fp.metodo_pago_sk = dmp.metodo_pago_sk
GROUP BY dmp.nombre, dmp.tipo
ORDER BY monto_exitoso DESC;

-- -----------------------------------------------------------------------------
-- Q6. Clientes con múltiples créditos activos o en mora
-- Identifica clientes con mayor concentración de riesgo.
-- -----------------------------------------------------------------------------
SELECT
    dc.cliente_id,
    dc.nombres || ' ' || COALESCE(dc.apellidos, '') AS nombre_cliente,
    dc.segmento,
    dc.ciudad,
    COUNT(fc.credito_id)            AS total_creditos_vigentes,
    SUM(fc.monto_aprobado)          AS exposicion_total,
    SUM(CASE WHEN dec.es_mora THEN fc.monto_aprobado ELSE 0 END)
                                    AS monto_en_mora,
    MAX(fc.dias_mora)               AS max_dias_mora
FROM dwh.fact_credito           fc
JOIN dwh.dim_cliente            dc  ON fc.cliente_sk        = dc.cliente_sk
JOIN dwh.dim_estado_credito     dec ON fc.estado_credito_sk = dec.estado_credito_sk
WHERE dec.nombre NOT IN ('Rechazado', 'Cancelado', 'Pagado')
GROUP BY dc.cliente_id, dc.nombres, dc.apellidos, dc.segmento, dc.ciudad
HAVING COUNT(fc.credito_id) > 1
ORDER BY exposicion_total DESC;

-- -----------------------------------------------------------------------------
-- Q7. Cosecha de morosidad (vintage) — lee desde la vista materializada
-- Muestra la evolución del deterioro por cohorte de desembolso.
-- -----------------------------------------------------------------------------
SELECT
    anio_cosecha,
    mes_cosecha,
    producto,
    total_creditos,
    creditos_deteriorados,
    tasa_deterioro_pct,
    ROUND(monto_promedio)           AS monto_promedio
FROM bi.vw_cosecha_morosidad
ORDER BY anio_cosecha, mes_cosecha, tasa_deterioro_pct DESC;

-- -----------------------------------------------------------------------------
-- Q8. Salud del pipeline ETL: últimas 10 ejecuciones y errores por regla
-- Útil para monitoreo operativo post-carga.
-- -----------------------------------------------------------------------------
-- Últimas ejecuciones
SELECT
    run_id,
    started_at,
    finished_at,
    status,
    ROUND(EXTRACT(EPOCH FROM (finished_at - started_at))) AS duracion_seg,
    filas_raw_clientes,
    filas_raw_creditos,
    filas_raw_pagos,
    filas_dq_errors,
    filas_fact_credito,
    filas_fact_pago,
    error_message
FROM dq.etl_runs
ORDER BY started_at DESC
LIMIT 10;

-- Distribución de errores DQ por regla en la última ejecución
SELECT
    e.regla_id,
    e.tabla_origen,
    e.severidad,
    COUNT(*)    AS num_errores,
    MIN(e.created_at) AS primer_error,
    MAX(e.created_at) AS ultimo_error
FROM dq.dq_errors e
JOIN (
    SELECT run_id FROM dq.etl_runs ORDER BY started_at DESC LIMIT 1
) last_run ON e.run_id = last_run.run_id
GROUP BY e.regla_id, e.tabla_origen, e.severidad
ORDER BY e.regla_id, num_errores DESC;
