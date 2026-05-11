# Medidas DAX — TUMIPAY

## Medidas de Cartera

```dax
Cartera Vigente =
CALCULATE(
    SUM(FactCredito[monto_aprobado]),
    DimEstadoCredito[es_activo] = TRUE
)

Num Creditos Activos =
CALCULATE(
    COUNTROWS(FactCredito),
    DimEstadoCredito[es_activo] = TRUE
)

Ticket Promedio =
CALCULATE(
    AVERAGE(FactCredito[monto_aprobado]),
    DimEstadoCredito[nombre] <> "Rechazado"
)
```

## Medidas de Mora

```dax
Tasa de Mora % =
DIVIDE(
    CALCULATE(COUNTROWS(FactCredito), DimEstadoCredito[es_mora] = TRUE),
    COUNTROWS(FactCredito),
    0
) * 100

Dias Mora Promedio =
CALCULATE(
    AVERAGE(FactCredito[dias_mora]),
    DimEstadoCredito[es_mora] = TRUE
)
```

## Medidas de Recaudo

```dax
Recaudo Total =
CALCULATE(
    SUM(FactPago[monto_pago]),
    FactPago[estado_pago] = "Exitoso"
)

Tasa Fallo Pago % =
DIVIDE(
    CALCULATE(COUNTROWS(FactPago), FactPago[estado_pago] = "Fallido"),
    COUNTROWS(FactPago),
    0
) * 100
```

## Medidas de Aprobación

```dax
Tasa Aprobacion % =
DIVIDE(
    CALCULATE(COUNTROWS(FactCredito), DimEstadoCredito[nombre] <> "Rechazado"),
    COUNTROWS(FactCredito),
    0
) * 100
```
