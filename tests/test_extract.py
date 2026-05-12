"""Tests para src/extract.py: validación de columnas y tolerancia de encoding."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.extract import _validate_columns, _read_csv


class TestValidateColumns:
    def _make_df(self, cols: list[str]) -> pd.DataFrame:
        return pd.DataFrame(columns=cols)

    def test_pasa_con_columnas_exactas(self):
        df = self._make_df([
            "cliente_id", "tipo_documento", "numero_documento", "nombres",
            "apellidos", "email", "telefono", "fecha_registro",
            "estado_cliente", "ciudad", "segmento",
        ])
        _validate_columns("clientes", df, Path("clientes.csv"))

    def test_pasa_con_columnas_extra(self):
        """Columnas adicionales no son problema."""
        df = self._make_df([
            "cliente_id", "tipo_documento", "numero_documento", "nombres",
            "apellidos", "email", "telefono", "fecha_registro",
            "estado_cliente", "ciudad", "segmento", "columna_extra",
        ])
        _validate_columns("clientes", df, Path("clientes.csv"))

    def test_falla_con_columna_renombrada(self):
        """id_cliente en vez de cliente_id debe lanzar ValueError claro."""
        df = self._make_df([
            "id_cliente",  # nombre incorrecto
            "tipo_documento", "numero_documento", "nombres",
            "apellidos", "email", "telefono", "fecha_registro",
            "estado_cliente", "ciudad", "segmento",
        ])
        with pytest.raises(ValueError, match="cliente_id"):
            _validate_columns("clientes", df, Path("clientes.csv"))

    def test_mensaje_lista_columnas_faltantes(self):
        """El ValueError indica exactamente qué columnas faltan."""
        df = self._make_df(["cliente_id"])
        with pytest.raises(ValueError, match="Columnas faltantes"):
            _validate_columns("clientes", df, Path("clientes.csv"))

    def test_creditos_columna_faltante(self):
        df = self._make_df([
            "credito_id", "cliente_id", "fecha_solicitud", "fecha_desembolso",
            "monto_aprobado", "plazo_meses", "estado_credito",
            "producto", "fecha_vencimiento", "canal",
            # falta tasa_interes_mensual
        ])
        with pytest.raises(ValueError, match="tasa_interes_mensual"):
            _validate_columns("creditos", df, Path("creditos.csv"))


class TestReadCsvEncoding:
    def test_utf8_con_bom_no_contamina_nombre_columna(self):
        """CSV guardado con BOM (Excel UTF-8) no debe añadir \\ufeff al primer header."""
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".csv", delete=False
        ) as f:
            # BOM + contenido UTF-8
            f.write(b"\xef\xbb\xbfcliente_id,nombre\n")
            f.write("C001,José\n".encode("utf-8"))
            tmp_path = Path(f.name)

        try:
            df = _read_csv(tmp_path)
            assert "cliente_id" in df.columns, (
                f"BOM contaminó el nombre de columna: {list(df.columns)}"
            )
            assert "﻿cliente_id" not in df.columns
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_utf8_sin_bom_funciona_normal(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("cliente_id,nombre\nC001,Ana\n")
            tmp_path = Path(f.name)

        try:
            df = _read_csv(tmp_path)
            assert "cliente_id" in df.columns
            assert df.iloc[0]["nombre"] == "Ana"
        finally:
            tmp_path.unlink(missing_ok=True)
