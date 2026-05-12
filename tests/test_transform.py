"""Tests para src/transform.py: normalización de catálogos y parseo de fechas."""

from datetime import date

import pandas as pd
import pytest

from src.transform import (
    ESTADO_CLIENTE_MAP,
    ESTADO_CREDITO_MAP,
    ESTADO_PAGO_MAP,
    _normalize_catalog,
    _parse_date,
    _safe_numeric,
    compute_dias_mora,
    transform_clientes,
    transform_creditos,
    transform_pagos,
)


# ---------------------------------------------------------------------------
# _normalize_catalog
# ---------------------------------------------------------------------------

class TestNormalizeCatalog:
    def test_exact_match(self):
        val, ok = _normalize_catalog("activo", ESTADO_CLIENTE_MAP)
        assert val == "Activo"
        assert ok is True

    def test_case_insensitive(self):
        val, ok = _normalize_catalog("MORA", ESTADO_CREDITO_MAP)
        assert val == "Mora"
        assert ok is True

    def test_en_revision(self):
        val, ok = _normalize_catalog("EN REVISION", ESTADO_CLIENTE_MAP)
        assert val == "EnRevision"
        assert ok is True

    def test_success_to_exitoso(self):
        val, ok = _normalize_catalog("success", ESTADO_PAGO_MAP)
        assert val == "Exitoso"
        assert ok is True

    def test_exitoso_uppercase(self):
        val, ok = _normalize_catalog("EXITOSO", ESTADO_PAGO_MAP)
        assert val == "Exitoso"
        assert ok is True

    def test_unknown_value_returns_original(self):
        val, ok = _normalize_catalog("Aprobado", ESTADO_CREDITO_MAP)
        assert val == "Aprobado"
        assert ok is False

    def test_strips_whitespace(self):
        val, ok = _normalize_catalog("  activo  ", ESTADO_CLIENTE_MAP)
        assert val == "Activo"
        assert ok is True


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_iso_format(self):
        assert _parse_date("2024-05-21") == date(2024, 5, 21)

    def test_slash_format(self):
        assert _parse_date("2024/03/20") == date(2024, 3, 20)

    def test_empty_returns_none(self):
        assert _parse_date("") is None

    def test_invalid_date_returns_none(self):
        # Mes 13 no existe
        assert _parse_date("2024-13-01") is None

    def test_valid_leap_day(self):
        assert _parse_date("2024-02-29") == date(2024, 2, 29)


# ---------------------------------------------------------------------------
# _safe_numeric
# ---------------------------------------------------------------------------

class TestSafeNumeric:
    def test_integer_string(self):
        assert _safe_numeric("2799828") == 2799828.0

    def test_float_string(self):
        assert _safe_numeric("1.77") == pytest.approx(1.77)

    def test_negative(self):
        assert _safe_numeric("-700000") == -700000.0

    def test_empty_returns_none(self):
        assert _safe_numeric("") is None

    def test_invalid_returns_none(self):
        assert _safe_numeric("N/A") is None


# ---------------------------------------------------------------------------
# transform_clientes
# ---------------------------------------------------------------------------

class TestTransformClientes:
    def _make_df(self, rows: list[dict]) -> pd.DataFrame:
        cols = [
            "cliente_id", "tipo_documento", "numero_documento", "nombres",
            "apellidos", "email", "telefono", "fecha_registro",
            "estado_cliente", "ciudad", "segmento", "fecha_nacimiento",
            "ingresos_mensuales", "_ingested_at", "_source_file",
        ]
        base = {c: "" for c in cols}
        result = []
        for row in rows:
            r = base.copy()
            r.update(row)
            result.append(r)
        return pd.DataFrame(result)

    def test_normaliza_estado_activo_lowercase(self):
        df = self._make_df([{
            "cliente_id": "C0036", "nombres": "Grupo", "tipo_documento": "NIT",
            "estado_cliente": "activo"
        }])
        out = transform_clientes(df)
        assert out.iloc[0]["estado_cliente"] == "Activo"
        assert out.iloc[0]["_estado_cliente_valido"] == True

    def test_normaliza_en_revision(self):
        df = self._make_df([{
            "cliente_id": "C0062", "nombres": "Laura", "tipo_documento": "CC",
            "estado_cliente": "EN REVISION"
        }])
        out = transform_clientes(df)
        assert out.iloc[0]["estado_cliente"] == "EnRevision"

    def test_fecha_registro_slash_format(self):
        df = self._make_df([{
            "cliente_id": "C0014", "nombres": "Carlos", "tipo_documento": "CC",
            "estado_cliente": "Bloqueado", "fecha_registro": "2024/03/20"
        }])
        out = transform_clientes(df)
        assert out.iloc[0]["fecha_registro"] == date(2024, 3, 20)

    def test_ingresos_negativos_pasan(self):
        """Ingresos negativos no son bloqueados en transform (pasan al modelo)."""
        df = self._make_df([{
            "cliente_id": "C0023", "nombres": "Diana", "tipo_documento": "CE",
            "estado_cliente": "Pendiente", "ingresos_mensuales": "-2500000"
        }])
        out = transform_clientes(df)
        assert out.iloc[0]["ingresos_mensuales"] == -2500000.0

    def test_estado_desconocido_marcado_invalido(self):
        df = self._make_df([{
            "cliente_id": "C0099", "nombres": "Test", "tipo_documento": "CC",
            "estado_cliente": "Desconocido"
        }])
        out = transform_clientes(df)
        assert out.iloc[0]["_estado_cliente_valido"] == False


