# Diccionario de Datos — FINTECH Data Platform

Proyecto: Prueba técnica Data Platform Engineer Lead — Revolutiva  
Candidato: Ronald Arévalo

---

## Esquema `raw` — Ingesta cruda

### raw.raw_clientes

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `_raw_id` | BIGSERIAL PK | Surrogate key de ingesta |
| `cliente_id` | TEXT | ID de negocio del cliente (ej. C0001) |
| `tipo_documento` | TEXT | CC / CE / NIT (valor original sin normalizar) |
| `numero_documento` | TEXT | Número de documento (puede estar vacío) |
| `nombres` | TEXT | Nombres del cliente |
| `apellidos` | TEXT | Apellidos (vacío para personas jurídicas NIT) |
| `email` | TEXT | Correo electrónico |
| `telefono` | TEXT | Número de teléfono |
| `fecha_registro` | TEXT | Fecha de registro (formato variable: YYYY-MM-DD o YYYY/MM/DD) |
| `estado_cliente` | TEXT | Estado tal cual viene del CSV (puede ser 'activo', 'EN REVISION', etc.) |
| `ciudad` | TEXT | Ciudad de residencia |
| `segmento` | TEXT | Segmento de negocio (Pyme, Retail, Corporativo) |
| `fecha_nacimiento` | TEXT | Fecha de nacimiento (vacío para NIT) |
| `ingresos_mensuales` | TEXT | Ingresos mensuales en COP |
| `_ingested_at` | TIMESTAMPTZ | Timestamp de ingesta |
| `_source_file` | TEXT | Nombre del archivo fuente |

### raw.raw_creditos

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `_raw_id` | BIGSERIAL PK | Surrogate key de ingesta |
| `credito_id` | TEXT | ID del crédito (ej. CR00001) |
| `cliente_id` | TEXT | ID del cliente asociado |
| `fecha_solicitud` | TEXT | Fecha de solicitud |
| `fecha_desembolso` | TEXT | Fecha de desembolso |
| `monto_aprobado` | TEXT | Monto aprobado en COP |
| `plazo_meses` | TEXT | Plazo en meses |
| `tasa_interes_mensual` | TEXT | Tasa de interés mensual en % (puede ser nulo) |
| `estado_credito` | TEXT | Estado (puede ser 'MORA', 'Aprobado', etc.) |
| `producto` | TEXT | Tipo de producto crediticio |
| `fecha_vencimiento` | TEXT | Fecha de vencimiento |
| `canal` | TEXT | Canal de originación |
| `_ingested_at` | TIMESTAMPTZ | Timestamp de ingesta |
| `_source_file` | TEXT | Nombre del archivo fuente |

### raw.raw_pagos

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `_raw_id` | BIGSERIAL PK | Surrogate key de ingesta |
| `pago_id` | TEXT | ID del pago (ej. P000001) |
| `credito_id` | TEXT | ID del crédito asociado |
| `fecha_pago` | TEXT | Fecha del pago (puede ser inválida: '2024-13-01') |
| `monto_pago` | TEXT | Monto pagado en COP (puede ser negativo o vacío) |
| `metodo_pago` | TEXT | Método de pago |
| `estado_pago` | TEXT | Estado (puede ser 'success', 'EXITOSO', etc.) |
| `referencia_transaccion` | TEXT | Referencia única de la transacción |
| `_ingested_at` | TIMESTAMPTZ | Timestamp de ingesta |
| `_source_file` | TEXT | Nombre del archivo fuente |

---

## Esquema `stg` — Datos limpios y tipados

