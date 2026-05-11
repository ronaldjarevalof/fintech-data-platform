"""Tests para src/validate.py: las 7 reglas DQ sobre datos sintéticos."""

from datetime import date

import pandas as pd
import pytest

from src.validate import (
    dq1_pk_uniqueness,
    dq2_referential_integrity,
    dq3_catalog_normalization,
    dq4_domain_values,
    dq5_temporal_coherence,
    dq6_not_null_critical,
    dq7_business_duplicates,
    validate_all,
)

RUN_ID = "test-run-00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clientes(**overrides) -> dict:
    base = {
        "cliente_id": "C0001", "tipo_documento": "CC",
        "numero_documento": "12345678", "nombres": "Test",
        "apellidos": "User", "email": "test@email.com",
        "telefono": "3001234567", "fecha_registro": date(2024, 1, 1),
        "estado_cliente": "Activo", "ciudad": "Bogota",
        "segmento": "Pyme", "fecha_nacimiento": date(1990, 1, 1),
        "ingresos_mensuales": 5000000.0,
        "_estado_cliente_valido": True, "_tipo_doc_valido": True,
        "_ingested_at": "2025-01-01", "_source_file": "clientes.csv",
    }
    base.update(overrides)
    return base


def _creditos(**overrides) -> dict:
    base = {
        "credito_id": "CR00001", "cliente_id": "C0001",
        "fecha_solicitud": date(2024, 1, 10),
        "fecha_desembolso": date(2024, 1, 12),
        "monto_aprobado": 5000000.0, "plazo_meses": 12,
        "tasa_interes_mensual": 1.5, "estado_credito": "Activo",
        "producto": "Consumo", "fecha_vencimiento": date(2025, 1, 10),
        "canal": "Web", "_estado_credito_valido": True,
        "_ingested_at": "2025-01-01", "_source_file": "creditos.csv",
    }
    base.update(overrides)
    return base


def _pagos(**overrides) -> dict:
    base = {
        "pago_id": "P000001", "credito_id": "CR00001",
        "fecha_pago": date(2024, 3, 1), "monto_pago": 500000.0,
        "metodo_pago": "PSE", "estado_pago": "Exitoso",
        "referencia_transaccion": "REF001",
        "_estado_pago_valido": True,
        "_ingested_at": "2025-01-01", "_source_file": "pagos.csv",
    }
    base.update(overrides)
    return base


def _dfs(clientes=None, creditos=None, pagos=None):
    return {
        "clientes": pd.DataFrame(clientes or [_clientes()]),
        "creditos": pd.DataFrame(creditos or [_creditos()]),
        "pagos": pd.DataFrame(pagos or [_pagos()]),
    }


# ---------------------------------------------------------------------------
# DQ-1: Unicidad de PK
# ---------------------------------------------------------------------------

class TestDQ1PKUniqueness:
    def test_aisla_credito_duplicado(self):
        cr = [_creditos(credito_id="CR00001"), _creditos(credito_id="CR00001")]
        valid, errs = dq1_pk_uniqueness(_dfs(creditos=cr), RUN_ID)
        assert len(valid["creditos"]) == 1
        assert len(errs) == 1
        assert errs[0]["regla_id"] == "DQ-1"

    def test_aisla_pago_duplicado(self):
        pg = [_pagos(pago_id="P000001"), _pagos(pago_id="P000001")]
        valid, errs = dq1_pk_uniqueness(_dfs(pagos=pg), RUN_ID)
        assert len(valid["pagos"]) == 1
        assert len(errs) == 1

    def test_sin_duplicados_no_genera_errores(self):
        valid, errs = dq1_pk_uniqueness(_dfs(), RUN_ID)
        assert len(errs) == 0
        assert len(valid["creditos"]) == 1


# ---------------------------------------------------------------------------
# DQ-2: Integridad referencial
# ---------------------------------------------------------------------------