# ---------------------------------------------------------------------------
# transform_creditos
# ---------------------------------------------------------------------------

class TestTransformCreditos:
    def _make_df(self, rows: list[dict]) -> pd.DataFrame:
        cols = [
            "credito_id", "cliente_id", "fecha_solicitud", "fecha_desembolso",
            "monto_aprobado", "plazo_meses", "tasa_interes_mensual",
            "estado_credito", "producto", "fecha_vencimiento", "canal",
            "_ingested_at", "_source_file",
        ]
        base = {c: "" for c in cols}
        result = []
        for row in rows:
            r = base.copy()
            r.update(row)
            result.append(r)
        return pd.DataFrame(result)

    def test_normaliza_mora_uppercase(self):
        df = self._make_df([{
            "credito_id": "CR00042", "cliente_id": "C0082",
            "estado_credito": "MORA", "fecha_solicitud": "2024-08-26",
            "monto_aprobado": "4804077", "plazo_meses": "6", "producto": "Microcredito"
        }])
        out = transform_creditos(df)
        assert out.iloc[0]["estado_credito"] == "Mora"
        assert out.iloc[0]["_estado_credito_valido"] == True

    def test_tasa_nula_queda_none(self):
        df = self._make_df([{
            "credito_id": "CR00067", "cliente_id": "C0044",
            "estado_credito": "Mora", "tasa_interes_mensual": "",
            "monto_aprobado": "21436526", "plazo_meses": "12",
            "fecha_solicitud": "2024-10-17", "producto": "Capital trabajo"
        }])
        out = transform_creditos(df)
        assert out.iloc[0]["tasa_interes_mensual"] is None

    def test_monto_negativo_parsea(self):
        df = self._make_df([{
            "credito_id": "CR00019", "cliente_id": "C0086",
            "estado_credito": "Pagado", "monto_aprobado": "-700000",
            "plazo_meses": "9", "tasa_interes_mensual": "1.56",
            "fecha_solicitud": "2024-09-04", "producto": "Capital trabajo"
        }])
        out = transform_creditos(df)
        assert out.iloc[0]["monto_aprobado"] == -700000.0

    def test_aprobado_marcado_invalido(self):
        """'Aprobado' no está en el catálogo canónico."""
        df = self._make_df([{
            "credito_id": "CR00053", "cliente_id": "C0033",
            "estado_credito": "Aprobado", "monto_aprobado": "9200018",
            "plazo_meses": "18", "tasa_interes_mensual": "2.27",
            "fecha_solicitud": "2024-05-11", "producto": "Libre inversion"
        }])
        out = transform_creditos(df)
        assert out.iloc[0]["_estado_credito_valido"] == False


# ---------------------------------------------------------------------------
# transform_pagos
# ---------------------------------------------------------------------------

class TestTransformPagos:
    def _make_df(self, rows: list[dict]) -> pd.DataFrame:
        cols = [
            "pago_id", "credito_id", "fecha_pago", "monto_pago",
            "metodo_pago", "estado_pago", "referencia_transaccion",
            "_ingested_at", "_source_file",
        ]
        base = {c: "" for c in cols}
        result = []
        for row in rows:
            r = base.copy()
            r.update(row)
            result.append(r)
        return pd.DataFrame(result)

    def test_normaliza_success_a_exitoso(self):
        df = self._make_df([{
            "pago_id": "P000109", "credito_id": "CR00187",
            "fecha_pago": "2025-03-26", "monto_pago": "499112",
            "metodo_pago": "Transferencia", "estado_pago": "success"
        }])
        out = transform_pagos(df)
        assert out.iloc[0]["estado_pago"] == "Exitoso"

    def test_normaliza_exitoso_uppercase(self):
        df = self._make_df([{
            "pago_id": "P000331", "credito_id": "CR00155",
            "fecha_pago": "2025-05-26", "monto_pago": "575600",
            "metodo_pago": "Tarjeta", "estado_pago": "EXITOSO"
        }])
        out = transform_pagos(df)
        assert out.iloc[0]["estado_pago"] == "Exitoso"

    def test_fecha_invalida_retorna_none(self):
        df = self._make_df([{
            "pago_id": "P000073", "credito_id": "CR00080",
            "fecha_pago": "2024-13-01", "monto_pago": "211169",
            "metodo_pago": "Tarjeta", "estado_pago": "Exitoso"
        }])
        out = transform_pagos(df)
        assert out.iloc[0]["fecha_pago"] is None


# ---------------------------------------------------------------------------
# compute_dias_mora
# ---------------------------------------------------------------------------

class TestComputeDiasMora:
    def test_mora_con_vencimiento_pasado(self):
        dias = compute_dias_mora("Mora", date(2025, 1, 1), date(2025, 3, 1))
        assert dias == 59

    def test_activo_siempre_cero(self):
        assert compute_dias_mora("Activo", date(2024, 1, 1), date(2025, 3, 1)) == 0

    def test_mora_fecha_futura_es_cero(self):
        dias = compute_dias_mora("Mora", date(2026, 1, 1), date(2025, 3, 1))
        assert dias == 0

    def test_vencido_calcula_igual_que_mora(self):
        dias = compute_dias_mora("Vencido", date(2025, 1, 1), date(2025, 3, 1))
        assert dias == 59

    def test_sin_fecha_retorna_cero(self):
        assert compute_dias_mora("Mora", None, date(2025, 3, 1)) == 0