### stg.stg_clientes

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| `cliente_id` | VARCHAR(20) PK | NO | ID del cliente |
| `tipo_documento` | VARCHAR(10) | NO | CC / CE / NIT (normalizado) |
| `numero_documento` | VARCHAR(50) | SÍ | Número de documento |
| `nombres` | VARCHAR(200) | NO | Nombres |
| `apellidos` | VARCHAR(200) | SÍ | Apellidos |
| `email` | VARCHAR(200) | SÍ | Email |
| `telefono` | VARCHAR(30) | SÍ | Teléfono |
| `fecha_registro` | DATE | SÍ | Fecha de registro |
| `estado_cliente` | VARCHAR(20) | NO | Estado canónico |
| `ciudad` | VARCHAR(100) | SÍ | Ciudad |
| `segmento` | VARCHAR(50) | SÍ | Segmento |
| `fecha_nacimiento` | DATE | SÍ | Fecha de nacimiento |
| `ingresos_mensuales` | NUMERIC(18,2) | SÍ | Ingresos mensuales COP |
| `flag_email_duplicado` | BOOLEAN | NO | TRUE si el email aparece en otro cliente |
| `flag_doc_duplicado` | BOOLEAN | NO | TRUE si numero_documento es compartido |
| `_ingested_at` | TIMESTAMPTZ | NO | Timestamp de ingesta original |
| `_source_file` | TEXT | NO | Archivo fuente |

**Catálogo estado_cliente:** `Activo`, `Inactivo`, `Bloqueado`, `Suspendido`, `Pendiente`, `EnRevision`

### stg.stg_creditos

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| `credito_id` | VARCHAR(20) PK | NO | ID del crédito |
| `cliente_id` | VARCHAR(20) | NO | FK a stg_clientes |
| `fecha_solicitud` | DATE | NO | Fecha de solicitud |
| `fecha_desembolso` | DATE | SÍ | Fecha de desembolso |
| `monto_aprobado` | NUMERIC(18,2) | NO | Monto aprobado COP |
| `plazo_meses` | INTEGER | NO | Plazo en meses |
| `tasa_interes_mensual` | NUMERIC(8,4) | SÍ | Tasa mensual en % |
| `estado_credito` | VARCHAR(30) | NO | Estado canónico |
| `producto` | VARCHAR(100) | NO | Producto crediticio |
| `fecha_vencimiento` | DATE | SÍ | Fecha de vencimiento |
| `canal` | VARCHAR(50) | NO | Canal de originación |
| `_ingested_at` | TIMESTAMPTZ | NO | Timestamp de ingesta original |
| `_source_file` | TEXT | NO | Archivo fuente |

**Catálogo estado_credito:** `Activo`, `Mora`, `Vencido`, `Pagado`, `Cancelado`, `Rechazado`

### stg.stg_pagos

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| `pago_id` | VARCHAR(20) PK | NO | ID del pago |
| `credito_id` | VARCHAR(20) | NO | FK a stg_creditos |
| `fecha_pago` | DATE | NO | Fecha del pago |
| `monto_pago` | NUMERIC(18,2) | NO | Monto pagado COP (> 0) |
| `metodo_pago` | VARCHAR(50) | NO | Método de pago |
| `estado_pago` | VARCHAR(30) | NO | Estado canónico |
| `referencia_transaccion` | VARCHAR(100) | SÍ | Referencia de la transacción |
| `flag_referencia_duplicada` | BOOLEAN | NO | TRUE si la referencia aparece en otro pago |
| `_ingested_at` | TIMESTAMPTZ | NO | Timestamp de ingesta original |
| `_source_file` | TEXT | NO | Archivo fuente |

**Catálogo estado_pago:** `Exitoso`, `Pendiente`, `Fallido`, `Reversado`  
**Catálogo metodo_pago:** `PSE`, `Efecty`, `Transferencia`, `Tarjeta`

---

## Esquema `dwh` — Modelo dimensional

### dwh.dim_tiempo

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `tiempo_sk` | INTEGER PK | Fecha en formato YYYYMMDD |
| `fecha` | DATE UNIQUE | Fecha calendario |
| `anio` | SMALLINT | Año |
| `mes` | SMALLINT | Mes (1–12) |
| `dia` | SMALLINT | Día del mes |
| `trimestre` | SMALLINT | Trimestre (1–4) |
| `semana_anio` | SMALLINT | Semana ISO del año |
| `nombre_mes` | VARCHAR(20) | Nombre del mes en español |
| `nombre_dia` | VARCHAR(20) | Nombre del día en español |
| `es_fin_semana` | BOOLEAN | TRUE para sábado y domingo |
| `es_festivo_co` | BOOLEAN | TRUE si es festivo colombiano (Ley Emiliani + Pascua) |