class TestDQ2ReferentialIntegrity:
    def test_credito_huerfano_aislado(self):
        cr = [_creditos(cliente_id="C9999")]  # cliente no existe
        valid, errs = dq2_referential_integrity(_dfs(creditos=cr), RUN_ID)
        assert len(valid["creditos"]) == 0
        assert len(errs) == 1
        assert "C9999" in errs[0]["motivo"]

    def test_pago_huerfano_aislado(self):
        cr = [_creditos(credito_id="CR00001")]
        pg = [_pagos(credito_id="CR99999")]  # crédito no existe
        valid, errs = dq2_referential_integrity(
            _dfs(creditos=cr, pagos=pg), RUN_ID
        )
        assert len(valid["pagos"]) == 0
        assert any("CR99999" in e["motivo"] for e in errs)

    def test_referencia_valida_pasa(self):
        valid, errs = dq2_referential_integrity(_dfs(), RUN_ID)
        assert len(errs) == 0


# ---------------------------------------------------------------------------
# DQ-3: Normalización de catálogos (valores no mapeables)
# ---------------------------------------------------------------------------

class TestDQ3CatalogNormalization:
    def test_estado_credito_no_mapeado_aislado(self):
        cr = [_creditos(estado_credito="Aprobado", _estado_credito_valido=False)]
        valid, errs = dq3_catalog_normalization(_dfs(creditos=cr), RUN_ID)
        assert len(valid["creditos"]) == 0
        assert len(errs) == 1
        assert errs[0]["regla_id"] == "DQ-3"

    def test_estado_valido_pasa(self):
        valid, errs = dq3_catalog_normalization(_dfs(), RUN_ID)
        assert len(errs) == 0
        assert len(valid["creditos"]) == 1


# ---------------------------------------------------------------------------
# DQ-4: Validación de dominio
# ---------------------------------------------------------------------------

class TestDQ4DomainValues:
    def test_monto_negativo_aislado(self):
        cr = [_creditos(monto_aprobado=-700000.0)]
        valid, errs = dq4_domain_values(_dfs(creditos=cr), RUN_ID)
        assert len(valid["creditos"]) == 0
        assert any("monto_aprobado" in e["motivo"] for e in errs)

    def test_plazo_cero_aislado(self):
        cr = [_creditos(plazo_meses=0)]
        valid, errs = dq4_domain_values(_dfs(creditos=cr), RUN_ID)
        assert len(valid["creditos"]) == 0

    def test_monto_pago_negativo_aislado(self):
        pg = [_pagos(monto_pago=-150000.0)]
        valid, errs = dq4_domain_values(_dfs(pagos=pg), RUN_ID)
        assert len(valid["pagos"]) == 0

    def test_monto_pago_cero_aislado(self):
        pg = [_pagos(monto_pago=0.0)]
        valid, errs = dq4_domain_values(_dfs(pagos=pg), RUN_ID)
        assert len(valid["pagos"]) == 0

    def test_valores_validos_pasan(self):
        valid, errs = dq4_domain_values(_dfs(), RUN_ID)
        assert len(errs) == 0


# ---------------------------------------------------------------------------
# DQ-5: Coherencia temporal
# ---------------------------------------------------------------------------

class TestDQ5TemporalCoherence:
    def test_desembolso_antes_de_solicitud(self):
        cr = [_creditos(
            fecha_solicitud=date(2024, 11, 16),
            fecha_desembolso=date(2024, 11, 14),  # ← antes de solicitud
        )]
        valid, errs = dq5_temporal_coherence(_dfs(creditos=cr), RUN_ID)
        assert len(valid["creditos"]) == 0
        assert len(errs) == 1
        assert errs[0]["regla_id"] == "DQ-5"

    def test_fecha_pago_invalida_aislada(self):
        pg = [_pagos(fecha_pago=None)]  # fecha no parseada
        valid, errs = dq5_temporal_coherence(_dfs(pagos=pg), RUN_ID)
        assert len(valid["pagos"]) == 0

    def test_fechas_coherentes_pasan(self):
        valid, errs = dq5_temporal_coherence(_dfs(), RUN_ID)
        assert len(errs) == 0


# ---------------------------------------------------------------------------
# DQ-6: No nulidad de campos críticos
# ---------------------------------------------------------------------------

