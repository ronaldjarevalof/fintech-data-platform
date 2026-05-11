# Modelo Semántico Power BI — FINTECH

## Tablas y conexiones

Power BI se conecta a PostgreSQL usando DirectQuery o Import mode contra el esquema `bi` y `dwh`.

### Tablas importadas

| Tabla/Vista PG | Tabla PBI | Notas |
|----------------|-----------|-------|
| `bi.vw_cliente_safe` | `DimCliente` | PII enmascarado |
| `dwh.dim_producto` | `DimProducto` | |
| `dwh.dim_canal` | `DimCanal` | |
| `dwh.dim_estado_credito` | `DimEstadoCredito` | |
| `dwh.dim_metodo_pago` | `DimMetodoPago` | |
| `dwh.dim_tiempo` | `DimTiempo` | |
| `dwh.fact_credito` | `FactCredito` | |
| `dwh.fact_pago` | `FactPago` | |

### Relaciones

| Desde | Columna | Hacia | Columna | Cardinalidad |
|-------|---------|-------|---------|--------------|
| `FactCredito` | `cliente_sk` | `DimCliente` | `cliente_sk` | M:1 |
| `FactCredito` | `producto_sk` | `DimProducto` | `producto_sk` | M:1 |
| `FactCredito` | `canal_sk` | `DimCanal` | `canal_sk` | M:1 |
| `FactCredito` | `estado_credito_sk` | `DimEstadoCredito` | `estado_credito_sk` | M:1 |
| `FactCredito` | `tiempo_solicitud_sk` | `DimTiempo` | `tiempo_sk` | M:1 |
| `FactPago` | `cliente_sk` | `DimCliente` | `cliente_sk` | M:1 |
| `FactPago` | `metodo_pago_sk` | `DimMetodoPago` | `metodo_pago_sk` | M:1 |
| `FactPago` | `tiempo_pago_sk` | `DimTiempo` | `tiempo_sk` | M:1 |

## Jerarquía de tiempo

`DimTiempo`: Año → Trimestre → Mes → Día