**Rango:** 2023-01-01 a 2027-12-31 (1.826 filas)

### dwh.dim_cliente

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `cliente_sk` | BIGSERIAL PK | Clave subrogada |
| `cliente_id` | VARCHAR(20) UNIQUE | Clave de negocio |
| `tipo_documento` | VARCHAR(10) | CC / CE / NIT |
| `numero_documento` | VARCHAR(50) | Número de documento |
| `nombres` | VARCHAR(200) | Nombres |
| `apellidos` | VARCHAR(200) | Apellidos |
| `email` | VARCHAR(200) | Email |
| `telefono` | VARCHAR(30) | Teléfono |
| `fecha_registro` | DATE | Fecha de registro |
| `estado_cliente` | VARCHAR(20) | Estado canónico |
| `ciudad` | VARCHAR(100) | Ciudad |
| `segmento` | VARCHAR(50) | Pyme / Retail / Corporativo |
| `fecha_nacimiento` | DATE | Fecha de nacimiento |
| `ingresos_mensuales` | NUMERIC(18,2) | Ingresos COP |
| `flag_email_duplicado` | BOOLEAN | Email compartido con otro cliente |
| `flag_doc_duplicado` | BOOLEAN | Número de documento compartido |

### dwh.dim_producto

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `producto_sk` | BIGSERIAL PK | Clave subrogada |
| `producto_id` | VARCHAR(30) UNIQUE | ID canónico (MICRO, LIBRE_INV, CAP_TRABAJO, CONSUMO) |
| `nombre` | VARCHAR(100) | Nombre del producto |

### dwh.dim_canal

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `canal_sk` | BIGSERIAL PK | Clave subrogada |
| `canal_id` | VARCHAR(20) UNIQUE | ALIADO / WEB / APP |
| `nombre` | VARCHAR(50) | Nombre del canal |

### dwh.dim_estado_credito

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `estado_credito_sk` | BIGSERIAL PK | Clave subrogada |
| `estado_id` | VARCHAR(20) UNIQUE | ACTIVO / MORA / VENCIDO / PAGADO / CANCELADO / RECHAZADO |
| `nombre` | VARCHAR(50) | Nombre canónico |
| `es_activo` | BOOLEAN | TRUE solo para ACTIVO |
| `es_mora` | BOOLEAN | TRUE solo para MORA |
| `es_terminado` | BOOLEAN | TRUE para PAGADO, CANCELADO, RECHAZADO |

### dwh.dim_metodo_pago

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `metodo_pago_sk` | BIGSERIAL PK | Clave subrogada |
| `metodo_id` | VARCHAR(20) UNIQUE | PSE / EFECTY / TRANSFERENCIA / TARJETA |
| `nombre` | VARCHAR(50) | Nombre del método |
| `tipo` | VARCHAR(30) | digital / efectivo / bancario |

### dwh.fact_credito

**Grano:** 1 crédito.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `fact_credito_sk` | BIGSERIAL PK | Clave subrogada de hecho |
| `credito_id` | VARCHAR(20) UNIQUE | Clave de negocio |
| `cliente_sk` | BIGINT FK | → dim_cliente |
| `producto_sk` | BIGINT FK | → dim_producto |
| `canal_sk` | BIGINT FK | → dim_canal |
| `estado_credito_sk` | BIGINT FK | → dim_estado_credito |
| `tiempo_solicitud_sk` | INTEGER FK | → dim_tiempo |
| `tiempo_desembolso_sk` | INTEGER FK | → dim_tiempo (nullable) |
| `tiempo_vencimiento_sk` | INTEGER FK | → dim_tiempo (nullable) |
| `monto_aprobado` | NUMERIC(18,2) | Monto aprobado COP |
| `plazo_meses` | INTEGER | Plazo en meses |
| `tasa_interes_mensual` | NUMERIC(8,4) | Tasa mensual en % |
| `dias_mora` | INTEGER | Días de atraso (0 si no está en mora) |

### dwh.fact_pago

