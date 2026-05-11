# FINTECH Data Platform

![CI](https://github.com/ronald-arevalo/fintech-data-platform/actions/workflows/ci.yml/badge.svg)

Solución de datos para FINTECH — entregable de la prueba técnica para el rol **Data Platform Engineer Lead** en Revolutiva.

**Candidato:** Ronald Arévalo

---

## Qué hace este proyecto

Consolida tres fuentes CSV (clientes, créditos, pagos) en un modelo dimensional PostgreSQL con:
- Pipeline ETL por capas: `raw → stg → dwh → bi`
- 7 reglas de calidad de datos con trazabilidad completa en `dq.dq_errors`
- 6 vistas analíticas + 2 vistas materializadas para consumo BI
- Enmascaramiento PII en capa BI

---

## Requisitos

- Docker Desktop con Compose V2

Los tres archivos CSV de datos sintéticos están incluidos en `data/raw/` — no se requiere ningún paso previo de datos.

---

## Cómo ejecutar

```bash
# 1. Copiar la plantilla de variables de entorno
cp .env.example .env

# 2. Levantar todo (Postgres + ETL + pgAdmin)
docker compose up --build
```

El servicio `etl` espera a que Postgres esté listo, ejecuta el pipeline completo y termina. Los scripts SQL en `sql/` se ejecutan automáticamente al primer arranque de Postgres (montados en `docker-entrypoint-initdb.d`).

Para ejecutar el ETL nuevamente sin recrear la base:

```bash
docker compose run --rm etl
```

---

## Qué se ve al ejecutar

El ETL imprime logs JSON con `run_id` en cada paso:

```
{"event": "pipeline_start", "run_id": "...", ...}
{"event": "step_extract_done", "clientes": 200, "creditos": 381, "pagos": 1801, ...}
{"event": "step_validate_done", "dq_errors": 13, "creditos_validos": 248, ...}
{"event": "pipeline_success", "elapsed_seconds": 12.4, ...}
```

Verificar resultados:

```sql
-- Estado de la ejecución
SELECT run_id, status, filas_dq_errors, filas_fact_credito, filas_fact_pago
FROM dq.etl_runs ORDER BY started_at DESC LIMIT 1;

-- Errores de calidad por regla
SELECT regla_id, tabla_origen, severidad, COUNT(*) AS n
FROM dq.dq_errors GROUP BY 1,2,3 ORDER BY 1;

-- KPI resumen
SELECT * FROM bi.vw_kpi_resumen;
```

---

## Estructura del proyecto

```
├── .github/workflows/
│   └── ci.yml              # CI: unit tests + pipeline smoke test con Postgres
├── docker-compose.yml      # Postgres 18 + ETL + pgAdmin
├── Dockerfile              # Python 3.11-slim
├── requirements.txt
├── pyproject.toml          # Configuración pytest, coverage y ruff
├── .env.example            # Variables necesarias
├── data/raw/               # CSVs sintéticos (200 clientes, 381 créditos, 1801 pagos)
├── sql/                    # DDL y vistas (01–09, ejecutados en orden)
│   ├── 01_schemas.sql      # Esquemas: raw, stg, dwh, bi, dq
│   ├── 02_ddl_raw.sql      # Tablas ingesta cruda (todo TEXT)
│   ├── 03_ddl_staging.sql  # Tablas tipadas post-DQ
│   ├── 04_ddl_dwh.sql      # Modelo estrella: 6 dims + 2 hechos
│   ├── 05_ddl_dq.sql       # dq_errors + etl_runs
│   ├── 06_indices.sql      # Índices en FKs y columnas de filtro
│   ├── 07_views_bi.sql     # 6 vistas KPI + enmascaramiento PII
│   ├── 08_roles_grants.sql # 5 roles con permisos mínimos
│   └── 09_consultas_analiticas.sql  # 8 consultas de referencia
├── src/
│   ├── config.py           # Variables de entorno y paths
│   ├── logger.py           # structlog JSON con run_id
│   ├── db.py               # Engine SQLAlchemy
│   ├── extract.py          # Lectura CSV → DataFrames
│   ├── transform.py        # Limpieza, catálogos canónicos, parseo
│   ├── validate.py         # 7 reglas DQ
│   ├── load.py             # Carga raw/stg/dwh + dim_tiempo
│   └── main.py             # Orquestador
└── tests/
    ├── test_transform.py   # Normalización, parseo de fechas
    └── test_validate.py    # Las 7 reglas DQ con datos sintéticos
```

---

## Dónde están los KPIs

| KPI | Vista |
|-----|-------|
| Cartera vigente | `bi.vw_cartera_vigente` |
| Tasa de mora por producto | `bi.vw_morosidad_por_producto` |
| Efectividad por canal | `bi.vw_efectividad_canal` |
| Recaudo mensual y tasa de fallo | `bi.vw_pagos_diarios` |
| Cosecha de morosidad (vintage) | `bi.vw_cosecha_morosidad` *(materializada)* |
| KPI resumen (una fila) | `bi.vw_kpi_resumen` *(materializada)* |
| Clientes con PII enmascarado | `bi.vw_cliente_safe` |

---

## pgAdmin

Disponible en `http://localhost:8080`
- Email: `admin@fintech.local`
- Password: `admin`
- Servidor: host `postgres`, port `5432`, user/pass del `.env`

---

## Tests y CI

El repositorio tiene dos niveles de verificación automatizada:

**CI en GitHub Actions** (se ejecuta en cada push):
- `unit-tests` — corre `pytest --cov=src` sin base de datos
- `pipeline-smoke` — levanta Postgres 18, aplica todos los scripts SQL, ejecuta el pipeline completo y verifica que `status = SUCCESS` y `dq_errors` tenga entre 10 y 15 registros

El workflow no contiene passwords en texto claro. Usa `${{ secrets.POSTGRES_PASSWORD || 'fintech' }}`: si el secret `POSTGRES_PASSWORD` está configurado en el repo (`Settings → Secrets → Actions`) lo utiliza; si no, cae al valor de ejemplo `fintech`.

**Local con virtualenv:**

```bash
pip install -r requirements.txt
pytest --cov=src --cov-report=term-missing tests/ -v
```

O dentro del contenedor ETL:

```bash
docker compose run --rm etl pytest --cov=src tests/ -v
```

La configuración de pytest, coverage y ruff está en `pyproject.toml`.

---

## Decisiones técnicas clave

**Por qué Postgres 18 y no MySQL/SQLite:** JSONB para payloads de error, CTEs analíticas, vistas materializadas, `pg_stat_statements`. Estándar fintech LATAM.

**Por qué full-load y no incremental:** Volumen reducido (< 2.000 filas). En producción se migraría a CDC con AWS DMS. Esta limitación está documentada en el documento de diseño.

**Por qué no dbt/Airflow/Spark:** La consigna dice explícitamente "no sobredimensionar". Esas herramientas viven en la propuesta de evolución AWS (Sección 10 del documento de diseño), no en el MVP entregado.

**Todos los datos inválidos van a `dq_errors`:** Nunca se descarta un registro silenciosamente. Todo error queda registrado con payload JSONB completo y regla identificada.

**`load_dwh` es atómico:** todos los TRUNCATE y todos los INSERT (dimensiones + hechos) ocurren dentro de una única transacción SQLAlchemy. Si cualquier paso falla, PostgreSQL hace rollback automático — el DWH nunca queda vacío ni parcialmente cargado.

---

## Limitaciones conocidas

- SCD-1 en todas las dimensiones (no hay historial de cambios)
- Carga full-load: trunca y recarga en cada ejecución
- `flag_doc_duplicado` en clientes detecta el duplicado real de C0001/C0195 pero no bloquea al cliente; la decisión de negocio sobre cuál es el válido está fuera del scope del pipeline

---

## Documento de diseño

`docs/Diseno_Solucion_FINTECH_Ronald_Arevalo.pdf` — 47 páginas con arquitectura completa, justificaciones y propuesta de evolución AWS.