class TestDQ6NotNullCritical:
    def test_tasa_nula_aislada(self):
        cr = [_creditos(tasa_interes_mensual=None)]
        valid, errs = dq6_not_null_critical(_dfs(creditos=cr), RUN_ID)
        assert len(valid["creditos"]) == 0
        assert any("tasa" in e["motivo"] for e in errs)

    def test_credito_id_vacio_en_pago_aislado(self):
        pg = [_pagos(credito_id="")]
        valid, errs = dq6_not_null_critical(_dfs(pagos=pg), RUN_ID)
        assert len(valid["pagos"]) == 0

    def test_campos_completos_pasan(self):
        valid, errs = dq6_not_null_critical(_dfs(), RUN_ID)
        assert len(errs) == 0


# ---------------------------------------------------------------------------
# DQ-7: Duplicados de negocio (flag, no aislar)
# ---------------------------------------------------------------------------

class TestDQ7BusinessDuplicates:
    def test_email_duplicado_marcado_no_aislado(self):
        cl = [
            _clientes(cliente_id="C0001", email="mismo@email.com"),
            _clientes(cliente_id="C0016", email="mismo@email.com"),
        ]
        valid, errs = dq7_business_duplicates(_dfs(clientes=cl), RUN_ID)
        # Ambos registros ENTRAN al modelo
        assert len(valid["clientes"]) == 2
        # Ambos quedan marcados
        assert valid["clientes"]["flag_email_duplicado"].all()
        # Se genera un error por cada uno
        dq7_errs = [e for e in errs if e["regla_id"] == "DQ-7"]
        assert len(dq7_errs) >= 2

    def test_numero_documento_duplicado_flaggeado(self):
        cl = [
            _clientes(cliente_id="C0001", numero_documento="46913810"),
            _clientes(cliente_id="C0121", numero_documento="46913810"),
        ]
        valid, errs = dq7_business_duplicates(_dfs(clientes=cl), RUN_ID)
        assert len(valid["clientes"]) == 2
        assert valid["clientes"]["flag_doc_duplicado"].all()

    def test_referencia_pago_duplicada_flaggeada(self):
        pg = [
            _pagos(pago_id="P000001", referencia_transaccion="REF001"),
            _pagos(pago_id="P000002", referencia_transaccion="REF001"),
        ]
        valid, errs = dq7_business_duplicates(_dfs(pagos=pg), RUN_ID)
        assert len(valid["pagos"]) == 2
        assert valid["pagos"]["flag_referencia_duplicada"].all()

    def test_sin_duplicados_no_genera_flags(self):
        valid, errs = dq7_business_duplicates(_dfs(), RUN_ID)
        assert not valid["clientes"]["flag_email_duplicado"].any()
        assert len([e for e in errs if e["regla_id"] == "DQ-7"]) == 0


# ---------------------------------------------------------------------------
# validate_all: integración del pipeline completo de validación
# ---------------------------------------------------------------------------

class TestValidateAll:
    def test_registro_limpio_pasa_todas_las_reglas(self):
        valid_dfs, dq_df = validate_all(_dfs(), RUN_ID)
        assert len(dq_df) == 0
        assert len(valid_dfs["clientes"]) == 1
        assert len(valid_dfs["creditos"]) == 1
        assert len(valid_dfs["pagos"]) == 1

    def test_multiples_errores_acumulados(self):
        cr = [
            _creditos(credito_id="CR00001"),           # válido
            _creditos(credito_id="CR00001"),           # DQ-1 dup
            _creditos(credito_id="CR00002", monto_aprobado=-1.0),  # DQ-4
        ]
        valid_dfs, dq_df = validate_all(_dfs(creditos=cr), RUN_ID)
        assert len(dq_df) > 0
        reglas = set(dq_df["regla_id"].tolist())
        assert "DQ-1" in reglas

    def test_dq_errors_df_tiene_columnas_correctas(self):
        _, dq_df = validate_all(_dfs(), RUN_ID)
        expected_cols = {
            "run_id", "regla_id", "tabla_origen",
            "severidad", "motivo", "payload_original",
        }
        assert expected_cols.issubset(set(dq_df.columns))