**Grano:** 1 transacción de pago.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `fact_pago_sk` | BIGSERIAL PK | Clave subrogada de hecho |
| `pago_id` | VARCHAR(20) UNIQUE | Clave de negocio |
| `credito_id` | VARCHAR(20) | Dimensión degenerada — FK de negocio al crédito |
| `cliente_sk` | BIGINT FK | → dim_cliente (denormalizado desde crédito) |
| `metodo_pago_sk` | BIGINT FK | → dim_metodo_pago |
| `tiempo_pago_sk` | INTEGER FK | → dim_tiempo |
| `monto_pago` | NUMERIC(18,2) | Monto del pago COP |
| `estado_pago` | VARCHAR(30) | Estado del pago |
| `referencia_transaccion` | VARCHAR(100) | Referencia de la transacción |
| `flag_referencia_duplicada` | BOOLEAN | TRUE si la referencia aparece en otro pago |

---

## Esquema `dq` — Calidad de datos

### dq.dq_errors

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `error_id` | BIGSERIAL PK | ID del error |
| `run_id` | UUID | ID de la ejecución que detectó el error |
| `regla_id` | VARCHAR(10) | DQ-1 a DQ-7 |
| `tabla_origen` | VARCHAR(50) | Tabla donde se detectó el error |
| `severidad` | VARCHAR(10) | ERROR o WARNING |
| `motivo` | TEXT | Descripción del error |
| `payload_original` | JSONB | Fila completa original en JSON |
| `created_at` | TIMESTAMPTZ | Timestamp del registro |

**Reglas y errores esperados tras primera ejecución:**

| Regla | Descripción | Registros esperados |
|-------|-------------|---------------------|
| DQ-1 | PK duplicada: CR00001 en créditos, P000001 en pagos | 2 |
| DQ-2 | Huérfanos FK: CR99991 (cliente C9999), P999901 (crédito CR99999) | 2 |
| DQ-3 | Estado no mapeado: CR00053 estado='Aprobado' | 1 |
| DQ-4 | Dominio: CR00019 monto=-700K, CR00028 plazo=0, P000028/P000045/P000202 monto ≤ 0 | 5 |
| DQ-5 | Temporal: CR00010 desembolso < solicitud, P000073 fecha_pago inválida | 2 |
| DQ-6 | Nulidad crítica: CR00067 tasa nula | 1 |
| DQ-7 | Duplicado negocio: C0121 doc duplicado + emails duplicados entre clientes | ≥1 (WARNING) |

### dq.etl_runs

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `run_id` | UUID PK | ID único de la ejecución |
| `started_at` | TIMESTAMPTZ | Inicio del pipeline |
| `finished_at` | TIMESTAMPTZ | Fin del pipeline |
| `status` | VARCHAR(10) | RUNNING / SUCCESS / FAILED |
| `filas_raw_*` | INTEGER | Filas cargadas en cada tabla raw |
| `filas_stg_*` | INTEGER | Filas cargadas en cada tabla stg |
| `filas_dq_errors` | INTEGER | Total de errores DQ detectados |
| `filas_dim_cliente` | INTEGER | Clientes cargados al DWH |
| `filas_fact_credito` | INTEGER | Créditos cargados al DWH |
| `filas_fact_pago` | INTEGER | Pagos cargados al DWH |
| `error_message` | TEXT | Mensaje de error si status=FAILED |

---

## Esquema `bi` — Capa analítica

| Vista | Tipo | Descripción |
|-------|------|-------------|
| `vw_cartera_vigente` | VIEW | Cartera activa por segmento y producto |
| `vw_morosidad_por_producto` | VIEW | Tasa de mora y días promedio por producto |
| `vw_efectividad_canal` | VIEW | Tasa de aprobación y ticket promedio por canal |
| `vw_pagos_diarios` | VIEW | Recaudo mensual y tasa de fallo de pago |
| `vw_cosecha_morosidad` | MATERIALIZED VIEW | Deterioro por cohorte de desembolso (vintage) |
| `vw_kpi_resumen` | MATERIALIZED VIEW | 7 KPIs en una fila para tarjetas de dashboard |
| `vw_cliente_safe` | VIEW | dim_cliente con PII enmascarado para capa BI |
